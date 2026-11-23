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


def test_default_fixture_order_is_a_session():
    files = default_fixtures(FIXTURES)
    assert files[0].name == "on-foot.jsonl.gz"
    assert len(files) == len(list(FIXTURES.glob("*.jsonl.gz")))
