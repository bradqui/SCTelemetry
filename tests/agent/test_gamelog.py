"""Game.log: parsing every line type we use, the state built from it, following the
file, and replaying logged lines. Lines are in the real LIVE format (names changed)."""

import time
from pathlib import Path

import pytest
from fleet_agent.gamelog import (
    ARRIVED_SHOWN_MS,
    GameLogTail,
    LineJoiner,
    LogState,
    RouteTracker,
    contract_title,
    destination_name,
    parse_line,
    ship_name,
    who,
)
from fleet_agent.replay import Recording
from fleet_agent.runtime import Pipeline
from fleet_shared import Snapshot, apply_sharing, event_shared

FIXTURES = Path(__file__).parents[2] / "fixtures"
TS = "<2026-11-23T18:45:17.407Z> "
ME = "TestPilot"


def note(text: str, action: str = "Next") -> str:
    return (
        f'{TS}[Notice] <UpdateNotificationItem> Notification "{text}" [7], Action: {action} '
        "[Team_CoreGameplayFeatures][Missions][Comms]"
    )


SELECTED = (
    f"{TS}[Notice] <Player Selected Quantum Target - Local> [ItemNavigation][CL][36708] | NOT AUTH"
    " | ORIG_m80_944712252115[944712252115]|CSCItemNavigation::OnPlayerSelectedQuantumTarget|"
    "Player has selected point OOC_Stanton_1b_Aberdeen as their destination, routing locally"
)
ARRIVED = (
    f"{TS}[Notice] <Quantum Drive Arrived - Arrived at Final Destination> [ItemNavigation][CL]"
    " | NOT AUTH | ORIG_m80_944712252115[944712252115]|CSCItemNavigation::OnQuantumDriveArrived|"
    "Quantum Drive has arrived at final destination [Team_CGP4][QuantumTravel]"
)
BLOCKED = note(
    "Quantum Travel: Your destination is obstructed and Quantum Travel cannot be initiated. "
    "You may need to travel somewhere else first to find a clear path."
)
LOGIN = (
    f"{TS}[Notice] <Legacy login response> [CIG-net] User Login Success - Handle[{ME}] - Time[1]"
)
JOIN = (
    f"{TS}[Notice] <Join PU> address[1.2.3.4] port[64355] shard[pub_use1b_13165946_150] "
    "locationId[-281470681677823] [Team_GameServices][GIM][Matchmaking]"
)


def destroyed(vehicle: str, killer: str, before: int = 0, after: int = 2) -> str:
    cls = vehicle.rsplit("_", 1)[0]
    return (
        f"{TS}[Notice] <Vehicle Destroyed> Vehicle '{vehicle}' [950384366871] in zone 'x' class "
        f"'{cls}' (owner player [0], driver [0]) destroyed: reason [Combat] level [{before}] -> "
        f"[{after}] flags [4066] killer '{killer}' [204782588372] authority [0] [Team_X]"
    )


ACTOR_DEATH = (
    f"{TS}[Notice] <Actor Death> CActor::Kill: '{ME}' [5926470253117] in zone 'Hangar' killed by "
    "'SomeoneElse' [292458386837] using 'behr_lmg_ballistic_01_123' [Class behr_lmg_ballistic_01] "
    "with damage type 'Bullet' from direction x: 0.6, y: -0.6, z: -0.2 [Team_ActorTech][Actor]"
)
JUMP = (
    f"{TS}[Notice] <Jump Drive State Changed> Now Exiting | CL74884 | NOT AUTH | Pyro | "
    "JDRV_TARS_S03_Exodus_SCItem_5251753660358 [5251753660358] (adam: RSI_Polaris_5251753660095 "
    "in zone P2_L4) | CSCItemJumpDrive::OnStateChanged [Team_CGP4][JumpSystem]"
)
END_ABANDON = (
    f"{TS}[Notice] <EndMission> Ending mission for player. MissionId[3043cc9f] Player[{ME}] "
    "PlayerId[1] CompletionType[Abandon] Reason[Player left] [Team_MissionFeatures][Missions]"
)


