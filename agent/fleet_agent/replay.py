"""A fake ``GameTelemetryService`` that plays captured frames back (spec §8 Phase 1).

Lets the agent, hub and UI be developed and tested without the game, on any OS.
Each client that calls ``TelemetryStream`` gets the recording from the start,
at the recorded pace (``speed`` scales it), optionally looping.

The server also offers gRPC reflection, so the agent needs neither
``StarCitizen.exe`` nor a protoset to talk to it.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable
from concurrent import futures
from pathlib import Path

import grpc
from google.protobuf import json_format
from grpc_reflection.v1alpha import reflection

from .capturefile import read_frames
from .schema import TelemetrySchema
from .scrub import SCRUBBED

log = logging.getLogger(__name__)

DEFAULT_PROTOSET = Path(__file__).resolve().parents[2] / "fixtures" / "telemetry.protoset"

SESSION_ORDER = (
    "on-foot",
    "on-foot-helmet",
    "sit-power-takeoff-gear",
    "cruise-nav-scm",
    "quantum-travel",
    "landing-leave-seat",
    "combat",
    "leave-seat-eva-reseat",
    "hangar-landing-refuel",
    "constellation-pilot-copilot-turret",
)
"""Fixtures in an order that plays like one session."""

MAX_GAP_S = 2.0
"""Pause between fixtures (and any long gap inside one) is capped at this."""


def default_fixtures(fixtures_dir: Path) -> list[Path]:
    ordered = [fixtures_dir / f"{n}.jsonl.gz" for n in SESSION_ORDER]
    present = [p for p in ordered if p.exists()]
    extra = sorted(p for p in fixtures_dir.glob("*.jsonl.gz") if p not in present)
    return present + extra


def _drop_scrubbed(value):
    """Scrubbed fields are strings like "<scrubbed>", which won't parse back into an int64."""
    if isinstance(value, dict):
        return {k: _drop_scrubbed(v) for k, v in value.items() if v != SCRUBBED}
    if isinstance(value, list):
        return [_drop_scrubbed(v) for v in value]
    return value


def load_messages(schema: TelemetrySchema, paths: Iterable[Path]) -> list[tuple[float, bytes]]:
    """(delay before this frame in seconds, serialized response) for every frame."""
    response_cls = schema.response_class("TelemetryStream")
    out: list[tuple[float, bytes]] = []
    for path in paths:
        last_t = None
        for t, raw in read_frames(path):
            delay = 0.0 if last_t is None else min((t - last_t) / 1000, MAX_GAP_S)
            if last_t is None and out:
                delay = MAX_GAP_S / 2
            last_t = t
            msg = json_format.ParseDict(
                _drop_scrubbed(raw), response_cls(), ignore_unknown_fields=True
            )
            out.append((delay, msg.SerializeToString()))
    return out


class ReplayServer:
    def __init__(
        self,
        paths: list[Path],
        *,
        port: int = 0,
        speed: float = 1.0,
        loop: bool = False,
        protoset: Path = DEFAULT_PROTOSET,
    ):
        self.schema = TelemetrySchema.from_protoset(protoset)
        self.frames = load_messages(self.schema, paths)
        self.speed = speed
        self.loop = loop
        request_cls = self.schema.request_class("TelemetryStream")

        handler = grpc.method_handlers_generic_handler(
            self.schema.service.full_name,
            {
                "TelemetryStream": grpc.unary_stream_rpc_method_handler(
                    self._stream,
                    request_deserializer=request_cls.FromString,
                    response_serializer=lambda b: b,  # already serialized
                )
            },
        )
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
        self.server.add_generic_rpc_handlers((handler,))
        reflection.enable_server_reflection(
            (self.schema.service.full_name, reflection.SERVICE_NAME),
            self.server,
            pool=self.schema.pool,
        )
        self.port = self.server.add_insecure_port(f"127.0.0.1:{port}")
        if not self.port:
            raise OSError(f"Couldn't listen on 127.0.0.1:{port} (is the game using it?)")

    def _stream(self, _request, context):
        log.info("Client connected; replaying %d frames", len(self.frames))
        while True:
            for delay, payload in self.frames:
                if not context.is_active():
                    return
                if delay and self.speed > 0:
                    time.sleep(delay / self.speed)
                yield payload
            if not self.loop:
                return

    def start(self) -> ReplayServer:
        self.server.start()
        return self

    def stop(self) -> None:
        self.server.stop(grace=None)
