"""The agent's live pipeline: game reader thread -> normalizer -> listeners.

``GameReader`` runs the blocking gRPC stream in a thread and hands raw frames
to the asyncio loop. ``Pipeline`` (on the loop) normalizes them, derives
events, and tells its listeners: the local UI now, the hub uplink in Phase 2.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

import grpc
from starglance_shared import Event, Snapshot

from . import client
from .events import EventDeriver
from .gamelog import LogState, parse_line
from .installs import Install
from .normalize import Normalizer, raw_game_events
from .scrub import scrub_uec

log = logging.getLogger(__name__)

RECENT_EVENTS = 50
TREND_EVERY_MS = 250
TREND_SAMPLES = 720
"""Flight trend history (3 minutes at 4/s) for pages that open mid-flight."""


def now_ms() -> int:
    return int(time.time() * 1000)


# ---------------------------------------------------------------- connection state


@dataclass
class GameState:
    connected: bool = False
    """The game's telemetry server is reachable."""
    streaming: bool = False
    """Frames are arriving (you're loaded in)."""
    port: int | None = None
    message: str = "Starting"
    since: int = field(default_factory=now_ms)

    def as_dict(self) -> dict:
        return {
            "type": "state",
            "connected": self.connected,
            "streaming": self.streaming,
            "port": self.port,
            "message": self.message,
            "since": self.since,
        }


# ---------------------------------------------------------------- pipeline (event loop)


