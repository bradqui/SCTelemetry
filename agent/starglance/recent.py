"""The last 30 minutes, kept on disk for problem reports (docs/REPORTS.md).

While the game streams, everything the agent receives and does is appended to one
gzipped JSON-lines file per minute in ``%LOCALAPPDATA%\\Starglance\\recent``, in the
capture format (``{"t", "frame" | "log" | "event" | "state" | "mark"}``), so a report
cut from it replays with ``run --replay``. Compressed as it arrives (tens of
microseconds a frame) and flushed every few seconds, so a crash costs seconds, not the
file. Files older than 30 minutes are deleted unless a mark keeps them: a mark keeps the
10 minutes around it for 24 hours, or until a report is saved from it.

Loop-thread only, like the pipeline that feeds it.
"""

from __future__ import annotations

import contextlib
import gzip
import json
import logging
import os
import shutil
import time
import zlib
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

from . import paths

log = logging.getLogger(__name__)

KEEP_MS = 30 * 60_000
SEGMENT_MS = 60_000
FLUSH_MS = 5_000
MARK_BEFORE_MS = 8 * 60_000
MARK_AFTER_MS = 2 * 60_000
MARK_KEEP_MS = 24 * 3600_000
MAX_MARKS = 20


def now_ms() -> int:
    return int(time.time() * 1000)


def settings_file() -> Path:
    return paths.data_dir() / "reports.json"


