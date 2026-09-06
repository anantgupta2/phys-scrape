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
import tarfile
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
SECTION = re.compile(r"\\section\{")
AUTHOR_MARKED = re.compile(r"\\changed\b|\\revised\b|\\added\b")

# Confidence levels whose excerpt is trustworthy enough to serve as a question.
# "corroborated_near" and "unresolved" are reviewed by a human instead.
SERVEABLE = frozenset({
    "corroborated_symbol", "corroborated_author_marked",
    "corroborated_unique", "corroborated_exact",
})

INLINE_MATH = re.compile(r"\$([^$]{2,80})\$")
# A subscripted compound such as v_{\rm wrong} identifies a quantity; a bare
# macro is weaker, and a formatting macro identifies nothing at all.
COMPOUND = re.compile(
    r"(?:\\[A-Za-z]+|[A-Za-z])[_^]\{[^{}]{1,40}\}|(?:\\[A-Za-z]+|[A-Za-z])[_^][A-Za-z0-9]")
# Referees retype expressions rather than copy source, so notation differs.
FONT_MACRO = re.compile(r"\\(?:rm|mathrm|text|textrm|mathbf|mathit|mathsf|bm|boldsymbol)\b")
BARE_MACRO = re.compile(r"\\[A-Za-z]{2,}")
FORMATTING = frozenset({
    r"\rm", r"\mathrm", r"\text", r"\textrm", r"\mathcal", r"\mathbb", r"\mathbf",
    r"\left", r"\right", r"\frac", r"\begin", r"\end", r"\quad", r"\qquad",
    r"\big", r"\Big", r"\displaystyle", r"\nonumber", r"\label", r"\hspace",
})

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


def environment_spans(lines: list[str]) -> list[tuple[int, int, int, str]]:
    """(start, end, ordinal, label) for each numbered environment, in order.

    `label` is the section-qualified number a paper using
    \numberwithin{equation}{section} would print, e.g. "3.26" for the 26th
    equation of section 3.  Referees cite whichever form the paper displays,
    so both are kept.
    """
    starts = set(numbered_environments(lines))
    spans, ordinal, section, in_section = [], 0, 0, 0
    for index, line in enumerate(lines):
        if SECTION.search(line):
            section, in_section = section + 1, 0
        if index not in starts:
            continue
        ordinal, in_section = ordinal + 1, in_section + 1
        end = next((j for j in range(index, len(lines)) if ANY_END.search(lines[j])), index)
        spans.append((index, end, ordinal, f"{section}.{in_section}"))
    return spans


