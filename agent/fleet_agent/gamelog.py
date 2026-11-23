"""Follow the game's Game.log for things the telemetry stream doesn't carry.

Game.log is the game's own debug log, written fresh on every launch. It isn't an
API: CIG can reword any line in any patch, so every parser here is optional and
an unrecognised line is simply ignored.

What we take from it today (docs/FIELDS.md, "Game.log"):

- quantum route plotted, with its destination
- quantum route arrived ("Arrived at Final Destination")
- quantum travel blocked ("destination is obstructed")

Only lines a parser recognises are ever kept (captures included), and those
carry no player names.
"""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fleet_shared import Event, Route

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- parsing


@dataclass(frozen=True)
class LogEvent:
    kind: str
    """"route" | "arrived" | "blocked"."""
    destination: str | None = None


_ROUTE = re.compile(
    r"<Player Selected Quantum Target[^>]*>.*?Player has selected point (\S+) as their destination"
)
_ARRIVED = re.compile(r"<Quantum Drive Arrived - Arrived at Final Destination>")
_BLOCKED = re.compile(r'Notification "Quantum Travel: Your destination is obstructed')
_INTERESTING = ("Quantum Target", "Quantum Drive Arrived", "Quantum Travel:")


def parse_line(line: str) -> LogEvent | None:
    if not any(k in line for k in _INTERESTING):
        return None  # fast path: almost every line
    if m := _ROUTE.search(line):
        return LogEvent("route", destination_name(m.group(1)))
    if _ARRIVED.search(line):
        return LogEvent("arrived")
    if _BLOCKED.search(line):
        return LogEvent("blocked")
    return None


_PREFIXES = ("OOC_", "ObjectContainer_", "MISSION_QT_", "Mission_QT_")
_BODY_CODE = re.compile(r"^[A-Za-z]+_\d+[a-z]?_")  # Stanton_1b_ (system + planet code)


def destination_name(raw: str) -> str:
    """Internal point names to something readable.

    OOC_Stanton_1b_Aberdeen -> Aberdeen; ObjectContainer_Lorville_City -> Lorville City;
    MISSION_QT_Bounty_Beacon_927914670160 -> Bounty Beacon.
    """
    name = re.sub(r"_\d{6,}$", "", raw)
    for prefix in _PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix) :]
            break
    name = _BODY_CODE.sub("", name)
    name = name.replace("_", " ").strip()
    return name or raw


# ---------------------------------------------------------------- route state

ARRIVED_SHOWN_MS = 120_000
"""How long "arrived at X" stays up."""


class RouteTracker:
    """Quantum route state from log events plus the telemetry's quantum flag."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.destination: str | None = None
        self.state: str | None = None  # plotted | en_route | arrived | blocked
        self.since = 0

    def on_log(self, ev: LogEvent, t: int) -> list[Event]:
        if ev.kind == "route":
            self.destination, self.state, self.since = ev.destination, "plotted", t
            return [Event(t=t, kind="quantum_route", data={"destination": ev.destination})]
        if ev.kind == "arrived":
            dest = self.destination
            self.state, self.since = "arrived", t
            return [Event(t=t, kind="quantum_arrived", data={"destination": dest})]
        if ev.kind == "blocked":
            self.state, self.since = "blocked", t
            return [Event(t=t, kind="quantum_blocked", data={"destination": self.destination})]
        return []

    def route(self, t: int, quantum: bool | None) -> Route | None:
        if self.state is None:
            return None
        if quantum and self.state in ("plotted", "blocked"):
            self.state, self.since = "en_route", t
        if self.state == "arrived" and t - self.since > ARRIVED_SHOWN_MS:
            self.reset()
            return None
        return Route(destination=self.destination, state=self.state, since=self.since)  # type: ignore[arg-type]


# ---------------------------------------------------------------- following the file


class GameLogTail:
    """Follows Game.log in a thread and hands recognised lines to ``on_line``.

    On start it reads the existing file quietly (``on_line(line, quiet=True)``) so a
    route plotted before the agent started is known. A new game launch replaces
    the file: when it shrinks, we start again from the top.
    """

    POLL_S = 0.5

    def __init__(self, path: Path, on_line: Callable[[str, bool], None]) -> None:
        self.path = path
        self.on_line = on_line
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="game-log", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=3)

    def _run(self) -> None:
        pos = 0
        quiet = True  # the first read is history
        buf = b""
        while not self._stop.is_set():
            try:
                size = self.path.stat().st_size
                if size < pos:  # the game restarted and began a new log
                    pos, buf = 0, b""
                    quiet = False
                if size > pos:
                    with open(self.path, "rb") as fh:
                        fh.seek(pos)
                        chunk = fh.read(size - pos)
                    pos += len(chunk)
                    *lines, buf = (buf + chunk).split(b"\n")
                    for raw in lines:
                        line = raw.decode("utf-8", errors="replace")
                        if parse_line(line):
                            self.on_line(line, quiet)
                quiet = False
            except FileNotFoundError:
                pos, buf = 0, b""
                quiet = False  # whatever appears next is a new session
            except OSError as exc:
                log.debug("Game.log not readable yet: %s", exc)
            self._stop.wait(self.POLL_S)
