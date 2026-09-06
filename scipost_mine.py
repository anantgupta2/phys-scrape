"""Mine SciPost's open peer review for referee-identified errors in physics papers.

Ground truth for this benchmark must not originate from a language model: if a
model finds the errors and is then graded on finding them, the benchmark
measures nothing.  Every candidate produced here traces to a vetted, publicly
posted referee report carrying a DOI.

Selection is deterministic.  A model may later rank the queue so that a
reviewer sees the strongest candidates first, but it never removes a
candidate, so the selected population is reproducible by running these rules.

Examples
--------
python scipost_mine.py enumerate --cache-dir data/scipost_api_cache
python scipost_mine.py select --cache-dir data/scipost_api_cache --output data/scipost_candidates.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import requests


API = "https://scipost.org/api/submissions/"
SITE = "https://scipost.org"
PAGE_SIZE = 200

# SciPost specialty names, verbatim.  A substring test on "Theory" would drop
# Quantum Physics, Mathematical Physics, Gravitation/Cosmology and Statistical
# and Soft Matter Physics -- roughly half the qualifying corpus -- so the
# allowlist is explicit.  Specialties ending in "- Experiment" are omitted.
THEORY_SPECIALTIES = frozenset({
    "Condensed Matter Physics - Theory",
    "Condensed Matter Physics - Computational",
    "High-Energy Physics - Theory",
    "High-Energy Physics - Phenomenology",
    "Quantum Physics",
    "Mathematical Physics",
    "Gravitation, Cosmology and Astroparticle Physics",
    "Statistical and Soft Matter Physics",
    "Atomic, Molecular and Optical Physics - Theory",
    "Nuclear Physics - Theory",
})

# Referees state real errors politely.  "I do not understand the first equality
# in (8)" precedes a derivation disproving that equality and contains no error
# keyword, so hedged forms are included alongside blunt ones.
OBJECTION = re.compile(
    r"sign error|incorrect|is wrong|error in|mistake|invalid|erroneous"
    r"|contradicts|inconsistent"
    r"|do(?:es)? not (?:understand|follow|hold|seem|agree)"
    r"|not clear (?:to me )?(?:that|how|why)"
    r"|(?:do not|don'?t|cannot|can not|could not|couldn'?t) (?:see|understand|agree|follow)"
    r"|not sure (?:I|that|how|why)"
    r"|should (?:be|read)"
    r"|seems? (?:to be )?(?:wrong|incorrect|inconsistent)"
    r"|fails? to (?:hold|follow)"
    r"|missing a|factor of",
    re.I,
)

# Objections about presentation are not theoretical errors.
PROSE = re.compile(
    r"\b(?:punctuation|grammar|spelling|wording|caption|reference list"
    r"|readable|rewritten|cryptic|be numbered|typos?)\b",
    re.I,
)

LOCATION_PATTERNS = (
    ("equation", re.compile(r"\beq(?:s|uations?)?\.?\s*\(?([A-Z]?\.?\d+(?:\.\d+)?)\)?", re.I)),
    ("theorem", re.compile(r"\btheorem\s+(\d+(?:\.\d+)?)", re.I)),
    ("lemma", re.compile(r"\blemma\s+(\d+(?:\.\d+)?)", re.I)),
    ("proposition", re.compile(r"\bproposition\s+(\d+(?:\.\d+)?)", re.I)),
    ("section", re.compile(r"\bsec(?:tion)?\.?\s*(\d+(?:\.\d+)*)", re.I)),
)
# A bare "(8)" is how referees most often cite an equation.  Three digits at
# most, so a year such as "(2020)" is not mistaken for a reference.
BARE_REFERENCE = re.compile(r"(?<![\w}\\])\(([1-9]\d{0,2}(?:\.\d+)?)\)")

_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
# "eq." ends in a period. Splitting there cut real objections in half: one
# fragment kept the complaint and the other the equation number, so neither
# qualified, and recorded quotes lost their strongest clause.
ABBREVIATION = re.compile(
    r"\b(?:eqs?|figs?|secs?|refs?|apps?|tabs?|chap?|no|vs|cf|al|resp|approx|i\.e|e\.g)\.$",
    re.I,
)
INITIAL = re.compile(r"\b[A-Z]\.$")
ARXIV_IDENTIFIER = re.compile(
    r"^(?P<id>\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})v(?P<version>\d+)$"
)
REPORT_FIELDS = ("report", "weaknesses", "requested_changes")


def sentences(text: str) -> list[str]:
    """Split into sentences without breaking on an abbreviation or initial."""
    parts: list[str] = []
    for fragment in _SPLIT.split(text or ""):
        previous = parts[-1] if parts else ""
        if parts and (ABBREVIATION.search(previous) or INITIAL.search(previous)):
            parts[-1] = f"{previous} {fragment}"
        else:
            parts.append(fragment)
    return [p for p in (" ".join(part.split()) for part in parts) if p]


def is_theory(submission: dict) -> bool:
    return (
        submission.get("acad_field") == "Physics"
        and bool(THEORY_SPECIALTIES.intersection(submission.get("specialties") or ()))
    )


def arxiv_reference(identifier: str) -> tuple[str, int] | None:
    """Split a SciPost identifier into (arXiv ID, version), or None if native.

    SciPost reuses the arXiv identifier verbatim, so the version here is the
    arXiv version the referees actually read.
    """
    match = ARXIV_IDENTIFIER.match(identifier or "")
    return (match["id"], int(match["version"])) if match else None


def cited_locations(text: str) -> list[dict]:
    """Extract numbered references, in order of appearance, deduplicated."""
    found: list[tuple[int, str, str]] = []
    for kind, pattern in LOCATION_PATTERNS:
        found += [(m.start(), kind, m[1]) for m in pattern.finditer(text)]
    found += [(m.start(), "equation", m[1]) for m in BARE_REFERENCE.finditer(text)]
    seen, ordered = set(), []
    for _, kind, number in sorted(found):
        if (kind, number) not in seen:
            seen.add((kind, number))
            ordered.append({"kind": kind, "number": number})
    return ordered


def objections(text: str) -> list[dict]:
    """Find sentences that both object and say where.

    Requiring both in the same sentence is what separates a real complaint from
    a compliment that happens to contain "does not follow", and it yields the
    exact quote to record as evidence.
    """
    results = []
    for sentence in sentences(text):
        if PROSE.search(sentence) or not OBJECTION.search(sentence):
            continue
        locations = cited_locations(sentence)
        if locations:
            results.append({"quote": sentence, "cited_locations": locations})
    return results


def group_by_thread(submissions: Iterable[dict]) -> dict[str, list[dict]]:
    threads: dict[str, list[dict]] = {}
    for submission in submissions:
        threads.setdefault(submission.get("thread_hash"), []).append(submission)
    return threads


def next_round(submission: dict, by_thread: dict[str, list[dict]]) -> dict | None:
    """The round that supersedes this one, i.e. where the authors' fix landed."""
    url = submission.get("url")
    siblings = by_thread.get(submission.get("thread_hash"), ())
    return next((s for s in siblings if s.get("is_resubmission_of") == url), None)


