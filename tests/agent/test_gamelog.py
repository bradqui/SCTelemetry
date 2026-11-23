"""Game.log parsing, quantum route state, following the file, and replaying logged lines."""

import time
from pathlib import Path

import pytest
from fleet_agent.gamelog import (
    ARRIVED_SHOWN_MS,
    GameLogTail,
    RouteTracker,
    destination_name,
    parse_line,
)
from fleet_agent.replay import Recording
from fleet_agent.runtime import Pipeline

FIXTURES = Path(__file__).parents[2] / "fixtures"

# Real lines from a LIVE Game.log (2026-11-23), shortened at the end.
SELECTED = (
    "<2026-11-23T18:45:17.407Z> [Notice] <Player Selected Quantum Target - Local> "
    "[ItemNavigation][CL][36708] | NOT AUTH | ORIG_m80_944712252115[944712252115]|"
    "CSCItemNavigation::OnPlayerSelectedQuantumTarget|Player has selected point "
    "OOC_Stanton_1b_Aberdeen as their destination, routing locally [Team_CGP4][QuantumTravel]"
)
ARRIVED = (
    "<2026-11-23T18:46:09.375Z> [Notice] <Quantum Drive Arrived - Arrived at Final Destination> "
    "[ItemNavigation][CL][36708] | NOT AUTH | ORIG_m80_944712252115[944712252115]|"
    "CSCItemNavigation::OnQuantumDriveArrived|Quantum Drive has arrived at final destination"
)
BLOCKED = (
    '<2026-11-23T18:44:44.801Z> [Notice] <UpdateNotificationItem> Notification "Quantum Travel: '
    "Your destination is obstructed and Quantum Travel cannot be initiated. You may need to "
    'travel somewhere else first to find a clear path." [18], Action: StartFade'
)
NOISE = (
    "<2026-11-23T18:32:05.910Z> [Notice] <Calculate Route> [ItemNavigation][CL][36708] | "
    "Projected Start Location is Hurston for route to destination X [Team_CGP4][QuantumTravel]"
)


def test_parse_lines():
    assert parse_line(SELECTED).kind == "route"
    assert parse_line(SELECTED).destination == "Aberdeen"
    assert parse_line(ARRIVED).kind == "arrived"
    assert parse_line(BLOCKED).kind == "blocked"
    assert parse_line(NOISE) is None
    assert parse_line("") is None


@pytest.mark.parametrize(
    "raw,name",
    [
        ("OOC_Stanton_1b_Aberdeen", "Aberdeen"),
        ("ObjectContainer_Lorville_City", "Lorville City"),
        ("MISSION_QT_Bounty_Beacon_927914670160", "Bounty Beacon"),
        ("MISSION_QT_Quantum_Beacon_927916631652", "Quantum Beacon"),
        ("Something_New", "Something New"),
    ],
)
def test_destination_names(raw, name):
    assert destination_name(raw) == name


def test_route_states():
    r = RouteTracker()
    assert r.route(0, False) is None
    [ev] = r.on_log(parse_line(SELECTED), 1000)
    assert ev.kind == "quantum_route" and ev.data["destination"] == "Aberdeen"
    assert r.route(1100, False).state == "plotted"
    assert r.route(1200, True).state == "en_route", "the jump starts"
    assert r.route(1300, False).state == "en_route", "between legs of a split route"
    [ev] = r.on_log(parse_line(ARRIVED), 5000)
    assert ev.kind == "quantum_arrived" and ev.data["destination"] == "Aberdeen"
    assert r.route(6000, False).state == "arrived"
    assert r.route(5000 + ARRIVED_SHOWN_MS + 1, False) is None, "arrival clears after a while"
    [ev] = r.on_log(parse_line(BLOCKED), 9000)
    assert ev.kind == "quantum_blocked"


def test_pipeline_puts_route_on_snapshots_and_quiet_history_has_no_events():
    p = Pipeline()
    events = []
    p.subscribe(lambda kind, payload: events.append(payload) if kind == "event" else None)
    p.on_log(SELECTED, 1000, quiet=True)
    assert events == []
    p.on_frame({"actor": {}}, 2000)
    assert p.latest.route.destination == "Aberdeen" and p.latest.route.state == "plotted"
    p.on_log(ARRIVED, 3000)
    assert [e.kind for e in events if e.kind.startswith("quantum")] == ["quantum_arrived"]


def test_tail_follows_appends_and_a_new_game_log(tmp_path):
    path = tmp_path / "Game.log"
    path.write_text(SELECTED + "\n" + NOISE + "\n", encoding="utf-8")
    seen = []
    tail = GameLogTail(path, lambda line, quiet: seen.append((parse_line(line).kind, quiet)))
    tail.POLL_S = 0.05
    tail.start()
    try:
        _wait(lambda: seen == [("route", True)])
        with path.open("a", encoding="utf-8") as fh:
            fh.write(ARRIVED + "\npartial line without newline")
        _wait(lambda: ("arrived", False) in seen)
        path.write_text(BLOCKED + "\n", encoding="utf-8")  # the game restarted: a shorter file
        _wait(lambda: ("blocked", False) in seen)
    finally:
        tail.stop()
    assert seen == [("route", True), ("arrived", False), ("blocked", False)]


def test_replay_carries_logged_lines():
    rec = Recording.load([FIXTURES / "quantum-travel.jsonl.gz"])
    kinds = [m.kind for m in rec.markers]
    assert "quantum_route" in kinds and "quantum_arrived" in kinds
    route = next(m for m in rec.markers if m.kind == "quantum_route")
    assert route.data["destination"] == "Bounty Beacon"
    arrived = next(m for m in rec.markers if m.kind == "quantum_arrived")
    end = next(m for m in rec.markers if m.kind == "quantum_end")
    assert abs(arrived.pos - end.pos) < 2, "the log's arrival matches the telemetry's drop-out"
    assert sum(len(v) for v in rec.logs.values()) == 2


def _wait(cond, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return
        time.sleep(0.02)
    raise AssertionError("timed out")
