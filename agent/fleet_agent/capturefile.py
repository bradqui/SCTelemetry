"""Read capture/fixture JSONL files (plain or .gz) written by tools/capture.py."""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterator
from pathlib import Path


def read_records(path: Path) -> Iterator[dict]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def read_frames(path: Path) -> Iterator[tuple[int, dict]]:
    """(t ms, raw frame) pairs, skipping notes."""
    for rec in read_records(path):
        if "frame" in rec:
            yield rec["t"], rec["frame"]