def report_objections(submission: dict) -> list[dict]:
    found = []
    for report in submission.get("reports") or ():
        if report.get("status") != "vetted":
            continue
        text = "\n".join(str(report.get(field) or "") for field in REPORT_FIELDS)
        for objection in objections(text):
            found.append(objection | {
                "report_nr": report.get("report_nr"),
                "report_url": SITE + str(report.get("url") or ""),
                "report_doi": report.get("doi_string"),
                "referee_validity_rating": report.get("validity"),
            })
    return found


def candidate(submission: dict, by_thread: dict[str, list[dict]]) -> dict | None:
    """Build a candidate record, or None if the submission does not qualify."""
    if not is_theory(submission):
        return None
    reference = arxiv_reference(submission.get("identifier", ""))
    if reference is None:
        return None
    following = next_round(submission, by_thread)
    if following is None:
        return None
    after = arxiv_reference(following.get("identifier", ""))
    if after is None:
        return None
    found = report_objections(submission)
    if not found:
        return None
    arxiv_id, before = reference
    return {
        "arxiv_id": arxiv_id,
        "v_before": before,
        "v_after": after[1],
        "scipost_identifier": submission["identifier"],
        "scipost_submission_url": f"{SITE}{submission.get('url')}",
        "thread_hash": submission.get("thread_hash"),
        "title": submission.get("title"),
        "author_list": submission.get("author_list"),
        "specialties": submission.get("specialties"),
        "status": submission.get("status"),
        "submission_date": submission.get("submission_date"),
        "objections": found,
    }


def fetch_all(cache_dir: Path, delay: float, session: requests.Session) -> int:
    """Page the API once into a local cache; everything downstream is offline."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    offset, pages = 0, 0
    while True:
        response = session.get(
            API,
            params={"format": "json", "limit": PAGE_SIZE, "offset": offset},
            timeout=60,
            headers={"User-Agent": "theory-review-benchmark/0.1 (research dataset collection)"},
        )
        response.raise_for_status()
        payload = response.json()
        target = cache_dir / f"submissions_{offset:05d}.json"
        temporary = target.with_suffix(".json.part")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(target)
        pages += 1
        print(f"  cached offset {offset:5d}  ({len(payload.get('results', []))} records)")
        if not payload.get("next"):
            return pages
        offset += PAGE_SIZE
        time.sleep(delay)


def load_cache(cache_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(cache_dir.glob("submissions_*.json")):
        rows += json.loads(path.read_text(encoding="utf-8")).get("results", [])
    return rows


def write_jsonl(path: Path, records: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    e = sub.add_parser("enumerate", help="page the SciPost API into a local cache")
    e.add_argument("--cache-dir", type=Path, required=True)
    e.add_argument("--delay", type=float, default=2.0)
    s = sub.add_parser("select", help="apply the selection rules to the cache")
    s.add_argument("--cache-dir", type=Path, required=True)
    s.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "enumerate":
        pages = fetch_all(args.cache_dir, args.delay, requests.Session())
        print(f"cached {pages} pages into {args.cache_dir}")
        return

    rows = load_cache(args.cache_dir)
    by_thread = group_by_thread(rows)
    retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    records = [c | {"retrieved_at": retrieved_at}
               for c in (candidate(row, by_thread) for row in rows) if c]
    write_jsonl(args.output, records)
    quotes = sum(len(r["objections"]) for r in records)
    print(f"{len(rows)} submissions -> {len(records)} candidates, {quotes} objection quotes")


if __name__ == "__main__":
    main()
