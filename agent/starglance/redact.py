"""Clean a problem report before it's saved (docs/REPORTS.md, "Cleaning").

Every text in a report goes through one ``Redactor``: Game.log lines, the app's log, the
agent's events and the recorded log lines. It removes what identifies the player or
their org and keeps what a diagnosis needs, consistently, so a name replaced in an event
is replaced the same way in the log line it came from:

- your handle -> ``<you>``; other players' handles, found in the lines the agent
  recognises (deaths, ships destroyed, ship channels, calibration) -> ``player-1``...
- account and session IDs, IP addresses, anything shaped like an email address
- hub addresses -> ``<hub-1>``..., fleet names -> ``<fleet-1>``..., other web
  addresses keep their path but lose their host (github.com and RSI's site stay)
- the PC's name -> ``<pc>``, the Windows user name in paths -> ``<user>``

aUEC balances are removed from frames separately (scrub.py), as in captures. Names in
lines the agent doesn't recognise can't be found, which is why the report is previewed.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from .gamelog import parse_line, who

KEPT_HOSTS = ("github.com", "robertsspaceindustries.com")

_IDS = re.compile(
    r"""(?ix)
    (?P<key>\b(?:player)?geid|\bplayerid|\b(?:login)?sessionid|\baccountid|\bnickname)
    (?P<sep>\s*[=:\[]\s*"?)
    (?P<value>[^\s"\],]+)
    """
)
_IP = re.compile(
    r"(?<![\w.-])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\w.])"
)
_VERSION_BEFORE = re.compile(r"Version:\s*$")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL = re.compile(r"\b(https?|wss?)://([^/\s'\"<>]+)")
_USER_PATH = re.compile(r"([A-Za-z]:[\\/]+Users[\\/]+)([^\\/\s'\"]+)", re.IGNORECASE)


def players_in(lines: Iterable[str], handle: str | None = None) -> list[str]:
    """Other players' handles in these Game.log lines, in order of appearance."""
    found: list[str] = []

    def add(name: str | None) -> None:
        name = (name or "").strip()
        if name and who(name) == name and name != handle and name not in found:
            found.append(name)

    for line in lines:
        ev = parse_line(line)
        if ev is None:
            continue
        d = ev.data
        if ev.kind == "actor_death":
            add(d.get("victim"))
            add(d.get("killer"))
        elif ev.kind == "vehicle_destroyed":
            add(d.get("killer"))
        elif ev.kind in ("channel_join", "channel_left"):
            add(d.get("owner"))
        elif ev.kind == "qt_calibration":
            add(d.get("by"))
    return found


class Redactor:
    def __init__(
        self,
        *,
        handle: str | None = None,
        you: Iterable[str] = (),
        players: Iterable[str] = (),
        hubs: Iterable[str] = (),
        fleets: Iterable[str] = (),
        pc: str | None = None,
    ) -> None:
        self.names: dict[str, str] = {}
        for name in [handle, *you]:
            if name and len(name) >= 2:
                self.names.setdefault(name, "<you>")
        n = 0
        for name in players:
            if name and len(name) >= 2 and name not in self.names:
                n += 1
                self.names[name] = f"player-{n}"
        if pc and len(pc) >= 2:
            self.names.setdefault(pc, "<pc>")
        self._names = self._alternation(self.names)
        self.hubs = {h.rstrip("/"): f"<hub-{i}>" for i, h in enumerate(dict.fromkeys(hubs), 1) if h}
        self.fleets = {
            f: f"<fleet-{i}>" for i, f in enumerate(dict.fromkeys(fleets), 1) if f and len(f) >= 2
        }
        self._fleets = self._alternation(self.fleets)

    @staticmethod
    def _alternation(names: dict[str, str]) -> re.Pattern | None:
        if not names:
            return None
        ordered = sorted(names, key=len, reverse=True)  # "Bob_2" before "Bob"
        return re.compile(r"(?<![\w-])(" + "|".join(map(re.escape, ordered)) + r")(?![\w-])")

    @property
    def players(self) -> int:
        return sum(1 for v in self.names.values() if v.startswith("player-"))

    def text(self, s: str) -> str:
        for hub, alias in self.hubs.items():
            s = s.replace(hub, alias)
        s = _URL.sub(self._url, s)
        s = _IDS.sub(lambda m: f"{m.group('key')}{m.group('sep')}<id>", s)
        s = _IP.sub(self._ip, s)
        s = _EMAIL.sub("<email>", s)
        s = _USER_PATH.sub(r"\1<user>", s)
        if self._names is not None:
            s = self._names.sub(lambda m: self.names[m.group(1)], s)
        if self._fleets is not None:
            s = self._fleets.sub(lambda m: self.fleets[m.group(1)], s)
        return s

    @staticmethod
    def _url(m: re.Match) -> str:
        host = m.group(2).lower()
        if any(host == h or host.endswith("." + h) for h in KEPT_HOSTS):
            return m.group(0)
        return f"{m.group(1)}://<host>"

    @staticmethod
    def _ip(m: re.Match) -> str:
        if _VERSION_BEFORE.search(m.string, 0, m.start()):
            return m.group(0)  # "FileVersion: 4.10.201.48" is a version, not an address
        return "<ip>"

    def obj(self, value: Any) -> Any:
        """A copy of a JSON value with every string cleaned (keys are left alone)."""
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, dict):
            return {k: self.obj(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.obj(v) for v in value]
        return value