def load_settings() -> dict:
    """``keep`` (the buffer, on unless switched off) and ``hotkey`` (a preset name or None)."""
    try:
        data = json.loads(settings_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    hotkey = data.get("hotkey")
    return {
        "keep": data.get("keep", True) is not False,
        "hotkey": hotkey if isinstance(hotkey, str) else None,
    }


def save_settings(**changes) -> dict:
    data = {**load_settings(), **changes}
    with contextlib.suppress(OSError):
        settings_file().write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


@dataclass
class Mark:
    id: str
    t: int
    source: str
    """"app" (the page or the tray), "hotkey", or "device" (a paired tablet or PC)."""
    until: int


def _segment_start(path: Path) -> int | None:
    try:
        return int(path.name.split("-", 1)[0])
    except ValueError:
        return None


def read_segment(path: Path) -> Iterator[bytes]:
    """The lines of one segment, up to wherever it ends: a file the agent was writing when
    it stopped has no gzip trailer, and its end may be cut short or damaged. Everything
    before that is kept (it's decompressed in small steps for that reason)."""
    try:
        data = path.read_bytes()
    except OSError:
        return
    out = bytearray()
    pos, step = 0, 4096
    while pos < len(data):
        d = zlib.decompressobj(31)  # one gzip member (a file reopened in the same minute has two)
        try:
            while pos < len(data) and not d.eof:
                chunk = data[pos : pos + step]
                saved = d.copy()
                try:
                    out += d.decompress(chunk)
                except zlib.error:
                    # Damaged here: go back and take what's good, a byte at a time.
                    d = saved
                    for i in range(len(chunk)):
                        out += d.decompress(chunk[i : i + 1])
                pos += len(chunk)
        except zlib.error:
            break
        if not d.eof:
            break
        pos -= len(d.unused_data)
    lines = bytes(out).split(b"\n")
    yield from (line for line in lines[:-1] if line)  # the last piece has no newline: cut short


class RecentBuffer:
    def __init__(
        self, folder: Path | None = None, *, keep: bool = True, clock: Callable[[], int] = now_ms
    ) -> None:
        self.folder = folder or paths.data_dir() / "recent"
        self.keep = keep
        self.clock = clock
        self._run = f"{os.getpid()}"
        self._fh: gzip.GzipFile | None = None
        self._path: Path | None = None
        self._segment: int | None = None
        self._flushed = 0
        self._failed = False
        self.marks: list[Mark] = self._load_marks() if keep else []
        self.on_marks: Callable[[list[Mark]], None] | None = None
        """Told whenever the marks change (the page's header shows them)."""
        if keep:
            self.prune()
        # Off: nothing to do. Switching it off deleted the folder (and a replay, which runs
        # with it off, mustn't touch the live agent's).

    # -- writing

    def record(self, rec: dict, t: int | None = None) -> None:
        if not self.keep or self._failed:
            return
        t = self.clock() if t is None else t
        try:
            segment = t - t % SEGMENT_MS
            if segment != self._segment or self._fh is None:
                self._open(segment)
            line = json.dumps({"t": t, **rec}, separators=(",", ":"), default=str)
            assert self._fh is not None
            self._fh.write(line.encode("utf-8") + b"\n")
            if t - self._flushed >= FLUSH_MS:
                self._fh.flush()
                self._flushed = t
        except OSError:
            log.exception("Problem reports: can't write the recent buffer; stopped")
            self._failed = True
            self._close()

    def _open(self, segment: int) -> None:
        self._close()
        self.folder.mkdir(parents=True, exist_ok=True)
        self._path = self.folder / f"{segment}-{self._run}.jsonl.gz"
        self._fh = gzip.open(self._path, "ab", compresslevel=6)  # noqa: SIM115 (kept open)
        self._segment = segment
        self.prune()

    def flush(self) -> None:
        if self._fh is not None:
            with contextlib.suppress(OSError):
                self._fh.flush()

    def _close(self) -> None:
        if self._fh is not None:
            with contextlib.suppress(OSError):
                self._fh.close()
        self._fh = None
        self._segment = None

    def close(self) -> None:
        self._close()

    # -- keeping and forgetting

    def _windows(self) -> list[tuple[int, int]]:
        return [(m.t - MARK_BEFORE_MS, m.t + MARK_AFTER_MS) for m in self.marks]

    def prune(self) -> None:
        now = self.clock()
        before = len(self.marks)
        self.marks = [m for m in self.marks if m.until > now]
        if len(self.marks) != before:
            self._save_marks()
        cutoff = now - KEEP_MS
        kept = self._windows()
        for path in self._segments():
            start = _segment_start(path)
            if start is None or path == self._path:
                continue
            end = start + SEGMENT_MS
            if end >= cutoff or any(start < b and end > a for a, b in kept):
                continue
            with contextlib.suppress(OSError):
                path.unlink()

    def _segments(self) -> list[Path]:
        if not self.folder.is_dir():
            return []
        return sorted(
            (p for p in self.folder.glob("*.jsonl.gz") if _segment_start(p) is not None),
            key=lambda p: (_segment_start(p), p.name),
        )

    def set_keep(self, on: bool) -> None:
        if on == self.keep:
            return
        self.keep = on
        self._failed = False
        if not on:
            self._close()
            self._delete_all()
            self.marks = []
            self._changed()

    def _delete_all(self) -> None:
        if self.folder.is_dir():
            shutil.rmtree(self.folder, ignore_errors=True)

    # -- marks

    def mark(self, source: str = "app", t: int | None = None) -> Mark | None:
        """Mark a moment; None when the buffer is off (there'd be nothing to keep)."""
        if not self.keep:
            return None
        t = self.clock() if t is None else t
        m = Mark(id=str(t), t=t, source=source, until=t + MARK_KEEP_MS)
        self.marks = [x for x in self.marks if x.id != m.id][-(MAX_MARKS - 1) :] + [m]
        self.record({"mark": {"id": m.id, "source": source}}, t)
        self.flush()
        self._save_marks()
        self._changed()
        return m

    def forget_mark(self, mark_id: str) -> None:
        before = len(self.marks)
        self.marks = [m for m in self.marks if m.id != mark_id]
        if len(self.marks) != before:
            self._save_marks()
            self._changed()
            self.prune()

    def _changed(self) -> None:
        if self.on_marks is not None:
            try:
                self.on_marks(list(self.marks))
            except Exception:
                log.exception("Marks listener failed")

    def _marks_file(self) -> Path:
        return self.folder / "marks.json"

    def _load_marks(self) -> list[Mark]:
        try:
            raw = json.loads(self._marks_file().read_text(encoding="utf-8"))
            return [Mark(**{k: m[k] for k in ("id", "t", "source", "until")}) for m in raw]
        except (OSError, ValueError, TypeError, KeyError):
            return []

    def _save_marks(self) -> None:
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            self._marks_file().write_text(
                json.dumps([asdict(m) for m in self.marks]), encoding="utf-8"
            )
        except OSError:
            log.warning("Problem reports: can't save marks", exc_info=True)

    # -- reading

    def read(self, start: int, end: int, *, frames: bool = True, flush: bool = True) -> list[dict]:
        """Every record from ``start`` to ``end`` (ms), oldest first. ``frames=False`` skips
        the telemetry frames, which is quick (the activity list for picking a moment).
        From another thread, flush on the loop first and pass ``flush=False``."""
        if flush:
            self.flush()
        out: list[dict] = []
        for path in self._segments():
            seg = _segment_start(path)
            if seg is None or seg + SEGMENT_MS < start or seg > end:
                continue
            for line in read_segment(path):
                if not frames and b'"frame":' in line[:40]:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue  # the cut-off last line of a file being written at a crash
                t = rec.get("t") if isinstance(rec, dict) else None
                if isinstance(t, int) and start <= t <= end:
                    out.append(rec)
        out.sort(key=lambda r: r["t"])
        return out

    def oldest(self) -> int | None:
        """When the oldest kept record starts (ms), roughly: its file's minute."""
        segments = self._segments()
        return _segment_start(segments[0]) if segments else None
