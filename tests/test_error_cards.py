"""Tests for benchmark card construction.

The card generator splits evidence into a model-facing file and a gold file.
The leakage test at the bottom is the project's central safety property: a
model evaluated on these cards must never see the referee's finding.
"""
from __future__ import annotations

import json
import re
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
    assert confidence == "corroborated_exact"
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


def test_an_exact_unmarked_match_beats_a_distant_marked_one():
    # The citation is the referee's own statement of location; an author tag
    # only says the authors touched something.
    after = list(V_AFTER)
    after[3] = r"E = m c^2 + \delta"
    after[11] = r"p = m v_{\rm fixed} \changed{corrected here}"
    anchor, confidence = cards.choose_anchor(V_BEFORE, after, cited_number="1")
    assert anchor.before_lines == (3, 4)
    assert confidence == "corroborated_exact"


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
    assert model["card_id"] == gold["card_id"]
    assert re.fullmatch(r"[0-9a-f]{16}", model["card_id"])


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
    assert model is None          # nothing model-facing for an unanchored card


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
    assert set(model) == {"card_id", "excerpt_lines", "excerpt", "task"}


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
    assert confidence == "corroborated_exact"
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


# --- exact versus near anchors -----------------------------------------------
# Measured over 37 real anchored cards, 20 matched the cited number exactly and
# 17 sat one to three ordinals away. A near match is a guess about which
# equation the referee meant, so it is reviewed rather than served.

def test_an_exact_ordinal_match_is_distinguished_from_a_near_one():
    after = list(V_BEFORE)
    after[3] = r"E = m c^2 + \delta"      # equation 1 changes
    after[7] = r"F = m a + \epsilon"      # equation 2 changes; equation 3 does not
    anchor, confidence = cards.choose_anchor(V_BEFORE, after, cited_number="3")
    assert confidence == "corroborated_near"
    assert anchor.before_lines == (7, 8)   # equation 2, the closest change


def test_near_anchors_go_to_the_human_queue():
    candidate = json.loads(json.dumps(CANDIDATE))
    after = list(V_BEFORE)
    after[3] = r"E = m c^2 + \delta"
    after[7] = r"F = m a + \epsilon"
    model, gold, unresolved = cards.route(cards.build(candidate, V_BEFORE, after))
    assert model == [] and gold == []
    assert unresolved[0]["location_confidence"] == "corroborated_near"


def test_exact_anchors_reach_the_benchmark_set():
    model, gold, unresolved = cards.route(cards.build(CANDIDATE, V_BEFORE, V_AFTER))
    assert len(model) == 1 and unresolved == []
    assert gold[0]["location_confidence"] in {
        "corroborated_unique", "corroborated_exact", "corroborated_author_marked"}


# --- symbols quoted by the referee -------------------------------------------
# Referees often quote the offending expression: "should read $j(-h)^{*}$
# instead of $J(-h)^{*}$". Only about a quarter of quotes carry usable symbols,
# but where they do they are stronger evidence than any ordinal count -- on
# real data they confirmed 5 anchors and contradicted 3 that ordinals accepted.

def test_symbols_are_extracted_from_inline_math():
    found = cards.quoted_symbols(r"should read $\alpha_{\ell}$ instead of $\beta_{k}$")
    assert r"\alpha" in found and r"\beta" in found


def test_prose_without_math_yields_no_symbols():
    assert cards.quoted_symbols("(21) is incorrect and must be corrected.") == set()


def test_a_quoted_symbol_present_in_the_excerpt_confirms_the_anchor():
    candidate = json.loads(json.dumps(CANDIDATE))
    candidate["objections"][0]["quote"] = r"(3) is wrong: $v_{\rm wrong}$ cannot appear here."
    (_, gold), = cards.build(candidate, V_BEFORE, V_AFTER)
    assert gold["location_confidence"] == "corroborated_symbol"


def test_a_quoted_symbol_absent_from_the_excerpt_contradicts_the_anchor():
    candidate = json.loads(json.dumps(CANDIDATE))
    candidate["objections"][0]["quote"] = r"(3) is wrong: $\Xi_{\rm nowhere}$ is misdefined."
    (_, gold), = cards.build(candidate, V_BEFORE, V_AFTER)
    assert gold["location_confidence"] == "contradicted_symbols"


def test_a_contradicted_anchor_is_not_served():
    candidate = json.loads(json.dumps(CANDIDATE))
    candidate["objections"][0]["quote"] = r"(3) is wrong: $\Xi_{\rm nowhere}$ is misdefined."
    model, gold, unresolved = cards.route(cards.build(candidate, V_BEFORE, V_AFTER))
    assert model == [] and gold == []
    assert unresolved[0]["location_confidence"] == "contradicted_symbols"