@pytest.mark.parametrize(
    "line,kind,data",
    [
        (SELECTED, "route", {"destination": "Aberdeen"}),
        (ARRIVED, "arrived", {}),
        (BLOCKED, "blocked", {}),
        (LOGIN, "handle", {"handle": ME}),
        (JOIN, "shard", {"shard": "pub_use1b_13165946_150"}),
        (
            f"{TS}[Notice] <Update Shard Id> New Shard Id: pub_use1b_9978513_040. Old Shard Id",
            "shard",
            {"shard": "pub_use1b_9978513_040"},
        ),
        (note("Entering Armistice Zone - Combat Prohibited: "), "armistice", {"on": True}),
        (note("Leaving Armistice Zone - Caution Advised: "), "armistice", {"on": False}),
        (
            note("Entered Hurston Dynamics Jurisdiction: "),
            "jurisdiction",
            {"name": "Hurston Dynamics"},
        ),
        (note("Entered Ungoverned Jurisdiction: "), "jurisdiction", {"name": "Ungoverned"}),
        (note("Entered Monitored Space: "), "monitored", {"on": True}),
        (note("Exited Monitored Space: "), "monitored", {"on": False}),
        (note("Monitored Space Down: "), "comms", {"up": False}),
        (note("Monitored Space Restored: "), "comms", {"up": True}),
        (note("Leaving Restricted Area: "), "restricted", {"on": False}),
        (note("Entering Private Property: "), "private", {"on": True}),
        (note("Leaving Private Property: "), "private", {"on": False}),
        (
            note(
                "Contract Accepted:  Retake Platforms From Nine Tails <EM4>[150 Rep] [BP]*</EM4>: "
            ),
            "contract_accepted",
            {"title": "Retake Platforms From Nine Tails", "tags": ["150 Rep", "BP"]},
        ),
        (
            note("Contract Complete: Combat Gauntlet - Scenario #1: "),
            "contract_complete",
            {"title": "Combat Gauntlet - Scenario #1", "tags": []},
        ),
        (
            note("Contract Failed: Defend Operative <EM4>[100 Rep]</EM4>: "),
            "contract_failed",
            {"title": "Defend Operative", "tags": ["100 Rep"]},
        ),
        (
            note("Contract Shared: Defend Operative: "),
            "contract_shared",
            {"title": "Defend Operative", "tags": []},
        ),
        (note("New Objective: Go to Arial Cave: "), "objective_new", {"text": "Go to Arial Cave"}),
        (
            note("Objective Complete: Go to Location: "),
            "objective_complete",
            {"text": "Go to Location"},
        ),
        (
            note("Objective Withdrawn: Reach Upper Platform: "),
            "objective_withdrawn",
            {"text": "Reach Upper Platform"},
        ),
        (note("Awarded 1000 aUEC: "), "reward", {"auec": 1000}),
        (
            note("Minor Injury Detected - Left arm - Tier 3 Treatment Required : "),
            "injury",
            {"severity": "minor", "part": "Left arm", "tier": 3},
        ),
        (
            note("Incapacitated: While incapacitated, ask others in your party..."),
            "incapacitated",
            {},
        ),
        (note("Medical Bed: The bed has restored your health and reset your BDL."), "healed", {}),
        (note("Hangar Request Completed: "), "hangar_ready", {}),
        (note("Received Blueprint: Monde Helmet: "), "blueprint", {"name": "Monde Helmet"}),
        (
            note("Quantum Travel Calibration Started By Wingmate: "),
            "qt_calibration",
            {"by": "Wingmate", "done": False},
        ),
        (destroyed("ANVL_Hurricane_PU_AI_CRIM_950384366871", ME), "vehicle_destroyed", None),
        (ACTOR_DEATH, "actor_death", None),
        (JUMP, "jump_drive", {"state": "Exiting", "system": "Pyro"}),
        (END_ABANDON, "end_mission", {"how": "Abandon"}),
    ],
)
def test_parse(line, kind, data):
    ev = parse_line(line)
    assert ev is not None and ev.kind == kind
    if data is not None:
        assert ev.data == data


def test_ignored_lines():
    assert parse_line("") is None
    assert parse_line(note("Entered Monitored Space: ", action="StartFade")) is None, "once only"
    assert parse_line(note("You have joined channel 'Origin M80 : x'.")) is None, "no comms"
    assert parse_line(f"{TS}[Notice] <Calculate Route> ... [QuantumTravel]") is None


def test_multiline_notifications_are_joined():
    j = LineJoiner()
    assert j.feed(f'{TS}[Notice] <UpdateNotificationItem> Notification "Restricted Area') is None
    joined = j.feed(f"{TS}For your safety, you've been relocated.: \" [9], Action: Next [Team]")
    ev = parse_line(joined)
    assert ev.kind == "restricted" and ev.data["on"] is True
    assert j.feed("plain line") == "plain line"


