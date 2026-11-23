"""The gRPC client against a fake local game server built from the synthetic schema."""

from concurrent import futures

import grpc
import pytest
from fleet_agent import client, protoset
from fleet_agent.schema import TelemetrySchema
from google.protobuf import json_format
from grpc_reflection.v1alpha import reflection

from .test_protoset import fake_exe, make_files

FRAMES = [
    {"crew_role": "pilot", "health": {"current": 90, "max": 100}},
    {"crew_role": "gunner"},
    {},
]


@pytest.fixture
def schema() -> TelemetrySchema:
    result = protoset.extract_from_buffer(fake_exe(make_files()))
    return TelemetrySchema.from_file_set(result.file_set, "test")


def _serve(schema: TelemetrySchema, with_reflection: bool):
    response_cls = schema.response_class("TelemetryStream")
    request_cls = schema.request_class("TelemetryStream")

    def stream(_request, _context):
        for frame in FRAMES:
            yield json_format.ParseDict(frame, response_cls())

    handler = grpc.method_handlers_generic_handler(
        schema.service.full_name,
        {
            "TelemetryStream": grpc.unary_stream_rpc_method_handler(
                stream,
                request_deserializer=request_cls.FromString,
                response_serializer=response_cls.SerializeToString,
            )
        },
    )
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    server.add_generic_rpc_handlers((handler,))
    if with_reflection:
        reflection.enable_server_reflection(
            (schema.service.full_name, reflection.SERVICE_NAME), server, pool=schema.pool
        )
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    return server, port


@pytest.mark.parametrize("with_reflection", [True, False])
def test_stream_frames(schema, tmp_path, monkeypatch, with_reflection):
    monkeypatch.setenv("FLEET_TELEMETRY_HOME", str(tmp_path / "home"))
    exe = tmp_path / "StarCitizen.exe"
    exe.write_bytes(fake_exe(make_files()))

    server, port = _serve(schema, with_reflection)
    try:
        channel = client.open_channel(port=port)
        assert client.wait_ready(channel, timeout=5)
        loaded = client.load_schema(channel, exe)
        assert loaded.source == "reflection" if with_reflection else loaded.source.startswith("exe")

        frames = [client.frame_to_dict(m) for m in client.stream_frames(channel, loaded)]
        assert [f["crew_role"] for f in frames] == ["pilot", "gunner", ""]
        assert frames[0]["health"] == {"current": 90.0, "max": 100.0}
        channel.close()
    finally:
        server.stop(None)


def test_remote_hosts_refused():
    with pytest.raises(ValueError):
        client.open_channel("192.168.1.10")