class Pipeline:
    """Normalize frames and fan out snapshots, events and state changes. Loop-thread only."""

    def __init__(self) -> None:
        self.state = GameState()
        self.latest: Snapshot | None = None
        self.recent: deque[Event] = deque(maxlen=RECENT_EVENTS)
        self.trend: deque[list] = deque(maxlen=TREND_SAMPLES)
        """[t, speed, alt, g] samples, oldest first."""
        self._normalizer = Normalizer()
        self._deriver = EventDeriver()
        self._log = LogState()
        self._log_active = False
        self._listeners: list[Callable[[str, object], None]] = []
        self.recorder = None
        """The recent buffer (recent.RecentBuffer) for problem reports, when live."""
        self.schema_bytes: bytes | None = None
        """The game's message definitions in use (a serialized FileDescriptorSet)."""
        self.schema_source: str | None = None
        self.names = None
        """Place names (places.Names), read from the game's files in the background."""

    def subscribe(self, listener: Callable[[str, object], None]) -> Callable[[], None]:
        """``listener(kind, payload)``: kind "snapshot" | "event" | "state" | "reset" | "replay"."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def _notify(self, kind: str, payload: object) -> None:
        for listener in list(self._listeners):
            try:
                listener(kind, payload)
            except Exception:
                log.exception("Listener failed")

    def _record(self, rec: dict, t: int | None = None) -> None:
        if self.recorder is not None:
            self.recorder.record(rec, t)

    def _emit(self, event: Event) -> None:
        self.recent.append(event)
        self._record({"event": json.loads(event.model_dump_json(by_alias=True))}, event.t)
        self._notify("event", event)

    def set_state(self, **changes) -> None:
        old = self.state
        new = GameState(**{**old.__dict__, **changes})
        if (new.connected, new.streaming, new.port, new.message) != (
            old.connected,
            old.streaming,
            old.port,
            old.message,
        ):
            new.since = now_ms()
            self.state = new
            self._record({"state": new.as_dict()}, new.since)
            self._notify("state", new)

    def set_names(self, names) -> None:
        """Place names from the game's own files (places.load), once read."""
        self.names = names
        self._log.names = names

    def on_schema(self, file_set: bytes, source: str) -> None:
        """The game's message definitions were loaded (kept for problem reports)."""
        self.schema_bytes, self.schema_source = file_set, source

    def on_frame(self, raw: dict, t: int) -> None:
        if self.recorder is not None:
            self._record({"frame": scrub_uec(raw)}, t)
        if not self.state.streaming:
            self.set_state(streaming=True, message="Receiving telemetry")
            self._emit(Event(t=t, kind="game_start"))
        self._normalizer.route_active = self._log_active and self._log.route.active
        snap = self._with_log(self._normalizer.feed(raw, t), t)
        for event in self._deriver.feed(snap, raw_game_events(raw)):
            if event.kind in ("spawn", "respawn"):
                self._log.respawned()
            self._emit(event)
        self.latest = snap
        self._sample(snap)
        self._notify("snapshot", snap)

    def _sample(self, snap: Snapshot) -> None:
        if self.trend and snap.t - self.trend[-1][0] < TREND_EVERY_MS:
            return
        f = snap.ship.flight if snap.ship else None
        self.trend.append(
            [snap.t, f.speed if f else None, f.alt if f else None, f.g if f else None]
        )

    def _with_log(self, snap: Snapshot, t: int) -> Snapshot:
        """Add what Game.log tells us (location, contracts, session counts, injuries)."""
        if not self._log_active:
            return snap
        quantum = snap.ship.flight.quantum if snap.ship else None
        self._log.balance(snap.uec)
        update: dict = {
            "location": self._log.location(t, quantum),
            "missions": self._log.mission_list(t),
            "session": self._log.session.model_copy(),
        }
        if snap.status is not None and self._log.handle:
            update["status"] = snap.status.model_copy(update={"handle": self._log.handle})
        if snap.vitals is not None and self._log.injuries:
            update["vitals"] = snap.vitals.model_copy(
                update={"injuries": list(self._log.injuries.values())}
            )
        return snap.model_copy(update=update)

    def attach_log(self) -> None:
        """A Game.log is being followed: snapshots carry its state from now on."""
        self._log_active = True

    def on_log(self, line: str, t: int | None = None, quiet: bool = False) -> None:
        """A Game.log line. ``quiet``: history being caught up on, so state only, no events."""
        ev = parse_line(line)
        if ev is None:
            return
        if not quiet:
            self._record({"log": line}, t)
        self._log_active = True
        my_ship = self.latest.ship.id if self.latest and self.latest.ship else None
        events = self._log.on_log(ev, now_ms() if t is None else t, my_ship)
        if not quiet:
            for event in events:
                self._emit(event)

    def on_new_log(self) -> None:
        """The game was relaunched (a new Game.log): session state starts over."""
        self._log.reset_session()

    def reset(self, *, clear_history: bool) -> None:
        """Start fresh mid-stream (a replay jump): no seat/ship carry-over between scenes."""
        self._normalizer = Normalizer()
        self._deriver = EventDeriver()
        self._log = LogState()
        self._log.names = self.names
        if clear_history:
            self.recent.clear()
            self.trend.clear()
            self.latest = None
            self._notify("reset", None)

    def on_disconnect(self, message: str) -> None:
        was_streaming = self.state.streaming
        self.set_state(connected=False, streaming=False, message=message)
        if was_streaming:
            self._emit(Event(t=now_ms(), kind="game_exit"))
            self.trend.clear()
            self.latest = None
            self._log.balance_lost()
            # A new game session starts fresh (seat, ship, debounce state).
            self._normalizer = Normalizer()
            self._deriver = EventDeriver()
            # Game.log state (contracts, location) lives on: a new launch resets it via
            # on_new_log, and a dropped stream mid-game shouldn't forget your contract.


# ---------------------------------------------------------------- reader thread


