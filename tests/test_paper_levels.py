"""Schema and coverage checks for the difficulty labels.

The labels themselves are judgements, not derivable from the data, so these
tests check what can be checked: that every candidate paper has exactly one
label, that the values are in range, and that provenance is recorded so a
human can tell which labels they have and have not overridden.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
LEVELS = ROOT / "data" / "paper_levels.jsonl"
CANDIDATES = ROOT / "data" / "scipost_candidates.jsonl"

MEANINGS = {
    1: "accessible to most or all graduate students",
    2: "accessible to some students and most specialists",
    3: "accessible to many specialists",
    4: "accessible only to elite specialists",
}
# Bands follow the stated descriptions rather than a forced quartile split,
# so they are checked for usability -- none tiny, none dominant -- not for
# equality. Band 1 cannot be padded to a quota without labelling
# subfield-specialist papers as readable by any graduate student.
MIN_SHARE, MAX_SHARE = 0.12, 0.38


def levels() -> list[dict]:
    return [json.loads(line) for line in LEVELS.read_text().splitlines() if line]


def test_every_candidate_paper_is_labelled():
    papers = {json.loads(l)["arxiv_id"] for l in CANDIDATES.read_text().splitlines() if l}
    assert {r["arxiv_id"] for r in levels()} == papers


def test_each_paper_is_labelled_exactly_once():
    ids = [r["arxiv_id"] for r in levels()]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("field", [
    "arxiv_id", "title", "paper_level", "paper_level_meaning", "level_basis",
    "assigned_by", "assigned_on", "axis", "scale", "human_reviewed",
])
def test_every_record_carries_the_field(field):
    assert all(field in r for r in levels())


def test_levels_are_in_range_and_match_their_stated_meaning():
    for r in levels():
        assert r["paper_level"] in MEANINGS
        assert r["paper_level_meaning"] == MEANINGS[r["paper_level"]]


def test_every_label_records_a_basis():
    assert all(r["level_basis"].strip() for r in levels())


def test_every_band_is_populated_and_none_dominates():
    rows = levels()
    for level in MEANINGS:
        share = sum(1 for r in rows if r["paper_level"] == level) / len(rows)
        assert MIN_SHARE <= share <= MAX_SHARE, f"level {level} holds {share:.1%}"


def test_the_scale_records_that_bands_follow_the_descriptions():
    assert all("stated description" in r["scale"] for r in levels())


def test_provenance_marks_the_labels_as_model_assigned_and_unreviewed():
    # These are judgements by a language model, not ground truth. Selection
    # elsewhere in the pipeline stays rule-based; this field exists so that
    # distinction survives into the data.
    for r in levels():
        assert r["assigned_by"].startswith("claude")
        assert r["human_reviewed"] is False
        assert r["axis"] == "background required to read the paper"