# --- the card id must not answer the question --------------------------------
# A readable id such as "2207.00854v2-equation8" names the equation, while the
# task asks the model to state where the error occurs.

def test_model_facing_card_id_does_not_name_the_cited_equation():
    (model, gold), = cards.build(CANDIDATE, V_BEFORE, V_AFTER)
    assert "equation" not in model["card_id"]
    assert "1234.56789" not in model["card_id"]
    assert re.fullmatch(r"[0-9a-f]{16}", model["card_id"])
    assert gold["card_id"] == model["card_id"]
    assert gold["cited_location"] == {"kind": "equation", "number": "3"}


def test_card_ids_are_stable_across_runs():
    first = cards.build(CANDIDATE, V_BEFORE, V_AFTER)[0][0]["card_id"]
    second = cards.build(CANDIDATE, V_BEFORE, V_AFTER)[0][0]["card_id"]
    assert first == second


def test_distinct_locations_get_distinct_ids():
    two = json.loads(json.dumps(CANDIDATE))
    two["objections"][0]["cited_locations"] = [
        {"kind": "equation", "number": "1"}, {"kind": "equation", "number": "3"}]
    ids = {gold["card_id"] for _, gold in cards.build(two, V_BEFORE, V_AFTER)}
    assert len(ids) == 2


def test_model_card_carries_no_retrievable_paper_identity():
    # arxiv_id + version reconstruct both the later revision and the SciPost
    # submission URL, so an agentic evaluee could fetch the answer.
    (model, gold), = cards.build(CANDIDATE, V_BEFORE, V_AFTER)
    assert set(model) == {"card_id", "excerpt_lines", "excerpt", "task"}
    assert gold["arxiv_id"] == "1234.56789"
    assert gold["version"] == 2


# --- an author-marked hunk must still match the citation ---------------------
# 20 of the 74 changed hunks on arXiv:2207.00854 carry \changed, so taking the
# first one anchors every card in the paper to the same arbitrary equation.

AUTHOR_MARKED_BEFORE = tex(
    r"\section{S}",
    r"\begin{equation}", r"a = 1", r"\end{equation}",      # eq 1
    r"\begin{equation}", r"b = 2", r"\end{equation}",      # eq 2
    r"\begin{equation}", r"c = 3", r"\end{equation}",      # eq 3
)
AUTHOR_MARKED_AFTER = tex(
    r"\section{S}",
    r"\begin{equation}", r"a = 1 \changed{x}", r"\end{equation}",
    r"\begin{equation}", r"b = 2", r"\end{equation}",
    r"\begin{equation}", r"c = 3 \changed{y}", r"\end{equation}",
)


def test_an_author_marked_hunk_matching_the_citation_is_used():
    anchor, confidence = cards.choose_anchor(
        AUTHOR_MARKED_BEFORE, AUTHOR_MARKED_AFTER, cited_number="3")
    assert confidence == "corroborated_author_marked"
    assert anchor.before_lines == (8, 9)          # equation 3, not equation 1


def test_author_marked_hunks_that_all_miss_the_citation_do_not_anchor():
    anchor, confidence = cards.choose_anchor(
        AUTHOR_MARKED_BEFORE, AUTHOR_MARKED_AFTER, cited_number="40")
    assert confidence == "unresolved"
    assert anchor is None


def test_two_citations_in_one_marked_paper_get_different_anchors():
    both = json.loads(json.dumps(CANDIDATE))
    both["objections"][0]["cited_locations"] = [
        {"kind": "equation", "number": "1"}, {"kind": "equation", "number": "3"}]
    built = cards.build(both, AUTHOR_MARKED_BEFORE, AUTHOR_MARKED_AFTER)
    anchors = {tuple(gold["anchor_hunk"]["before_lines"]) for _, gold in built}
    assert len(anchors) == 2


# --- nothing is dropped without a record -------------------------------------
# 153 of 793 objections cite only a theorem, lemma or section, and 83 of 462
# candidates cite no equation at all. They previously produced no output row
# of any kind.

def test_a_non_equation_citation_is_recorded_rather_than_discarded():
    theorem = json.loads(json.dumps(CANDIDATE))
    theorem["objections"][0]["cited_locations"] = [{"kind": "theorem", "number": "2"}]
    built = cards.build(theorem, V_BEFORE, V_AFTER)
    model, gold, unresolved = cards.route(built)
    assert model == []
    assert len(unresolved) == 1
    assert unresolved[0]["location_confidence"] == "unsupported_location_kind"
    assert unresolved[0]["cited_location"]["kind"] == "theorem"
    assert unresolved[0]["referee_quote"]


