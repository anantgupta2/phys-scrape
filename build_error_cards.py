"""Build benchmark cards from SciPost candidates and their arXiv source pairs.

Each card pairs an excerpt of the manuscript the referees actually read with
the referee's own statement of what is wrong.  The two sides are written to
separate files: only the model-facing file may ever be shown to an evaluated
model, and keeping the gold evidence in a different file makes that a property
of the layout rather than of a convention someone has to remember.

Localization anchors on the source diff rather than on LaTeX equation
numbering.  Equation numbers are assigned at typesetting time, so resolving
"Eq. (20)" against the source means replaying LaTeX's counters -- accurate
until it silently is not.  Anchoring instead on what the authors changed uses
two independent signals, the referee's complaint and the authors' edit, and
requires the authors to have actually acted.  Cards that cannot be anchored
are still emitted, marked unresolved, with every candidate hunk attached: a
referee may be right about a paper whose authors rebutted them.

Example
-------
python build_error_cards.py --candidates data/scipost_candidates.jsonl \
    --source-dir data/scipost_sources --output-dir data
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import audit_latex_pairs as audit


CONTEXT_LINES = 10
MAX_EXCERPT_LINES = 400
# The fracton case (arXiv:2207.00854) sat exactly two ordinals from the
# referee's number, so the window is a little wider than that.
ORDINAL_TOLERANCE = 3

NUMBERED_BEGIN = re.compile(r"\\begin\{(equation|align|gather|multline|eqnarray)\}")
ANY_END = re.compile(r"\\end\{(equation|align|gather|multline|eqnarray)\}")
AUTHOR_MARKED = re.compile(r"\\changed\b|\\revised\b|\\added\b")

TASK = (
    "Find any mathematical or physical mistake in this excerpt, state where it "
    "occurs, and explain why it fails."
)


@dataclass(frozen=True)
class Hunk:
    before_lines: tuple[int, int]
    after_lines: tuple[int, int]


def numbered_environments(lines: list[str]) -> list[int]:
    """Line indices where a numbered math environment opens."""
    return [i for i, line in enumerate(lines) if NUMBERED_BEGIN.search(line)]


def environment_spans(lines: list[str]) -> list[tuple[int, int, int]]:
    """(start, end, ordinal) for each numbered environment, in document order."""
    spans, ordinal = [], 0
    for start in numbered_environments(lines):
        ordinal += 1
        end = next((j for j in range(start, len(lines)) if ANY_END.search(lines[j])), start)
        spans.append((start, end, ordinal))
    return spans


def changed_hunks(old: list[str], new: list[str]) -> list[Hunk]:
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    return [Hunk((i1, i2), (j1, j2))
            for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"]


def hunk_ordinal(hunk: Hunk, spans: Iterable[tuple[int, int, int]]) -> int | None:
    """The numbered environment a hunk falls inside, if any."""
    start, end = hunk.before_lines
    for span_start, span_end, ordinal in spans:
        if start <= span_end and max(start, span_start) <= min(max(end - 1, start), span_end):
            return ordinal
    return None


def equation_hunks(hunks: list[Hunk], old: list[str], new: list[str]) -> list[Hunk]:
    """Hunks that sit inside, or introduce, a numbered math environment."""
    spans = environment_spans(old)
    keep = []
    for hunk in hunks:
        introduces = NUMBERED_BEGIN.search("\n".join(new[slice(*hunk.after_lines)]))
        if introduces or hunk_ordinal(hunk, spans) is not None:
            keep.append(hunk)
    return keep


def choose_anchor(old: list[str], new: list[str], cited_number: str) -> tuple[Hunk | None, str]:
    """Pick the changed hunk the referee is most likely pointing at."""
    candidates = equation_hunks(changed_hunks(old, new), old, new)
    if not candidates:
        return None, "unresolved"

    marked = [h for h in candidates
              if AUTHOR_MARKED.search("\n".join(new[slice(*h.after_lines)]))]
    if marked:
        # Authors who tag their own revisions have localized the fix for us.
        return marked[0], "corroborated_author_marked"

    try:
        cited = int(cited_number)
    except (TypeError, ValueError):
        # Section-style numbering such as "3.26" cannot be compared to an
        # ordinal count, so a lone candidate is the only safe answer.
        return (candidates[0], "corroborated_unique") if len(candidates) == 1 else (None, "unresolved")

    spans = environment_spans(old)
    within = [(abs((hunk_ordinal(h, spans) or 0) - cited), h) for h in candidates
              if hunk_ordinal(h, spans) is not None
              and abs(hunk_ordinal(h, spans) - cited) <= ORDINAL_TOLERANCE]
    if not within:
        return None, "unresolved"
    if len(candidates) == 1:
        return candidates[0], "corroborated_unique"
    return min(within, key=lambda pair: pair[0])[1], "corroborated_ordinal"


def excerpt(lines: list[str], hunk: Hunk) -> tuple[int, int, str]:
    """Text around a hunk, widened to whole environments and capped."""
    start, end = hunk.before_lines
    start = max(0, start - CONTEXT_LINES)
    end = min(len(lines), max(end, start + 1) + CONTEXT_LINES)
    for span_start, span_end, _ in environment_spans(lines):
        if span_start < end and span_end >= start:
            start, end = min(start, span_start), max(end, span_end + 1)
    if end - start > MAX_EXCERPT_LINES:
        end = start + MAX_EXCERPT_LINES
    return start + 1, end, "\n".join(lines[start:end])


def _hunk_record(hunk: Hunk) -> dict:
    return {"before_lines": [hunk.before_lines[0] + 1, hunk.before_lines[1]],
            "after_lines": [hunk.after_lines[0] + 1, hunk.after_lines[1]]}


def build(candidate: dict, old: list[str], new: list[str],
          main_tex: str | None = None) -> list[tuple[dict, dict]]:
    """Return (model-facing, gold) pairs, one per cited equation."""
    hunks = changed_hunks(old, new)
    fallback = equation_hunks(hunks, old, new) or hunks
    added = sum(h.after_lines[1] - h.after_lines[0] for h in hunks)
    deleted = sum(h.before_lines[1] - h.before_lines[0] for h in hunks)
    built = []
    for objection in candidate.get("objections", ()):
        for location in objection.get("cited_locations", ()):
            if location.get("kind") != "equation":
                continue
            anchor, confidence = choose_anchor(old, new, location.get("number"))
            source = anchor or (fallback[0] if fallback else None)
            if source is None:
                continue
            start, end, text = excerpt(old, source)
            card_id = f"{candidate['scipost_identifier']}-{location['kind']}{location['number']}"
            built.append((
                {
                    "card_id": card_id,
                    "arxiv_id": candidate["arxiv_id"],
                    "version": candidate["v_before"],
                    "main_tex": main_tex,
                    "excerpt_lines": [start, end],
                    "excerpt": text,
                    "task": TASK,
                },
                {
                    "card_id": card_id,
                    "arxiv_id": candidate["arxiv_id"],
                    "title": candidate.get("title"),
                    "scipost_submission_url": candidate.get("scipost_submission_url"),
                    "report_url": objection.get("report_url"),
                    "report_doi": objection.get("report_doi"),
                    "referee_quote": objection["quote"],
                    "referee_validity_rating": objection.get("referee_validity_rating"),
                    "cited_location": location,
                    "location_confidence": confidence,
                    "anchor_hunk": _hunk_record(anchor) if anchor else None,
                    "candidate_hunks": [_hunk_record(h) for h in fallback[:12]] if anchor is None else [],
                    "v_before": candidate["v_before"],
                    "v_after": candidate["v_after"],
                    "diff_summary": {"added": added, "deleted": deleted},
                    "text_hash": "sha256:" + hashlib.sha256(objection["quote"].encode()).hexdigest(),
                    "evidence_class": "referee_stated_technical",
                    "human_severity_label": "unreviewed",
                },
            ))
    return built


def write_jsonl(path: Path, records: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    rows = [json.loads(line) for line in
            args.candidates.read_text(encoding="utf-8").splitlines() if line]
    model_cards, gold_cards, skipped = [], [], []
    for row in rows:
        folder = args.source_dir / row["arxiv_id"].replace("/", "_")
        try:
            name, old = audit.main_tex(audit.source_file(folder, row["v_before"]))
            _, new = audit.main_tex(audit.source_file(folder, row["v_after"]))
        except Exception as exc:  # sources absent or unreadable; keep for retry
            skipped.append({"arxiv_id": row["arxiv_id"], "reason": str(exc)})
            continue
        for model, gold in build(row, old, new, main_tex=name):
            model_cards.append(model)
            gold_cards.append(gold)

    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    write_jsonl(args.output_dir / "error_cards.jsonl", model_cards)
    write_jsonl(args.output_dir / "error_cards_gold.jsonl",
                [g | {"retrieved_at": stamp} for g in gold_cards])
    if skipped:
        write_jsonl(args.output_dir / "error_cards_skipped.jsonl", skipped)
    confidence: dict[str, int] = {}
    for gold in gold_cards:
        confidence[gold["location_confidence"]] = confidence.get(gold["location_confidence"], 0) + 1
    print(f"{len(rows)} candidates -> {len(model_cards)} cards ({len(skipped)} skipped)")
    for key in sorted(confidence):
        print(f"  {key:32} {confidence[key]}")


if __name__ == "__main__":
    main()
