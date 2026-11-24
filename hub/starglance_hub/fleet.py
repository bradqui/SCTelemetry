"""Live fleet state (memory only) and the fan-out to viewers (spec §4, §6.2).

Agents send a full snapshot, then deltas (``starglance_shared.patch``) at up to
10 Hz. The hub keeps each member's latest state and tells viewers:

- the **roster**: a summary of every member (presence, ship, mode, location,
  warnings...), as patches at most every 100 ms;
- the **member** a viewer has open: their full state, as patches at most
  every 100 ms;
- **events** from anyone, immediately.

Each viewer diffs against what it last sent, so a slow viewer just skips
states (latest wins) and never holds anyone else up.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections import deque
from collections.abc import Callable
from typing import Any

from aiohttp import web
from pydantic import ValidationError
from starglance_shared import (
    FLEET_ALARM_HOLD_MS,
    FLEET_ALARM_OFF_MS,
    RELEASES_URL,
    SCHEMA_VERSION,
    SHARE_CATEGORIES,
    Event,
    Hello,
    Snapshot,
    alert_lights,
    apply_patch,
    event_shared,
    expected_light,
    fleet_alarm_lights,
    make_patch,
    version_tuple,
)

from .config import Config
from .db import Database, Member, now_ms

log = logging.getLogger(__name__)

TICK_S = 0.1
ROSTER_EVERY = 1  # ticks: 100 ms, as fast as agents send (Cards and Wingmates show speeds)
RECENT_EVENTS = 200
VIEWER_QUEUE = 200

SHARE_KEYS = {
    "status": "status",
    "ship": "ship",
    "weapons": "weapons",
    "vitals": "vitals",
    "uec": "uec",
    "location": "location",
    "mission": "missions",
    "combat": "session",
}
"""Share category -> the snapshot key it covers."""


class ProtocolError(Exception):
    """A message an agent shouldn't send. ``fatal``: close the connection."""

    def __init__(self, message: str, *, code: str = "bad_message", fatal: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.fatal = fatal


# ---------------------------------------------------------------- per member


def too_old(agent_version: str) -> None:
    """Refuse an agent older than MIN_AGENT_VERSION (development builds always pass)."""
    from . import MIN_AGENT_VERSION

    have, need = version_tuple(agent_version), version_tuple(MIN_AGENT_VERSION)
    if have is not None and need is not None and have < need:
        raise ProtocolError(
            f"Your agent ({agent_version}) is older than this hub supports "
            f"({MIN_AGENT_VERSION} or newer). Download the latest: {RELEASES_URL}",
            code="version",
            fatal=True,
        )


class MemberLive:
    def __init__(self, member: Member) -> None:
        self.info = member.public()
        self.snapshot: dict | None = None
        self.in_game = False
        self.last_seen: int | None = None
        self.share: set[str] = set(SHARE_CATEGORIES)
        self.agent_version: str | None = None
        self.channel: str | None = None
        self.alarms: dict[str, list] = {}
        """Fleet alarm lights: light -> [first on, last on, level], by snapshot time."""
        self.alerts: dict[str, list] = {}
        """Every lit light, held the same way (the pages pick which to show)."""
        self.sockets: dict[int, web.WebSocketResponse] = {}
        """Connected agents by agent id (a member may run more than one PC)."""

    @property
    def connected(self) -> bool:
        return bool(self.sockets)

    def presence(self, now: int, cfg: Config) -> str:
        """live | idle (agent on, not in game) | stale | offline."""
        if self.last_seen is None:
            return "offline"
        age = (now - self.last_seen) / 1000
        if not self.connected:
            return "stale" if age < cfg.stale_after_s else "offline"
        if age >= cfg.offline_after_s:
            return "offline"
        # Not in game, the agent only sends heartbeats: quiet is normal there.
        if age >= (cfg.stale_after_s if self.in_game else cfg.idle_stale_after_s):
            return "stale"
        return "live" if self.in_game else "idle"


def enforce_sharing(state: dict, share: set[str]) -> dict:
    """Blank whatever the member switched off: the agent already does; this is a backstop.

    Works on a whole snapshot or on a patch of one.
    """
    for category, key in SHARE_KEYS.items():
        if category not in share and state.get(key) is not None:
            state[key] = None
    session = state.get("session")
    if "uec" not in share and isinstance(session, dict) and session.get("earned"):
        state["session"] = {**session, "earned": 0}
    return state


# ---------------------------------------------------------------- roster summary


def _worst(lights: dict, master_mode: str | None = None) -> tuple[str | None, list[str]]:
    lit = {
        k: v for k, v in lights.items() if isinstance(v, str) and not expected_light(k, master_mode)
    }
    major = [k for k, v in lit.items() if v.startswith("major")]
    if major:
        return "major", major
    minor = [k for k, v in lit.items() if v.startswith("minor")]
    return ("minor", minor) if minor else (None, [])


def _hold(store: dict[str, list], now_on: dict[str, str], t: int) -> dict[str, str]:
    """Lights on for FLEET_ALARM_HOLD_MS before they count, kept until off for
    FLEET_ALARM_OFF_MS. Timed by the member's snapshots, not the hub's clock."""
    for light, lvl in now_on.items():
        seen = store.get(light)
        if seen is None or t - seen[1] > FLEET_ALARM_OFF_MS:
            store[light] = [t, t, lvl]
        else:
            seen[1], seen[2] = t, lvl
    for light in [k for k, v in store.items() if t - v[1] > FLEET_ALARM_OFF_MS]:
        del store[light]
    # Seen on across the hold (gaps shorter than the off time allowed), not merely seen
    # once and not yet cleared: a shield blip never counts.
    return {k: v[2] for k, v in store.items() if v[1] - v[0] >= FLEET_ALARM_HOLD_MS}


def _held_alerts(m: MemberLive, ship: dict, t: int) -> dict[str, str]:
    """``alert_lights``, held: light -> "major" | "minor"."""
    return _hold(m.alerts, alert_lights(ship.get("lights") or {}, ship.get("master_mode")), t)


def _fleet_alarm(m: MemberLive, ship: dict, t: int) -> tuple[str | None, list[str]]:
    """``fleet_alarm_lights``, held (``_hold``)."""
    held = _hold(m.alarms, fleet_alarm_lights(ship.get("lights") or {}), t)
    level = "major" if "major" in held.values() else ("minor" if held else None)
    return level, sorted(held)


SEVERITY = {"minor": 1, "moderate": 2, "severe": 3}


def _r(value: Any, digits: int = 0, *, step: float | None = None) -> float | int | None:
    """Rounded for the roster: small jitter shouldn't cost an update."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    if step:
        return round(value / step) * step
    return round(value, digits) if digits else round(value)


def summarize(m: MemberLive, now: int, cfg: Config) -> dict:
    """What the roster shows for one member: small, and only what changes slowly."""
    s = m.snapshot or {}
    status = s.get("status") or {}
    presence = m.presence(now, cfg)
    out: dict[str, Any] = {
        **m.info,
        "presence": presence,
        # Only when it matters: a live member's last_seen changes with every message.
        "last_seen": m.last_seen if presence in ("stale", "offline") else None,
        "channel": m.channel,
        "locomotion": status.get("locomotion"),
        "role": status.get("role"),
        "handle": status.get("handle"),
        "ship": None,
        "location": None,
        "vitals": None,
        "mission": None,
        "session": s.get("session"),
    }
    if presence == "offline":
        return out
    ship = s.get("ship")
    if ship:
        flight = ship.get("flight") or {}
        level, lit = _worst(ship.get("lights") or {}, ship.get("master_mode"))
        fleet_level, fleet_lit = _fleet_alarm(m, ship, s.get("t") or now)
        alerts = _held_alerts(m, ship, s.get("t") or now)
        speed = flight.get("speed")
        out["ship"] = {
            "id": ship.get("id"),
            "model": ship.get("model"),
            "manufacturer": ship.get("manufacturer"),
            "master_mode": ship.get("master_mode"),
            "powered": ship.get("powered"),
            "landed": ship.get("landed"),
            "gear": ship.get("gear"),
            "hull": ship.get("hull"),
            "shields": {
                "powered": (ship.get("shields") or {}).get("powered"),
                "level": (ship.get("shields") or {}).get("level"),
            },
            "quantum": flight.get("quantum"),
            "speed": _r(speed),
            # For flying together: where everyone is heading and how high. alt is None
            # in space; agl (height over the ground) only near a surface.
            "alt": _r(flight.get("alt"), step=10 if abs(flight.get("alt") or 0) >= 10_000 else 1),
            "agl": _r(flight.get("radar_alt")),
            "vsi": _r(flight.get("vsi")),
            "heading": _r(flight.get("heading")),
            "g": _r(flight.get("g"), 1),
            "h2_fuel": _r(flight.get("h2_fuel"), 2),
            "alarm": level,
            "lights": lit,
            # What the whole fleet should hear about (the header): getting hit, a radar
            # warning; held, see fleet_alarm_lights. Never "minor": no fleet-wide cautions.
            "fleet_alarm": fleet_level,
            "fleet_lights": fleet_lit,
            # Every lit light, held the same way: light -> "major" | "minor". Each page
            # chooses which go in its fleet header (its alert settings). fleet_alarm and
            # fleet_lights stay for pages from agents before 0.5.
            "alerts": alerts,
        }
    loc = s.get("location")
    if loc:
        route = loc.get("route")
        out["location"] = {
            k: loc.get(k)
            for k in (
                "armistice",
                "restricted",
                "private",
                "monitored",
                "comms",
                "jurisdiction",
                "system",
                "shard",
            )
        }
        out["location"]["route"] = (
            {"destination": route.get("destination"), "state": route.get("state")}
            if route
            else None
        )
        aboard = loc.get("aboard")
        # owner_id / ship_id: filled in across the roster by resolve_aboard.
        out["location"]["aboard"] = (
            {
                "ship": aboard.get("ship"),
                "owner": aboard.get("owner"),
                "since": aboard.get("since"),
                "owner_id": None,
                "ship_id": None,
            }
            if aboard
            else None
        )
    vit = s.get("vitals")
    if vit:
        severities = [i.get("severity", "") for i in vit.get("injuries") or []]
        worst = max(severities, key=lambda x: SEVERITY.get(x, 0)) if severities else None
        out["vitals"] = {
            "health": _r(vit.get("health"), 2),
            "oxygen": _r(vit.get("oxygen"), 2),
            "hunger": _r(vit.get("hunger"), 2),
            "thirst": _r(vit.get("thirst"), 2),
            "body_temp": _r(vit.get("body_temp"), 1),
            "heart_rate": _r(vit.get("heart_rate")),
            "injury": worst,
            "injuries": len(severities),
        }
    missions = s.get("missions") or []
    active = next((x for x in missions if x.get("state") == "active"), None)
    if active:
        out["mission"] = {"title": active.get("title"), "objective": active.get("objective")}
    return out


def resolve_aboard(roster: dict[str, dict]) -> None:
    """Who owns the ship each member is aboard: a ship channel names its owner by
    in-game handle, so match handles first, then display names (they default to the
    handle). When the owner is flying that model now, link their ship too."""
    by_name: dict[str, str] = {}
    for key in ("handle", "name"):
        for mid, row in roster.items():
            if isinstance(row.get(key), str) and row[key]:
                by_name.setdefault(row[key].lower(), mid)
    for row in roster.values():
        aboard = (row.get("location") or {}).get("aboard")
        if not aboard or not aboard.get("owner"):
            continue
        owner_id = by_name.get(aboard["owner"].lower())
        aboard["owner_id"] = owner_id
        ship = roster[owner_id].get("ship") if owner_id else None
        model = _words((ship or {}).get("model"))
        same = bool(model) and model <= _words(aboard.get("ship"))
        aboard["ship_id"] = ship.get("id") if ship and same else None


_ROMAN = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6"}


def _words(name: str | None) -> set[str]:
    """A ship name's words, so the class-derived model ("Hornet F7A Mk2") is found in the
    channel's marketing name ("Anvil F7A Hornet Mk II"): Mk II -> mk2, lowercase."""
    out: list[str] = []
    for w in (name or "").lower().replace("-", " ").split():
        if out and out[-1] == "mk" and (w in _ROMAN or w.isdigit()):
            out[-1] = "mk" + _ROMAN.get(w, w)
        else:
            out.append(w)
    return set(out)


# ---------------------------------------------------------------- viewers


class Viewer:
    def __init__(
        self, ws: web.WebSocketResponse, member: Member, session: str | None = None
    ) -> None:
        self.ws = ws
        self.member_id = member.id
        self.session = session
        """The browser session's public id; None for a PC's agent relaying it."""
        self.focus: str | None = None
        self.sent_roster: dict[str, dict] = {}
        self.roster_version = -1
        self.sent_focus: dict | None = None
        self.sent_focus_id: str | None = None
        self.queue: deque[dict] = deque(maxlen=VIEWER_QUEUE)
        self.wake = asyncio.Event()

    def push(self, message: dict) -> None:
        self.queue.append(message)
        self.wake.set()


# ---------------------------------------------------------------- the fleet


class Fleet:
    def __init__(self, cfg: Config, db: Database) -> None:
        self.cfg = cfg
        self.db = db
        self.members: dict[str, MemberLive] = {}
        self.viewers: set[Viewer] = set()
        self.taps: set[Callable[[dict], None]] = set()
        """Internal listeners (the cog's event socket): every fleet event."""
        self.recent: deque[dict] = deque(db.recent_events(100), maxlen=RECENT_EVENTS)
        self.roster: dict[str, dict] = {}
        self.roster_version = 0
        linked, seen = db.linked_member_ids(), db.member_last_seen()
        for member in db.members():
            if member.active and member.id in linked:
                live = self.members[member.id] = MemberLive(member)
                live.last_seen = seen.get(member.id)
        self.refresh_roster()

    # -- agents

    def live(self, member: Member) -> MemberLive:
        m = self.members.get(member.id)
        if m is None:
            m = self.members[member.id] = MemberLive(member)
        else:
            m.info = member.public()
        return m

    def agent_connected(
        self, member: Member, agent_id: int, ws: web.WebSocketResponse
    ) -> MemberLive:
        m = self.live(member)
        old = m.sockets.get(agent_id)
        if old is not None and not old.closed:
            # Same agent reconnected before the old socket timed out: keep the new one.
            asyncio.ensure_future(old.close(code=4000, message=b"replaced"))
        m.sockets[agent_id] = ws
        m.last_seen = now_ms()
        self.refresh_roster()
        return m

    def agent_disconnected(self, m: MemberLive, agent_id: int, ws: web.WebSocketResponse) -> None:
        if m.sockets.get(agent_id) is ws:
            del m.sockets[agent_id]
        if not m.connected:
            m.in_game = False
        self.refresh_roster()

    async def drop_agent(self, member_id: str, agent_id: int, reason: str) -> None:
        m = self.members.get(member_id)
        ws = m.sockets.get(agent_id) if m else None
        if ws is not None:
            with contextlib.suppress(Exception):
                await ws.send_json({"type": "error", "code": "revoked", "message": reason})
            await ws.close(code=4001, message=reason.encode()[:120])

    async def drop_member(self, member_id: str, reason: str, *, forget: bool = False) -> None:
        """Disconnect a member's PCs; ``forget``: also take them off the roster."""
        m = self.members.get(member_id)
        if m is None:
            return
        for agent_id in list(m.sockets):
            await self.drop_agent(member_id, agent_id, reason)
        if forget:
            self.members.pop(member_id, None)
            self.recent = deque(
                (e for e in self.recent if e["member"] != member_id), maxlen=RECENT_EVENTS
            )
            self.refresh_roster()

    def rename(self, member: Member) -> None:
        m = self.members.get(member.id)
        if m is not None:
            m.info = member.public()
            self.refresh_roster()

    def agent_message(self, m: MemberLive, data: Any) -> dict | None:
        """Apply one message from an agent. Returns a reply to send back, if any."""
        if not isinstance(data, dict):
            raise ProtocolError("not a JSON object")
        kind = data.get("type")
        v = data.get("v")
        if v is not None and v != SCHEMA_VERSION:
            raise ProtocolError(
                f"This hub speaks version {SCHEMA_VERSION}; please update your agent.",
                code="version",
                fatal=True,
            )
        m.last_seen = now_ms()
        try:
            if kind == "hello":
                hello = Hello.model_validate(data)
                too_old(hello.agent_version)
                m.share = {c for c in hello.share if c in SHARE_CATEGORIES}
                m.agent_version, m.channel = hello.agent_version[:32], (hello.channel or None)
                return None
            if kind == "snapshot":
                snap = Snapshot.model_validate(data)
                self._set_snapshot(m, snap.model_dump(mode="json", by_alias=True))
                return None
            if kind == "delta":
                if m.snapshot is None:
                    return {"type": "resync"}  # we lost the base (hub restarted)
                patch = data.get("patch")
                if not isinstance(patch, dict):
                    raise ProtocolError("delta without a patch")
                merged = apply_patch(m.snapshot, enforce_sharing(dict(patch), m.share))
                try:
                    Snapshot.model_validate(merged)
                except ValidationError:
                    return {"type": "resync"}
                self._set_snapshot(m, merged)
                return None
            if kind == "event":
                event = Event.model_validate(data)
                if event_shared(event, m.share):
                    self.add_event(m.info["id"], event)
                return None
            if kind == "heartbeat":
                if data.get("in_game") is False and m.in_game:
                    m.in_game = False
                    m.snapshot = None
                    self.refresh_roster()
                return None
        except ValidationError as exc:
            raise ProtocolError(f"invalid {kind}: {exc.error_count()} error(s)") from exc
        raise ProtocolError(f"unknown message type {kind!r}")

    def _set_snapshot(self, m: MemberLive, state: dict) -> None:
        m.snapshot = enforce_sharing(state, m.share)
        if not m.in_game:
            m.in_game = True
            self.refresh_roster()

    def add_event(self, member_id: str, event: Event) -> None:
        record = {"member": member_id, "t": event.t, "kind": event.kind, "data": event.data}
        self.db.add_event(member_id, event.t, event.kind, event.data)
        self.recent.append(record)
        message = {"type": "event", **record}
        for viewer in self.viewers:
            viewer.push(message)
        for tap in list(self.taps):
            try:
                tap(record)
            except Exception:
                log.exception("Event tap failed")

    # -- viewers

    def add_viewer(self, viewer: Viewer) -> None:
        self.viewers.add(viewer)

    def remove_viewer(self, viewer: Viewer) -> None:
        self.viewers.discard(viewer)

    async def close_viewers(
        self, member_id: str, session: str | None = None, *, keep: str | None = None
    ) -> None:
        """A device was signed out: close its open fleet views. ``session``: that one;
        ``keep``: every browser but this one. PCs' agents aren't sessions: unlink those."""
        for v in list(self.viewers):
            if v.member_id != member_id or v.session is None:
                continue
            if (session is not None and v.session == session) or (
                keep is not None and v.session != keep
            ):
                await v.ws.close(code=4001, message=b"signed out")

    def set_focus(self, viewer: Viewer, member_id: str | None) -> None:
        viewer.focus = member_id if member_id in self.members else None
        viewer.wake.set()

    def refresh_roster(self) -> bool:
        now = now_ms()
        roster = {mid: summarize(m, now, self.cfg) for mid, m in self.members.items()}
        resolve_aboard(roster)
        if roster == self.roster:
            return False
        self.roster = roster
        self.roster_version += 1
        for viewer in self.viewers:
            viewer.wake.set()
        return True

    async def pump(self, viewer: Viewer) -> None:
        """Send a viewer what changed for it, whenever woken. One task per viewer."""
        ws = viewer.ws
        while not ws.closed:
            await viewer.wake.wait()
            viewer.wake.clear()
            while viewer.queue:
                await ws.send_json(viewer.queue.popleft())
            if viewer.roster_version != self.roster_version:
                patch = make_patch(viewer.sent_roster, self.roster)
                viewer.sent_roster, viewer.roster_version = self.roster, self.roster_version
                if patch:
                    await ws.send_json({"type": "roster_delta", "patch": patch})
            focus = viewer.focus
            if focus != viewer.sent_focus_id:
                viewer.sent_focus_id = focus
                viewer.sent_focus = self.members[focus].snapshot if focus in self.members else None
                await ws.send_json({"type": "member", "id": focus, "snapshot": viewer.sent_focus})
            elif focus is not None:
                state = self.members[focus].snapshot if focus in self.members else None
                if state is not viewer.sent_focus:
                    if state is None or viewer.sent_focus is None:
                        await ws.send_json({"type": "member", "id": focus, "snapshot": state})
                    else:
                        patch = make_patch(viewer.sent_focus, state)
                        if patch:
                            await ws.send_json(
                                {"type": "member_delta", "id": focus, "patch": patch}
                            )
                    viewer.sent_focus = state

    async def run(self) -> None:
        """The clock: focus updates and the roster (and presence) every 100 ms."""
        tick = 0
        while True:
            await asyncio.sleep(TICK_S)
            tick += 1
            if tick % ROSTER_EVERY == 0:
                self.refresh_roster()
            for viewer in self.viewers:
                if viewer.focus is not None:
                    viewer.wake.set()

    # -- for the internal API

    def member_state(self, member_id: str) -> dict | None:
        m = self.members.get(member_id)
        return m.snapshot if m else None
