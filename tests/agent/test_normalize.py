"""The normalizer and event deriver against every real fixture (spec §8 Phase 1 tests)."""

from collections import Counter
from pathlib import Path

import pytest
from fleet_agent.capturefile import read_frames
from fleet_agent.events import EventDeriver
from fleet_agent.normalize import Normalizer, model_name, raw_game_events, seat_role
from fleet_shared import Snapshot, apply_sharing

FIXTURES = Path(__file__).parents[2] / "fixtures"
ALL = sorted(FIXTURES.glob("*.jsonl.gz"))


def run(name: str) -> tuple[list[Snapshot], list]:
    norm, deriver = Normalizer(), EventDeriver()
    snaps, events = [], []
    for t, raw in read_frames(FIXTURES / f"{name}.jsonl.gz"):
        snap = norm.feed(raw, t)
        snaps.append(snap)
        events.extend(deriver.feed(snap, raw_game_events(raw)))
    return snaps, events


def kinds(events) -> list[str]:
    return [e.kind for e in events]


@pytest.mark.parametrize("path", ALL, ids=lambda p: p.name)
def test_every_fixture_normalizes_and_serializes(path):
    snaps, _ = run(path.name.removesuffix(".jsonl.gz"))
    assert snaps
    for s in snaps:
        assert s.status is not None and s.status.locomotion != "unknown"
        assert s.vitals is not None
        assert s.uec is None, "fixtures are scrubbed, so uec must come out as None"
        Snapshot.model_validate_json(s.model_dump_json(by_alias=True))  # round-trips


def test_on_foot_has_no_ship():
    snaps, events = run("on-foot")
    assert all(s.ship is None and s.weapons is None for s in snaps)
    assert {s.status.locomotion for s in snaps} == {"on_foot"}
    assert snaps[0].vitals.health == 1.0 and snaps[0].vitals.environment.breathable is True
    assert events == []


def test_sit_power_takeoff_gear():
    snaps, events = run("sit-power-takeoff-gear")
    ships = [s.ship for s in snaps if s.ship]
    assert ships[0].id.startswith("ORIG_m80_")
    assert ships[0].model == "M80" and ships[0].manufacturer == "Origin Jumpworks"
    assert ships[0].type == "spaceship"

    k = kinds(events)
    assert k.count("seat_enter") == 1, "derived from state even though the game sent no event"
    assert "takeoff" in k
    roles = [s.status.role for s in snaps if s.ship]
    assert set(roles) == {"pilot"}, "the PILOT/UNSPECIFIED flicker is smoothed"

    gears = [s.ship.gear for s in snaps if s.ship]
    changes = [g for i, g in enumerate(gears) if i == 0 or g != gears[i - 1]]
    assert changes[:4] == ["deployed", "retracting", "retracted", "deploying"]
    assert all(s.ship.flight.h2_fuel != 0 for s in snaps if s.ship)
    assert all(s.ship.flight.qt_fuel is None for s in snaps if s.ship)
    assert any(s.ship.powered is False for s in snaps if s.ship), "power cycle seen"
    assert all(s.ship.master_mode is None for s in snaps if s.ship and s.ship.powered is False)


def test_nav_scm_inferred():
    snaps, events = run("cruise-nav-scm")
    modes = [e.data["mode"] for e in events if e.kind == "mode_change"]
    assert modes == ["SCM", "NAV"]
    # Shield power follows the mode; the qdrv light can lead it by a frame.
    mismatched = [
        s
        for s in snaps
        if s.ship and s.ship.master_mode and s.ship.shields.powered != (s.ship.master_mode == "SCM")
    ]
    assert len(mismatched) <= 3


def test_quantum_travel_altitude_in_space_is_none():
    snaps, _ = run("quantum-travel")
    alts = [s.ship.flight.alt for s in snaps if s.ship]
    assert None in alts, "FLT_MAX in space becomes None"
    assert any(a is not None for a in alts)


def test_quantum_travel_is_inferred():
    """Speed and G freeze for the whole jump while the heading still drifts."""
    snaps, events = run("quantum-travel")
    t0 = snaps[0].t
    on = [(s.t - t0) / 1000 for s in snaps if s.ship and s.ship.flight.quantum]
    assert on, "the jump is detected"
    # In this slice the jump starts ~18 s in and ends when speed returns at ~87 s.
    assert 15 < on[0] < 20 and 84 < on[-1] < 88
    assert kinds(events).count("quantum_start") == 1
    assert kinds(events).count("quantum_end") == 1
    # Sitting still at 23 km before the jump (speed 0) is not quantum travel.
    assert not any(s.ship.flight.quantum for s in snaps if s.ship and (s.t - t0) / 1000 < 15)


