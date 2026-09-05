"""Regression tests for arXiv identifier parsing and SciPost URL construction."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build_review_evidence_queue as queue
import collect_arxiv_candidates as collect


# --- arXiv identifiers -------------------------------------------------------

def test_new_style_id_drops_the_version_suffix():
    assert collect.paper_id("http://arxiv.org/abs/2401.01234v2") == "2401.01234"


def test_new_style_id_without_a_version_is_unchanged():
    assert collect.paper_id("http://arxiv.org/abs/2401.01234") == "2401.01234"


def test_pre_2007_id_keeps_its_archive_prefix():
    assert collect.paper_id("http://arxiv.org/abs/hep-th/0605196v2") == "hep-th/0605196"


def test_pre_2007_id_without_a_version_keeps_its_archive_prefix():
    assert collect.paper_id("http://arxiv.org/abs/gr-qc/9310026") == "gr-qc/9310026"


def test_id_containing_a_letter_v_is_not_truncated_at_it():
    assert collect.paper_id("http://arxiv.org/abs/quant-ph/0201082v1") == "quant-ph/0201082"


# --- SciPost submission URLs -------------------------------------------------

def test_scipost_candidate_urls_use_the_bare_identifier():
    record = queue.queue_record({"arxiv_id": "2506.24112", "version_count": 2})
    assert record["scipost_candidate_urls"] == [
        "https://scipost.org/submissions/2506.24112v1/",
        "https://scipost.org/submissions/2506.24112v2/",
    ]


def test_scipost_candidate_urls_are_empty_without_a_version_count():
    record = queue.queue_record({"arxiv_id": "2506.24112", "version_count": None})
    assert record["scipost_candidate_urls"] == []
