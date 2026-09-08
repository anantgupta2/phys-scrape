"""Atomic JSONL writing, shared by the collection scripts.

Every stage writes through a temporary file so an interrupted run leaves the
previous output intact rather than a truncated one.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line]


def write_jsonl(path: Path, records: Iterable[dict], sort_keys: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=sort_keys) + "\n")
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
