"""Triage downloaded arXiv v1/v2 source pairs before human physics review.

This is deliberately a *routing* tool: it never declares a flaw fatal.  It
finds the largest TeX source in each revision, estimates the source-diff size,
and preserves changed hunks containing mathematical-claim cues.
"""
from __future__ import annotations

import argparse
import difflib
import gzip
import json
import re
import tarfile
from pathlib import Path


CUE = re.compile(r"\\(?:begin\{(?:theorem|lemma|proposition|corollary)|label\{|eqref\{|cite\{)|\b(?:theorem|lemma|proposition|corollary|bound|scaling|error|mistake|incorrect|contradiction|unitar(?:y|ity)|singular)\b", re.I)


def gzip_original_name(path: Path) -> str | None:
    """Read the FNAME field arXiv stores in a single-file .gz e-print."""
    with path.open("rb") as handle:
        if handle.read(2) != b"\x1f\x8b":
            return None
        handle.read(1)
        flags = handle.read(1)[0]
        handle.read(6)
        if flags & 0x04:  # FEXTRA
            handle.read(int.from_bytes(handle.read(2), "little"))
        if not flags & 0x08:  # FNAME
            return None
        name = bytearray()
        while (byte := handle.read(1)) not in (b"", b"\x00"):
            name += byte
    return name.decode("latin-1") or None


def main_tex(archive: Path) -> tuple[str, list[str]]:
    if not tarfile.is_tarfile(archive):
        # arXiv serves a bare gzipped .tex for single-file submissions.
        with gzip.open(archive, "rb") as handle:
            raw = handle.read()
        name = gzip_original_name(archive) or archive.name.removesuffix(".gz")
        return name, raw.decode("utf-8", errors="replace").splitlines()
    with tarfile.open(archive, "r:*") as tar:
        members = [m for m in tar.getmembers() if m.isfile() and m.name.lower().endswith(".tex")]
        if not members:
            raise ValueError(f"no TeX file in {archive}")
        # arXiv's 00README.json names toplevel TeX sources. Prefer that exact
        # declaration over filename/size heuristics, which are fragile under
        # journal formatting or file renames.
        declared: set[str] = set()
        try:
            readme = next(m for m in tar.getmembers() if m.isfile() and m.name == "00README.json")
            metadata = json.loads(tar.extractfile(readme).read().decode("utf-8"))
            declared = {str(s["filename"]).replace("\\", "/") for s in metadata.get("sources", []) if s.get("usage") == "toplevel"}
        except (StopIteration, json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError):
            pass
        chosen = next((m for m in members if m.name.replace("\\", "/") in declared), max(members, key=lambda m: m.size))
        raw = tar.extractfile(chosen).read()
    return chosen.name, raw.decode("utf-8", errors="replace").splitlines()


def source_file(paper_dir: Path, version: int) -> Path:
    for suffix in (".tar", ".tex.gz"):
        candidate = paper_dir / f"v{version}{suffix}"
        if candidate.exists():
            return candidate
    raise ValueError(f"no retained source for v{version} in {paper_dir}")


# "downloaded_v1_v2" predates support for other version pairs; both mean a
# retained pair of sources.
PAIR_STATUSES = {"downloaded_v1_v2", "downloaded_pair"}


def audit(row: dict, source_dir: Path) -> dict:
    result = {"arxiv_id": row["arxiv_id"], "comment": row.get("comment", ""), "version_count": row.get("version_count")}
    if row.get("source_status") not in PAIR_STATUSES:
        return result | {"triage": "exclude_no_pair", "reason": row.get("source_status")}
    folder = source_dir / row["arxiv_id"].replace("/", "_")
    before, after = (int(v) for v in (row.get("source_versions") or (1, 2)))
    try:
        old_name, old = main_tex(source_file(folder, before))
        new_name, new = main_tex(source_file(folder, after))
    except (OSError, tarfile.TarError, ValueError) as exc:
        return result | {"triage": "unreadable_source", "reason": str(exc)}
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    added = deleted = 0
    cues: list[dict] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        deleted += i2 - i1
        added += j2 - j1
        old_hunk, new_hunk = old[i1:i2], new[j1:j2]
        if CUE.search("\n".join(old_hunk + new_hunk)):
            cues.append({"old_lines": [i1 + 1, i2], "new_lines": [j1 + 1, j2], "old": old_hunk[:4], "new": new_hunk[:4]})
    changed = added + deleted
    # The thresholds only prioritize reviewer attention; the comment can be
    # wrong, and severity remains a human-/report-backed label.
    triage = "compact_claim_change_candidate" if changed <= 180 and cues else "needs_human_review"
    return result | {"triage": triage, "v1_main_tex": old_name, "v2_main_tex": new_name, "added_lines": added, "deleted_lines": deleted, "claim_cue_hunks": cues[:12]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line]
    records = [audit(row, args.source_dir) for row in rows]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    temporary.replace(args.output)
