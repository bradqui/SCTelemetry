"""gRPC client for the game's local telemetry server (127.0.0.1:50051, plaintext).

Read-only for now: only ``TelemetryStream`` is called. ``TriggerGameAction`` is a
later, local-only phase (spec §7).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import grpc
from google.protobuf import json_format

from . import paths, protoset
from .schema import TelemetrySchema

log = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 50051
STREAM_METHOD = "TelemetryStream"


def open_channel(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> grpc.Channel:
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("The game's telemetry server is local-only; refusing a remote host.")
    return grpc.insecure_channel(
        f"{host}:{port}", options=[("grpc.max_receive_message_length", 16 * 1024 * 1024)]
    )


def wait_ready(channel: grpc.Channel, timeout: float) -> bool:
    try:
        grpc.channel_ready_future(channel).result(timeout=timeout)
        return True
    except grpc.FutureTimeoutError:
        return False


def load_schema(
    channel: grpc.Channel, exe: Path | None = None, *, prefer_reflection: bool = True
) -> TelemetrySchema:
    """Reflection first (if the server offers it), else definitions extracted from the exe."""
    if prefer_reflection:
        try:
            return TelemetrySchema.from_reflection(channel)
        except grpc.RpcError as exc:
            log.info("Server reflection unavailable (%s); using the exe instead.", exc.code())
        except KeyError as exc:
            log.info("Reflection didn't list the telemetry service (%s); using the exe.", exc)
    if exe is None:
        raise RuntimeError("Reflection is unavailable and no StarCitizen.exe path was given.")
    file_set, cached = protoset.load_or_extract(exe, paths.protoset_cache_dir())
    return TelemetrySchema.from_file_set(file_set, f"exe ({cached.name})")


def stream_frames(
    channel: grpc.Channel, schema: TelemetrySchema, request: dict | None = None
) -> Iterator:
    """Yield ``TelemetryStreamResponse`` messages until the stream ends or errors."""
    request_cls = schema.request_class(STREAM_METHOD)
    response_cls = schema.response_class(STREAM_METHOD)
    call = channel.unary_stream(
        schema.path(STREAM_METHOD),
        request_serializer=request_cls.SerializeToString,
        response_deserializer=response_cls.FromString,
    )
    req = json_format.ParseDict(request or {}, request_cls())
    yield from call(req)


def frame_to_dict(message) -> dict:
    """Spec §2.3: field names as in the .proto, zero/empty fields included so every name shows."""
    try:
        return json_format.MessageToDict(
            message,
            preserving_proto_field_name=True,
            always_print_fields_with_no_presence=True,
        )
    except TypeError:  # older protobuf
        return json_format.MessageToDict(
            message, preserving_proto_field_name=True, including_default_value_fields=True
        )
