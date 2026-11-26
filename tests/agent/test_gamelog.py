"""Game.log: parsing every line type we use, the state built from it, following the
file, and replaying logged lines. Lines are in the real LIVE format (names changed)."""

import time
from pathlib import Path

import pytest
from starglance.capturefile import read_frames
from starglance.gamelog import (
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
from starglance.replay import Recording
from starglance.runtime import Pipeline
from starglance_shared import Snapshot, apply_sharing, event_shared

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
        (SELECTED, "route", {"destination": "Aberdeen", "id": "OOC_Stanton_1b_Aberdeen"}),
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
        (END_ABANDON, "end_mission", {"mission": "3043cc9f", "how": "Abandon"}),
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
    assert parse_line(f"{TS}[Notice] <Calculate Route> ... [QuantumTravel]") is None


def test_multiline_notifications_are_joined():
    j = LineJoiner()
    assert j.feed(f'{TS}[Notice] <UpdateNotificationItem> Notification "Restricted Area') is None
    joined = j.feed(f"{TS}For your safety, you've been relocated.: \" [9], Action: Next [Team]")
    ev = parse_line(joined)
    # Sent after the game has moved you out: not in a restricted area any more.
    assert ev.kind == "restricted" and ev.data["on"] is False
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
    assert [(o.text, o.state) for o in m.objectives] == [("Defeat Hostile Ships", "active")]
    feed(s, note("Objective Complete: Defeat Hostile Ships: "))
    assert s.mission_list(1000)[0].objectives[0].state == "complete"
    events = feed(
        s, note("Contract Complete: Combat Gauntlet - Scenario #1: "), note("Awarded 500 aUEC: ")
    )
    assert [e.kind for e in events] == ["contract_complete", "reward"]
    assert s.session.contracts == 1 and s.session.earned == 500
    assert s.mission_list(1000)[0].state == "complete"
    assert s.mission_list(1000 + 200_000) == [], "finished contracts clear after a while"


def told(text: str, n: int, mission: str, objective: str = "") -> tuple[str, str]:
    """A notice as the game logs it: queued (with its ids), then shown (without)."""
    return (
        f'{TS}[Notice] <SHUDEvent_OnNotification> Added notification "{text}" [{n}] to queue. '
        f"New queue size: 1, MissionId: [{mission}], ObjectiveId: [{objective}] "
        "[Team_CoreGameplayFeatures][Missions][Comms]",
        f'{TS}[Notice] <UpdateNotificationItem> Notification "{text}" [{n}], Action: Next '
        "[Team_CoreGameplayFeatures][Missions][Comms]",
    )


HAUL = "1a2b3c4d-0000-4000-8000-000000000001"
CARGO = ["Ammonia", "Hydrogen Fuel", "Argon", "Pressurized Ice", "Construction Materials"]


def haul_accepted(n: int = 2) -> list[str]:
    lines = [*told("Contract Accepted:  Rookie Hauler Needed for Direct Bulk Shipment: ", n, HAUL)]
    for i, what in enumerate(CARGO):
        lines += told(
            f"New Objective: Deliver 0/48 SCU of {what} to Stanton System: ",
            n + 1 + i,
            HAUL,
            f"dropoff_x_{i}",
        )
    return lines


def test_a_haul_keeps_all_its_objectives():
    s = LogState()
    feed(s, *haul_accepted())
    [m] = s.mission_list(1000)
    assert m.id == HAUL and m.state == "active"
    assert [o.text.split(" of ")[1].split(" to ")[0] for o in m.objectives] == CARGO
    assert all(o.state == "active" for o in m.objectives)
    feed(s, *told("Contract Complete: Rookie Hauler Needed for Direct Bulk Shipment: ", 20, HAUL))
    m = s.mission_list(1000)[0]
    assert m.state == "complete" and all(o.state == "complete" for o in m.objectives)


def test_a_relog_announces_it_again_without_doubling():
    s = LogState()
    feed(s, *haul_accepted(2))
    feed(s, *haul_accepted(40))  # the game says it all again after a relog
    [m] = s.mission_list(1000)
    assert len(m.objectives) == 5


def test_objectives_find_their_own_contract():
    s = LogState()
    other = "1a2b3c4d-0000-4000-8000-000000000002"
    feed(s, *haul_accepted())
    feed(s, *told("Contract Accepted:  Retake: ", 10, other))
    feed(s, *told("New Objective: Defeat Hostile Ships: ", 11, other, "kill_0"))
    feed(
        s,
        *told(
            "Objective Withdrawn: Deliver 0/48 SCU of Argon to Stanton System: ",
            12,
            HAUL,
            "dropoff_x_2",
        ),
    )
    retake, haul = s.mission_list(1000)
    assert [o.text for o in retake.objectives] == ["Defeat Hostile Ships"]
    assert len(haul.objectives) == 5 and haul.objectives[2].state == "withdrawn"


def test_abandon_by_mission_id():
    s = LogState()
    other = "1a2b3c4d-0000-4000-8000-000000000002"
    feed(s, *haul_accepted())
    feed(s, *told("Contract Accepted:  Retake: ", 10, other))
    end = END_ABANDON.replace("MissionId[3043cc9f]", f"MissionId[{HAUL}]")
    assert [e.data["title"] for e in feed(s, end)] == [
        "Rookie Hauler Needed for Direct Bulk Shipment"
    ]
    assert [m.state for m in s.mission_list(1000)] == ["active", "abandoned"]


def test_auec_from_the_balance_and_from_notices():
    s = LogState()
    s.balance(0)  # still loading: not counted
    s.balance(120_000)  # where counting starts
    s.balance(95_000)  # spent: doesn't take earnings back
    s.balance(140_000)  # a hauling payout, no notice
    assert s.session.earned == 45_000
    feed(s, note("Awarded 5,000 aUEC: "))  # the notice for money already counted
    assert s.session.earned == 45_000
    s = LogState()  # no balance in the stream: the notices still count
    feed(s, note("Awarded 5,000 aUEC: "))
    assert s.session.earned == 5000


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
    bed = note("Medical Bed: The bed has restored your health and reset your BDL.")
    assert [e.kind for e in feed(s, bed)] == ["healed"]
    assert s.injuries == {}
    assert feed(s, bed, bed) == [], "the game repeats it near a bed: nothing more to heal"


def test_one_explosion_has_the_same_id_everywhere():
    s = LogState()
    feed(s, LOGIN)
    [near] = feed(s, destroyed("ANVL_Hawk_PU_AI_CRIM_950384366871", "Someone"))
    assert near.kind == "vehicle_destroyed" and near.data["vehicle"] == "950384366871"
    [kill] = feed(s, destroyed("ANVL_Hawk_PU_AI_CRIM_950384366872", ME))
    assert kill.kind == "kill" and kill.data["vehicle"] == "950384366872"


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


def test_last_arrived_is_remembered_for_a_while():
    from starglance.gamelog import LAST_ARRIVED_MS

    s = LogState()
    feed(s, JOIN, SELECTED, t=1000)
    assert s.location(1100, False).last_arrived is None, "not there yet"
    feed(s, ARRIVED, t=5000)
    last = s.location(5000 + ARRIVED_SHOWN_MS + 1, False).last_arrived
    assert last.destination == "Aberdeen" and last.since == 5000, "outlasts the arrived route"
    assert s.location(5000 + LAST_ARRIVED_MS + 1, False) is not None
    assert s.location(5000 + LAST_ARRIVED_MS + 1, False).last_arrived is None, "too old"

    for forget in (
        lambda: feed(s, SELECTED, t=7000),  # a new route: off somewhere else
        lambda: feed(s, JOIN.replace("13165946", "99999999"), t=7000),  # another server
        lambda: s.respawned(),
    ):
        feed(s, SELECTED, ARRIVED, t=6000)
        assert s.location(6500, False).last_arrived is not None
        forget()
        assert s.location(7100, False).last_arrived is None


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
    end = [m for m in rec.markers if m.kind == "quantum_end"][-1]
    assert abs(arrived.pos - end.pos) < 2, "the log's arrival matches the last leg's end"


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


def test_ship_channels():
    """Boarding a ship joins its comms channel: "<Manufacturer Model> : <owner>"."""
    ev = parse_line(note("You have joined channel 'RSI Constellation Taurus : Wing_Mate-7'.: "))
    assert ev.kind == "channel_join"
    assert ev.data == {"ship": "RSI Constellation Taurus", "owner": "Wing_Mate-7"}
    ev = parse_line(note("You have left the channel 'Origin M80 : TestPilot'."))
    assert ev.kind == "channel_left" and ev.data["ship"] == "Origin M80"
    # An untranslated name.
    ev = parse_line(note("You have joined channel '@vehicle_NameRSI_Perseus : TestPilot'."))
    assert ev.data["ship"] == "RSI Perseus"


def test_aboard_state():
    s = LogState()
    s.handle = ME
    join = parse_line(note("You have joined channel 'RSI Constellation Taurus : Wing'."))
    events = s.on_log(join, 1000)
    assert [e.kind for e in events] == ["boarded"]
    assert events[0].data == {"ship": "RSI Constellation Taurus", "owner": "Wing"}
    a = s.location(2000, None).aboard
    assert (a.ship, a.owner, a.since) == ("RSI Constellation Taurus", "Wing", 1000)
    assert s.on_log(join, 3000) == [], "the same channel again is not news"
    # Leaving a different ship's channel changes nothing.
    other = parse_line(note("You have left the channel 'Origin M80 : TestPilot'."))
    assert s.on_log(other, 4000) == [] and s.aboard is not None
    left = parse_line(note("You have left the channel 'RSI Constellation Taurus : Wing'."))
    assert [e.kind for e in s.on_log(left, 5000)] == ["disembarked"]
    assert s.location(6000, None) is None


@pytest.mark.parametrize("how", ["other ship", "server", "respawn", "new game"])
def test_aboard_ends_without_a_left_line(how):
    """Leaving isn't always logged: other things end it too."""
    s = LogState()
    s.on_log(parse_line(note("You have joined channel 'Origin M80 : TestPilot'.")), 0)
    s.on_log(parse_line(f"{TS}[Notice] <Update Shard Id> New Shard Id: pub_use1b_1_1."), 1)
    assert s.aboard is not None, "the first server of the session doesn't end it"
    if how == "other ship":
        s.on_log(parse_line(note("You have joined channel 'Drake Cutlass Black : Wing'.")), 10)
        assert s.aboard.ship == "Drake Cutlass Black"
        return
    if how == "server":
        s.on_log(parse_line(f"{TS}[Notice] <Update Shard Id> New Shard Id: pub_use1b_1_2."), 10)
    elif how == "respawn":
        s.respawned()
    else:
        s.reset_session()
    assert s.aboard is None


def test_pipeline_adds_the_handle_and_aboard():
    p = Pipeline()
    p.on_log(
        f"{TS}[Notice] <Legacy login response> [CIG-net] User Login Success - Handle[{ME}]",
        t=0,
    )
    p.on_log(note("You have joined channel 'Origin M80 : TestPilot'."), t=10)
    raw = next(raw for _, raw in read_frames(FIXTURES / "on-foot.jsonl.gz"))
    p.on_frame(raw, 20)
    snap = p.latest
    assert snap.status.handle == ME
    assert snap.location.aboard.ship == "Origin M80"
    # Shared under "location", the handle under "status".
    hidden = apply_sharing(snap, ["status"])
    assert hidden.location is None and hidden.status.handle == ME


def _four_legs(log: bool) -> list[str]:
    """The four-leg recording (legs of 1, 1, 2 and 25 s, 10-15 s apart), with or
    without its route in Game.log: the quantum events it makes."""
    p = Pipeline()
    events = []
    p.subscribe(lambda kind, payload: events.append(payload) if kind == "event" else None)
    frames = list(read_frames(Path(__file__).parents[2] / "fixtures" / "quantum-travel.jsonl.gz"))
    if log:
        p.on_log(SELECTED, frames[0][0])
    for t, raw in frames:
        p.on_frame(raw, t)
    if log:
        p.on_log(ARRIVED, frames[-1][0])
    return [e.kind for e in events if e.kind.startswith("quantum")]


def test_a_quantum_trip_is_one_jump_however_many_legs():
    """Players see one jump: no "dropped out" right after the first short leg."""
    assert _four_legs(log=True) == ["quantum_route", "quantum_start", "quantum_arrived"]


def test_without_game_log_each_leg_ends_on_its_own():
    assert _four_legs(log=False) == ["quantum_start", "quantum_end"] * 4
