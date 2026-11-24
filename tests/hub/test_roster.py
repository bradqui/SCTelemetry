"""The roster's cross-member parts: whose ship someone on foot is aboard."""

from starglance_hub.fleet import resolve_aboard


def row(mid, name, *, handle=None, ship=None, aboard=None):
    return {
        "id": mid,
        "name": name,
        "handle": handle,
        "ship": ship,
        "location": {"aboard": {**aboard, "owner_id": None, "ship_id": None}} if aboard else None,
    }


def test_aboard_resolves_the_owner_and_their_ship():
    roster = {
        "a": row(
            "a",
            "Wren",
            handle="Wren_SC",
            ship={"id": "RSI_Constellation_Taurus_1", "model": "Constellation Taurus"},
        ),
        "b": row(
            "b",
            "Kestrel",
            aboard={"ship": "RSI Constellation Taurus", "owner": "wren_sc", "since": 1},
        ),
        # Matched by display name when the handle isn't known; flying something else.
        "c": row("c", "Pike", ship={"id": "DRAK_Cutlass_Black_2", "model": "Cutlass Black"}),
        "d": row("d", "Nova", aboard={"ship": "Origin M80", "owner": "Pike", "since": 1}),
        # Not a member.
        "e": row("e", "Vale", aboard={"ship": "Argo MOLE", "owner": "Stranger", "since": 1}),
    }
    resolve_aboard(roster)
    b = roster["b"]["location"]["aboard"]
    assert (b["owner_id"], b["ship_id"]) == ("a", "RSI_Constellation_Taurus_1")
    d = roster["d"]["location"]["aboard"]
    assert (d["owner_id"], d["ship_id"]) == ("c", None), "Pike's flying a different ship"
    e = roster["e"]["location"]["aboard"]
    assert (e["owner_id"], e["ship_id"]) == (None, None)


def test_handles_win_over_display_names():
    roster = {
        "a": row("a", "Ace", handle="Real_Ace"),
        "b": row("b", "Real_Ace"),  # someone else picked that display name
        "c": row("c", "Mara", aboard={"ship": "Origin M80", "owner": "Real_Ace", "since": 1}),
    }
    resolve_aboard(roster)
    assert roster["c"]["location"]["aboard"]["owner_id"] == "a"


def test_model_names_match_channel_names():
    """Class-derived models vs the channel's marketing names."""
    for model, channel in [
        ("Constellation Mk5 Centaurus", "RSI Constellation Mk V Centaurus"),
        ("Hornet F7A Mk2", "Anvil F7A Hornet Mk II"),
        ("Spirit C1", "Crusader C1 Spirit"),
        ("C8R Pisces", "Anvil C8R Pisces Rescue"),
        ("M80", "Origin M80"),
    ]:
        roster = {
            "a": row("a", "Owner", ship={"id": "ship_1", "model": model}),
            "b": row("b", "Crew", aboard={"ship": channel, "owner": "Owner", "since": 1}),
        }
        resolve_aboard(roster)
        assert roster["b"]["location"]["aboard"]["ship_id"] == "ship_1", (model, channel)


def test_fleet_alarm_lights():
    from starglance_shared import fleet_alarm_lights

    assert fleet_alarm_lights({"hit": "major_flashing"}) == {"hit": "major"}
    assert fleet_alarm_lights({"radr": "major"}) == {"radr": "major"}
    # No cautions (thruster damage lasts minutes); routine lights: shields coming back,
    # weapons not ready while landed, proximity, the quantum drive's THR.
    quiet = {"thr": "minor", "shld": "major", "wpn": "minor", "prox": "major", "cool": "nominal"}
    assert fleet_alarm_lights(quiet) == {}
    assert fleet_alarm_lights({"thr": "major"}) == {}


def test_fleet_alarm_is_held():
    """On for a second before the fleet hears it; kept until off for three (between hits)."""
    from starglance_hub.db import Member
    from starglance_hub.fleet import MemberLive, _fleet_alarm

    m = MemberLive(Member("m1", "Rook", None, "member", 1, 0))

    def at(t, **lights):
        return _fleet_alarm(m, {"lights": lights, "master_mode": "SCM"}, t)

    assert at(0, shld="major") == (None, [])
    assert at(200, shld="nominal") == (None, []), "a shield blip never shows"
    assert at(1000, hit="major_flashing") == (None, [])
    assert at(1900, hit="major_flashing") == (None, [])
    assert at(2000, hit="major_flashing") == ("major", ["hit"])
    assert at(4000) == ("major", ["hit"]), "a gap between hits"
    assert at(4500, hit="major_flashing") == ("major", ["hit"])
    assert at(7600) == (None, []), "clear after 3 s"
    assert at(8000, radr="major") == (None, [])
    assert at(9100, radr="major") == ("major", ["radr"])
    assert at(9200, radr="major", thr="minor") == ("major", ["radr"]), "no cautions"