@pytest.mark.parametrize("path", [p for p in ALL if "quantum" not in p.name], ids=lambda p: p.name)
def test_no_quantum_travel_elsewhere(path):
    """Includes stopping dead in space (speed 0, g 0), which must not count."""
    norm = Normalizer()
    for t, raw in read_frames(path):
        snap = norm.feed(raw, t)
        assert not (snap.ship and snap.ship.flight.quantum), f"false quantum at {t}"


def test_landing_and_leaving_seat():
    snaps, events = run("landing-leave-seat")
    k = kinds(events)
    assert k.index("landed") < k.index("seat_leave")
    assert snaps[-1].ship is None and snaps[-1].status.seat is None


def test_combat_warnings_are_not_spammy():
    snaps, events = run("combat")
    hits = [e for e in events if e.data.get("light") == "hit"]
    assert any(e.kind == "warning_on" for e in hits)
    # The hit light flashed ~25 times in this window; with the hold it's a few on/off pairs.
    assert len(hits) <= 12
    scm_unshielded = [
        s
        for s in snaps
        if s.ship and s.ship.master_mode == "SCM" and s.ship.shields.powered is False
    ]
    assert scm_unshielded, "shields knocked out while staying in SCM"


def test_eva_debounced():
    snaps, events = run("leave-seat-eva-reseat")
    locos = [s.status.locomotion for s in snaps]
    changes = [x for i, x in enumerate(locos) if i == 0 or x != locos[i - 1]]
    assert "eva" in changes
    assert len(changes) <= 6, f"flicker should be smoothed: {changes}"
    assert any(s.vitals.environment.temperature == -273.15 for s in snaps)
    assert Counter(kinds(events))["seat_enter"] == 1


def test_constellation_seat_roles():
    snaps, events = run("constellation-pilot-copilot-turret")
    roles = [e.data["role"] for e in events if e.kind == "seat_enter"]
    assert roles == ["pilot", "copilot", "gunner"]
    assert Counter(kinds(events))["seat_leave"] == 3
    models = {s.ship.model for s in snaps if s.ship}
    assert models == {"Constellation Mk5 Centaurus"}
    assert not any(e.kind == "ship_change" for e in events), "same ship, different seats"


def test_ship_change_across_fixtures():
    norm, deriver = Normalizer(), EventDeriver()
    events = []
    for name in ("hangar-landing-refuel", "constellation-pilot-copilot-turret"):
        for t, raw in read_frames(FIXTURES / f"{name}.jsonl.gz"):
            events.extend(deriver.feed(norm.feed(raw, t)))
    changes = [e for e in events if e.kind == "ship_change"]
    assert len(changes) == 1 and changes[0].data["model"] == "Constellation Mk5 Centaurus"


def test_refuel_fuel_rises():
    snaps, _ = run("hangar-landing-refuel")
    fuel = [s.ship.flight.h2_fuel for s in snaps if s.ship and s.ship.flight.h2_fuel is not None]
    assert max(fuel) > 0.99 and min(fuel) < 0.9


# ---------------------------------------------------------------- unit bits


def test_unknown_shapes_do_not_raise():
    norm = Normalizer()
    for raw in ({}, {"actor": "nonsense"}, {"vehicle": {"state": {"name": 5}}}, {"brand_new": {}}):
        snap = norm.feed(raw, 1)
        assert snap.status is not None


def test_unknown_enum_values_are_dropped():
    norm = Normalizer()
    raw = {
        "actor": {"state": {"locomotion": "ACTOR_LOCOMOTION_STATE_JETPACK"}},
        "vehicle": {
            "state": {
                "name": "ANVL_Hornet_123456789",
                "class_name": "ANVL_Hornet",
                "type": "VEHICLE_TYPE_SPACESTATION",
                "annunciators": {
                    "hit": "ANNUNCIATOR_STATE_PLAID",
                    "pwr": "ANNUNCIATOR_STATE_NOMINAL",
                },
                "flight": {"state": {"gear": "VEHICLE_COMPONENT_DEPLOYMENT_STATE_EXPLODED"}},
            }
        },
    }
    snap = norm.feed(raw, 1)
    assert snap.status.locomotion == "unknown"
    assert snap.ship.type == "unknown" and snap.ship.gear is None
    assert snap.ship.lights == {"pwr": "nominal"}
    assert snap.ship.manufacturer == "Anvil Aerospace"