# --- serve only exact anchors ------------------------------------------------

def test_a_lone_but_distant_equation_change_is_not_served():
    # Referee cites equation 4; only equation 1 changed. One candidate, but the
    # ordinal is three away -- the same distance that produced a wrong anchor
    # on real data.
    after = list(V_BEFORE)
    after[3] = r"E = m c^2 + \delta"
    anchor, confidence = cards.choose_anchor(V_BEFORE, after, cited_number="4")
    assert confidence == "corroborated_near"


def test_a_lone_exact_equation_change_is_served():
    anchor, confidence = cards.choose_anchor(V_BEFORE, V_AFTER, cited_number="3")
    assert confidence == "corroborated_unique"


# --- symbol agreement --------------------------------------------------------

def test_a_bare_macro_alone_cannot_confirm_an_anchor():
    # A lone \alpha appears in almost any excerpt; it is not evidence.
    assert cards.symbol_agreement(r"(3) is wrong: $\alpha$ is misused.",
                                  r"\begin{equation}\alpha = 1\end{equation}") is None


def test_notation_differences_do_not_count_as_contradiction():
    # Referees retype rather than copy source, so \rm and \mathrm must fold.
    assert cards.symbol_agreement(r"should read $v_{\rm wrong}$",
                                  r"p = m v_{\mathrm{wrong}}") is True


def test_symbols_are_matched_against_the_hunk_not_the_padded_excerpt():
    # The excerpt is padded by context and whole neighbouring environments, so
    # a symbol from an adjacent equation must not confirm the anchor.
    candidate = json.loads(json.dumps(CANDIDATE))
    candidate["objections"][0]["quote"] = r"(3) is wrong: $c^2$ is misplaced."
    (_, gold), = cards.build(candidate, V_BEFORE, V_AFTER)
    assert gold["location_confidence"] == "contradicted_symbols"


# --- the human queue needs alternatives --------------------------------------

def test_near_anchors_carry_candidate_hunks_for_the_reviewer():
    after = list(V_BEFORE)
    after[3] = r"E = m c^2 + \delta"
    after[7] = r"F = m a + \epsilon"
    _, _, unresolved = cards.route(cards.build(CANDIDATE, V_BEFORE, after))
    assert unresolved[0]["location_confidence"] == "corroborated_near"
    assert len(unresolved[0]["candidate_hunks"]) >= 2


# --- the firewall, checked exhaustively rather than by keyword ---------------
# The earlier leakage test grepped for four literal strings, which is how a
# readable card_id naming the cited equation reached the model-facing file.
# This one compares every gold value against every model value.

def leak_candidates() -> list[dict]:
    base = json.loads(json.dumps(CANDIDATE))
    variants = []
    for number, quote in (
        ("3", "(3) is incorrect, the momentum should not carry that factor."),
        ("1", r"(1) is wrong: $c^2$ has the wrong power."),
        ("3", r"(3) should read $v_{\rm fixed}$ throughout."),
    ):
        variant = json.loads(json.dumps(base))
        variant["objections"][0]["quote"] = quote
        variant["objections"][0]["cited_locations"] = [{"kind": "equation", "number": number}]
        variants.append(variant)
    return variants


def test_no_gold_value_appears_in_any_model_card():
    for candidate in leak_candidates():
        for model, gold in cards.build(candidate, V_BEFORE, V_AFTER):
            if model is None:
                continue
            blob = json.dumps(model)
            for key, value in gold.items():
                if key in {"card_id", "diff_summary", "human_severity_label",
                           "evidence_class", "cited_location", "supporting_quotes"}:
                    continue
                if isinstance(value, str) and len(value) > 3:
                    assert value not in blob, f"{key} leaked into the model card"


def test_no_model_card_exposes_a_key_outside_the_allowed_set():
    allowed = {"card_id", "excerpt_lines", "excerpt", "task"}
    for candidate in leak_candidates():
        for model, _ in cards.build(candidate, V_BEFORE, V_AFTER):
            if model is not None:
                assert set(model) == allowed


def test_no_model_card_contains_the_after_version_text():
    for candidate in leak_candidates():
        for model, _ in cards.build(candidate, V_BEFORE, V_AFTER):
            if model is not None:
                assert "v_{\\rm fixed}" not in model["excerpt"]
