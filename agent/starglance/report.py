"""Problem reports: the moment a player picks, as one cleaned zip (docs/REPORTS.md).

``Reports`` is what the page's Report a problem dialog, the tray and the hotkey use: the
buffer's settings and marks, the activity list to pick a moment from, and making a
report. A report is built in two steps: ``preview`` writes a draft to the agent's own
folder and returns its contents to read; ``save`` moves it to Downloads, shows it in
Explorer and gives the pre-filled GitHub issue address. Nothing is sent anywhere.
"""

from __future__ import annotations

import asyncio
import contextlib
import gzip
import io
import json
import logging
import platform
import shutil
import socket
import sys
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

from . import __version__, hotkey, paths
from .recent import (
    KEEP_MS,
    MARK_AFTER_MS,
    MARK_BEFORE_MS,
    RecentBuffer,
    load_settings,
    save_settings,
)
from .redact import Redactor, players_in

log = logging.getLogger(__name__)

FORMAT = 1
BEFORE_MIN = (1, 2, 3, 5, 8)
AFTER_MIN = (1, 2)
ISSUE_URL = "https://github.com/bradqui/starglance/issues/new"
PARTS = (
    "The app or cockpit view (on my PC)",
    "The fleet (cards, roster, fleet header)",
    "Another device (Show on other devices)",
    "The hub (running it, signing in, invites)",
    "Updating",
    "Something else",
)
"""The issue form's "Where" choices (.github/ISSUE_TEMPLATE/bug_report.yml)."""
PREVIEW_CHARS = 400_000
TIMELINE_MAX = 400