def test_hull_and_shield_level_used_if_the_game_adds_them():
    raw = {
        "vehicle": {
            "state": {
                "name": "X_1234567",
                "class_name": "AEGS_Gladius",
                "health": {"current": 60, "max": 100},
                "shields": {"level": 0.4},
            }
        }
    }
    ship = Normalizer().feed(raw, 1).ship
    assert ship.hull == 0.6 and ship.shields.level == 0.4


def test_hull_threshold_events():
    norm, deriver = Normalizer(), EventDeriver()
    out = []
    for t, hp in enumerate((100, 80, 70, 40, 20)):
        raw = {
            "vehicle": {
                "state": {
                    "name": "S_1234567",
                    "class_name": "AEGS_Gladius",
                    "health": {"current": hp, "max": 100},
                }
            }
        }
        out.extend(deriver.feed(norm.feed(raw, t)))
    assert [e.data["below"] for e in out if e.kind == "hull_threshold"] == [0.75, 0.5, 0.25]


@pytest.mark.parametrize(
    "seat,crew,expected",
    [
        ("Orig_m80_Seat_Pilot", "pilot", "pilot"),
        ("RSI_Constellation_Mk5_CoPilot_SeatDashboard", "pilot", "copilot"),
        ("RSI_Constellation_Mk5_Gunner_Right_SeatDashboard", "crew", "gunner"),
        ("Some_Bed", "crew", "crew"),
        ("Some_Seat", None, "crew"),
    ],
)
def test_seat_role(seat, crew, expected):
    assert seat_role(seat, crew) == expected


def test_model_name():
    assert model_name("RSI_Constellation_Mk5_Centaurus") == "Constellation Mk5 Centaurus"
    assert model_name("ORIG_m80") == "M80"


def test_privacy_filter_removes_unshared():
    snaps, _ = run("sit-power-takeoff-gear")
    snap = next(s for s in snaps if s.ship)
    filtered = apply_sharing(snap, {"status", "ship"})
    assert filtered.ship is not None and filtered.status is not None
    assert filtered.weapons is None and filtered.vitals is None and filtered.uec is None
    body = filtered.model_dump_json(by_alias=True)
    assert '"vitals":null' in body and '"heart_rate"' not in body


def test_heading_is_unknown_in_deep_space():
    """Away from planets (altitude FLT_MAX) the game repeats a stale heading."""
    snaps, _ = run("combat")
    ships = [s.ship.flight for s in snaps if s.ship]
    assert ships and all(f.alt is None for f in ships), "the fight is in deep space"
    assert all(f.heading is None for f in ships)
    near, _ = run("sit-power-takeoff-gear")
    assert any(s.ship and s.ship.flight.heading is not None for s in near)


def _deep_space_stop(qdrv: str):
    """A frame in deep space with the instruments frozen: speed 0, G 0, heading still."""
    import copy

    template = next(
        raw for _, raw in read_frames(FIXTURES / "combat.jsonl.gz") if raw.get("vehicle")
    )
    raw = copy.deepcopy(template)
    state = raw["vehicle"]["state"]
    inst = state["flight"]["instruments"]
    inst["speed"], inst["g_meter"]["current"], inst["heading"] = 0.0, 0.0, 268.0939
    state["annunciators"]["qdrv"] = f"ANNUNCIATOR_STATE_{qdrv}"
    return raw


@pytest.mark.parametrize(
    "route, qdrv, expected",
    [
        (False, "NOMINAL", False),  # stopped in NAV, no route plotted
        (True, "OFF", False),  # route plotted but in SCM: can't be jumping
        (True, "NOMINAL", True),  # route plotted, drive lit, instruments frozen
    ],
)
def test_deep_space_quantum_needs_a_route(route, qdrv, expected):
    norm = Normalizer()
    norm.route_active = route
    raw = _deep_space_stop(qdrv)
    snaps = [norm.feed(raw, t) for t in range(0, 3000, 50)]
    assert snaps[-1].ship.flight.quantum is expected
    assert not snaps[0].ship.flight.quantum, "needs to stay frozen for a second first"
