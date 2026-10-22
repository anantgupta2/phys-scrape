"""Tests for the edit-scope annotation.

Each case here is a real pattern from the corpus that an earlier version of
the classifier got wrong. Three iterations were refuted by hand-auditing the
output; the cases below are what those audits found.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import annotate_edit_scope as scope

ROOT = Path(__file__).resolve().parent.parent
ANNOTATIONS = ROOT / "data" / "precutoff" / "annotations_edit_scope.jsonl"


def card(before: str, after: str, quote: str = "Eq. (3) is wrong.") -> dict:
    return {
        "card_id": "x" * 16, "arxiv_id": "2101.00001",
        "referee_quote": quote,
        "anchor_hunk": {"before_text": before, "after_text": after},
        "human_severity_label": "unreviewed",
    }


# --- a bare letter is a symbol, not prose -----------------------------------
# "Please remove the erroneous factor $g$" changes exactly one character, and a
# regex for mathematics does not fire on a bare letter.

def test_deleting_a_single_factor_is_a_symbolic_edit():
    out = scope.edit_scope(card(r"V = g \phi^2", r"V = \phi^2",
                                "Please remove the erroneous factor $g$ in Eq. (11)."))
    assert out["edit_scope"] == "bounded_symbolic"


# --- a minus sign is never punctuation --------------------------------------

def test_a_sign_change_is_symbolic_and_recorded_as_a_sign():
    out = scope.edit_scope(card(r"E = + m c^2", r"E = - m c^2",
                                "Eq. (6) should be written with a minus sign."))
    assert out["edit_scope"] == "bounded_symbolic"
    assert out["sign_changed"] is True


def test_pm_counts_as_a_sign():
    out = scope.edit_scope(card(r"a \mp 1", r"a \pm i"))
    assert out["sign_changed"] is True


# --- diffing must not split a LaTeX command ---------------------------------
# Character-level diffing turned \beta -> \gamma into 'bet' -> 'gamm', which a
# prose-word test reads as prose.

def test_swapping_two_greek_letters_is_symbolic():
    out = scope.edit_scope(card(r"x = \beta y", r"x = \gamma y",
                                "in eq. (25) beta should be exchanged with gamma"))
    assert out["edit_scope"] == "bounded_symbolic"
    assert any("symbol changed" in s for s in out["signals"])


# --- identifiers are not mathematics ----------------------------------------
# \label{eq:overlap} scored as symbolic because the fragment "eq" is short
# enough to look like a variable.

def test_adding_a_label_is_typesetting_not_mathematics():
    out = scope.edit_scope(card(r"\begin{equation} x = y \end{equation}",
                                r"\begin{equation} x = y \label{eq:overlap} \end{equation}",
                                "The physical background should be explained."))
    assert out["edit_scope"] == "typesetting_only"


def test_adding_nonumber_is_typesetting_not_mathematics():
    out = scope.edit_scope(card(r"a = b \\ c = d", r"a = b \\ \nonumber c = d",
                                "eqs (9,10) should have only one equation number"))
    assert out["edit_scope"] == "typesetting_only"


# --- braces group mathematics -----------------------------------------------
# A referee reported missing brackets, and the authors' fix was exactly a pair
# of braces.

def test_adding_a_missing_brace_pair_is_symbolic():
    out = scope.edit_scope(card(r"\langle A B \rangle", r"\langle {A B} \rangle",
                                "commutator brackets seem to be missing"))
    assert out["edit_scope"] == "bounded_symbolic"


# --- the two axes stay separate ---------------------------------------------

def test_a_correction_answered_by_a_comma_is_flagged():
    out = scope.edit_scope(card("the result, which", "the result. which",
                                "Eq. (29) is wrong."))
    assert out["edit_scope"] == "punctuation_only"
    assert out["complaint_kind"] == "correction"
    assert out["anchor_answers_the_complaint"] is False


def test_a_presentational_request_is_not_flagged():
    out = scope.edit_scope(card("the result, which", "the result. which",
                                "$n$ should be defined."))
    assert out["complaint_kind"] == "presentational"
    assert out["anchor_answers_the_complaint"] is True


def test_a_large_rewrite_is_a_restructured_derivation():
    before = " ".join(f"x_{i} = y_{i} +" for i in range(40))
    out = scope.edit_scope(card(before, ""))
    assert out["edit_scope"] == "derivation_restructured"


# --- the annotation must never become authoritative -------------------------

def test_the_annotation_never_assigns_severity():
    out = scope.edit_scope(card(r"a = b", r"a = c"))
    assert out["is_severity_judgement"] is False
    assert out["human_severity_label"] == "unreviewed"


def test_no_annotation_file_ever_fills_human_severity_label():
    if not ANNOTATIONS.exists():
        pytest.skip("annotations not built")
    rows = [json.loads(l) for l in ANNOTATIONS.read_text().splitlines() if l.strip()]
    assert rows
    assert {r["human_severity_label"] for r in rows} == {"unreviewed"}
    assert all(r["is_severity_judgement"] is False for r in rows)


def test_the_annotation_never_reaches_the_model_facing_file():
    served = ROOT / "data" / "precutoff" / "error_cards.jsonl"
    if not (served.exists() and ANNOTATIONS.exists()):
        pytest.skip("not built")
    cards = [json.loads(l) for l in served.read_text().splitlines() if l.strip()]
    assert all(set(c) == {"card_id", "excerpt_lines", "excerpt", "task"} for c in cards)


def test_every_served_card_is_annotated():
    served = ROOT / "data" / "precutoff" / "error_cards_gold.jsonl"
    if not (served.exists() and ANNOTATIONS.exists()):
        pytest.skip("not built")
    gold = {json.loads(l)["card_id"] for l in served.read_text().splitlines() if l.strip()}
    annotated = {json.loads(l)["card_id"] for l in ANNOTATIONS.read_text().splitlines() if l.strip()}
    assert gold == annotated
