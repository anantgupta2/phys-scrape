"""High-recall arXiv candidate collection for theory-review benchmark cards.

This script intentionally does *not* declare a paper an error case from a
keyword alone.  It records broad discovery evidence, downloads both source
revisions, and leaves final admission to a source-diff/evidence review stage.

Examples
--------
python collect_arxiv_candidates.py discover --output data/candidates.jsonl --per-query 500
python collect_arxiv_candidates.py fetch-sources --input data/candidates.jsonl --source-dir data/sources

The arXiv API is rate-limited.  The default delay is deliberately conservative.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

import requests


API = "https://export.arxiv.org/api/query"
ABS = "https://export.arxiv.org/abs/{paper_id}"
SOURCE = "https://export.arxiv.org/e-print/{paper_id}v{version}"
TARGET_CATEGORIES = {"hep-th", "quant-ph", "gr-qc"}
NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

# Search terms are split into high-precision and high-recall buckets so later
# sampling can include both while reporting their provenance separately.
HIGH_PRECISION_TERMS = (
    '"sign error"', '"minus sign"', '"factor of"', '"boundary term"',
    '"incorrect equation"', '"error in equation"', '"mistake in equation"',
    '"calculation error"', '"algebraic error"', '"wrong result"',
)
HIGH_RECALL_TERMS = (
    'corrected', 'correction', 'erratum', 'revised', 'mistake', 'error',
    'typo', 'clarified', 'fixed', 'amended',
)


@dataclass(frozen=True)
class Candidate:
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    categories: list[str]
    primary_category: str | None
    published: str
    updated: str
    comment: str
    matched_queries: list[str]
    discovery_tier: str
    # Populated in fetch-sources; null means the revision page was unavailable.
    version_count: int | None = None


def clean(text: str | None) -> str:
    return " ".join((text or "").split())


def paper_id(entry_id: str) -> str:
    # API IDs look like http://arxiv.org/abs/2401.01234v2.
    return entry_id.rsplit("/", 1)[-1].split("v", 1)[0]


def api_search(term: str | None, start: int, limit: int, session: requests.Session, category: str | None = None) -> bytes:
    # arXiv's API accepts cat:hep-th but returns zero results for a parenthesized
    # OR category expression. Category-specific requests are therefore both more
    # reliable and auditable than a union query.
    if term is None:
        if category is None:
            raise ValueError("category is required for a category-only query")
        query = f"cat:{category}"
    else:
        query = f"all:{term}" if category is None else f"cat:{category}+AND+all:{term}"
    params = {"search_query": query, "start": start, "max_results": limit, "sortBy": "lastUpdatedDate", "sortOrder": "descending"}
    for attempt, pause in enumerate((0.0, 20.0, 60.0, 180.0)):
        if pause:
            time.sleep(pause)
        response = session.get(API, params=params, timeout=45, headers={"User-Agent": "theory-review-benchmark/0.1 (research dataset collection)"})
        if response.status_code != 429:
            response.raise_for_status()
            return response.content
    response.raise_for_status()  # keeps the response details if all retries throttled
    raise AssertionError("unreachable")


def parse_entries(xml: bytes) -> list[dict]:
    root = ET.fromstring(xml)
    parsed = []
    for entry in root.findall("atom:entry", NS):
        categories = [node.attrib["term"] for node in entry.findall("atom:category", NS)]
        if not TARGET_CATEGORIES.intersection(categories):
            continue
        primary = entry.find("arxiv:primary_category", NS)
        parsed.append({
            "arxiv_id": paper_id(entry.findtext("atom:id", default="", namespaces=NS)),
            "title": clean(entry.findtext("atom:title", default="", namespaces=NS)),
            "abstract": clean(entry.findtext("atom:summary", default="", namespaces=NS)),
            "authors": [clean(a.findtext("atom:name", default="", namespaces=NS)) for a in entry.findall("atom:author", NS)],
            "categories": categories,
            "primary_category": primary.attrib.get("term") if primary is not None else None,
            "published": entry.findtext("atom:published", default="", namespaces=NS),
            "updated": entry.findtext("atom:updated", default="", namespaces=NS),
            "comment": clean(entry.findtext("arxiv:comment", default="", namespaces=NS)),
        })
    return parsed


def discover(per_query: int, delay: float, revision_pool: int = 0, include_keywords: bool = True) -> Iterable[Candidate]:
    """Yield deduplicated candidates, preserving every query that found them."""
    found: dict[str, dict] = {}
    session = requests.Session()
    query_groups = (("high_precision", HIGH_PRECISION_TERMS), ("high_recall", HIGH_RECALL_TERMS)) if include_keywords else ()
    for tier, terms in query_groups:
        for term in terms:
            for category in sorted(TARGET_CATEGORIES):
                for start in range(0, per_query, 100):
                    entries = parse_entries(api_search(term, start, min(100, per_query - start), session, category))
                    for entry in entries:
                        current = found.setdefault(entry["arxiv_id"], {**entry, "matched_queries": [], "tiers": set()})
                        current["matched_queries"].append(f"{category}:{term}")
                        current["tiers"].add(tier)
                    if len(entries) < min(100, per_query - start):
                        break
                    time.sleep(delay)
            time.sleep(delay)
    # This is a deliberate recall tranche, not a claim that every record is an
    # error case. fetch-sources will later discard records with fewer than two
    # versions, and the diff/evidence stage decides final admission.
    for category in sorted(TARGET_CATEGORIES):
        for start in range(0, revision_pool, 100):
            entries = parse_entries(api_search(None, start, min(100, revision_pool - start), session, category))
            for entry in entries:
                current = found.setdefault(entry["arxiv_id"], {**entry, "matched_queries": [], "tiers": set()})
                current["matched_queries"].append(f"{category}_revision_pool")
                current["tiers"].add("revision_pool")
            if len(entries) < min(100, revision_pool - start):
                break
            time.sleep(delay)
    for item in sorted(found.values(), key=lambda x: (x["updated"], x["arxiv_id"]), reverse=True):
        tier = "high_precision" if "high_precision" in item["tiers"] else ("high_recall" if "high_recall" in item["tiers"] else "revision_pool")
        yield Candidate(**{k: item[k] for k in Candidate.__dataclass_fields__ if k not in {"discovery_tier", "version_count"}}, discovery_tier=tier)


VERSION_RE = re.compile(r"\[v(\d+)(?:\s|\])")


def version_count(arxiv_id: str, session: requests.Session) -> int | None:
    response = session.get(ABS.format(paper_id=arxiv_id), timeout=45, headers={"User-Agent": "theory-review-benchmark/0.1"})
    if response.status_code == 404:
        return None
    response.raise_for_status()
    versions = [int(v) for v in VERSION_RE.findall(response.text)]
    return max(versions) if versions else None


def write_jsonl(path: Path, records: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def fetch_sources(input_path: Path, source_dir: Path, delay: float) -> list[dict]:
    """Download v1/v2 only. Preserve failed records for retry rather than hiding them."""
    rows = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line]
    source_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    for row in rows:
        arxiv_id = row["arxiv_id"]
        count = version_count(arxiv_id, session)
        row["version_count"] = count
        row["source_status"] = "skipped_single_version" if not count or count < 2 else "pending"
        if not count or count < 2:
            continue
        paper_dir = source_dir / arxiv_id.replace("/", "_")
        paper_dir.mkdir(parents=True, exist_ok=True)
        row["source_artifacts"] = []
        try:
            for version in (1, 2):
                output = paper_dir / f"v{version}.tar"
                # A 200 response can be an HTML throttle/interstitial. Re-fetch
                # invalid existing files too, but write atomically so a valid
                # archive is never replaced by a partial response.
                for attempt, pause in enumerate((0.0, 15.0, 60.0)):
                    if output.exists() and tarfile.is_tarfile(output):
                        break
                    if pause:
                        time.sleep(pause)
                    response = session.get(SOURCE.format(paper_id=arxiv_id, version=version), timeout=120, headers={"User-Agent": "theory-review-benchmark/0.1"})
                    response.raise_for_status()
                    temporary = output.with_suffix(".tar.part")
                    temporary.write_bytes(response.content)
                    if tarfile.is_tarfile(temporary):
                        temporary.replace(output)
                        break
                if not output.exists() or not tarfile.is_tarfile(output):
                    row["source_status"] = "invalid_archive"
                    row["source_error"] = f"v{version} download is not a readable tar archive"
                    break
                payload = output.read_bytes()
                row["source_artifacts"].append({"version": version, "path": str(output), "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})
                time.sleep(delay)
            else:
                row["source_status"] = "downloaded_v1_v2"
        except requests.RequestException as exc:
            row["source_status"] = "download_failed"
            row["source_error"] = str(exc)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("discover", help="query arXiv and write a deduplicated candidate manifest")
    d.add_argument("--output", type=Path, required=True)
    d.add_argument("--per-query", type=int, default=500, help="maximum API entries per keyword")
    d.add_argument("--revision-pool", type=int, default=0, help="add this many recent target-category records as a labeled recall tranche")
    d.add_argument("--skip-keywords", action="store_true", help="collect only the balanced target-category recall tranche")
    d.add_argument("--delay", type=float, default=3.1)
    f = sub.add_parser("fetch-sources", help="retrieve v1/v2 sources for candidates with >=2 versions")
    f.add_argument("--input", type=Path, required=True)
    f.add_argument("--output", type=Path, required=True)
    f.add_argument("--source-dir", type=Path, required=True)
    f.add_argument("--delay", type=float, default=3.1)
    p = sub.add_parser("filter-primary", help="retain only papers whose primary category is a target theory category")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    s = sub.add_parser("select-ids", help="write an auditable small subset from an existing manifest")
    s.add_argument("--input", type=Path, required=True)
    s.add_argument("--output", type=Path, required=True)
    s.add_argument("--ids", nargs="+", required=True, help="arXiv IDs, e.g. 2506.24112 2503.22805")
    args = parser.parse_args()
    if args.command == "discover":
        write_jsonl(args.output, (asdict(item) for item in discover(args.per_query, args.delay, args.revision_pool, not args.skip_keywords)))
    elif args.command == "fetch-sources":
        write_jsonl(args.output, fetch_sources(args.input, args.source_dir, args.delay))
    elif args.command == "filter-primary":
        rows = (json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line)
        write_jsonl(args.output, (row for row in rows if row.get("primary_category") in TARGET_CATEGORIES))
    else:
        requested = set(args.ids)
        rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line]
        selected = [row for row in rows if row["arxiv_id"] in requested]
        missing = requested - {row["arxiv_id"] for row in selected}
        if missing:
            raise SystemExit(f"IDs not found in manifest: {', '.join(sorted(missing))}")
        write_jsonl(args.output, selected)


if __name__ == "__main__":
    main()
