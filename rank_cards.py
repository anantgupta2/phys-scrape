"""Order the reviewer queue by how strong each card's evidence is.

Ranking is deterministic and uses no language model.  That is the point: no
model decides which errors a physicist sees first, so the ordering is
reproducible from the rules alone and cannot quietly bury a class of error
that a model happens to be weak at.  Ranking reorders the queue; it never
removes a card.

Every score is explained by the signals that produced it, so a reviewer can
disagree with the ordering rather than having to trust it.

Example
-------
python rank_cards.py --gold data/error_cards_gold.jsonl \
    --unresolved data/error_cards_unresolved.jsonl
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from jsonl_io import read_jsonl, write_jsonl


# A referee who blocks the paper is making the strongest claim available.
BLOCKING = re.compile(
    r"\b(?:critical error|fatal|cannot be published|before the paper can be"
    r"|must be corrected|cannot be accepted|invalidates|does not hold"
    r"|main result is|central claim)\b",
    re.I,
)
# Unhedged assertions of error, as opposed to "I do not understand".
UNHEDGED = re.compile(
    r"\b(?:is (?:in)?correct|is wrong|sign error|erroneous|contradicts"
    r"|does not agree|dimensionally inconsistent|is invalid|is false)\b",
    re.I,
)
DOUBTED_VALIDITY = frozenset({"poor", "low", "ok"})
ANCHORED = frozenset({
    "corroborated_symbol", "corroborated_author_marked",
    "corroborated_unique", "corroborated_exact",
})
COMPACT_REVISION_LINES = 120

# Weight, signal name, and the test that earns it.
SIGNALS: tuple[tuple[int, str], ...] = (
    (4, "blocking"),
    (3, "unhedged_error"),
    (3, "symbol_confirmed"),
    (2, "stated_error"),
    (2, "author_marked"),
    (2, "multiple_referees"),
    (2, "anchored"),
    (1, "compact_revision"),
    (1, "referee_doubts_validity"),
    (1, "restated"),
)
WEIGHT = {name: weight for weight, name in SIGNALS}


@dataclass(frozen=True)
class Score:
    total: int
    signals: list[str] = field(default_factory=list)


def _signals(card: dict) -> list[str]:
    quote = " ".join([card.get("referee_quote") or ""] + list(card.get("supporting_quotes") or ()))
    diff = card.get("diff_summary") or {}
    changed = (diff.get("added") or 0) + (diff.get("deleted") or 0)
    found = []
    if BLOCKING.search(quote):
        found.append("blocking")
    if UNHEDGED.search(quote):
        found.append("unhedged_error")
    if card.get("location_confidence") == "corroborated_symbol":
        found.append("symbol_confirmed")
    if card.get("tier") == "stated_error":
        found.append("stated_error")
    if card.get("anchor_marked"):
        found.append("author_marked")
    if (card.get("referee_count") or 1) > 1:
        found.append("multiple_referees")
    if card.get("location_confidence") in ANCHORED:
        found.append("anchored")
    if 0 < changed <= COMPACT_REVISION_LINES:
        found.append("compact_revision")
    if (card.get("referee_validity_rating") or "") in DOUBTED_VALIDITY:
        found.append("referee_doubts_validity")
    if card.get("supporting_quotes"):
        found.append("restated")
    return found


def score(card: dict) -> Score:
    found = _signals(card)
    return Score(sum(WEIGHT[name] for name in found), found)


def rank(cards: Iterable[dict]) -> list[dict]:
    """Return the cards in descending evidence order, each explaining itself.

    Sorting is stable, so cards with equal scores keep their input order and a
    rerun over unchanged input produces an unchanged queue.
    """
    scored = [(card, score(card)) for card in cards]
    ordered = sorted(scored, key=lambda pair: -pair[1].total)
    return [card | {"rank": position, "rank_score": result.total,
                    "rank_signals": result.signals}
            for position, (card, result) in enumerate(ordered, start=1)]


def annotate(records: list[dict]) -> list[dict]:
    """Add the cross-card signals that a single record cannot see."""
    per_location: dict[tuple, set] = {}
    for record in records:
        key = (record.get("scipost_identifier"),
               tuple((record.get("cited_location") or {}).values()))
        per_location.setdefault(key, set()).add(record.get("report_url"))
    annotated = []
    for record in records:
        key = (record.get("scipost_identifier"),
               tuple((record.get("cited_location") or {}).values()))
        annotated.append(record | {"referee_count": len(per_location[key])})
    return annotated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--unresolved", type=Path)
    args = parser.parse_args()

    for path in (args.gold, args.unresolved):
        if path is None:
            continue
        ranked = rank(annotate(read_jsonl(path)))
        write_jsonl(path, ranked)
        top = [r for r in ranked if r["rank"] <= 10]
        print(f"{path.name}: ranked {len(ranked)} cards")
        for record in top[:5]:
            print(f"  {record['rank']:3}. score {record['rank_score']:2}  "
                  f"{record['arxiv_id']:12} {','.join(record['rank_signals'])[:56]}")


if __name__ == "__main__":
    main()