def test_names():
    assert destination_name("OOC_Stanton_1b_Aberdeen") == "Aberdeen"
    assert destination_name("ObjectContainer_Lorville_City") == "Lorville City"
    assert destination_name("MISSION_QT_Bounty_Beacon_927914670160") == "Bounty Beacon"
    assert ship_name("ANVL_Hurricane_PU_AI_CRIM") == ("Hurricane", "hostile")
    assert ship_name("ORIG_300i_PU_AI_CIV") == ("300i", "civilian")
    assert ship_name("CRUS_Spirit_A1_AI_CRIM") == ("Spirit A1", "hostile")
    assert who("PU_Pilots-Human-Criminal-Pilot_Light") == "an NPC"
    assert who("AIModule_Unmanned_PU_PDC") == "a defence turret"
    assert who("ace_pilot-7") == "ace_pilot-7", "player handles can have underscores"
    assert contract_title(" A Call to Arms: ") == ("A Call to Arms", [])


def feed(state: LogState, *lines, t=1000, ship=None):
    out = []
    for line in lines:
        out += state.on_log(parse_line(line), t, ship)
    return out


def test_location_state():
    s = LogState()
    assert s.location(0, None) is None
    events = feed(
        s,
        JOIN,
        note("Entered Hurston Dynamics Jurisdiction: "),
        note("Entering Armistice Zone - Combat Prohibited: "),
        note("Entering Armistice Zone - Combat Prohibited: "),  # repeated by the game
        note("Entered Monitored Space: "),
        note("Monitored Space Down: "),
    )
    assert [e.kind for e in events] == [
        "shard_join",
        "jurisdiction",
        "armistice_enter",
        "monitored_enter",
        "comms_down",
    ]
    loc = s.location(2000, None)
    assert loc.armistice and loc.monitored and loc.comms is False
    assert loc.jurisdiction == "Hurston Dynamics" and loc.shard == "pub_use1b_13165946_150"
    feed(s, JUMP)
    assert s.location(2000, None).system == "Pyro"


def test_contracts_objectives_rewards():
    s = LogState()
    feed(s, note("Contract Accepted:  Combat Gauntlet - Scenario #1: "))
    feed(s, note("New Objective: Defeat Hostile Ships: "))
    [m] = s.mission_list(1000)
    assert m.title == "Combat Gauntlet - Scenario #1" and m.state == "active"
    assert m.objective == "Defeat Hostile Ships" and not m.objective_done
    feed(s, note("Objective Complete: Defeat Hostile Ships: "))
    assert s.mission_list(1000)[0].objective_done
    events = feed(
        s, note("Contract Complete: Combat Gauntlet - Scenario #1: "), note("Awarded 500 aUEC: ")
    )
    assert [e.kind for e in events] == ["contract_complete", "reward"]
    assert s.session.contracts == 1 and s.session.earned == 500
    assert s.mission_list(1000)[0].state == "complete"
    assert s.mission_list(1000 + 200_000) == [], "finished contracts clear after a while"


def test_abandon_only_when_unambiguous():
    s = LogState()
    feed(s, note("Contract Accepted:  A: "))
    assert [e.kind for e in feed(s, END_ABANDON)] == ["contract_abandoned"]
    s = LogState()
    feed(s, note("Contract Accepted:  A: "), note("Contract Accepted:  B: "))
    assert feed(s, END_ABANDON) == [], "two active contracts: can't tell which"


def test_kills_losses_and_nearby():
    s = LogState()
    feed(s, LOGIN)
    my_ship = "ORIG_m80_944712252115"
    events = feed(
        s,
        destroyed("ANVL_Hurricane_PU_AI_CRIM_1", ME),
        destroyed("ANVL_Hurricane_PU_AI_CRIM_2", ME, before=0, after=1),  # disabled only
        destroyed("ANVL_Hawk_PU_AI_CRIM_3", "Wingmate"),
        destroyed(my_ship, "PU_Pilots-Human-Criminal-Pilot_Light"),
        ship=my_ship,
    )
    assert [e.kind for e in events] == ["kill", "vehicle_destroyed", "ship_lost"]
    assert events[0].data["target"] == "Hurricane" and events[0].data["npc"] == "hostile"
    assert events[1].data["by"] == "Wingmate"
    assert events[2].data["by"] == "an NPC"
    assert s.session.kills == 1 and s.session.ships_lost == 1
    [death] = feed(s, ACTOR_DEATH)
    assert death.kind == "death" and death.data["by"] == "SomeoneElse"


