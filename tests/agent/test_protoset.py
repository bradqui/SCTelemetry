"""Extraction against a synthetic 'exe': real FileDescriptorProtos buried in noise."""

import random

import pytest
from fleet_agent import protoset
from fleet_agent.schema import TelemetrySchema
from google.protobuf import descriptor_pb2, json_format

F = descriptor_pb2.FieldDescriptorProto


def _msg(name: str, *fields: tuple[str, int, int, str | None]) -> descriptor_pb2.DescriptorProto:
    m = descriptor_pb2.DescriptorProto(name=name)
    for fname, number, ftype, type_name in fields:
        f = m.field.add(name=fname, number=number, type=ftype, label=F.LABEL_OPTIONAL)
        if type_name:
            f.type_name = type_name
    return m


def make_files() -> list[descriptor_pb2.FileDescriptorProto]:
    common = descriptor_pb2.FileDescriptorProto(
        name="sc/game/common/v1/types.proto", package="sc.game.common.v1", syntax="proto3"
    )
    common.message_type.append(
        _msg("Meter", ("current", 1, F.TYPE_FLOAT, None), ("max", 2, F.TYPE_FLOAT, None))
    )

    tel = descriptor_pb2.FileDescriptorProto(
        name="sc/game/telemetry/v1/telemetry.proto",
        package="sc.game.telemetry.v1",
        syntax="proto3",
        dependency=["sc/game/common/v1/types.proto", "google/protobuf/timestamp.proto"],
    )
    tel.message_type.append(_msg("TelemetryStreamRequest"))
    tel.message_type.append(
        _msg(
            "TelemetryStreamResponse",
            ("health", 1, F.TYPE_MESSAGE, ".sc.game.common.v1.Meter"),
            ("crew_role", 2, F.TYPE_STRING, None),
            ("at", 3, F.TYPE_MESSAGE, ".google.protobuf.Timestamp"),
        )
    )
    svc = tel.service.add(name="GameTelemetryService")
    svc.method.add(
        name="TelemetryStream",
        input_type=".sc.game.telemetry.v1.TelemetryStreamRequest",
        output_type=".sc.game.telemetry.v1.TelemetryStreamResponse",
        server_streaming=True,
    )
    return [common, tel]


def fake_exe(files, seed=7) -> bytes:
    rng = random.Random(seed)
    parts = [b"MZ" + bytes(rng.randrange(256) for _ in range(5000))]
    for f in files:
        parts.append(b"\x00" * 8)  # padding, as in a real .rdata section
        parts.append(f.SerializeToString())
        parts.append(b"\x00" * 3 + bytes(rng.randrange(256) for _ in range(3000)))
    # A decoy: the name appearing as a plain string, not as a file's name field.
    parts.append(b"see sc/game/telemetry/v1/telemetry.proto for details\x00")
    return b"".join(parts)


def test_extracts_files_and_dependencies():
    files = make_files()
    result = protoset.extract_from_buffer(fake_exe(files))

    names = [f.name for f in result.file_set.file]
    assert result.service_file == "sc/game/telemetry/v1/telemetry.proto"
    assert result.missing == []
    assert set(names) == {
        "sc/game/common/v1/types.proto",
        "google/protobuf/timestamp.proto",
        "sc/game/telemetry/v1/telemetry.proto",
    }
    assert names[-1] == "sc/game/telemetry/v1/telemetry.proto", "dependencies come first"
    for original in files:
        got = next(f for f in result.file_set.file if f.name == original.name)
        assert got == original


def test_schema_builds_usable_message_classes():
    result = protoset.extract_from_buffer(fake_exe(make_files()))
    schema = TelemetrySchema.from_file_set(result.file_set, "test")
    assert (
        schema.path("TelemetryStream")
        == "/sc.game.telemetry.v1.GameTelemetryService/TelemetryStream"
    )

    Response = schema.response_class("TelemetryStream")
    msg = json_format.ParseDict(
        {"health": {"current": 50, "max": 100}, "crew_role": "pilot"}, Response()
    )
    again = Response.FromString(msg.SerializeToString())
    assert (
        json_format.MessageToDict(again, preserving_proto_field_name=True)["crew_role"] == "pilot"
    )


def test_only_name_fields_count_as_files():
    data = b"\x00junk sc/game/telemetry/v1/other.proto junk\x00"
    assert protoset.telemetry_file_names(data) == []
    with pytest.raises(protoset.ExtractionError):
        protoset.extract_from_buffer(data)


def test_missing_dependency_reported():
    files = make_files()
    result = protoset.extract_from_buffer(fake_exe(files[1:]))  # no common/types.proto
    assert "sc/game/common/v1/types.proto" in result.missing
    assert not result.has_service


def test_load_or_extract_caches(tmp_path):
    exe = tmp_path / "StarCitizen.exe"
    exe.write_bytes(fake_exe(make_files()))
    file_set, cached = protoset.load_or_extract(exe, tmp_path / "cache")
    assert cached.exists()
    again, cached2 = protoset.load_or_extract(exe, tmp_path / "cache")
    assert cached2 == cached and again == file_set


@pytest.mark.parametrize("length", [5, 127, 128, 300, 16384])
def test_varint_roundtrip(length):
    encoded = protoset.encode_varint(length)
    assert protoset._read_varint(encoded, 0, len(encoded)) == (length, len(encoded))