class GameReader:
    """Connects to the game (retrying with backoff) and streams frames into the pipeline."""

    def __init__(
        self,
        pipeline: Pipeline,
        loop: asyncio.AbstractEventLoop,
        *,
        install: Install | None,
        port: int | None = None,
    ) -> None:
        self.pipeline = pipeline
        self.loop = loop
        self.install = install
        self.fixed_port = port
        self._stop = threading.Event()
        self._channel: grpc.Channel | None = None
        self._thread = threading.Thread(target=self._run, name="game-reader", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._channel is not None:
            self._channel.close()  # unblocks a waiting stream
        self._thread.join(timeout=5)

    def _post(self, fn, *args) -> None:
        if not self.loop.is_closed():
            self.loop.call_soon_threadsafe(fn, *args)

    def _port(self) -> int:
        if self.fixed_port:
            return self.fixed_port
        return client.discover_port(self.install.game_log if self.install else None)

    def _run(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            port = self._port()
            channel = client.open_channel(port=port)
            self._channel = channel
            try:
                if not client.wait_ready(channel, timeout=2.0):
                    self._post(self.pipeline.on_disconnect, "Waiting for the game")
                    self._stop.wait(backoff)
                    backoff = min(backoff * 1.5, 10.0)
                    continue
                schema = client.load_schema(channel, self.install.exe if self.install else None)
                self._post(
                    self.pipeline.on_schema, schema.file_set.SerializeToString(), schema.source
                )
                backoff = 1.0
                self._post(
                    lambda p=port: self.pipeline.set_state(
                        connected=True, port=p, message="Connected; load into the game"
                    )
                )
                for message in client.stream_frames(channel, schema):
                    if self._stop.is_set():
                        break
                    self._post(self.pipeline.on_frame, client.frame_to_dict(message), now_ms())
                self._post(self.pipeline.on_disconnect, "Game stream ended")
            except grpc.RpcError as exc:
                if not self._stop.is_set():
                    self._post(
                        self.pipeline.on_disconnect, f"Game connection lost ({exc.code().name})"
                    )
            except Exception as exc:  # keep the agent alive; report it
                log.exception("Game reader error")
                self._post(self.pipeline.on_disconnect, f"Error: {exc}")
                self._stop.wait(backoff)
            finally:
                channel.close()
                self._channel = None


# ---------------------------------------------------------------- replay source


class ReplaySource:
    """Feeds a replay ``Playhead`` straight into the pipeline (``run --replay``).

    Stands in for ``GameReader``: same thread-to-loop hand-off, no gRPC. On a
    jump (seek, step back, loop) the pipeline starts fresh and the view clears;
    at a chapter boundary (the next recording) it starts fresh but keeps the
    event list, as if it were one long session.
    """

    def __init__(self, pipeline: Pipeline, loop: asyncio.AbstractEventLoop, playhead) -> None:
        self.pipeline = pipeline
        self.loop = loop
        self.playhead = playhead
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="replay-source", daemon=True)
        playhead.subscribe(self._on_status)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self.playhead.close()
        self._thread.join(timeout=5)

    def _post(self, fn, *args) -> None:
        if not self.loop.is_closed():
            self.loop.call_soon_threadsafe(fn, *args)

    def _on_status(self, status: dict) -> None:
        self._post(self.pipeline._notify, "replay", status)

    def _run(self) -> None:
        self._post(lambda: self.pipeline.set_state(connected=True, port=None, message="Replaying"))
        seq, epoch, chapter = -1, -1, 0
        last_status = 0.0
        # Frames are stamped on the recording's clock, so time-based rules (debounces,
        # the quantum freeze) behave the same at any replay speed.
        base_wall, base_pos = now_ms(), 0.0
        epoch_fed = 0
        while not self._stop.is_set():
            tick = self.playhead.wait_next(seq)
            if time.monotonic() - last_status >= 1.0:  # keeps the UI's timeline in step
                last_status = time.monotonic()
                self._on_status(self.playhead.status())
            if tick is None:
                continue
            seq = tick.seq
            pos = self.playhead.rec.positions[tick.index]
            if tick.epoch != epoch:
                base_wall, base_pos = now_ms(), pos
                if epoch != -1:
                    self._post(lambda: self.pipeline.reset(clear_history=True))
            elif tick.chapter != chapter:
                self._post(lambda: self.pipeline.reset(clear_history=False))
            epoch, chapter = tick.epoch, tick.chapter
            t = base_wall + int((pos - base_pos) * 1000)
            rec = self.playhead.rec
            if tick.epoch != epoch_fed:
                # After a jump, catch up quietly on this chapter's log so far (a route
                # plotted before the jump point is still known), without events.
                first = rec.chapters[tick.chapter].first if rec.chapters else 0
                for i in range(first, tick.index):
                    for line, _quiet in rec.logs.get(i, ()):
                        self._post(self.pipeline.on_log, line, t, True)
                epoch_fed = tick.epoch
            for line, quiet in rec.logs.get(tick.index, ()):
                self._post(self.pipeline.on_log, line, t, quiet)
            self._post(self.pipeline.on_frame, rec.decode(tick.index), t)
