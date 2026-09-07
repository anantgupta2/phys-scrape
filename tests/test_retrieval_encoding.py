"""Regression tests for the three retrieval-layer encoding defects.

Each test reproduces a failure observed against the live arXiv API and
recorded in data/collection_status_and_risks.md.
"""
from __future__ import annotations

import gzip
import io
import json
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


# --- Version pairs: a review round is not always v1 -> v2 --------------------
# SciPost thread 2207.00854 ran v2 -> v3. Fetching v1/v2 there retrieves two
# revisions the referees never discussed.

def test_fetch_sources_downloads_the_version_pair_named_by_the_row(tmp_path, monkeypatch):
    monkeypatch.setattr(collect, "version_count", lambda arxiv_id, session: 3)
    sources = tmp_path / "src"
    paper = sources / "2207.00854"
    paper.mkdir(parents=True)
    for version in (2, 3):
        write_tar(paper / f"v{version}.tar", "fracton.tex", b"\\documentclass{article}")
    manifest = tmp_path / "in.jsonl"
    manifest.write_text(
        json.dumps({"arxiv_id": "2207.00854", "source_versions": [2, 3]}) + "\n",
        encoding="utf-8",
    )

    row = collect.fetch_sources(manifest, sources, delay=0)[0]

    assert row["source_status"] == "downloaded_pair"
    assert [a["version"] for a in row["source_artifacts"]] == [2, 3]


def test_fetch_sources_still_defaults_to_v1_v2(tmp_path, monkeypatch):
    monkeypatch.setattr(collect, "version_count", lambda arxiv_id, session: 2)
    sources = tmp_path / "src"
    paper = sources / "2401.01234"
    paper.mkdir(parents=True)
    for version in (1, 2):
        write_tar(paper / f"v{version}.tar", "main.tex", b"\\documentclass{article}")
    manifest = tmp_path / "in.jsonl"
    manifest.write_text(json.dumps({"arxiv_id": "2401.01234"}) + "\n", encoding="utf-8")

    row = collect.fetch_sources(manifest, sources, delay=0)[0]

    assert [a["version"] for a in row["source_artifacts"]] == [1, 2]


def test_audit_reads_the_version_pair_named_by_the_row(tmp_path):
    paper = tmp_path / "2207.00854"
    paper.mkdir(parents=True)
    write_tar(paper / "v2.tar", "fracton.tex", b"before\n")
    write_tar(paper / "v3.tar", "fracton.tex", b"after\n")
    row = {"arxiv_id": "2207.00854", "source_status": "downloaded_pair",
           "source_versions": [2, 3]}

    result = audit.audit(row, tmp_path)

    assert result["triage"] != "unreadable_source"
    assert (result["v1_main_tex"], result["v2_main_tex"]) == ("fracton.tex", "fracton.tex")


def test_audit_still_accepts_the_legacy_status_value(tmp_path):
    paper = tmp_path / "2401.01234"
    paper.mkdir(parents=True)
    write_tar(paper / "v1.tar", "main.tex", b"before\n")
    write_tar(paper / "v2.tar", "main.tex", b"after\n")
    row = {"arxiv_id": "2401.01234", "source_status": "downloaded_v1_v2"}

    assert audit.audit(row, tmp_path)["triage"] != "exclude_no_pair"


def test_fetch_sources_skips_the_network_when_both_sources_are_present(tmp_path, monkeypatch):
    # Re-running the rebuild must not re-query arXiv for 538 papers it already
    # has: that is 27 minutes of requests to learn nothing.
    def refuse(arxiv_id, session):
        raise AssertionError("version_count should not be called when sources exist")
    monkeypatch.setattr(collect, "version_count", refuse)

    sources = tmp_path / "src"
    paper = sources / "2207.00854"
    paper.mkdir(parents=True)
    for version in (2, 3):
        write_tar(paper / f"v{version}.tar", "fracton.tex", b"\\documentclass{article}")
    manifest = tmp_path / "in.jsonl"
    manifest.write_text(
        json.dumps({"arxiv_id": "2207.00854", "source_versions": [2, 3]}) + "\n",
        encoding="utf-8")

    row = collect.fetch_sources(manifest, sources, delay=0)[0]

    assert row["source_status"] == "downloaded_pair"
    assert [a["version"] for a in row["source_artifacts"]] == [2, 3]


def test_fetch_sources_still_queries_when_a_source_is_missing(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(collect, "version_count",
                        lambda arxiv_id, session: calls.append(arxiv_id) or 1)
    manifest = tmp_path / "in.jsonl"
    manifest.write_text(json.dumps({"arxiv_id": "2401.01234"}) + "\n", encoding="utf-8")

    collect.fetch_sources(manifest, tmp_path / "src", delay=0)

    assert calls == ["2401.01234"]
