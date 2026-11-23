"""Committed fixtures are readable, scrubbed, and contain what their names promise."""

import gzip
import json
from pathlib import Path

import pytest
from fleet_agent import scrub

FIXTURES = sorted((Path(__file__).parents[1] / "fixtures").glob("*.jsonl.gz"))


def records(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            yield json.loads(line)


def uec_values(value):
    if isinstance(value, dict):
        for k, v in value.items():
            if scrub.is_uec_key(k):
                yield v
            yield from uec_values(v)
    elif isinstance(value, list):
        for v in value:
            yield from uec_values(v)


def test_fixtures_exist():
    assert len(FIXTURES) >= 10


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_fixture_is_valid_and_scrubbed(path):
    frames = [r["frame"] for r in records(path) if "frame" in r]
    assert frames, "fixture has frames"
    assert all("actor" in f for f in frames), "actor is in every frame"
    assert all(v == scrub.SCRUBBED for f in frames for v in uec_values(f)), "aUEC scrubbed"


def test_constellation_seats_and_roles():
    path = next(p for p in FIXTURES if p.name.startswith("constellation"))
    seen = {
        (
            f["actor"]["state"]["seat_name"].split("_SeatDashboard")[0],
            f["actor"]["state"]["crew_role"],
        )
        for r in records(path)
        if "frame" in r and "vehicle" in (f := r["frame"])
    }
    assert ("RSI_Constellation_Mk5_CoPilot", "ACTOR_CREW_ROLE_PILOT") in seen
    assert ("RSI_Constellation_Mk5_Gunner_Right", "ACTOR_CREW_ROLE_CREW") in seen


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_fixture_log_lines_are_scrubbed(path):
    """Game.log lines in fixtures: your handle is TestPilot, other players Wingmate, no address."""
    import re

    lines = [r["log"] for r in records(path) if "log" in r]
    for line in lines:
        if "Handle[" in line:
            assert "Handle[TestPilot]" in line
        for name in re.findall(r"killer '([^']*)'", line):
            assert name in ("TestPilot", "Wingmate") or not name[:1].islower() or "_" in name
        assert "address[" not in line or "address[0.0.0.0]" in line
