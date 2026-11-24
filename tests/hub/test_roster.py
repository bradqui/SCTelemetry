"""The roster's cross-member parts: whose ship someone on foot is aboard."""

from fleet_hub.fleet import resolve_aboard


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
