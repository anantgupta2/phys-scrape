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
    assert set(model) == {"card_id", "arxiv_id", "version",
                          "excerpt_lines", "excerpt", "task"}


# --- section-qualified equation numbers --------------------------------------
# Physics papers commonly use \numberwithin{equation}{section}, so "(3.26)" is
# the 26th equation of section 3 rather than the 326th of the document.

SECTIONED = tex(
    r"\section{One}",            # 0
    r"\begin{equation}",         # 1   -> 1.1
    r"a = 1",                    # 2
    r"\end{equation}",           # 3
    r"\section{Two}",            # 4
    r"\begin{equation}",         # 5   -> 2.1
    r"b = 2",                    # 6
    r"\end{equation}",           # 7
    r"\begin{equation}",         # 8   -> 2.2
    r"c = 3",                    # 9
    r"\end{equation}",           # 10
    r"\begin{equation}",         # 11  -> 2.3
    r"d = 4",                    # 12
    r"\end{equation}",           # 13
)


def test_environments_carry_a_section_qualified_label():
    labels = [(start, label) for start, _, _, label in cards.environment_spans(SECTIONED)]
    assert labels == [(1, "1.1"), (5, "2.1"), (8, "2.2"), (11, "2.3")]


def test_a_dotted_citation_resolves_against_section_numbering():
    after = list(SECTIONED)
    after[2] = "a = 1 + x"        # change equation 1.1 as well
    after[12] = "d = 4 + y"       # and equation 2.3
    anchor, confidence = cards.choose_anchor(SECTIONED, after, cited_number="2.3")
    assert confidence == "corroborated_ordinal"
    assert anchor.before_lines == (12, 13)


def test_a_dotted_citation_with_one_candidate_is_unique():
    after = list(SECTIONED)
    after[12] = "d = 4 + y"
    anchor, confidence = cards.choose_anchor(SECTIONED, after, cited_number="2.3")
    assert confidence == "corroborated_unique"
    assert anchor.before_lines == (12, 13)


def test_a_dotted_citation_naming_no_existing_equation_is_unresolved():
    after = list(SECTIONED)
    after[12] = "d = 4 + y"
    anchor, confidence = cards.choose_anchor(SECTIONED, after, cited_number="9.7")
    assert confidence == "unresolved"
    assert anchor is None


def test_plain_ordinals_still_work_in_a_sectioned_document():
    after = list(SECTIONED)
    after[12] = "d = 4 + y"
    anchor, confidence = cards.choose_anchor(SECTIONED, after, cited_number="4")
    assert confidence == "corroborated_unique"
    assert anchor.before_lines == (12, 13)


# --- one card per cited location ---------------------------------------------
# Real: report 1 on arXiv:2002.02120v2 objects to equation (21) in three
# separate sentences. The model-facing side is identical for all three, so
# emitting three cards would duplicate the benchmark item.

MULTI = json.loads(json.dumps(CANDIDATE))
MULTI["objections"] = [
    {"quote": "(3), presented as the main result, does not agree with the standard form.",
     "cited_locations": [{"kind": "equation", "number": "3"}],
     "report_nr": 1, "report_url": "https://scipost.org/x/#report_1",
     "report_doi": "10.21468/SciPost.Report.1", "referee_validity_rating": "ok"},
    {"quote": "(3) is incorrect, and the derivation leading to it must contain an error.",
     "cited_locations": [{"kind": "equation", "number": "3"}],
     "report_nr": 1, "report_url": "https://scipost.org/x/#report_1",
     "report_doi": "10.21468/SciPost.Report.1", "referee_validity_rating": "ok"},
]


def test_repeated_objections_to_one_equation_make_a_single_card():
    built = cards.build(MULTI, V_BEFORE, V_AFTER)
    assert len(built) == 1


def test_card_ids_are_unique_within_a_candidate():
    ids = [model["card_id"] for model, _ in cards.build(MULTI, V_BEFORE, V_AFTER)]
    assert len(ids) == len(set(ids))


def test_supporting_quotes_are_retained_on_the_gold_side():
    (_, gold), = cards.build(MULTI, V_BEFORE, V_AFTER)
    assert gold["referee_quote"].startswith("(3), presented as the main result")
    assert len(gold["supporting_quotes"]) == 1
    assert "must contain an error" in gold["supporting_quotes"][0]


def test_main_tex_filename_stays_on_the_gold_side():
    # Real: 'SciPostPhys_arxiv.tex'. The filename can name the venue, and an
    # evaluated model has no use for it.
    model, gold = cards.build(CANDIDATE, V_BEFORE, V_AFTER, main_tex="SciPostPhys_arxiv.tex")[0]
    assert "main_tex" not in model
    assert gold["main_tex"] == "SciPostPhys_arxiv.tex"
    assert "scipost" not in json.dumps(model).lower()


# --- routing -----------------------------------------------------------------
# An unresolved card's excerpt is a guess, so it may not contain the error at
# all. Serving it as a benchmark item would ask a model an unanswerable
# question. It goes to the human queue instead -- kept, not dropped.

def test_anchored_cards_are_routed_to_the_model_facing_set():
    built = cards.build(CANDIDATE, V_BEFORE, V_AFTER)
    model, gold, unresolved = cards.route(built)
    assert len(model) == 1 and len(gold) == 1 and unresolved == []


def test_unresolved_cards_are_routed_to_the_human_queue_with_their_hunks():
    stubborn = json.loads(json.dumps(CANDIDATE))
    stubborn["objections"][0]["cited_locations"] = [{"kind": "equation", "number": "97"}]
    built = cards.build(stubborn, V_BEFORE, V_AFTER)
    model, gold, unresolved = cards.route(built)
    assert model == [] and gold == []
    assert len(unresolved) == 1
    assert unresolved[0]["location_confidence"] == "unresolved"
    assert unresolved[0]["candidate_hunks"]
    assert unresolved[0]["referee_quote"]


def test_the_human_queue_carries_no_model_facing_excerpt():
    stubborn = json.loads(json.dumps(CANDIDATE))
    stubborn["objections"][0]["cited_locations"] = [{"kind": "equation", "number": "97"}]
    _, _, unresolved = cards.route(cards.build(stubborn, V_BEFORE, V_AFTER))
    assert "excerpt" not in unresolved[0]
