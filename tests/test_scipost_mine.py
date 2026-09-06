"""Tests for SciPost candidate selection.

The two report excerpts used as fixtures are real text from vetted reports on
arXiv:2207.00854v2, and encode the two failures found while designing the
rules: a compliment that a document-level scan mistook for an objection, and a
politely-worded objection that a keyword scan missed entirely.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scipost_mine as mine

FIXTURE = Path(__file__).parent / "fixtures" / "scipost_thread_2207.00854.json"

# Real: report 1 on 2207.00854v2. A substantive objection with no error keyword.
POLITE_OBJECTION = "1)  I do not understand the first equality in (8)."
# Real: report 2 on 2207.00854v2. An explicit contradiction claim.
EXPLICIT_OBJECTION = (
    'On page 6 the authors state that "$q_z$ has non-vanishing commutation '
    'relations with translations," which directly contradicts equation (20).'
)
# Real: a compliment. "does not follow" appears, but nothing is cited.
COMPLIMENT = (
    "The authors also take great care to provide a physical interpretation of "
    "the mathematical notions that underlie their analysis, and the argument "
    "does not follow the usual route."
)
PROSE_REQUEST = "5) many equations are missing a punctuation at the end, starting from Eq.(27)."


def submissions() -> list[dict]:
    return json.loads(FIXTURE.read_text())["results"]


# --- specialty gate ----------------------------------------------------------

@pytest.mark.parametrize("specialty", [
    "Quantum Physics",
    "Mathematical Physics",
    "Gravitation, Cosmology and Astroparticle Physics",
    "Statistical and Soft Matter Physics",
    "High-Energy Physics - Theory",
])
def test_theory_specialties_without_the_word_theory_are_included(specialty):
    assert mine.is_theory({"acad_field": "Physics", "specialties": [specialty]})


def test_experimental_specialties_are_excluded():
    assert not mine.is_theory(
        {"acad_field": "Physics", "specialties": ["High-Energy Physics - Experiment"]}
    )


def test_non_physics_is_excluded():
    assert not mine.is_theory(
        {"acad_field": "Political Science", "specialties": ["Migration Politics"]}
    )


# --- identifiers -------------------------------------------------------------

def test_arxiv_reference_splits_id_and_version():
    assert mine.arxiv_reference("2207.00854v2") == ("2207.00854", 2)


def test_arxiv_reference_handles_a_v0_round():
    assert mine.arxiv_reference("2207.11940v0") == ("2207.11940", 0)


def test_scipost_native_identifier_has_no_arxiv_reference():
    assert mine.arxiv_reference("scipost_202209_00008v1") is None


# --- cited locations ---------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("I do not understand the first equality in (8).", [("equation", "8")]),
    ("which directly contradicts equation (20).", [("equation", "20")]),
    ("there should be a normalisation factor in eq.(12);", [("equation", "12")]),
    ("I believe equation 3 is incorrect", [("equation", "3")]),
    ("the equality in (3.12) should be replaced", [("equation", "3.12")]),
    ("this contradicts Theorem 3.2 of the paper", [("theorem", "3.2")]),
    ("Lemma 4 does not hold", [("lemma", "4")]),
])
def test_cited_locations_are_parsed(text, expected):
    found = [(loc["kind"], loc["number"]) for loc in mine.cited_locations(text)]
    assert found == expected


def test_a_four_digit_year_is_not_a_location():
    assert mine.cited_locations("as shown by Smith (2020) elsewhere") == []


def test_a_sentence_with_no_reference_has_no_location():
    assert mine.cited_locations(COMPLIMENT) == []


# --- objection extraction ----------------------------------------------------

def test_politely_worded_objection_is_found():
    found = mine.objections(POLITE_OBJECTION)
    assert len(found) == 1
    assert found[0]["cited_locations"] == [{"kind": "equation", "number": "8"}]


def test_explicit_objection_is_found():
    found = mine.objections(EXPLICIT_OBJECTION)
    assert [loc["number"] for loc in found[0]["cited_locations"]] == ["20"]


def test_compliment_is_not_an_objection():
    assert mine.objections(COMPLIMENT) == []


def test_prose_request_is_not_an_objection():
    assert mine.objections(PROSE_REQUEST) == []


def test_objection_language_far_from_a_location_does_not_match():
    text = "The result is incorrect in spirit. Separately, see equation (12) for context."
    assert mine.objections(text) == []


# --- rounds ------------------------------------------------------------------

def test_next_round_is_found_through_is_resubmission_of():
    rows = submissions()
    by_thread = mine.group_by_thread(rows)
    before = next(r for r in rows if r["identifier"] == "2207.00854v2")
    assert mine.next_round(before, by_thread)["identifier"] == "2207.00854v3"


def test_final_round_has_no_next_round():
    rows = submissions()
    by_thread = mine.group_by_thread(rows)
    last = next(r for r in rows if r["identifier"] == "2207.00854v3")
    assert mine.next_round(last, by_thread) is None


# --- candidate records -------------------------------------------------------

def test_candidate_carries_the_version_pair_from_the_thread():
    rows = submissions()
    by_thread = mine.group_by_thread(rows)
    before = next(r for r in rows if r["identifier"] == "2207.00854v2")
    card = mine.candidate(before, by_thread)
    assert card["arxiv_id"] == "2207.00854"
    assert (card["v_before"], card["v_after"]) == (2, 3)


def test_candidate_records_both_real_objections_with_provenance():
    rows = submissions()
    by_thread = mine.group_by_thread(rows)
    before = next(r for r in rows if r["identifier"] == "2207.00854v2")
    card = mine.candidate(before, by_thread)
    quotes = [o["quote"] for o in card["objections"]]
    assert any("first equality in (8)" in q for q in quotes)
    assert any("contradicts equation (20)" in q for q in quotes)
    assert all(o["report_doi"].startswith("10.21468/") for o in card["objections"])


def test_final_round_is_not_a_candidate():
    rows = submissions()
    by_thread = mine.group_by_thread(rows)
    last = next(r for r in rows if r["identifier"] == "2207.00854v3")
    assert mine.candidate(last, by_thread) is None


def test_wire_format_fields_are_present_in_the_recorded_response():
    for row in submissions():
        assert {"identifier", "thread_hash", "is_resubmission_of", "status",
                "specialties", "acad_field", "reports", "url"} <= set(row)


def test_a_bare_zero_is_not_an_equation_reference():
    # Real: "the delta(0) in Fourier should be related to..." -- mathematical
    # notation, not a citation. Equation numbering starts at 1.
    assert mine.cited_locations("the delta(0) in Fourier should be related") == []


def test_a_bare_single_digit_reference_is_still_parsed():
    assert mine.cited_locations("I do not understand (8).") == [
        {"kind": "equation", "number": "8"}
    ]


# --- sentence splitting around abbreviations ---------------------------------
# "eq." ends in a period, so a naive splitter cuts the sentence in half. Real
# case, report 1 on arXiv:2002.02120v2: the recorded quote began at "(21),
# presented as the main result", discarding "the paper contains a critical
# error" -- and "This contradicts Eq. (5)." splits into one fragment with the
# objection and another with the location, so neither half qualifies.

REAL_TRUNCATED = (
    "While the motivation is interesting, the paper contains a critical error: "
    "eq. (21), presented as the main result, does not agree with the standard "
    "Weinberg soft factor."
)


def test_an_abbreviation_does_not_end_a_sentence():
    assert mine.sentences("This contradicts Eq. (5).") == ["This contradicts Eq. (5)."]


def test_the_real_truncated_objection_stays_whole():
    found = mine.objections(REAL_TRUNCATED)
    assert len(found) == 1
    assert found[0]["quote"].startswith("While the motivation")
    assert "critical error" in found[0]["quote"]


def test_a_lowercase_abbreviation_is_handled():
    assert mine.sentences("See eq. (12) here.") == ["See eq. (12) here."]


def test_genuine_sentence_boundaries_still_split():
    assert mine.sentences("The first claim holds. The second is wrong.") == [
        "The first claim holds.", "The second is wrong."]


def test_an_abbreviation_does_not_swallow_the_following_sentence():
    assert mine.sentences("See Fig. 3. The result is wrong.") == [
        "See Fig. 3.", "The result is wrong."]


def test_an_author_initial_does_not_end_a_sentence():
    assert mine.sentences("As shown by J. Smith the bound fails.") == [
        "As shown by J. Smith the bound fails."]


# --- report fields must not be welded into one sentence ----------------------
# 2,033 field boundaries in the corpus lack terminal punctuation, which fused
# the tail of one field to the head of the next and fabricated 13 quotes --
# including one that read a bibliography entry as "equation 247".

def test_fields_lacking_terminal_punctuation_do_not_fuse():
    submission = {
        "acad_field": "Physics", "specialties": ["Quantum Physics"],
        "identifier": "2401.00001v1", "url": "/submissions/2401.00001v1/",
        "thread_hash": "t", "reports": [{
            "status": "vetted", "report_nr": 1, "url": "/x", "doi_string": "10.21468/x",
            "validity": "ok",
            "weaknesses": "no weaknesses",                       # no terminal stop
            "requested_changes": "Page 7, Eq (28) should be corrected.",
            "report": "",
        }],
    }
    quotes = [o["quote"] for o in mine.report_objections(submission)]
    assert not any(q.startswith("no weaknesses") for q in quotes)


# --- notation is not a citation ----------------------------------------------
# 33 recorded locations came from gauge groups and function calls: SO(6),
# U(1), sqrt(2). A reference is preceded by whitespace or punctuation, never
# glued to a letter, brace or backslash.

@pytest.mark.parametrize("text", [
    "I find the description of the various SO(6) representations confusing",
    r"the $U(1)_{3/2}$ index should be corrected",
    r"$p' \in H^3(\mathbb{Z}_2,U(1)$ should be different",
    "this is off by a factor of sqrt(2) throughout",
])
def test_notation_is_not_read_as_an_equation_reference(text):
    assert mine.cited_locations(text) == []


def test_a_genuine_bare_reference_is_still_parsed():
    assert mine.cited_locations("I do not understand the first equality in (8).") == [
        {"kind": "equation", "number": "8"}]


def test_a_lowercase_subject_class_identifier_is_recognised():
    assert mine.arxiv_reference("cond-mat.stat-mech/9901001v2") == (
        "cond-mat.stat-mech/9901001", 2)


def test_the_cache_is_deduplicated_by_identifier():
    # Offset pagination over 45 requests can repeat a record if a submission is
    # added mid-enumeration.
    page = {"results": [
        {"identifier": "2401.00001v1", "title": "A"},
        {"identifier": "2401.00001v1", "title": "A"},
        {"identifier": "2401.00002v1", "title": "B"},
    ]}
    assert [r["identifier"] for r in mine.deduplicate(page["results"])] == [
        "2401.00001v1", "2401.00002v1"]


# --- corrective requests -----------------------------------------------------
# A referee asking for a specific change to a specific equation is a candidate
# even without a word like "wrong". This is the recall tier: it adds 317
# (round, location) pairs on the real corpus, taking the total past 1,600.
# It is weaker evidence than a stated error, so it is labelled as such.

def test_a_corrective_request_qualifies_as_a_candidate():
    found = mine.objections("In eq. (14) the prefactor should be replaced by 2/N.")
    assert len(found) == 1
    assert found[0]["tier"] == "corrective_request"


def test_a_stated_error_outranks_a_corrective_request():
    found = mine.objections("(14) is incorrect and should be replaced.")
    assert found[0]["tier"] == "stated_error"


def test_a_corrective_request_without_an_equation_does_not_qualify():
    # Section-level change requests are too weak to carry the tier.
    assert mine.objections("Section 4 should be expanded with more detail.") == []


def test_a_corrective_request_about_prose_is_still_rejected():
    assert mine.objections("The caption of Eq. (3) should be rewritten for grammar.") == []


def test_a_plain_statement_citing_an_equation_is_not_a_candidate():
    assert mine.objections("The derivation of eq. (7) follows Ref. [3].") == []
