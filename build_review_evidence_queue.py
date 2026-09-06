"""Create a review-first annotation queue without exposing labels to models."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def queue_record(row: dict, triage: dict | None = None) -> dict:
    arxiv_id = row["arxiv_id"]
    version = row.get("version_count")
    status = row.get("source_status", "not_checked")
    if triage and triage.get("triage") == "unreadable_source":
        route = "retry_source_download"
    elif status in {"downloaded_v1_v2", "downloaded_pair"}:
        route = "needs_scipost_match"
    elif status == "invalid_archive":
        route = "retry_source_download"
    elif status in {"skipped_single_version", "skipped_missing_version"}:
        route = "exclude_no_v1_v2_pair"
    else:
        route = "source_status_unknown"
    candidate_urls = []
    if version:
        # SciPost addresses arXiv-based submissions by the bare versioned
        # identifier; an "arXiv:" prefix 404s.
        candidate_urls = [f"https://scipost.org/submissions/{arxiv_id}v{v}/" for v in range(1, version + 1)]
    return {
        "arxiv_id": arxiv_id,
        "title": row.get("title"),
        "primary_category": row.get("primary_category"),
        "version_count": version,
        "source_status": status,
        "queue_route": route,
        "scipost_match_status": "unattempted",
        "scipost_submission_url": None,
        "scipost_candidate_urls": candidate_urls,
        "report_urls": [],
        "author_reply_urls": [],
        "resubmission_comment_urls": [],
        "evidence_class": "unreviewed",
        "human_severity_label": "unreviewed",
        "model_input_policy": "Never include reports, replies, later versions, or diff markup in model prompts.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True, help="source-status JSONL from fetch-sources")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--triage", type=Path, help="optional source-pair triage JSONL; unreadable archives override stale success statuses")
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line]
    triage = {}
    if args.triage:
        triage = {row["arxiv_id"]: row for row in (json.loads(line) for line in args.triage.read_text(encoding="utf-8").splitlines() if line)}
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text("".join(json.dumps(queue_record(row, triage.get(row["arxiv_id"])), ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    temporary.replace(args.output)
