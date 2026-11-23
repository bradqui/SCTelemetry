from pathlib import Path

from fleet_agent import client
from fleet_agent.capturefile import read_frames
from fleet_agent.normalize import Normalizer
from fleet_agent.replay import ReplayServer, default_fixtures

FIXTURES = Path(__file__).parents[2] / "fixtures"


def test_replay_roundtrip_matches_fixture():
    path = FIXTURES / "constellation-pilot-copilot-turret.jsonl.gz"
    server = ReplayServer([path], speed=0).start()  # speed 0 = no waiting
    try:
        channel = client.open_channel(port=server.port)
        assert client.wait_ready(channel, timeout=5)
        schema = client.load_schema(channel, exe=None)  # reflection: no exe needed
        assert schema.source == "reflection"
        streamed = [client.frame_to_dict(m) for m in client.stream_frames(channel, schema)]
        channel.close()
    finally:
        server.stop()

    original = [raw for _, raw in read_frames(path)]
    assert len(streamed) == len(original)

    a, b = Normalizer(), Normalizer()
    for i, (got, want) in enumerate(zip(streamed, original, strict=True)):
        sa = a.feed(got, i).model_dump(exclude={"uec"})
        sb = b.feed(want, i).model_dump(exclude={"uec"})
        assert sa == sb, f"frame {i} differs after replay"


def test_every_fixture_loads_for_replay():
    """Includes FLT_MAX altitudes (space) and scrubbed aUEC, which must survive the round trip."""
    server = ReplayServer(default_fixtures(FIXTURES), speed=0)
    try:
        response_cls = server.schema.response_class("TelemetryStream")
        alts = [
            response_cls.FromString(p).vehicle.state.flight.instruments.altitude
            for _, p in server.frames
        ]
        assert max(alts) > 3e38, "space altitude kept"
    finally:
        server.stop()


def test_default_fixture_order_is_a_session():
    files = default_fixtures(FIXTURES)
    assert files[0].name == "on-foot.jsonl.gz"
    assert len(files) == len(list(FIXTURES.glob("*.jsonl.gz")))


# ---------------------------------------------------------------- recording + playhead

from fleet_agent.replay import Playhead, Recording  # noqa: E402


def _recording(*names: str) -> Recording:
    return Recording.load([FIXTURES / f"{n}.jsonl.gz" for n in names])


def test_recording_indexes_chapters_and_events():
    rec = _recording("cruise-nav-scm", "combat")
    idx = rec.index()
    assert [c["title"] for c in idx["chapters"]] == ["Cruise nav scm", "Combat"]
    second = idx["chapters"][1]
    assert second["start"] > idx["chapters"][0]["end"]
    kinds = {m["kind"] for m in idx["markers"]}
    assert {"mode_change", "warning_on", "warning_off"} <= kinds
    # Combat's warnings sit inside the combat chapter.
    assert all(
        second["start"] <= m["pos"] <= second["end"]
        for m in idx["markers"]
        if m["kind"].startswith("warning")
    )
    assert idx["frames"] == len(rec.payloads)
    assert abs(idx["duration"] - rec.positions[-1]) < 0.001
    assert "vehicle" in rec.decode(0), "frames decode like the live stream"


def test_playhead_plays_pauses_seeks_and_steps():
    rec = _recording("cruise-nav-scm")
    ph = Playhead(rec, speed=16, loop=False)
    seq, got = -1, []
    for _ in range(20):
        tick = ph.wait_next(seq, timeout=1)
        assert tick is not None
        seq = tick.seq
        got.append(tick.index)
    assert got == list(range(got[0], got[0] + 20)), "frames in order"
    assert got[0] == 0 and tick.epoch == 0

    ph.pause()
    assert ph.wait_next(seq, timeout=0.2) is None, "paused: nothing new"

    ph.seek(30.0)
    tick = ph.wait_next(seq, timeout=1)
    assert tick.epoch == 1 and abs(rec.positions[tick.index] - 30.0) < 1
    seq = tick.seq

    ph.step(3)
    tick = ph.wait_next(seq, timeout=1)
    assert tick.epoch == 1, "stepping forward is not a jump"
    ph.step(-1)
    tick = ph.wait_next(tick.seq, timeout=1)
    assert tick.epoch == 2, "stepping back is a jump"
    assert ph.status()["paused"] is True

    ph.seek(rec.duration + 100)  # clamps to the last frame
    assert ph.status()["pos"] == round(rec.duration, 3)
    ph.close()
    assert ph.wait_next(-99, timeout=1) is None


def test_playhead_loops_as_a_jump():
    rec = _recording("on-foot")
    ph = Playhead(rec, speed=16, loop=True)
    statuses = []
    ph.subscribe(statuses.append)
    ph.seek(rec.duration)
    seq = ph.wait_next(-1).seq
    tick = ph.wait_next(seq, timeout=2)
    assert tick.index == 0 and tick.epoch == 2
    assert statuses, "listeners hear about the loop"
