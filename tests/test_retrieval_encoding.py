"""Regression tests for the three retrieval-layer encoding defects.

Each test reproduces a failure observed against the live arXiv API and
recorded in data/collection_status_and_risks.md.
"""
from __future__ import annotations

import gzip
import io
import sys
import tarfile
from pathlib import Path
from urllib.parse import parse_qs, urlencode

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import audit_latex_pairs as audit
import collect_arxiv_candidates as collect


def as_arxiv_receives(params: dict) -> str:
    """Round-trip params the way requests encodes them and arXiv decodes them."""
    return parse_qs(urlencode(params))["search_query"][0]


ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <opensearch:totalResults xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">900</opensearch:totalResults>
  {entries}
</feed>"""

ENTRY = """<entry>
    <id>http://arxiv.org/abs/{aid}v2</id>
    <title>Paper {aid}</title>
    <summary>Abstract {aid}</summary>
    <published>2026-01-01T00:00:00Z</published>
    <updated>2026-02-01T00:00:00Z</updated>
    <author><name>A. Author</name></author>
    <arxiv:primary_category term="{cat}"/>
    <category term="{cat}"/>
  </entry>"""


def feed(categories: list[str]) -> bytes:
    entries = "".join(
        ENTRY.format(aid=f"2601.{index:05d}", cat=category)
        for index, category in enumerate(categories)
    )
    return ATOM.format(entries=entries).encode("utf-8")


# --- Defect 1: the AND/category conjunction is destroyed by URL encoding -------

def test_keyword_query_reaches_arxiv_as_a_category_scoped_conjunction():
    params = collect.search_params('"sign error"', "hep-th", start=0, limit=100)
    assert as_arxiv_receives(params) == 'cat:hep-th AND all:"sign error"'


def test_category_only_query_is_unchanged():
    params = collect.search_params(None, "gr-qc", start=0, limit=100)
    assert as_arxiv_receives(params) == "cat:gr-qc"


# --- Defect 2: pagination stops early because it counts post-filter entries ----

def test_page_reports_entries_returned_separately_from_entries_kept():
    returned, kept = collect.parse_page(feed(["hep-th", "astro-ph.CO", "math.NT"]))
    assert returned == 3
    assert [row["arxiv_id"] for row in kept] == ["2601.00000"]


def test_full_page_of_mostly_off_target_entries_is_not_treated_as_exhausted():
    returned, kept = collect.parse_page(feed(["hep-th"] + ["astro-ph.CO"] * 99))
    assert len(kept) == 1
    assert not collect.page_exhausted(returned, requested=100)


def test_short_page_is_exhausted():
    returned, _ = collect.parse_page(feed(["hep-th"] * 40))
    assert collect.page_exhausted(returned, requested=100)


# --- Defect 3: single-file submissions arrive as bare gzip, not tar -----------

def write_tar(path: Path, name: str, body: bytes) -> Path:
    with tarfile.open(path, "w") as tar:
        info = tarfile.TarInfo(name)
        info.size = len(body)
        tar.addfile(info, io.BytesIO(body))
    return path


def write_gzipped_tex(path: Path, name: str, body: bytes) -> Path:
    buffer = io.BytesIO()
    with gzip.GzipFile(filename=name, mode="wb", fileobj=buffer) as handle:
        handle.write(body)
    path.write_bytes(buffer.getvalue())
    return path


def test_tar_archive_is_recognised(tmp_path):
    path = write_tar(tmp_path / "v1.tar", "main.tex", b"\\documentclass{article}")
    assert collect.source_kind(path) == "tar"


def test_bare_gzipped_tex_is_recognised(tmp_path):
    path = write_gzipped_tex(tmp_path / "v1.tex.gz", "paper.tex", b"\\documentclass{article}")
    assert collect.source_kind(path) == "gzip_tex"


def test_html_interstitial_is_rejected(tmp_path):
    path = tmp_path / "v1.tar"
    path.write_bytes(b"<!DOCTYPE html><html><body>slow down</body></html>")
    assert collect.source_kind(path) is None


def test_audit_reads_a_bare_gzipped_tex_source(tmp_path):
    path = write_gzipped_tex(tmp_path / "v1.tex.gz", "paper.tex", b"line one\nline two\n")
    name, lines = audit.main_tex(path)
    assert name == "paper.tex"
    assert lines == ["line one", "line two"]


def test_audit_still_reads_a_tar_source(tmp_path):
    path = write_tar(tmp_path / "v1.tar", "main.tex", b"line one\nline two\n")
    name, lines = audit.main_tex(path)
    assert name == "main.tex"
    assert lines == ["line one", "line two"]
