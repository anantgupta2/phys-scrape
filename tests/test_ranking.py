"""Tests for heuristic card ranking.

Ranking orders the reviewer's queue by how strong the evidence is. It is
deterministic on purpose: no model decides what a physicist looks at first,
so the ordering is reproducible and cannot quietly bury a class of error.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import rank_cards


def card(**overrides) -> dict:
    base = {
        "card_id": "aaaa000000000000",
        "referee_quote": "In eq. (14) the prefactor should be replaced by 2/N.",
        "supporting_quotes": [],
        "tier": "corrective_request",
        "location_confidence": "corroborated_exact",
        "referee_validity_rating": "high",
        "diff_summary": {"added": 40, "deleted": 30},
        "anchor_marked": False,
        "referee_count": 1,
    }
    return base | overrides


# --- individual signals ------------------------------------------------------

def test_a_stated_error_scores_above_a_corrective_request():
    stated = rank_cards.score(card(tier="stated_error",
                                   referee_quote="(14) is incorrect."))
    request = rank_cards.score(card())
    assert stated.total > request.total


def test_blocking_language_scores_highest():
    blocking = rank_cards.score(card(
        tier="stated_error",
        referee_quote="(21) is incorrect and must be corrected before the paper "
                      "can be reconsidered."))
    plain = rank_cards.score(card(tier="stated_error",
                                  referee_quote="(21) is incorrect."))
    assert blocking.total > plain.total
    assert "blocking" in blocking.signals


def test_symbol_confirmation_raises_the_score():
    confirmed = rank_cards.score(card(location_confidence="corroborated_symbol"))
    assert confirmed.total > rank_cards.score(card()).total
    assert "symbol_confirmed" in confirmed.signals


def test_an_author_marked_anchor_raises_the_score():
    marked = rank_cards.score(card(anchor_marked=True))
    assert "author_marked" in marked.signals
    assert marked.total > rank_cards.score(card()).total


def test_a_compact_revision_raises_the_score():
    compact = rank_cards.score(card(diff_summary={"added": 6, "deleted": 4}))
    sprawling = rank_cards.score(card(diff_summary={"added": 900, "deleted": 800}))
    assert compact.total > sprawling.total
    assert "compact_revision" in compact.signals


def test_a_low_validity_rating_raises_the_score():
    poor = rank_cards.score(card(referee_validity_rating="poor"))
    assert "referee_doubts_validity" in poor.signals
    assert poor.total > rank_cards.score(card()).total


def test_two_referees_on_one_location_raise_the_score():
    both = rank_cards.score(card(referee_count=2))
    assert "multiple_referees" in both.signals
    assert both.total > rank_cards.score(card()).total


def test_repeated_objections_to_one_location_raise_the_score():
    repeated = rank_cards.score(card(supporting_quotes=["(14) is wrong.", "still wrong"]))
    assert "restated" in repeated.signals
    assert repeated.total > rank_cards.score(card()).total


def test_an_unanchored_card_scores_below_an_anchored_one():
    assert (rank_cards.score(card(location_confidence="unresolved")).total
            < rank_cards.score(card()).total)


# --- ordering ----------------------------------------------------------------

def test_ranking_is_descending_and_dense():
    cards = [card(card_id="a", tier="corrective_request"),
             card(card_id="b", tier="stated_error",
                  referee_quote="(3) is incorrect and must be corrected before publication."),
             card(card_id="c", location_confidence="unresolved")]
    ranked = rank_cards.rank(cards)
    assert [r["card_id"] for r in ranked] == ["b", "a", "c"]
    assert [r["rank"] for r in ranked] == [1, 2, 3]
    assert all(r["rank_signals"] for r in ranked[:2])


def test_ranking_is_stable_for_equal_scores():
    same = [card(card_id="x"), card(card_id="y"), card(card_id="z")]
    assert [r["card_id"] for r in rank_cards.rank(same)] == ["x", "y", "z"]


def test_ranking_does_not_drop_or_add_cards():
    cards = [card(card_id=f"c{i}", tier="stated_error" if i % 2 else "corrective_request")
             for i in range(20)]
    ranked = rank_cards.rank(cards)
    assert len(ranked) == 20
    assert {r["card_id"] for r in ranked} == {c["card_id"] for c in cards}


def test_every_ranked_card_explains_its_score():
    for ranked in rank_cards.rank([card(), card(card_id="b", tier="stated_error")]):
        assert isinstance(ranked["rank_score"], (int, float))
        assert isinstance(ranked["rank_signals"], list)
