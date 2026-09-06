"""Tests for benchmark card construction.

The card generator splits evidence into a model-facing file and a gold file.
The leakage test at the bottom is the project's central safety property: a
model evaluated on these cards must never see the referee's finding.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build_error_cards as cards


def tex(*body: str) -> list[str]:
    return list(body)


V_BEFORE = tex(
    r"\section{Setup}",                      # 1
    r"Some prose about the model.",          # 2
    r"\begin{equation}",                     # 3   equation 1
    r"E = m c^2",                            # 4
    r"\end{equation}",                       # 5
    r"More prose here.",                     # 6
    r"\begin{equation}",                     # 7   equation 2
    r"F = m a",                              # 8
    r"\end{equation}",                       # 9
    r"Closing remarks.",                     # 10
    r"\begin{equation}",                     # 11  equation 3
    r"p = m v_{\rm wrong}",                  # 12
    r"\end{equation}",                       # 13
    r"Final line.",                          # 14
)
V_AFTER = tex(
    r"\section{Setup}",
    r"Some prose about the model.",
    r"\begin{equation}",
    r"E = m c^2",
    r"\end{equation}",
    r"More prose here.",
    r"\begin{equation}",
    r"F = m a",
    r"\end{equation}",
    r"Closing remarks.",
    r"\begin{equation}",
    r"p = m v_{\rm fixed}",                  # the only change
    r"\end{equation}",
    r"Final line.",
)

CANDIDATE = {
    "arxiv_id": "1234.56789",
    "v_before": 2,
    "v_after": 3,
    "scipost_identifier": "1234.56789v2",
    "scipost_submission_url": "https://scipost.org/submissions/1234.56789v2/",
    "title": "A Paper",
    "objections": [{
        "quote": "(3) is incorrect, the momentum should not carry that factor.",
        "cited_locations": [{"kind": "equation", "number": "3"}],
        "report_nr": 1,
        "report_url": "https://scipost.org/submissions/1234.56789v2/#report_1",
        "report_doi": "10.21468/SciPost.Report.9999",
        "referee_validity_rating": "ok",
    }],
}


# --- structure ---------------------------------------------------------------

def test_numbered_environments_are_located_in_order():
    assert cards.numbered_environments(V_BEFORE) == [2, 6, 10]


def test_starred_environments_are_not_numbered():
    assert cards.numbered_environments([r"\begin{equation*}", "x", r"\end{equation*}"]) == []


def test_changed_hunks_ignore_unchanged_text():
    hunks = cards.changed_hunks(V_BEFORE, V_AFTER)
    assert len(hunks) == 1
    assert hunks[0].before_lines == (11, 12)


def test_only_equation_bearing_hunks_are_anchor_candidates():
    old = ["prose one", r"\begin{equation}", "x = 1", r"\end{equation}"]
    new = ["prose two", r"\begin{equation}", "x = 2", r"\end{equation}"]
    hunks = cards.changed_hunks(old, new)
    assert len(hunks) == 2
    assert len(cards.equation_hunks(hunks, old, new)) == 1


# --- anchoring ---------------------------------------------------------------

def test_a_single_equation_hunk_anchors_uniquely():
    anchor, confidence = cards.choose_anchor(V_BEFORE, V_AFTER, cited_number="3")
    assert confidence == "corroborated_unique"
    assert anchor.before_lines == (11, 12)


def test_several_hunks_are_resolved_by_ordinal_proximity():
    after = list(V_AFTER)
    after[3] = r"E = m c^2 + \delta"          # also change equation 1
    anchor, confidence = cards.choose_anchor(V_BEFORE, after, cited_number="3")
    assert confidence == "corroborated_ordinal"
    assert anchor.before_lines == (11, 12)     # equation 3, not equation 1


def test_an_ordinal_far_from_every_hunk_is_unresolved():
    anchor, confidence = cards.choose_anchor(V_BEFORE, V_AFTER, cited_number="97")
    assert confidence == "unresolved"
    assert anchor is None


def test_no_equation_change_at_all_is_unresolved():
    after = list(V_BEFORE)
    after[1] = "Some different prose."
    anchor, confidence = cards.choose_anchor(V_BEFORE, after, cited_number="3")
    assert confidence == "unresolved"
    assert anchor is None


def test_author_marked_changes_are_preferred_over_ordinal_proximity():
    # Some authors wrap revisions in \changed{...}; when they do, that is a
    # stronger anchor than counting environments.
    after = list(V_AFTER)
    after[3] = r"E = m c^2 + \delta"
    after[11] = r"p = m v_{\rm fixed} \changed{corrected here}"
    anchor, confidence = cards.choose_anchor(V_BEFORE, after, cited_number="1")
    assert confidence == "corroborated_author_marked"
    assert anchor.before_lines == (11, 12)


# --- excerpts ----------------------------------------------------------------

def test_excerpt_covers_the_whole_enclosing_environment():
    anchor, _ = cards.choose_anchor(V_BEFORE, V_AFTER, cited_number="3")
    start, end, text = cards.excerpt(V_BEFORE, anchor)
    assert r"\begin{equation}" in text and r"\end{equation}" in text
    assert "v_{\\rm wrong}" in text


def test_excerpt_is_capped():
    long_doc = ["line %d" % i for i in range(2000)]
    long_new = list(long_doc); long_new[1000] = "changed"
    hunk = cards.changed_hunks(long_doc, long_new)[0]
    start, end, text = cards.excerpt(long_doc, hunk)
    assert len(text.splitlines()) <= cards.MAX_EXCERPT_LINES


# --- card construction -------------------------------------------------------

def test_one_card_is_built_per_cited_equation():
    built = cards.build(CANDIDATE, V_BEFORE, V_AFTER)
    assert len(built) == 1
    model, gold = built[0]
    assert model["card_id"] == gold["card_id"] == "1234.56789v2-equation3"


def test_gold_card_carries_the_referee_evidence():
    (_, gold), = cards.build(CANDIDATE, V_BEFORE, V_AFTER)
    assert gold["referee_quote"].startswith("(3) is incorrect")
    assert gold["report_doi"] == "10.21468/SciPost.Report.9999"
    assert gold["location_confidence"] == "corroborated_unique"
    assert (gold["v_before"], gold["v_after"]) == (2, 3)
    assert gold["human_severity_label"] == "unreviewed"


def test_unresolved_cards_are_still_emitted_with_candidate_hunks():
    stubborn = json.loads(json.dumps(CANDIDATE))
    stubborn["objections"][0]["cited_locations"] = [{"kind": "equation", "number": "97"}]
    (model, gold), = cards.build(stubborn, V_BEFORE, V_AFTER)
    assert gold["location_confidence"] == "unresolved"
    assert gold["candidate_hunks"]
    assert model["excerpt"]


# --- the leakage firewall ----------------------------------------------------

def test_model_card_never_contains_referee_or_after_version_content():
    (model, gold), = cards.build(CANDIDATE, V_BEFORE, V_AFTER)
    serialized = json.dumps(model)
    assert "incorrect" not in serialized
    assert "Report" not in serialized
    assert "v_{\\rm fixed}" not in serialized
    assert "scipost" not in serialized.lower()
    for forbidden in ("referee_quote", "report_doi", "report_url",
                      "location_confidence", "v_after", "candidate_hunks"):
        assert forbidden not in model


def test_model_card_holds_only_the_before_version_excerpt():
    (model, _), = cards.build(CANDIDATE, V_BEFORE, V_AFTER)
    assert "v_{\\rm wrong}" in model["excerpt"]
    assert set(model) == {"card_id", "arxiv_id", "version", "main_tex",
                          "excerpt_lines", "excerpt", "task"}
