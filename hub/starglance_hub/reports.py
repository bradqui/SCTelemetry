"""Problem reports members send to their fleet's admins (docs/REPORTS.md, "On the hub").

The agent uploads the zip it built and cleaned; the hub checks that it is one (a zip
with ``report.json`` and only the files a report has, not too big unpacked), stores it,
and reads its summary for the admins' list. Nothing in it is ever run or rendered as a
page: admins read the text files as text and download the zip.
"""

from __future__ import annotations

import io
import json
import zipfile

MAX_BYTES = 4 * 1024 * 1024
"""The zip as uploaded (a 10-minute report is well under 1 MB)."""
MAX_UNPACKED = 64 * 1024 * 1024
PER_DAY = 10
"""Reports one member may send in a day."""
TEXT_FILES = ("report.json", "events.jsonl", "gamelog.txt", "agent.log")
FILES = {*TEXT_FILES, "capture.jsonl.gz", "telemetry.protoset"}
PREVIEW_CHARS = 400_000
STATUSES = ("new", "forwarded", "not_a_bug")


class BadReport(ValueError):
    pass


def check(data: bytes) -> dict:
    """The summary of a valid report (from its report.json), or BadReport."""
    if len(data) > MAX_BYTES:
        raise BadReport("The report is too big.")
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        infos = z.infolist()
    except (zipfile.BadZipFile, ValueError, OSError):
        raise BadReport("That isn't a Starglance report.") from None
    names = {i.filename for i in infos}
    if "report.json" not in names or not names <= FILES or len(infos) != len(names):
        raise BadReport("That isn't a Starglance report.")
    if sum(i.file_size for i in infos) > MAX_UNPACKED:
        raise BadReport("The report is too big.")
    try:
        report = json.loads(z.read("report.json").decode("utf-8"))
        for name in names:
            z.read(name)  # every file opens and its checksum matches
    except (ValueError, UnicodeDecodeError, zipfile.BadZipFile, OSError):
        raise BadReport("The report is damaged.") from None
    if not isinstance(report, dict) or not isinstance(report.get("format"), int):
        raise BadReport("That isn't a Starglance report.")
    return summary(report)


def _text(value: object, limit: int) -> str | None:
    return str(value)[:limit] if isinstance(value, str | int | float) and value != "" else None


def summary(report: dict) -> dict:
    """What the admins' list shows, from report.json (all of it as text, length-limited)."""
    agent = report.get("agent") if isinstance(report.get("agent"), dict) else {}
    game = report.get("game") if isinstance(report.get("game"), dict) else {}
    window = report.get("window") if isinstance(report.get("window"), dict) else {}
    return {
        "what": _text(report.get("what"), 4000) or "",
        "expected": _text(report.get("expected"), 4000) or "",
        "part": _text(report.get("part"), 100),
        "agent_version": _text(agent.get("version"), 20),
        "windows": _text(agent.get("windows"), 80),
        "game": " ".join(
            x for x in (_text(game.get("channel"), 12), _text(game.get("version"), 40)) if x
        )
        or None,
        "start": window.get("start") if isinstance(window.get("start"), int) else None,
        "end": window.get("end") if isinstance(window.get("end"), int) else None,
        "format": report.get("format"),
    }


def texts(data: bytes) -> dict[str, str]:
    """The report's text files, for reading on the page (cut short if huge)."""
    out: dict[str, str] = {}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = set(z.namelist())
        for name in TEXT_FILES:
            if name in names:
                text = z.read(name).decode("utf-8", errors="replace")
                if len(text) > PREVIEW_CHARS:
                    text = text[:PREVIEW_CHARS] + "\n… (cut here; the download has it all)"
                out[name] = text
    return out
