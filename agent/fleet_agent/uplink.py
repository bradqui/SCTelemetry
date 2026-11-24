"""The agent's connection to the fleet hub (spec §4, §6.1).

Outbound only: a WebSocket to ``<hub>/ws/agent`` with the PC's token. On
connect it sends ``hello`` (version, channel, what's shared) and a full
snapshot; after that, only what changed, at most ``RATE_HZ`` times a second,
plus a full snapshot every ``FULL_EVERY_S``. Events go immediately.

Privacy: everything leaves through ``apply_sharing`` / ``event_shared``, so a
category the member switched off is never sent.

Latest wins: if the hub is slow or away, snapshots are skipped, never queued.
Events are kept (up to ``EVENT_BUFFER``) and sent on reconnect. Reconnects with
backoff; stops for good if the hub says the token is revoked or the member
isn't in the org any more.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from collections import deque
from collections.abc import Callable

import aiohttp
from fleet_shared import (
    SCHEMA_VERSION,
    Event,
    Hello,
    Snapshot,
    apply_sharing,
    event_shared,
    make_patch,
)

from . import __version__

log = logging.getLogger(__name__)

RATE_HZ = 10
FULL_EVERY_S = 30.0
HEARTBEAT_S = 25.0
EVENT_BUFFER = 500


def ws_url(hub_url: str, path: str = "/ws/agent") -> str:
    base = hub_url.rstrip("/")
    if base.startswith("https://"):
        return "wss://" + base[8:] + path
    if base.startswith("http://"):
        return "ws://" + base[7:] + path
    return base + path


class Uplink:
    def __init__(
        self,
        pipeline,
        hub_url: str,
        token: str,
        share: set[str],
        *,
        channel: str | None = None,
        rate_hz: float = RATE_HZ,
        on_status: Callable[[dict], None] | None = None,
    ) -> None:
        self.pipeline = pipeline
        self.hub_url = hub_url.rstrip("/")
        self.token = token
        self.share = set(share)
        self.channel = channel
        self.interval = 1.0 / rate_hz
        self.on_status = on_status
        self.status: dict = {"state": "connecting", "hub": self.hub_url, "member": None}
        self._events: deque[Event] = deque(maxlen=EVENT_BUFFER)
        self._wake = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._unsubscribe: Callable[[], None] | None = None
        self.sent = {"snapshot": 0, "delta": 0, "event": 0, "heartbeat": 0}

    @contextlib.asynccontextmanager
    async def fleet_view(self):
        """The hub's fleet stream (/ws/view) as this PC's member, for the local fleet view.
        Opened only while a local page shows the fleet; the agent relays it to 127.0.0.1."""
        async with (
            aiohttp.ClientSession() as http,
            http.ws_connect(
                ws_url(self.hub_url, "/ws/view"),
                headers={"Authorization": f"Bearer {self.token}"},
                heartbeat=25,
                max_msg_size=0,
            ) as ws,
        ):
            yield ws

    async def login_link(self) -> str:
        """A one-time address that opens the fleet page signed in (the cockpit's Fleet chip)."""
        from .fleetlink import login_link

        return await login_link(self.hub_url, self.token)

    # -- lifecycle

    def start(self) -> None:
        self._unsubscribe = self.pipeline.subscribe(self._on_pipeline)
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._unsubscribe:
            self._unsubscribe()
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    def _set_status(self, **changes) -> None:
        self.status = {**self.status, **changes}
        if self.on_status:
            self.on_status(dict(self.status))

    def _on_pipeline(self, kind: str, payload: object) -> None:
        if kind == "event" and isinstance(payload, Event) and event_shared(payload, self.share):
            self._events.append(payload)
            self._wake.set()
        elif kind == "state":
            self._wake.set()  # e.g. the game closed: say so now, not at the next tick

    # -- connection loop

    async def _run(self) -> None:
        backoff = 1.0
        async with aiohttp.ClientSession() as http:
            while True:
                self._set_status(state="connecting", message=None)
                try:
                    async with http.ws_connect(
                        ws_url(self.hub_url),
                        headers={"Authorization": f"Bearer {self.token}"},
                        heartbeat=25,
                        timeout=aiohttp.ClientWSTimeout(ws_close=10),
                    ) as ws:
                        backoff = 1.0
                        stop = await self._session(ws)
                        if stop:
                            return
                except aiohttp.WSServerHandshakeError as exc:
                    if exc.status == 401:
                        self._set_status(
                            state="rejected",
                            message="This PC isn't linked any more. Run: fleet_agent link",
                        )
                        log.warning("Hub refused the token; not retrying")
                        return
                    if exc.status == 403:
                        self._set_status(
                            state="rejected", message="The hub says you're not an org member."
                        )
                        log.warning("Hub: not an org member; not retrying")
                        return
                    self._set_status(state="offline", message=f"Hub error {exc.status}")
                except (TimeoutError, aiohttp.ClientError, OSError) as exc:
                    self._set_status(state="offline", message=f"Can't reach the hub: {exc}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

    async def _session(self, ws: aiohttp.ClientWebSocketResponse) -> bool:
        """One connection. Returns True when the hub told us to stop for good."""
        hello = Hello(agent_version=__version__, channel=self.channel, share=sorted(self.share))
        await ws.send_str(hello.model_dump_json())
        base: dict | None = None  # the hub's copy of our snapshot, as last sent
        resync = asyncio.Event()
        stop_for_good = False

        async def receive() -> None:
            nonlocal stop_for_good
            async for msg in ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    continue
                with contextlib.suppress(ValueError):
                    data = json.loads(msg.data)
                    kind = data.get("type")
                    if kind == "welcome":
                        member = (data.get("member") or {}).get("name")
                        self._set_status(state="connected", member=member, message=None)
                    elif kind == "resync":
                        resync.set()
                    elif kind == "error":
                        log.warning("Hub: %s", data.get("message"))
                        if data.get("code") in ("revoked", "version"):
                            stop_for_good = True
                            self._set_status(state="rejected", message=data.get("message"))

        receiver = asyncio.create_task(receive())
        last_full = last_sent = last_state = 0.0
        was_in_game = False
        try:
            while not ws.closed and not receiver.done():
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(self._wake.wait(), timeout=self.interval)
                self._wake.clear()
                while self._events:
                    event = self._events[0]
                    await ws.send_str(event.model_dump_json(by_alias=True))
                    self._events.popleft()
                    self.sent["event"] += 1
                now = time.monotonic()
                snap: Snapshot | None = self.pipeline.latest
                in_game = bool(self.pipeline.state.streaming and snap is not None)
                if resync.is_set():
                    resync.clear()
                    base = None
                if in_game and snap is not None and now - last_state < self.interval * 0.9:
                    continue  # woken early by an event: keep the snapshot rate
                if in_game and snap is not None:
                    last_state = now
                    state = json.loads(
                        apply_sharing(snap, self.share).model_dump_json(by_alias=True)
                    )
                    if base is None or now - last_full >= FULL_EVERY_S:
                        await ws.send_str(json.dumps(state, separators=(",", ":")))
                        last_full = last_sent = now
                        self.sent["snapshot"] += 1
                    else:
                        patch = make_patch(base, state)
                        if patch:
                            delta = {"type": "delta", "v": SCHEMA_VERSION, "t": state["t"]}
                            delta["patch"] = patch
                            await ws.send_str(json.dumps(delta, separators=(",", ":")))
                            last_sent = now
                            self.sent["delta"] += 1
                    base = state
                elif was_in_game or now - last_sent >= HEARTBEAT_S:
                    beat = {"type": "heartbeat", "v": SCHEMA_VERSION, "t": int(time.time() * 1000)}
                    beat["in_game"] = False
                    await ws.send_str(json.dumps(beat))
                    last_sent = now
                    base = None
                    self.sent["heartbeat"] += 1
                was_in_game = in_game
        except (ConnectionResetError, aiohttp.ClientError) as exc:
            log.info("Hub connection dropped: %s", exc)
        finally:
            receiver.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await receiver
        if not stop_for_good:
            self._set_status(state="offline", message="Disconnected from the hub")
        return stop_for_good
