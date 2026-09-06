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
import gzip
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

from jsonl_io import write_jsonl


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
    """Strip the API URL prefix and any trailing version suffix.

    Pre-2007 identifiers carry an archive prefix that is part of the ID
    (hep-th/0605196v2 -> hep-th/0605196), so the path cannot simply be split
    on "/", and the ID itself may contain a "v".
    """
    identifier = entry_id.split("/abs/", 1)[-1]
    return re.sub(r"v\d+$", "", identifier)


def search_params(term: str | None, category: str | None, start: int, limit: int) -> dict:
    # arXiv's API accepts cat:hep-th but returns zero results for a parenthesized
    # OR category expression. Category-specific requests are therefore both more
    # reliable and auditable than a union query.
    if term is None:
        if category is None:
            raise ValueError("category is required for a category-only query")
        query = f"cat:{category}"
    else:
        # A literal "+" here is percent-encoded to %2B by requests, and arXiv
        # then parses "cat:X+AND+all:Y" as "cat:X AND all: OR all:Y" -- an OR
        # with an empty category clause. A space encodes to "+" on the wire,
        # which is arXiv's documented field separator.
        query = f"all:{term}" if category is None else f"cat:{category} AND all:{term}"
    return {"search_query": query, "start": start, "max_results": limit, "sortBy": "lastUpdatedDate", "sortOrder": "descending"}


def api_search(term: str | None, start: int, limit: int, session: requests.Session, category: str | None = None) -> bytes:
    params = search_params(term, category, start, limit)
    for attempt, pause in enumerate((0.0, 20.0, 60.0, 180.0)):
        if pause:
            time.sleep(pause)
        response = session.get(API, params=params, timeout=45, headers={"User-Agent": "theory-review-benchmark/0.1 (research dataset collection)"})
        if response.status_code != 429:
            response.raise_for_status()
            return response.content
    response.raise_for_status()  # keeps the response details if all retries throttled
    raise AssertionError("unreachable")


def page_exhausted(returned: int, requested: int) -> bool:
    return returned < requested


def parse_page(xml: bytes) -> tuple[int, list[dict]]:
    """Return (entries arXiv returned, entries in a target category).

    The two counts differ whenever the filter drops cross-lists, so only the
    first may be compared against the requested page size.
    """
    root = ET.fromstring(xml)
    returned = len(root.findall("atom:entry", NS))
    return returned, parse_entries(xml)


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
                    requested = min(100, per_query - start)
                    returned, entries = parse_page(api_search(term, start, requested, session, category))
                    for entry in entries:
                        current = found.setdefault(entry["arxiv_id"], {**entry, "matched_queries": [], "tiers": set()})
                        current["matched_queries"].append(f"{category}:{term}")
                        current["tiers"].add(tier)
                    if page_exhausted(returned, requested):
                        break
                    time.sleep(delay)
            time.sleep(delay)
    # This is a deliberate recall tranche, not a claim that every record is an
    # error case. fetch-sources will later discard records with fewer than two
    # versions, and the diff/evidence stage decides final admission.
    for category in sorted(TARGET_CATEGORIES):
        for start in range(0, revision_pool, 100):
            requested = min(100, revision_pool - start)
            returned, entries = parse_page(api_search(None, start, requested, session, category))
            for entry in entries:
                current = found.setdefault(entry["arxiv_id"], {**entry, "matched_queries": [], "tiers": set()})
                current["matched_queries"].append(f"{category}_revision_pool")
                current["tiers"].add("revision_pool")
            if page_exhausted(returned, requested):
                break
            time.sleep(delay)
    for item in sorted(found.values(), key=lambda x: (x["updated"], x["arxiv_id"]), reverse=True):
        tier = "high_precision" if "high_precision" in item["tiers"] else ("high_recall" if "high_recall" in item["tiers"] else "revision_pool")
        yield Candidate(**{k: item[k] for k in Candidate.__dataclass_fields__ if k not in {"discovery_tier", "version_count"}}, discovery_tier=tier)


SOURCE_SUFFIX = {"tar": ".tar", "gzip_tex": ".tex.gz"}


def source_kind(path: Path) -> str | None:
    """Classify an e-print response, or None if it is neither source form.

    arXiv returns a tar(.gz) for multi-file submissions and a bare gzipped
    .tex for single-file ones; a throttle interstitial is HTML and is neither.
    """
    if tarfile.is_tarfile(path):
        return "tar"
    try:
        with gzip.open(path, "rb") as handle:
            handle.read(1)
    except (OSError, EOFError):
        return None
    return "gzip_tex"


def existing_source(paper_dir: Path, version: int) -> tuple[Path, str] | None:
    for suffix in SOURCE_SUFFIX.values():
        candidate = paper_dir / f"v{version}{suffix}"
        kind = source_kind(candidate) if candidate.exists() else None
        if kind:
            return candidate, kind
    return None


VERSION_RE = re.compile(r"\[v(\d+)(?:\s|\])")


def version_count(arxiv_id: str, session: requests.Session) -> int | None:
    response = session.get(ABS.format(paper_id=arxiv_id), timeout=45, headers={"User-Agent": "theory-review-benchmark/0.1"})
    if response.status_code == 404:
        return None
    response.raise_for_status()
    versions = [int(v) for v in VERSION_RE.findall(response.text)]
    return max(versions) if versions else None


def fetch_sources(input_path: Path, source_dir: Path, delay: float) -> list[dict]:
    """Download v1/v2 only. Preserve failed records for retry rather than hiding them."""
    rows = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line]
    source_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    for row in rows:
        arxiv_id = row["arxiv_id"]
        # A peer-review round is not always v1 -> v2. SciPost thread 2207.00854
        # ran v2 -> v3, and fetching v1/v2 there retrieves two revisions the
        # referees never saw.
        before, after = (int(v) for v in (row.get("source_versions") or (1, 2)))
        count = version_count(arxiv_id, session)
        row["version_count"] = count
        if not count or count < after:
            row["source_status"] = "skipped_missing_version"
            continue
        row["source_status"] = "pending"
        paper_dir = source_dir / arxiv_id.replace("/", "_")
        paper_dir.mkdir(parents=True, exist_ok=True)
        row["source_artifacts"] = []
        try:
            for version in (before, after):
                # A 200 response can be an HTML throttle/interstitial. Re-fetch
                # invalid existing files too, but write atomically so a valid
                # source is never replaced by a partial response.
                accepted = existing_source(paper_dir, version)
                for pause in (0.0, 15.0, 60.0):
                    if accepted:
                        break
                    if pause:
                        time.sleep(pause)
                    response = session.get(SOURCE.format(paper_id=arxiv_id, version=version), timeout=120, headers={"User-Agent": "theory-review-benchmark/0.1"})
                    response.raise_for_status()
                    temporary = paper_dir / f"v{version}.part"
                    temporary.write_bytes(response.content)
                    kind = source_kind(temporary)
                    if kind:
                        output = paper_dir / f"v{version}{SOURCE_SUFFIX[kind]}"
                        temporary.replace(output)
                        accepted = (output, kind)
                        break
                    temporary.unlink()
                if not accepted:
                    row["source_status"] = "invalid_archive"
                    row["source_error"] = f"v{version} download is neither a tar archive nor a gzipped TeX source"
                    break
                output, kind = accepted
                payload = output.read_bytes()
                row["source_artifacts"].append({"version": version, "path": str(output), "kind": kind, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})
                time.sleep(delay)
            else:
                row["source_status"] = "downloaded_pair"
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
