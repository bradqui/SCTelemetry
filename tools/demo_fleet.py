"""Build the showcase's demo fleet from the recorded fixtures.

    uv run python tools/demo_fleet.py            # writes web/showcase/demo-fleet.json

Every member is a real recording run through the real agent pipeline (normalizer,
events, Game.log state) and summarized by the hub's own roster code, then stored
as merge patches every 250 ms. Ships are relabelled so the demo shows several
manufacturers (and their themes); the telemetry itself is as recorded. Fixtures
are already scrubbed, and the member names are made up.
"""

from __future__ import annotations

import json
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "agent"), str(ROOT / "hub"), str(ROOT / "shared")]

from fleet_agent.replay import FIXTURES_DIR, Recording  # noqa: E402
from fleet_agent.runtime import Pipeline  # noqa: E402
from fleet_hub.config import Config  # noqa: E402
from fleet_hub.db import Member  # noqa: E402
from fleet_hub.fleet import MemberLive, summarize  # noqa: E402
from fleet_shared import Event, make_patch  # noqa: E402

STEP_MS = 250
OUT = ROOT / "web" / "showcase" / "demo-fleet.json"
CFG = Config()

# id, name, fixture, start (s), ship relabel (class, model, maker) or None, role override
LIVE = [
    ("m_rook", "Rook", "combat", 140, ("AEGS_Gladius", "Gladius", "Aegis Dynamics"), None),
    (
        "m_ace",
        "Ace",
        "quantum-travel",
        0,
        ("DRAK_Cutlass_Black", "Cutlass Black", "Drake Interplanetary"),
        None,
    ),
    ("m_kestrel", "Kestrel", "constellation-pilot-copilot-turret", 0, None, None),
    ("m_wren", "Wren", "constellation-pilot-copilot-turret", 0, None, "copilot"),
    (
        "m_vale",
        "Vale",
        "cruise-nav-scm",
        0,
        ("ANVL_Hornet_F7C_Mk2", "F7C Hornet Mk II", "Anvil Aerospace"),
        None,
    ),
    (
        "m_mara",
        "Mara",
        "landing-leave-seat",
        0,
        ("MISC_Freelancer_MAX", "Freelancer MAX", "MISC"),
        None,
    ),
    ("m_nova", "Nova", "on-foot", 0, None, None),
]
ABOARD = {"m_nova": ("RSI Constellation Mk V Centaurus", "Kestrel", "m_kestrel")}
"""On foot aboard someone's ship: the ship's comms channel, as Game.log has it."""
STATIC = [
    ("m_pike", "Pike", "idle", None),
    ("m_juno", "Juno", "offline", -2 * 3600 * 1000 - 14 * 60 * 1000),
]


def relabel(state: dict, ship_label, role) -> dict:
    ship = state.get("ship")
    if ship and ship_label:
        cls, model, maker = ship_label
        ship["id"] = f"{cls}_{zlib.crc32(ship['id'].encode()) % 10**9}"
        ship["class"], ship["model"], ship["manufacturer"] = cls, model, maker
    if role and state.get("status"):
        state["status"]["role"] = role
        state["status"]["seat"] = (state["status"].get("seat") or "").replace("Pilot", "CoPilot")
    return state


def relative(obj, base_ms: int):
    """Times become ms from the member's loop start (the page adds its own clock)."""
    if isinstance(obj, dict):
        return {
            k: (
                v - base_ms
                if k in ("t", "since") and isinstance(v, (int, float))
                else relative(v, base_ms)
            )
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [relative(v, base_ms) for v in obj]
    return obj


def run(member_id, name, fixture, start, ship_label, role):
    rec = Recording.load([FIXTURES_DIR / f"{fixture}.jsonl.gz"])
    pipeline = Pipeline()
    events: list[tuple[float, Event]] = []
    pos_now = {"pos": 0.0}
    pipeline.subscribe(lambda kind, p: kind == "event" and events.append((pos_now["pos"], p)))
    samples: list[dict] = []
    next_ms = start * 1000
    if member_id in ABOARD:
        ship, owner, _ = ABOARD[member_id]
        pipeline.on_log(
            '<2026-11-24T18:00:00.000Z> [Notice] <UpdateNotificationItem> Notification "You have'
            f" joined channel '{ship} : {owner}'.\" [1], Action: Next [Comms]",
            0,
            True,
        )
    for i, pos in enumerate(rec.positions):
        pos_now["pos"] = pos
        t = int(pos * 1000)
        for line, _quiet in rec.logs.get(i, ()):
            pipeline.on_log(line, t, pos < start)
        pipeline.on_frame(rec.decode(i), t)
        while pos >= start and t >= next_ms and pipeline.latest is not None:
            state = json.loads(pipeline.latest.model_dump_json(by_alias=True))
            samples.append(relabel(state, ship_label, role))
            next_ms += STEP_MS
    base = start * 1000
    live = MemberLive(Member(member_id, name, None, "member", 1, 0))
    live.sockets = {1: object()}  # connected
    snaps, rows, prev_s, prev_r = [], [], None, None
    for state in samples:
        state = relative(state, base)
        live.snapshot, live.in_game, live.last_seen = state, True, 10**13
        row = summarize(live, 10**13, CFG)
        row["last_seen"] = None
        snaps.append(make_patch(prev_s, state) or {})
        rows.append(make_patch(prev_r, row) or {})
        prev_s, prev_r = state, row
    evs = []
    if role is None:  # a crewmate shares the pilot's recording: don't repeat their events
        for pos, ev in events:
            if pos >= start and ev.kind != "game_start":
                data = dict(ev.data)
                if ship_label and "model" in data:
                    data["model"] = ship_label[1]
                evs.append(
                    {"i": int((pos - start) * 1000 // STEP_MS), "kind": ev.kind, "data": data}
                )
    print(f"{name:8} {fixture:36} {len(samples) * STEP_MS / 1000:5.0f} s  {len(evs):3} events")
    return {"id": member_id, "name": name, "snaps": snaps, "rows": rows, "events": evs}


def static(member_id, name, kind, last_seen):
    live = MemberLive(Member(member_id, name, None, "member", 1, 0))
    if kind == "idle":
        live.sockets, live.last_seen, live.in_game = {1: object()}, 10**13, False
        row = summarize(live, 10**13, CFG)
        row["last_seen"] = None
    else:
        live.last_seen = 10**13 + last_seen
        row = summarize(live, 10**13, CFG)
        row["last_seen"] = last_seen
    return {"id": member_id, "name": name, "snaps": [], "rows": [row], "events": []}


def main() -> None:
    members = [run(*m) for m in LIVE] + [static(*m) for m in STATIC]
    # The hub resolves whose ship it is across the roster (resolve_aboard): here, by hand.
    by_id = {m["id"]: m for m in members}
    for member_id, (_, _, owner_id) in ABOARD.items():
        ship_id = next((r["ship"]["id"] for r in by_id[owner_id]["rows"] if r.get("ship")), None)
        aboard = (by_id[member_id]["rows"][0].get("location") or {}).get("aboard")
        if aboard:
            aboard["owner_id"], aboard["ship_id"] = owner_id, ship_id
    data = {"step_ms": STEP_MS, "me": "m_rook", "org": "Friday Night Club", "members": members}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
