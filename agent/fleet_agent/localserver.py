"""The agent's local web UI server: ``http://127.0.0.1:<port>`` only (spec §6.1, §10).

- ``/``      the built web UI (web/dist), in local mode
- ``/ws``    WebSocket: state, then every snapshot (~17/s) and event as they happen
- ``/api/state``  the latest of everything, as JSON
- ``/api/mode``   ``{"mode": "local"}``: the same page is served by the hub in fleet mode

In replay mode (``run --replay``) the page also gets the recording's timeline
(chapters and every event on it) and may send replay controls over ``/ws``:
``{"type": "replay", "action": "play" | "pause" | "seek" | "speed" | "step", ...}``.
Nothing else a page sends is acted on.

Each WebSocket client has a latest-wins snapshot slot and a bounded event
queue, so a slow client (a VR overlay, a sleeping phone) never backs up the
pipeline.

Only same-machine pages may connect: the Host header must be 127.0.0.1 or
localhost (stops DNS rebinding) and a browser Origin must be this server
(stops other websites reading your telemetry through your browser).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING

from aiohttp import WSMsgType, web
from fleet_shared import Event, Snapshot

from . import __version__, paths
from .runtime import Pipeline

if TYPE_CHECKING:
    from .replay import Playhead

log = logging.getLogger(__name__)

LOCAL_HOSTS = {"127.0.0.1", "localhost"}
CLIENT_EVENT_QUEUE = 200


def _dump(model: Snapshot | Event) -> str:
    return model.model_dump_json(by_alias=True)


class _Client:
    def __init__(self, ws: web.WebSocketResponse) -> None:
        self.ws = ws
        self.snapshot: str | None = None
        self.messages: deque[str] = deque(maxlen=CLIENT_EVENT_QUEUE)
        self.wake = asyncio.Event()

    def push(self, kind: str, payload: object) -> None:
        if kind == "snapshot":
            self.snapshot = _dump(payload)  # type: ignore[arg-type]
        elif kind == "event":
            self.messages.append(_dump(payload))  # type: ignore[arg-type]
        elif kind == "state":
            self.messages.append(json.dumps(payload.as_dict()))  # type: ignore[attr-defined]
        elif kind == "reset":
            self.snapshot = None
            self.messages.append(json.dumps({"type": "reset"}))
        elif kind == "replay":
            self.messages.append(json.dumps({"type": "replay", **payload}))  # type: ignore[dict-item]
        elif kind == "uplink":
            self.messages.append(json.dumps({"type": "uplink", **payload}))  # type: ignore[dict-item]
        self.wake.set()

    async def pump(self) -> None:
        while not self.ws.closed:
            await self.wake.wait()
            self.wake.clear()
            while self.messages:
                await self.ws.send_str(self.messages.popleft())
            if self.snapshot is not None:
                snap, self.snapshot = self.snapshot, None
                await self.ws.send_str(snap)


def _host_ok(request: web.Request, port: int) -> bool:
    host = (request.host or "").rsplit(":", 1)
    return host[0].strip("[]") in LOCAL_HOSTS | {"::1"}


def _origin_ok(request: web.Request, port: int) -> bool:
    origin = request.headers.get("Origin")
    if origin is None:
        return True  # not a browser page (curl, overlay tools)
    return origin in {f"http://{h}:{port}" for h in LOCAL_HOSTS}


class LocalServer:
    def __init__(
        self,
        pipeline: Pipeline,
        *,
        port: int,
        web_dir: Path | None = None,
        playhead: Playhead | None = None,
    ) -> None:
        self.pipeline = pipeline
        self.playhead = playhead
        self.port = port
        self.web_dir = web_dir or paths.web_dist_dir()
        self.app = web.Application(middlewares=[self._guard])
        self.app.add_routes(
            [
                web.get("/ws", self._ws),
                web.get("/api/state", self._api_state),
                web.get("/api/mode", self._api_mode),
                web.get("/{tail:.*}", self._static),
            ]
        )
        self._runner: web.AppRunner | None = None

    @web.middleware
    async def _guard(self, request: web.Request, handler):
        if not _host_ok(request, self.port):
            return web.Response(status=403, text="Local access only.")
        if not _origin_ok(request, self.port):
            return web.Response(status=403, text="Cross-origin access refused.")
        return await handler(request)

    # -- routes

    async def _api_mode(self, _request: web.Request) -> web.Response:
        return web.json_response({"mode": "local", "agent_version": __version__})

    async def _api_state(self, _request: web.Request) -> web.Response:
        body = {
            "agent_version": __version__,
            "state": self.pipeline.state.as_dict(),
            "snapshot": json.loads(_dump(self.pipeline.latest)) if self.pipeline.latest else None,
            "events": [json.loads(_dump(e)) for e in self.pipeline.recent],
        }
        return web.json_response(body)

    async def _ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(request)
        c = _Client(ws)
        await ws.send_str(
            json.dumps(
                {
                    "type": "hello",
                    "mode": "local",
                    "agent_version": __version__,
                    "replay": self.playhead is not None,
                }
            )
        )
        if self.playhead is not None:
            await ws.send_str(json.dumps({"type": "replay_index", **self.playhead.rec.index()}))
            await ws.send_str(json.dumps({"type": "replay", **self.playhead.status()}))
        await ws.send_str(json.dumps(self.pipeline.state.as_dict()))
        await ws.send_str(
            json.dumps(
                {"type": "history", "events": [json.loads(_dump(e)) for e in self.pipeline.recent]}
            )
        )
        if self.pipeline.trend:
            await ws.send_str(json.dumps({"type": "trends", "samples": list(self.pipeline.trend)}))
        if self.pipeline.latest:
            await ws.send_str(_dump(self.pipeline.latest))
        unsubscribe = self.pipeline.subscribe(c.push)
        pump = asyncio.create_task(c.pump())
        try:
            async for msg in ws:
                if msg.type == WSMsgType.ERROR:
                    break
                if msg.type == WSMsgType.TEXT and self.playhead is not None:
                    self._replay_command(msg.data)
        finally:
            unsubscribe()
            pump.cancel()
        return ws

    def _replay_command(self, text: str) -> None:
        """Replay controls only; anything else (or anything malformed) is ignored."""
        assert self.playhead is not None
        try:
            cmd = json.loads(text)
            if not isinstance(cmd, dict) or cmd.get("type") != "replay":
                return
            action = cmd.get("action")
            if action == "play":
                self.playhead.play()
            elif action == "pause":
                self.playhead.pause()
            elif action == "seek":
                self.playhead.seek(float(cmd["pos"]))
            elif action == "speed":
                self.playhead.set_speed(float(cmd["speed"]))
            elif action == "step":
                self.playhead.step(int(cmd.get("frames", 1)))
        except (ValueError, TypeError, KeyError):
            log.debug("Ignored replay command %r", text[:200])

    async def _static(self, request: web.Request) -> web.StreamResponse:
        index = self.web_dir / "index.html"
        if not index.exists():
            return web.Response(
                content_type="text/html",
                text="<h1>Fleet Telemetry agent</h1><p>The web UI isn't built. Run "
                "<code>npm install && npm run build</code> in <code>web/</code>.</p>"
                '<p>Live data: <a href="/api/state">/api/state</a></p>',
            )
        rel = request.match_info["tail"]
        target = (self.web_dir / rel).resolve()
        if rel and target.is_file() and self.web_dir.resolve() in target.parents:
            return web.FileResponse(target)
        return web.FileResponse(index)  # SPA fallback

    # -- lifecycle

    async def start(self) -> None:
        self._runner = web.AppRunner(self.app, access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", self.port)  # never 0.0.0.0
        await site.start()
        if self.port == 0:
            self.port = self._runner.addresses[0][1]

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()
