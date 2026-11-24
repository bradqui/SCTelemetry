"""Play captured telemetry back without the game (spec §8 Phase 1).

Two ways to use a recording:

- ``ReplayServer``: a fake ``GameTelemetryService`` over gRPC. Each client that
  calls ``TelemetryStream`` gets the recording from the start, at the recorded
  pace (``speed`` scales it), optionally looping. It offers gRPC reflection, so
  the agent needs neither ``StarCitizen.exe`` nor a protoset to talk to it.
- ``Playhead``: one shared, controllable position in a ``Recording`` (play,
  pause, speed, seek, step). ``starglance run --replay`` feeds it straight into
  the pipeline, and the local view gets a timeline with every event on it.
"""

from __future__ import annotations

import bisect
import logging
import threading
import time
from collections.abc import Iterable, Iterator
from concurrent import futures
from dataclasses import dataclass, field
from pathlib import Path

import grpc
from google.protobuf import json_format
from grpc_reflection.v1alpha import reflection

from .capturefile import read_frames
from .schema import TelemetrySchema
from .scrub import SCRUBBED

log = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"
DEFAULT_PROTOSET = FIXTURES_DIR / "telemetry.protoset"

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


FLOAT32_MAX = float.fromhex("0x1.fffffep+127")


def _parseable(value):
    """Undo what JSON did to a frame so it parses back into the message.

    - Scrubbed fields are strings like "<scrubbed>", which won't parse into an int64.
    - The game's FLT_MAX ("in space" altitude) comes out of JSON as 3.4028235e38,
      a hair above float32's max, which the parser rejects.
    """
    if isinstance(value, dict):
        return {k: _parseable(v) for k, v in value.items() if v != SCRUBBED}
    if isinstance(value, list):
        return [_parseable(v) for v in value]
    if isinstance(value, float) and abs(value) > FLOAT32_MAX:
        return FLOAT32_MAX if value > 0 else -FLOAT32_MAX
    return value


def load_messages(schema: TelemetrySchema, paths: Iterable[Path]) -> list[tuple[float, bytes]]:
    """(delay before this frame in seconds, serialized response) for every frame."""
    return [(delay, payload) for delay, payload, _raw in _frames(schema, paths)]


def _frames(schema: TelemetrySchema, paths: Iterable[Path]) -> Iterator[tuple[float, bytes, dict]]:
    """(delay, serialized response, raw dict) per frame, across all files."""
    response_cls = schema.response_class("TelemetryStream")
    first = True
    for path in paths:
        last_t = None
        for t, raw in read_frames(path):
            if last_t is None:
                delay = 0.0 if first else MAX_GAP_S / 2
            else:
                delay = min((t - last_t) / 1000, MAX_GAP_S)
            first = False
            last_t = t
            msg = json_format.ParseDict(_parseable(raw), response_cls(), ignore_unknown_fields=True)
            yield delay, msg.SerializeToString(), raw


# ---------------------------------------------------------------- recording + playhead


def chapter_title(path: Path) -> str:
    name = path.name.removesuffix(".gz").removesuffix(".jsonl")
    return name.replace("-", " ").replace("_", " ").capitalize()


@dataclass
class Chapter:
    title: str
    start: float
    """Seconds into the recording."""
    end: float
    first: int
    """Index of its first frame."""


@dataclass
class Marker:
    """An event the agent derives at this point in the recording."""

    pos: float
    kind: str
    data: dict = field(default_factory=dict)


@dataclass
class Recording:
    """Every frame on one timeline (seconds), with a chapter per file and an event index."""

    positions: list[float]
    payloads: list[bytes]
    chapters: list[Chapter]
    markers: list[Marker]
    response_cls: type
    logs: dict[int, list[tuple[str, bool]]] = field(default_factory=dict)
    """Game.log lines recorded with the capture, by the index of the frame they precede,
    with ``quiet`` set for lines from before the recording started (state, not news)."""

    @property
    def duration(self) -> float:
        return self.positions[-1] if self.positions else 0.0

    def chapter_at(self, index: int) -> int:
        return max(0, bisect.bisect_right([c.first for c in self.chapters], index) - 1)

    def decode(self, index: int) -> dict:
        from .client import frame_to_dict

        return frame_to_dict(self.response_cls.FromString(self.payloads[index]))

    def index(self) -> dict:
        """What the UI needs to draw the timeline."""
        return {
            "duration": round(self.duration, 3),
            "frames": len(self.positions),
            "chapters": [
                {"title": c.title, "start": round(c.start, 3), "end": round(c.end, 3)}
                for c in self.chapters
            ],
            "markers": [
                {"pos": round(m.pos, 3), "kind": m.kind, "data": m.data} for m in self.markers
            ],
        }

    @classmethod
    def load(cls, paths: list[Path], protoset: Path = DEFAULT_PROTOSET) -> Recording:
        from .capturefile import read_records
        from .events import EventDeriver
        from .gamelog import LogState, parse_line
        from .normalize import Normalizer, raw_game_events

        schema = TelemetrySchema.from_protoset(protoset)
        rec = cls([], [], [], [], schema.response_class("TelemetryStream"))
        pos = 0.0
        for path in paths:
            # Each file is a separate slice of play. The agent starts each one
            # fresh (see ReplaySource), so the event index does too.
            normalizer, deriver, logstate = Normalizer(), EventDeriver(), LogState()
            ship_id = None
            first = len(rec.positions)
            # Log lines (t, line) in this file, attached to the next frame at or after them.
            lines = sorted(
                (r["t"], r["log"]) for r in read_records(path) if "log" in r and "t" in r
            )
            frame_times = [t for t, _ in read_frames(path)]
            li = 0
            for k, (delay, payload, raw) in enumerate(_frames(schema, [path])):
                pos += delay if rec.positions else 0.0
                if len(rec.positions) == first and first:
                    pos += MAX_GAP_S / 2
                index = len(rec.positions)
                ms = int(pos * 1000)
                while li < len(lines) and lines[li][0] <= frame_times[k]:
                    line_t, line = lines[li]
                    quiet = line_t < frame_times[0]
                    rec.logs.setdefault(index, []).append((line, quiet))
                    if ev := parse_line(line):
                        events = logstate.on_log(ev, ms, ship_id)
                        if not quiet:
                            rec.markers.extend(Marker(pos, e.kind, e.data) for e in events)
                    li += 1
                rec.positions.append(pos)
                rec.payloads.append(payload)
                normalizer.route_active = logstate.route.active
                snap = normalizer.feed(raw, int(pos * 1000))
                ship_id = snap.ship.id if snap.ship else None
                for e in deriver.feed(snap, raw_game_events(raw)):
                    rec.markers.append(Marker(pos, e.kind, e.data))
            if len(rec.positions) > first:
                rec.chapters.append(Chapter(chapter_title(path), rec.positions[first], pos, first))
        return rec