def utc_stamp(ms: int) -> str:
    """Game.log's timestamp form, ``2026-11-24T18:16:27.354Z``, which sorts as text."""
    return datetime.fromtimestamp(ms / 1000, UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# ---------------------------------------------------------------- Game.log and the app's log


def gamelog_files(game_log: Path, start_ms: int) -> list[Path]:
    """The current Game.log and any older ones (logbackups) written to since ``start_ms``."""
    files: list[tuple[float, Path]] = []
    backups = game_log.parent / "logbackups"
    if backups.is_dir():
        for p in backups.glob("*.log"):
            with contextlib.suppress(OSError):
                mtime = p.stat().st_mtime
                if mtime * 1000 >= start_ms:
                    files.append((mtime, p))
    out = [p for _, p in sorted(files)]
    if game_log.exists():
        out.append(game_log)
    return out


def gamelog_window(files: list[Path], start_ms: int, end_ms: int) -> list[str]:
    """Every Game.log line stamped from ``start_ms`` to ``end_ms``, with the unstamped lines
    that continue them."""
    lo, hi = utc_stamp(start_ms), utc_stamp(end_ms)
    out: list[str] = []
    for path in files:
        inside = False
        with contextlib.suppress(OSError), path.open(encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                line = raw.rstrip("\r\n")
                if len(line) > 25 and line[0] == "<" and line[25] == ">" and line[1:3] == "20":
                    stamp = line[1:25]
                    if stamp > hi:
                        break
                    inside = stamp >= lo
                if inside:
                    out.append(line)
    return out


def game_version(files: list[Path]) -> dict:
    """The game's version and build, from the header of the newest log in the window."""
    for path in reversed(files):
        info: dict = {}
        with contextlib.suppress(OSError), path.open(encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i > 80:
                    break
                if "ProductVersion:" in line:
                    info["version"] = line.split("ProductVersion:", 1)[1].strip()
                elif "Build(" in line and "build" not in info:
                    info["build"] = line.split("Build(", 1)[1].split(")", 1)[0]
        if info:
            return info
    return {}


def agent_log_window(start_ms: int, end_ms: int) -> list[str]:
    """The app's own log (starglance.log and its older parts) from ``start_ms`` to ``end_ms``."""
    folder = paths.logs_dir()
    files = []
    for p in folder.glob("starglance.log*"):
        with contextlib.suppress(OSError):
            if p.stat().st_mtime * 1000 >= start_ms:
                files.append((p.stat().st_mtime, p))
    out: list[str] = []
    for _, path in sorted(files):
        inside = False
        with contextlib.suppress(OSError), path.open(encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                line = raw.rstrip("\r\n")
                try:
                    t = datetime.strptime(line[:23], "%Y-%m-%d %H:%M:%S,%f").timestamp() * 1000
                    inside = start_ms <= t <= end_ms
                except ValueError:
                    pass  # a traceback's next line: goes with the line above
                if inside:
                    out.append(line)
    return out


# ---------------------------------------------------------------- the report


@dataclass
class Draft:
    id: str
    path: Path
    name: str
    issue: dict


def downloads_dir() -> Path:
    d = Path.home() / "Downloads"
    if d.is_dir():
        return d
    d = paths.data_dir() / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def issue_url(*, what: str, expected: str, part: str, version: str, game: str, name: str) -> str:
    body = what.strip()
    if expected.strip():
        body += f"\n\nExpected: {expected.strip()}"
    params = {
        "template": "bug_report.yml",
        "title": what.strip().splitlines()[0][:80] if what.strip() else "Problem report",
        "what": body[:1500],
        "version": version,
        "part": part,
        "game": game,
        "logs": f"Report: {name} (drop the file here)",
    }
    return f"{ISSUE_URL}?{urlencode(params)}"


class Reports:
    """The buffer, marks, hotkey and report making, for one running agent."""

    def __init__(
        self,
        pipeline,
        *,
        install=None,
        notify: Callable[[dict], None] | None = None,
        buffer: RecentBuffer | None = None,
        live: bool = True,
    ) -> None:
        settings = load_settings()
        self.pipeline = pipeline
        self.install = install
        self.live = live
        """False when replaying: nothing is recorded (it isn't real play)."""
        self.buffer = buffer or RecentBuffer(keep=settings["keep"] and live)
        self.buffer.on_marks = lambda _m: self._notify()
        self.notify = notify
        self.hotkey = hotkey.Hotkey(self._hotkey_pressed)
        self.loop: asyncio.AbstractEventLoop | None = None
        self._draft: Draft | None = None
        if live:
            pipeline.recorder = self.buffer
        if live and settings["hotkey"]:
            self.hotkey.set(settings["hotkey"])

    # -- status, for the page

    def status(self) -> dict:
        return {
            "available": self.live,
            "keep": self.buffer.keep,
            "keep_minutes": KEEP_MS // 60_000,
            "hotkey": self.hotkey.key or load_settings()["hotkey"],
            "hotkey_on": self.hotkey.key is not None,
            "hotkey_error": self.hotkey.error,
            "hotkeys": [{"id": k, "label": v[0]} for k, v in hotkey.PRESETS.items()],
            "marks": [{"id": m.id, "t": m.t, "source": m.source} for m in self.buffer.marks],
        }

    @staticmethod
    def for_device(status: dict) -> dict:
        """What a paired device (Show on other devices) sees: whether it can mark, and the
        marks, so its top bar shows them. Reports themselves are made on this PC."""
        return {k: status[k] for k in ("available", "keep", "keep_minutes", "marks")} | {
            "remote": True
        }

    def _notify(self) -> None:
        if self.notify is not None:
            self.notify(self.status())

    def stop(self) -> None:
        self.hotkey.stop()
        self.buffer.close()

    # -- settings

    def set_keep(self, on: bool) -> dict:
        save_settings(keep=on)
        self.buffer.set_keep(on and self.live)
        self._notify()
        return self.status()

    def set_hotkey(self, key: str | None) -> dict:
        key = key if key in hotkey.PRESETS else None
        save_settings(hotkey=key)
        if self.live:
            self.hotkey.set(key)
        self._notify()
        return self.status()

    # -- marks

    def mark(self, source: str = "app") -> dict:
        m = self.buffer.mark(source)
        if m is None:
            raise ValueError("Keeping the last 30 minutes is off (Settings -> Agent).")
        return {"id": m.id, "t": m.t, **self.status()}

    def _hotkey_pressed(self) -> None:
        loop = self.loop
        if loop is not None and not loop.is_closed():
            loop.call_soon_threadsafe(lambda: self.mark("hotkey"))
            hotkey.chime()

    def forget_mark(self, mark_id: str) -> dict:
        self.buffer.forget_mark(mark_id)
        return self.status()

    # -- picking a moment

    async def timeline_async(self) -> dict:
        self.buffer.flush()
        return await asyncio.to_thread(self.timeline)

    def timeline(self) -> dict:
        """The events of the last 30 minutes and around each mark, newest first. Reads the
        files without flushing: call on the loop after a flush, or via timeline_async."""
        now = self.buffer.clock()
        spans = [(now - KEEP_MS, now)] + [
            (m.t - MARK_BEFORE_MS, m.t + MARK_AFTER_MS) for m in self.buffer.marks
        ]
        seen: set[tuple] = set()
        events = []
        for start, end in spans:
            for rec in self.buffer.read(start, end, frames=False, flush=False):
                ev = rec.get("event")
                if isinstance(ev, dict) and ev.get("kind") not in ("game_start", "game_exit"):
                    key = (rec["t"], ev.get("kind"), json.dumps(ev.get("data"), sort_keys=True))
                    if key not in seen:
                        seen.add(key)
                        events.append(
                            {"t": rec["t"], "kind": ev.get("kind"), "data": ev.get("data") or {}}
                        )
        events.sort(key=lambda e: e["t"], reverse=True)
        return {
            "now": now,
            "oldest": self.buffer.oldest(),
            "events": events[:TIMELINE_MAX],
            "before": list(BEFORE_MIN),
            "after": list(AFTER_MIN),
            "parts": list(PARTS),
            "fleets": self._fleets(),
            **self.status(),
        }

    # -- making it

    async def preview(self, body: dict) -> dict:
        if not self.live:
            raise ValueError("Reports are made from live play, not a replay.")
        at = int(body.get("t") or self.buffer.clock())
        before = int(body.get("before") or 3)
        after = int(body.get("after") or 1)
        if before not in BEFORE_MIN or after not in AFTER_MIN:
            raise ValueError("Pick a window from the list.")
        what = str(body.get("what") or "").strip()
        if not what:
            raise ValueError("Say what happened.")
        fields = {
            "at": at,
            "start": at - before * 60_000,
            "end": at + after * 60_000,
            "focus": body.get("focus") if isinstance(body.get("focus"), dict) else None,
            "mark": str(body["mark"]) if body.get("mark") else None,
            "what": what[:4000],
            "expected": str(body.get("expected") or "").strip()[:4000],
            "part": body.get("part") if body.get("part") in PARTS else PARTS[0],
        }
        self.buffer.flush()
        context = self._context()
        draft, contents = await asyncio.to_thread(self._build, fields, context)
        self._draft = draft
        return {"id": draft.id, "name": draft.name, **contents}

    def _the_draft(self, draft_id: str) -> Draft:
        d = self._draft
        if d is None or d.id != draft_id or not d.path.exists():
            raise ValueError("That report is gone; make it again.")
        return d

    def _reported(self, d: Draft) -> None:
        """Sent or saved: its mark needn't keep those minutes any longer."""
        mark = d.issue.pop("mark", None)
        if mark:
            self.buffer.forget_mark(mark)

    def save(self, draft_id: str) -> dict:
        """For a GitHub issue: a copy in Downloads (the draft stays, to send it too)."""
        d = self._the_draft(draft_id)
        dest = downloads_dir() / d.name
        shutil.copyfile(d.path, dest)
        self._reported(d)
        show_in_folder(dest)
        issue = {k: v for k, v in d.issue.items() if k != "mark"}
        return {
            "path": str(dest),
            "folder": str(dest.parent),
            "issue_url": issue_url(name=d.name, **issue),
        }

    async def send(self, draft_id: str, hub: str) -> dict:
        """To a fleet's admins: uploaded to its hub with this PC's key (docs/REPORTS.md)."""
        import aiohttp

        from .fleetlink import load_settings as fleet_settings
        from .fleetlink import load_token

        d = self._the_draft(draft_id)
        fleet = fleet_settings().get(hub)
        token = load_token(fleet.hub_url) if fleet else None
        if fleet is None or not token:
            raise ValueError("This PC isn't linked to that fleet.")
        data = await asyncio.to_thread(d.path.read_bytes)
        try:
            async with (
                aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=60),
                    headers={"Authorization": f"Bearer {token}"},
                ) as http,
                http.post(
                    f"{fleet.hub_url}/api/agent/report",
                    data=data,
                    headers={"Content-Type": "application/zip"},
                ) as resp,
            ):
                try:
                    body = await resp.json(content_type=None)
                except ValueError:
                    body = {}
                status = resp.status
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise ValueError(f"Can't reach {fleet.label}'s hub: {exc}") from exc
        body = body if isinstance(body, dict) else {}
        if status in (404, 405):
            raise ValueError(
                f"{fleet.label}'s hub is too old to take reports. Ask its admin to update it, "
                "or save the report for a GitHub issue."
            )
        if status != 200:
            raise ValueError(body.get("error") or f"{fleet.label}'s hub refused it ({status}).")
        self._reported(d)
        return {"ok": True, "hub": fleet.hub_url, "label": fleet.label}

    def discard(self) -> dict:
        if self._draft is not None:
            with contextlib.suppress(OSError):
                self._draft.path.unlink()
            self._draft = None
        return {"ok": True}

    @staticmethod
    def _fleets() -> list[dict]:
        """The fleets a report can go to: linked ones, with their key on this PC."""
        from .fleetlink import load_settings as fleet_settings
        from .fleetlink import load_token

        return [
            {"hub": f.hub_url, "label": f.label}
            for f in fleet_settings().fleets
            if _safe(lambda f=f: load_token(f.hub_url))
        ]

    def _context(self) -> dict:
        """What the build needs from the running agent (read on the loop thread)."""
        from .fleetlink import game_handle
        from .fleetlink import load_settings as fleet_settings
        from .lanview import load_settings as lan_settings
        from .selfupdate import load_auto, load_check

        fleets = fleet_settings().fleets
        game_log = self.install.game_log if self.install else None
        return {
            "handle": getattr(getattr(self.pipeline, "_log", None), "handle", None)
            or game_handle(game_log),
            "game_log": game_log,
            "channel": self.install.channel if self.install else None,
            "schema": getattr(self.pipeline, "schema_bytes", None),
            "schema_source": getattr(self.pipeline, "schema_source", None),
            "hubs": [f.hub_url for f in fleets],
            "fleet_names": [n for f in fleets for n in (f.org, f.label) if n],
            "you": [f.member_name for f in fleets if f.member_name],
            "settings": {
                "fleets": [
                    {
                        "fleet": i,
                        "enabled": f.enabled,
                        "sharing": [c for c, on in f.share.items() if on],
                    }
                    for i, f in enumerate(fleets, 1)
                ],
                "other_devices": _safe(lambda: lan_settings().enabled),
                "auto_update": _safe(load_auto),
                "check_updates": _safe(load_check),
                "hotkey": self.hotkey.key,
            },
        }

    def _build(self, f: dict, ctx: dict) -> tuple[Draft, dict]:
        start, end = f["start"], f["end"]
        records = self.buffer.read(start, end, flush=False)  # flushed before, on the loop
        log_files = gamelog_files(ctx["game_log"], start) if ctx["game_log"] else []
        game_lines = gamelog_window(log_files, start, end)
        recorded = [r["log"] for r in records if isinstance(r.get("log"), str)]
        red = Redactor(
            handle=ctx["handle"],
            you=ctx["you"],
            players=players_in([*recorded, *game_lines], ctx["handle"]),
            hubs=ctx["hubs"],
            fleets=ctx["fleet_names"],
            pc=socket.gethostname(),
        )
        capture = io.BytesIO()
        events: list[str] = []
        frames = 0
        with gzip.GzipFile(fileobj=capture, mode="wb", compresslevel=6) as gz:
            for rec in records:
                if "frame" in rec:
                    frames += 1
                    clean = rec  # aUEC already removed when recorded; no names in frames
                else:
                    clean = red.obj(rec)
                    if "event" in clean:
                        events.append(json.dumps({"t": clean["t"], **clean["event"]}))
                gz.write(json.dumps(clean, separators=(",", ":")).encode("utf-8") + b"\n")
        game_text = "\n".join(red.text(x) for x in game_lines)
        agent_text = "\n".join(red.text(x) for x in agent_log_window(start, end))
        version = game_version(log_files)
        game = " ".join(x for x in (ctx["channel"], version.get("version")) if x)
        report = {
            "format": FORMAT,
            "made": utc_stamp(int(datetime.now(UTC).timestamp() * 1000)),
            "agent": {
                "version": __version__,
                "app": bool(getattr(sys, "frozen", False)),
                "windows": platform.platform(),
            },
            "game": {"channel": ctx["channel"], **version},
            "window": {
                "start": start,
                "end": end,
                "at": f["at"],
                "start_utc": utc_stamp(start),
                "end_utc": utc_stamp(end),
            },
            "focus": red.obj(f["focus"]) if f["focus"] else None,
            "marks": [
                m["mark"] | {"t": m["t"]} for m in records if isinstance(m.get("mark"), dict)
            ],
            "what": red.text(f["what"]),
            "expected": red.text(f["expected"]),
            "part": f["part"],
            "settings": ctx["settings"],
            "schema": ctx["schema_source"],
            "counts": {
                "frames": frames,
                "events": len(events),
                "log_lines_recognised": len(recorded),
                "gamelog_lines": len(game_lines),
                "agent_log_lines": agent_text.count("\n") + 1 if agent_text else 0,
                "players_renamed": red.players,
            },
        }
        made = datetime.now()
        name = f"Starglance-report-{made:%Y-%m-%d-%H%M%S}.zip"
        drafts = paths.data_dir() / "reports"
        drafts.mkdir(parents=True, exist_ok=True)
        for old in drafts.glob("draft-*.zip"):
            with contextlib.suppress(OSError):
                old.unlink()
        draft_id = f"{made:%Y%m%d%H%M%S%f}"
        path = drafts / f"draft-{draft_id}.zip"
        texts = {
            "report.json": json.dumps(report, indent=2, ensure_ascii=False),
            "events.jsonl": "\n".join(events),
            "gamelog.txt": game_text,
            "agent.log": agent_text,
        }
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for fname, text in texts.items():
                z.writestr(fname, text)
            z.writestr("capture.jsonl.gz", capture.getvalue(), compress_type=zipfile.ZIP_STORED)
            if ctx["schema"]:
                z.writestr("telemetry.protoset", ctx["schema"])
        with zipfile.ZipFile(path) as z:
            files = [{"name": i.filename, "size": i.file_size} for i in z.infolist()]
        draft = Draft(
            draft_id,
            path,
            name,
            {
                "what": report["what"],
                "expected": report["expected"],
                "part": f["part"],
                "version": __version__,
                "game": game,
                "mark": f["mark"],
            },
        )
        contents = {
            "size": path.stat().st_size,
            "files": files,
            "texts": {
                k: (
                    v
                    if len(v) <= PREVIEW_CHARS
                    else v[:PREVIEW_CHARS] + "\n… (cut here in the preview; the file has it all)"
                )
                for k, v in texts.items()
            },
            "counts": report["counts"],
        }
        return draft, contents


def _safe(fn):
    try:
        return fn()
    except Exception:  # noqa: BLE001 (a settings file that can't be read: leave it out)
        return None


def show_in_folder(path: Path) -> None:
    if sys.platform != "win32":
        return
    import subprocess

    with contextlib.suppress(OSError):
        subprocess.Popen(["explorer", "/select,", str(path)])  # noqa: S603, S607