def changed_hunks(old: list[str], new: list[str]) -> list[Hunk]:
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    return [Hunk((i1, i2), (j1, j2))
            for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"]


def hunk_span(hunk: Hunk, spans: Iterable[tuple[int, int, int, str]]):
    """The numbered environment a hunk falls inside, if any."""
    start, end = hunk.before_lines
    for span in spans:
        span_start, span_end = span[0], span[1]
        if start <= span_end and max(start, span_start) <= min(max(end - 1, start), span_end):
            return span
    return None


def citation_distance(span, cited: str) -> int | None:
    """How far a numbered environment sits from a referee's citation.

    A dotted citation is matched against the section-qualified label and only
    within the same section; a plain one against the document ordinal.
    None means the two are not comparable, which is not evidence either way.
    """
    _, _, ordinal, label = span
    try:
        if "." in cited:
            section, _, index = cited.partition(".")
            label_section, _, label_index = label.partition(".")
            return abs(int(index) - int(label_index)) if section == label_section else None
        return abs(ordinal - int(cited))
    except ValueError:
        return None


def equation_hunks(hunks: list[Hunk], old: list[str], new: list[str]) -> list[Hunk]:
    """Hunks that sit inside, or introduce, a numbered math environment."""
    spans = environment_spans(old)
    keep = []
    for hunk in hunks:
        introduces = NUMBERED_BEGIN.search("\n".join(new[slice(*hunk.after_lines)]))
        if introduces or hunk_span(hunk, spans) is not None:
            keep.append(hunk)
    return keep


def choose_anchor(old: list[str], new: list[str], cited_number: str) -> tuple[Hunk | None, str]:
    """Pick the changed hunk the referee is most likely pointing at."""
    candidates = equation_hunks(changed_hunks(old, new), old, new)
    if not candidates:
        return None, "unresolved"

    spans = environment_spans(old)
    within = []
    for index, hunk in enumerate(candidates):
        span = hunk_span(hunk, spans)
        distance = citation_distance(span, str(cited_number)) if span else None
        if distance is None or distance > ORDINAL_TOLERANCE:
            continue
        marked = bool(AUTHOR_MARKED.search("\n".join(new[slice(*hunk.after_lines)])))
        within.append((distance, not marked, index, hunk))
    if not within:
        return None, "unresolved"

    # Rank by the referee's own statement of location first. An author tag
    # says only that the authors touched something: taking the first tagged
    # hunk anchored every card in a paper to the same equation, and 20 of the
    # 74 changed hunks on arXiv:2207.00854 are tagged.
    distance, unmarked, _, hunk = min(within)
    if not unmarked:
        return hunk, "corroborated_author_marked"
    if distance:
        return hunk, "corroborated_near"
    return hunk, "corroborated_unique" if len(candidates) == 1 else "corroborated_exact"


def excerpt(lines: list[str], hunk: Hunk) -> tuple[int, int, str]:
    """Text around a hunk, widened to whole environments and capped."""
    start, end = hunk.before_lines
    start = max(0, start - CONTEXT_LINES)
    end = min(len(lines), max(end, start + 1) + CONTEXT_LINES)
    for span_start, span_end, _, _ in environment_spans(lines):
        if span_start < end and span_end >= start:
            start, end = min(start, span_start), max(end, span_end + 1)
    if end - start > MAX_EXCERPT_LINES:
        end = start + MAX_EXCERPT_LINES
    return start + 1, end, "\n".join(lines[start:end])


def _span_record(start: int, end: int) -> list[int]:
    # An insertion or deletion has an empty range on one side; report it as
    # empty rather than as an inverted pair.
    return [] if end <= start else [start + 1, end]


def _hunk_record(hunk: Hunk) -> dict:
    return {"before_lines": _span_record(*hunk.before_lines),
            "after_lines": _span_record(*hunk.after_lines)}


def build(candidate: dict, old: list[str], new: list[str],
          main_tex: str | None = None) -> list[tuple[dict, dict]]:
    """Return (model-facing, gold) pairs, one per cited equation."""
    hunks = changed_hunks(old, new)
    fallback = equation_hunks(hunks, old, new) or hunks
    added = sum(h.after_lines[1] - h.after_lines[0] for h in hunks)
    deleted = sum(h.before_lines[1] - h.before_lines[0] for h in hunks)
    # Referees often object to one equation across several sentences, and the
    # model-facing side is identical for each, so group by cited location.
    grouped: dict[tuple[str, str], list[dict]] = {}
    for objection in candidate.get("objections", ()):
        for location in objection.get("cited_locations", ()):
            grouped.setdefault((location["kind"], location["number"]), []).append(objection)

    built = []
    for (kind, number), group in grouped.items():
        location = {"kind": kind, "number": number}
        primary = group[0]
        card_id = card_identifier(candidate["scipost_identifier"], kind, number)
        gold = {
            "card_id": card_id,
            "arxiv_id": candidate["arxiv_id"],
            "version": candidate["v_before"],
            "scipost_identifier": candidate["scipost_identifier"],
            "title": candidate.get("title"),
            "scipost_submission_url": candidate.get("scipost_submission_url"),
            "main_tex": main_tex,
            "report_url": primary.get("report_url"),
            "report_doi": primary.get("report_doi") or None,
            "referee_quote": primary["quote"],
            "supporting_quotes": [o["quote"] for o in group[1:]],
            "referee_validity_rating": primary.get("referee_validity_rating"),
            "cited_location": location,
            "v_before": candidate["v_before"],
            "v_after": candidate["v_after"],
            "diff_summary": {"added": added, "deleted": deleted},
            "text_hash": "sha256:" + hashlib.sha256(primary["quote"].encode()).hexdigest(),
            "evidence_class": "referee_stated_technical",
            "human_severity_label": "unreviewed",
        }

        if kind != "equation":
            # Theorem, lemma and section citations are parsed but cannot be
            # anchored by an equation diff. They are recorded for a reviewer
            # rather than dropped: 153 of 793 objections cite only these.
            built.append((None, gold | {
                "location_confidence": "unsupported_location_kind",
                "anchor_hunk": None,
                "candidate_hunks": [_hunk_record(h) for h in fallback[:12]],
            }))
            continue

        anchor, confidence = choose_anchor(old, new, number)
        source = anchor or (fallback[0] if fallback else None)
        if source is None:
            built.append((None, gold | {
                "location_confidence": "no_source_change",
                "anchor_hunk": None,
                "candidate_hunks": [],
            }))
            continue

        start_line, end_line, text = excerpt(old, source)
        if anchor is not None:
            # Test the symbols against the hunk itself. The excerpt is padded
            # with context and whole neighbouring environments, so a symbol
            # from an adjacent equation would confirm any anchor.
            hunk_text = "\n".join(old[slice(*anchor.before_lines)] +
                                   new[slice(*anchor.after_lines)])
            agreement = symbol_agreement(primary["quote"], hunk_text)
            if agreement is True:
                confidence = "corroborated_symbol"
            elif agreement is False:
                confidence = "contradicted_symbols"

        served = confidence in SERVEABLE
        built.append((
            {
                "card_id": card_id,
                "excerpt_lines": [start_line, end_line],
                "excerpt": text,
                "task": TASK,
            } if served else None,
            gold | {
                "location_confidence": confidence,
                "anchor_hunk": _hunk_record(anchor) if anchor else None,
                # A reviewer needs the alternatives, which is the whole point
                # when the chosen anchor was rejected.
                "candidate_hunks": [] if served else [_hunk_record(h) for h in fallback[:12]],
            },
        ))
    return built


def normalize_symbol(text: str) -> str:
    """Fold font macros and whitespace so \\rm and \\mathrm compare equal."""
    return re.sub(r"[\s{}]+", "", FONT_MACRO.sub("", text))


def card_identifier(scipost_identifier: str, kind: str, number: str) -> str:
    """A stable, opaque id.

    A readable id would name the cited equation, and the task asks the model
    to say where the error is; the id must not answer that.
    """
    seed = f"{scipost_identifier}|{kind}|{number}".encode()
    return hashlib.sha256(seed).hexdigest()[:16]


def quoted_symbols(quote: str) -> set[str]:
    """LaTeX symbols the referee typed inside inline math.

    Referees frequently quote the offending expression verbatim.  Only a
    minority of quotes carry symbols, but when they do they are far better
    evidence than an ordinal count.
    """
    found: set[str] = set()
    for fragment in INLINE_MATH.findall(quote or ""):
        found.update(COMPOUND.findall(fragment))
        found.update(m for m in BARE_MACRO.findall(fragment) if m not in FORMATTING)
    return found


def symbol_agreement(quote: str, excerpt_text: str) -> bool | None:
    """True/False if the referee's symbols do/do not appear; None if untestable."""
    # Only a sub/superscripted compound names a specific quantity. A lone
    # \alpha appears in almost any excerpt, so its presence is not evidence
    # and its absence is not counter-evidence: report untestable instead.
    compounds = {s for s in quoted_symbols(quote) if "_" in s or "^" in s}
    if not compounds:
        return None
    haystack = normalize_symbol(excerpt_text)
    return any(normalize_symbol(symbol) in haystack for symbol in compounds)


# Below this, the two revisions are not recognizably the same document.
# Measured over 59 real renamed pairs the median similarity is 0.92, and the
# three genuinely mismatched pairs sat at 0.14-0.21.
SAME_DOCUMENT_RATIO = 0.5


def same_document(old: list[str], new: list[str]) -> bool:
    """Whether two revisions are the same document.

    main_tex falls back to the largest .tex when no toplevel is declared, so
    the two revisions can resolve to different files and the diff would be
    noise presented as a localized change.  The filename is not the test:
    authors rename the main file per revision routinely.
    """
    return difflib.SequenceMatcher(a=old, b=new, autojunk=False).quick_ratio() >= SAME_DOCUMENT_RATIO


def route(built: list[tuple[dict, dict]]) -> tuple[list[dict], list[dict], list[dict]]:
    """Split cards into the model-facing set and the human localization queue.

    A card is served only when its excerpt is anchored by evidence: the authors
    marked the change, it was the only changed equation, or the ordinal matched
    the cited number exactly.  A near match is a guess about which of several
    changed equations the referee meant, and an unresolved card's excerpt may
    not contain the error at all; serving either would ask a question the
    excerpt cannot answer and score the model wrong for our own imprecision.

    Both are kept, with their candidate hunks, for a reviewer.  A referee can
    be right about a paper whose authors rebutted them.
    """
    model_cards, gold_cards, unresolved = [], [], []
    for model, gold in built:
        if model is None:
            unresolved.append(gold)
        else:
            model_cards.append(model)
            gold_cards.append(gold)
    return model_cards, gold_cards, unresolved


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
    model_cards, gold_cards, unresolved, skipped = [], [], [], []
    for row in rows:
        folder = args.source_dir / row["arxiv_id"].replace("/", "_")
        try:
            before_name, old = audit.main_tex(audit.source_file(folder, row["v_before"]))
            after_name, new = audit.main_tex(audit.source_file(folder, row["v_after"]))
        except (OSError, tarfile.TarError, ValueError) as exc:
            skipped.append({"arxiv_id": row["arxiv_id"], "reason": str(exc)})
            continue
        if not same_document(old, new):
            skipped.append({"arxiv_id": row["arxiv_id"],
                            "reason": f"revisions are not the same document: "
                                      f"{before_name} vs {after_name}"})
            continue
        model_part, gold_part, unresolved_part = route(
            build(row, old, new, main_tex=before_name))
        model_cards += model_part
        gold_cards += gold_part
        unresolved += unresolved_part

    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    write_jsonl(args.output_dir / "error_cards.jsonl", model_cards)
    write_jsonl(args.output_dir / "error_cards_gold.jsonl",
                [g | {"retrieved_at": stamp} for g in gold_cards])
    write_jsonl(args.output_dir / "error_cards_unresolved.jsonl",
                [g | {"retrieved_at": stamp} for g in unresolved])
    write_jsonl(args.output_dir / "error_cards_skipped.jsonl", skipped)
    missing_doi = sum(1 for g in gold_cards + unresolved if not g.get("report_doi"))
    confidence: dict[str, int] = {}
    for gold in gold_cards:
        confidence[gold["location_confidence"]] = confidence.get(gold["location_confidence"], 0) + 1
    for gold in unresolved:
        confidence[gold["location_confidence"]] = confidence.get(gold["location_confidence"], 0) + 1
    print(f"{len(rows)} candidates -> {len(model_cards)} benchmark cards, "
          f"{len(unresolved)} for human localization, {len(skipped)} sources unusable")
    for key in sorted(confidence):
        served = " (served)" if key in SERVEABLE else ""
        print(f"  {key:30} {confidence[key]:4}{served}")
    if missing_doi:
        print(f"  note: {missing_doi} gold records have no report DOI; "
              f"attribution falls back to the submission URL")


if __name__ == "__main__":
    main()