def test_injuries_and_healing():
    s = LogState()
    feed(
        s,
        note("Minor Injury Detected - Head - Tier 3 Treatment Required : "),
        note("Moderate Injury Detected - Head - Tier 2 Treatment Required : "),
        note("Minor Injury Detected - Torso - Tier 3 Treatment Required : "),
    )
    assert {i.part: i.severity for i in s.injuries.values()} == {
        "Head": "moderate",
        "Torso": "minor",
    }
    feed(s, note("Medical Bed: The bed has restored your health and reset your BDL."))
    assert s.injuries == {}


def test_jump_drive_counts_system_jumps_not_quantum():
    s = LogState()
    enter = JUMP.replace("Now Exiting", "Now Entering").replace("| Pyro |", "| Stanton |")
    assert [e.kind for e in feed(s, enter)] == ["jump_start"]
    assert [e.kind for e in feed(s, JUMP)] == ["jump_end"]
    assert s.session.system_jumps == 1 and s.session.quantum_trips == 0
    feed(s, SELECTED, ARRIVED)
    assert s.session.quantum_trips == 1


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
    assert r.route(5000 + ARRIVED_SHOWN_MS + 1, False) is None


def test_pipeline_merges_log_state_and_quiet_history_has_no_events():
    p = Pipeline()
    events = []
    p.subscribe(lambda kind, payload: events.append(payload) if kind == "event" else None)
    p.on_frame({"actor": {}}, 500)
    assert p.latest.location is None, "no Game.log yet: nothing added"
    p.on_log(SELECTED, 1000, quiet=True)
    p.on_log(note("Minor Injury Detected - Head - Tier 3 Treatment Required : "), 1000, quiet=True)
    assert [e for e in events if e.kind.startswith("quantum")] == []
    p.on_frame({"actor": {"vitals": {"health": 1}}}, 2000)
    snap = p.latest
    assert snap.location.route.destination == "Aberdeen" and snap.location.route.state == "plotted"
    assert snap.session is not None and snap.missions == []
    p.on_log(ARRIVED, 3000)
    assert [e.kind for e in events if e.kind.startswith("quantum")] == ["quantum_arrived"]


def test_sharing_defaults_and_opt_outs():
    s = LogState()
    feed(s, JOIN, note("Contract Accepted:  A: "), note("Awarded 500 aUEC: "))
    snap = Snapshot(
        t=1, location=s.location(1, None), missions=s.mission_list(1), session=s.session
    )
    everything = ["status", "ship", "weapons", "vitals", "uec", "location", "mission", "combat"]
    full = apply_sharing(snap, everything)
    assert full.location and full.missions and full.session.earned == 500
    less = apply_sharing(snap, ["status", "combat"])
    assert less.location is None and less.missions is None and less.session.earned == 0
    [route_event] = feed(LogState(), SELECTED)
    assert event_shared(route_event, everything)
    assert not event_shared(route_event, ["status"]), "location opted out"


def test_tail_follows_appends_and_a_new_game_log(tmp_path):
    path = tmp_path / "Game.log"
    path.write_text(SELECTED + "\nnoise\n", encoding="utf-8")
    seen, sessions = [], []
    tail = GameLogTail(
        path,
        lambda line, quiet: seen.append((parse_line(line).kind, quiet)),
        lambda: sessions.append(1),
    )
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
    assert sessions == [1]


def test_replay_carries_logged_lines():
    rec = Recording.load([FIXTURES / "quantum-travel.jsonl.gz"])
    kinds = [m.kind for m in rec.markers]
    assert "quantum_arrived" in kinds
    # The route was plotted before the slice starts: it's carried as quiet context
    # (state for the view), not as an event on the timeline.
    context = [line for line, quiet in rec.logs.get(0, []) if quiet]
    assert any(parse_line(x).kind == "route" for x in context)
    assert "quantum_route" not in kinds
    arrived = next(m for m in rec.markers if m.kind == "quantum_arrived")
    end = next(m for m in rec.markers if m.kind == "quantum_end")
    assert abs(arrived.pos - end.pos) < 2, "the log's arrival matches the telemetry's drop-out"


def test_combat_replay_has_kills_and_the_contract():
    rec = Recording.load([FIXTURES / "combat.jsonl.gz"])
    kinds = [m.kind for m in rec.markers]
    assert kinds.count("kill") == 3 and "contract_complete" in kinds


def _wait(cond, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return
        time.sleep(0.02)
    raise AssertionError("timed out")