@dataclass
class Tick:
    """One frame handed out by the playhead."""

    seq: int
    epoch: int
    """Changes on every jump (seek, step back, loop): the agent starts fresh then."""
    index: int
    chapter: int


class Playhead:
    """A shared, controllable position in a recording. Thread-safe.

    One consumer calls ``wait_next`` in a loop. The position advances in real
    time (scaled by ``speed``) unless paused. Controls may come from any thread.
    """

    def __init__(self, recording: Recording, *, speed: float = 1.0, loop: bool = True) -> None:
        if not recording.positions:
            raise ValueError("The recording has no frames")
        self.rec = recording
        self.loop = loop
        self._cond = threading.Condition()
        self._index = 0
        self._seq = 0
        self._epoch = 0
        self._speed = speed
        self._paused = False
        self._closed = False
        self._anchor_wall = time.monotonic()
        self._anchor_pos = recording.positions[0]
        self._listeners: list = []

    # -- state

    def _reanchor(self) -> None:
        self._anchor_wall = time.monotonic()
        self._anchor_pos = self.rec.positions[self._index]

    def _moved(self, *, jumped: bool) -> None:
        self._seq += 1
        if jumped:
            self._epoch += 1
        self._cond.notify_all()

    def subscribe(self, listener) -> None:
        """``listener(status)`` after a control change or a loop (on the caller's thread)."""
        self._listeners.append(listener)

    def _announce(self) -> None:
        status = self.status()
        for listener in list(self._listeners):
            try:
                listener(status)
            except Exception:
                log.exception("Playhead listener failed")

    def status(self) -> dict:
        with self._cond:
            return {
                "pos": round(self.rec.positions[self._index], 3),
                "paused": self._paused,
                "speed": self._speed,
                "loop": self.loop,
                "chapter": self.rec.chapter_at(self._index),
            }

    # -- controls

    def play(self) -> None:
        with self._cond:
            if self._index >= len(self.rec.positions) - 1:
                self._index = 0
                self._moved(jumped=True)
            self._paused = False
            self._reanchor()
            self._cond.notify_all()
        self._announce()

    def pause(self) -> None:
        with self._cond:
            self._paused = True
            self._cond.notify_all()
        self._announce()

    def set_speed(self, speed: float) -> None:
        with self._cond:
            self._speed = max(0.1, min(float(speed), 16.0))
            self._reanchor()
            self._cond.notify_all()
        self._announce()

    def seek(self, pos: float) -> None:
        """Jump to the last frame at or before ``pos`` seconds."""
        with self._cond:
            i = bisect.bisect_right(self.rec.positions, float(pos)) - 1
            self._index = max(0, min(i, len(self.rec.positions) - 1))
            self._reanchor()
            self._moved(jumped=True)
        self._announce()

    def step(self, frames: int = 1) -> None:
        """Pause and move a few frames. Going back is a jump (the agent starts fresh)."""
        with self._cond:
            self._paused = True
            i = max(0, min(self._index + int(frames), len(self.rec.positions) - 1))
            jumped = i < self._index
            self._index = i
            self._moved(jumped=jumped)
        self._announce()

    def close(self) -> None:
        with self._cond:
            self._closed = True
            self._cond.notify_all()

    # -- consumer

    def _tick(self) -> Tick:
        return Tick(self._seq, self._epoch, self._index, self.rec.chapter_at(self._index))

    def wait_next(self, last_seq: int, timeout: float = 0.5) -> Tick | None:
        """The next frame once it is due, or None on timeout or close."""
        deadline = time.monotonic() + timeout
        announce = False
        tick = None
        with self._cond:
            while not self._closed:
                if self._seq != last_seq:
                    tick = self._tick()
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                if self._paused:
                    self._cond.wait(remaining)
                    continue
                nxt = self._index + 1
                if nxt >= len(self.rec.positions):
                    if self.loop:
                        self._index = 0
                        self._reanchor()
                        self._moved(jumped=True)
                    else:
                        self._paused = True
                    announce = True
                    continue
                due = self._anchor_wall + (self.rec.positions[nxt] - self._anchor_pos) / self._speed
                wait = due - time.monotonic()
                if wait <= 0:
                    self._index = nxt
                    self._moved(jumped=False)
                    continue
                self._cond.wait(min(wait, remaining))
        if announce:
            self._announce()
        return tick


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
