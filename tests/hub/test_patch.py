"""Merge patches between states (starglance_shared.patch)."""

import json
from pathlib import Path

import pytest
from starglance.capturefile import read_frames
from starglance.normalize import Normalizer
from starglance_shared import apply_patch, make_patch

FIXTURES = Path(__file__).parents[2] / "fixtures"


def roundtrip(old, new):
    patch = make_patch(old, new)
    assert (apply_patch(old, patch) if patch is not None else old) == new
    return patch


def test_unchanged_is_none():
    assert make_patch({"a": 1, "b": {"c": [1, 2]}}, {"a": 1, "b": {"c": [1, 2]}}) is None


def test_only_changes_are_sent():
    patch = roundtrip(
        {"t": 1, "ship": {"model": "M80", "flight": {"speed": 10.0, "g": 1.0}}},
        {"t": 2, "ship": {"model": "M80", "flight": {"speed": 12.5, "g": 1.0}}},
    )
    assert patch == {"t": 2, "ship": {"flight": {"speed": 12.5}}}


@pytest.mark.parametrize(
    "old, new",
    [
        ({"ship": None}, {"ship": {"id": "x", "flight": {"speed": 1}}}),  # boarded
        ({"ship": {"id": "x"}}, {"ship": None}),  # left the ship
        ({"guns": [1, 2]}, {"guns": [1]}),  # lists replace
        ({"flag": 1}, {"flag": True}),  # 1 == True in Python, but not on the wire
        ({}, {"new": {"deep": 1}}),
    ],
)
def test_roundtrips(old, new):
    patch = roundtrip(old, new)
    assert patch is not None


def test_a_key_that_disappears_becomes_null():
    patch = make_patch({"lights": {"hit": "major", "pwr": "off"}}, {"lights": {"pwr": "off"}})
    assert patch == {"lights": {"hit": None}}
    assert apply_patch({"lights": {"hit": "major"}}, patch) == {"lights": {"hit": None}}


def test_patch_doesnt_modify_its_input():
    old = {"a": {"b": 1}}
    apply_patch(old, {"a": {"b": 2}})
    assert old == {"a": {"b": 1}}


def test_real_snapshots_shrink_to_a_few_fields():
    """Consecutive frames of the combat fixture: the patch is a fraction of the snapshot."""
    norm = Normalizer()
    states = [
        json.loads(norm.feed(raw, t).model_dump_json(by_alias=True))
        for t, raw in read_frames(FIXTURES / "combat.jsonl.gz")
    ][:400]
    sizes = []
    for old, new in zip(states, states[1:], strict=False):
        patch = roundtrip(old, new)
        if patch:
            sizes.append(len(json.dumps(patch)))
    full = len(json.dumps(states[-1]))
    median = sorted(sizes)[len(sizes) // 2]
    assert median < full / 5
