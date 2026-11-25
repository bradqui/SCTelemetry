"""Read capture/fixture JSONL files (plain or .gz) written by tools/capture.py, and problem
reports (a .zip with capture.jsonl.gz inside, docs/REPORTS.md)."""

from __future__ import annotations

import gzip
import io
import json
import zipfile
from collections.abc import Iterator
from pathlib import Path

REPORT_CAPTURE = "capture.jsonl.gz"
REPORT_PROTOSET = "telemetry.protoset"


def read_records(path: Path) -> Iterator[dict]:
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            data = gzip.decompress(z.read(REPORT_CAPTURE))
        lines = io.StringIO(data.decode("utf-8"))
        for line in lines:
            if line.strip():
                yield json.loads(line)
        return
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def report_protoset(path: Path) -> bytes | None:
    """The game's message definitions a report was made with, if it has them."""
    if path.suffix != ".zip":
        return None
    with zipfile.ZipFile(path) as z:
        return z.read(REPORT_PROTOSET) if REPORT_PROTOSET in z.namelist() else None


def read_frames(path: Path) -> Iterator[tuple[int, dict]]:
    """(t ms, raw frame) pairs, skipping notes."""
    for rec in read_records(path):
        if "frame" in rec:
            yield rec["t"], rec["frame"]
