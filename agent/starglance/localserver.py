"""The agent's local web UI server: ``http://127.0.0.1:<port>`` only (spec §6.1, §10).

- ``/``      the built web UI (web/dist), in local mode
- ``/ws``    WebSocket: state, then every snapshot (~17/s) and event as they happen
- ``/api/state``  the latest of everything, as JSON
- ``/api/mode``   ``{"mode": "local"}``: the same page is served by the hub in fleet mode
- ``/api/fleet/open``  POST: a one-time link to the fleet page, signed in (when linked)
- ``/api/agent/settings`` GET, and POST ``/api/agent/share``, ``/fleet``, ``/join``,
  ``/leave``, ``/telemetry``: the cockpit's Agent settings (``control.AgentControl``);
  the fleet ones name a fleet by its ``hub``
- ``/api/agent/lan``, ``/lan/code``, ``/lan/forget`` POST: Show on other devices
  (``lanview``: a second, view-only server on your network, opt-in, paired devices only)
- ``/api/app/show`` POST: the Windows app brings its window forward (a second launch)
- ``/ws/fleet?hub=``  WebSocket: that fleet's stream from its hub, relayed (default: the
  first fleet this PC sends to). The agent
  connects to the hub with its own token; the page may only send ``focus``.

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
from starglance_shared import Event, Snapshot

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
        elif kind == "updater":
            self.messages.append(json.dumps({"type": "updater", **payload}))  # type: ignore[dict-item]
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


def _hub_error(exc: Exception) -> str:
    status = getattr(exc, "status", None)
    if status == 401:
        return "The hub doesn't recognise this PC any more: link it again."
    if status == 403:
        return "Your membership is suspended."
    return "Can't reach the fleet hub."


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
                web.get("/api/state", self.api_state),
                web.get("/api/mode", self._api_mode),
                web.post("/api/fleet/open", self._fleet_open),
                web.get("/ws/fleet", self._fleet_ws),
                web.get("/api/agent/settings", self._agent_settings),
                web.post("/api/agent/share", self._agent_share),
                web.post("/api/agent/join", self._agent_join),
                web.post("/api/agent/leave", self._agent_leave),
                web.post("/api/agent/fleet", self._agent_fleet),
                web.post("/api/agent/telemetry", self._agent_telemetry),
                web.post("/api/agent/lan", self._agent_lan),
                web.post("/api/agent/lan/code", self._agent_lan_code),
                web.post("/api/agent/lan/forget", self._agent_lan_forget),
                web.post("/api/agent/update", self._agent_update),
                web.post("/api/agent/update/auto", self._agent_update_auto),
                web.post("/api/agent/update/check", self._agent_update_check),
                web.post("/api/agent/update/check-now", self._agent_update_check_now),
                web.post("/api/app/show", self._app_show),
                web.get("/{tail:.*}", self.static),
            ]
        )
        self._runner: web.AppRunner | None = None
        self.fleet_open = None
        """async (hub URL | None) -> one-time sign-in URL for that fleet's page."""
        self.fleet_view = None
        """(hub URL | None) -> async context giving that hub's fleet WebSocket, or None."""
        self.on_show = None
        """The Windows app: () -> bring its window forward (starting it again does this)."""
        self.control = None
        """The running agent's settings (control.AgentControl); None in tests."""
        self.uplinks: dict[str, dict] = {}
        """Each fleet's latest link status, by hub, for pages that open later (Fleet chip)."""
        pipeline.subscribe(self._remember)

    def _remember(self, kind: str, payload: object) -> None:
        if kind == "uplink" and isinstance(payload, dict):
            hub = str(payload.get("hub") or "")
            if payload.get("state") == "unlinked":
                self.uplinks.pop(hub, None)
            else:
                self.uplinks[hub] = payload

    @web.middleware
    async def _guard(self, request: web.Request, handler):
        if not _host_ok(request, self.port):
            return web.Response(status=403, text="Local access only.")
        if not _origin_ok(request, self.port):
            return web.Response(status=403, text="Cross-origin access refused.")
        return await handler(request)

    # -- routes

    async def _fleet_open(self, request: web.Request) -> web.Response:
        if self.fleet_open is None:
            return web.json_response({"error": "not linked to a fleet"}, status=404)
        try:
            url = await self.fleet_open(request.query.get("hub") or None)
        except Exception as exc:  # the hub is down, the token was revoked...
            return web.json_response({"error": str(exc)}, status=502)
        return web.json_response({"url": url})

    async def _fleet_ws(self, request: web.Request) -> web.WebSocketResponse:
        return await self.fleet_stream(request)

    async def fleet_stream(self, request: web.Request, *, track=None) -> web.WebSocketResponse:
        """Relay the hub's fleet view to a page (here, or another device: lanview). Hub ->
        page: everything; page -> hub: only which member is open. Either side closing
        closes both. ``track`` as for ``stream``."""
        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(request)
        done = track(ws) if track else None
        try:
            return await self._fleet_relay(request, ws)
        finally:
            if done:
                done()

    async def _fleet_relay(
        self, request: web.Request, ws: web.WebSocketResponse
    ) -> web.WebSocketResponse:
        view = self.fleet_view(request.query.get("hub") or None) if self.fleet_view else None
        if view is None:
            await ws.send_json({"type": "unlinked"})
            await ws.close()
            return ws
        try:
            async with view as hub:

                async def down() -> None:
                    async for msg in hub:
                        if msg.type != WSMsgType.TEXT:
                            break
                        await ws.send_str(msg.data)

                relay = asyncio.create_task(down())
                try:
                    async for msg in ws:
                        if msg.type != WSMsgType.TEXT:
                            break
                        try:
                            data = json.loads(msg.data)
                        except ValueError:
                            continue
                        if isinstance(data, dict) and data.get("type") == "focus":
                            member = data.get("member")
                            await hub.send_json(
                                {"type": "focus", "member": str(member) if member else None}
                            )
                        if relay.done():
                            break
                finally:
                    relay.cancel()
        except Exception as exc:  # the hub is down or refused us
            log.info("Fleet view: %s", exc)
            if not ws.closed:
                await ws.send_json({"type": "error", "message": _hub_error(exc)})
        if not ws.closed:
            await ws.close()
        return ws

    # -- Agent settings (the cockpit page's Agent tab)

    async def _agent_call(self, request: web.Request, action) -> web.Response:
        from .fleetlink import LinkError

        if self.control is None:
            return web.json_response({"error": "settings aren't available here"}, status=404)
        if request.method == "POST" and request.content_type != "application/json":
            return web.json_response({"error": "expected JSON"}, status=415)
        try:
            body = (
                await request.json() if request.method == "POST" and request.can_read_body else {}
            )
            result = action(body if isinstance(body, dict) else {})
            if asyncio.iscoroutine(result):
                result = await result
        except LinkError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except Exception as exc:  # the hub is down, the file is locked...
            log.warning("Agent settings: %s", exc)
            return web.json_response({"error": str(exc) or exc.__class__.__name__}, status=502)
        return web.json_response(result)

    async def _agent_settings(self, request: web.Request) -> web.Response:
        return await self._agent_call(request, lambda _b: self.control.state())

    async def _agent_share(self, request: web.Request) -> web.Response:
        return await self._agent_call(
            request, lambda b: self.control.set_share(str(b.get("hub", "")), b.get("share") or {})
        )

    async def _agent_fleet(self, request: web.Request) -> web.Response:
        return await self._agent_call(
            request,
            lambda b: self.control.set_enabled(str(b.get("hub", "")), bool(b.get("enabled"))),
        )

    async def _agent_join(self, request: web.Request) -> web.Response:
        return await self._agent_call(
            request,
            lambda b: self.control.join(str(b.get("target", "")), str(b.get("name", ""))),
        )

    async def _agent_leave(self, request: web.Request) -> web.Response:
        return await self._agent_call(request, lambda b: self.control.leave(str(b.get("hub", ""))))

    async def _agent_telemetry(self, request: web.Request) -> web.Response:
        return await self._agent_call(
            request,
            lambda b: self.control.set_telemetry(str(b.get("channel", "")), bool(b.get("on"))),
        )

    async def _agent_lan(self, request: web.Request) -> web.Response:
        return await self._agent_call(request, lambda b: self.control.set_lan(bool(b.get("on"))))

    async def _agent_lan_code(self, request: web.Request) -> web.Response:
        return await self._agent_call(
            request, lambda b: self.control.lan_code(bool(b.get("cancel")))
        )

    async def _agent_lan_forget(self, request: web.Request) -> web.Response:
        return await self._agent_call(
            request, lambda b: self.control.lan_forget(str(b["id"]) if b.get("id") else None)
        )

    async def _agent_update(self, request: web.Request) -> web.Response:
        return await self._agent_call(request, lambda _b: self.control.update_now())

    async def _agent_update_auto(self, request: web.Request) -> web.Response:
        return await self._agent_call(
            request, lambda b: self.control.set_auto_update(bool(b.get("on")))
        )

    async def _agent_update_check(self, request: web.Request) -> web.Response:
        return await self._agent_call(
            request, lambda b: self.control.set_check_updates(bool(b.get("on")))
        )

    async def _agent_update_check_now(self, request: web.Request) -> web.Response:
        return await self._agent_call(request, lambda _b: self.control.check_updates_now())

    async def _app_show(self, _request: web.Request) -> web.Response:
        if self.on_show is None:
            return web.json_response({"error": "not the app"}, status=404)
        self.on_show()
        return web.json_response({"ok": True})

    async def _api_mode(self, _request: web.Request) -> web.Response:
        return web.json_response({"mode": "local", "agent_version": __version__})

    async def api_state(self, _request: web.Request) -> web.Response:
        body = {
            "agent_version": __version__,
            "state": self.pipeline.state.as_dict(),
            "snapshot": json.loads(_dump(self.pipeline.latest)) if self.pipeline.latest else None,
            "events": [json.loads(_dump(e)) for e in self.pipeline.recent],
        }
        return web.json_response(body)

    async def _ws(self, request: web.Request) -> web.WebSocketResponse:
        return await self.stream(request)

    async def stream(
        self, request: web.Request, *, remote: bool = False, track=None
    ) -> web.WebSocketResponse:
        """The live feed. ``remote``: another device (lanview), which may only watch: the
        page hides the controls and anything it sends is ignored. ``track(ws)`` is told
        about the socket and returns a callback for when it ends."""
        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(request)
        done = track(ws) if track else None
        try:
            return await self._stream(ws, remote=remote)
        finally:
            if done:
                done()

    async def _stream(self, ws: web.WebSocketResponse, *, remote: bool) -> web.WebSocketResponse:
        c = _Client(ws)
        await ws.send_str(
            json.dumps(
                {
                    "type": "hello",
                    "mode": "local",
                    "agent_version": __version__,
                    "replay": self.playhead is not None,
                    "remote": remote,
                }
            )
        )
        if self.playhead is not None:
            await ws.send_str(json.dumps({"type": "replay_index", **self.playhead.rec.index()}))
            await ws.send_str(json.dumps({"type": "replay", **self.playhead.status()}))
        await ws.send_str(json.dumps(self.pipeline.state.as_dict()))
        for status in list(self.uplinks.values()):
            await ws.send_str(json.dumps({"type": "uplink", **status}))
        updater = getattr(self.control, "updater", None)
        if updater is not None:
            await ws.send_str(json.dumps({"type": "updater", **updater.status()}))
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
                if msg.type == WSMsgType.TEXT and self.playhead is not None and not remote:
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

    async def static(self, request: web.Request) -> web.StreamResponse:
        """The page and its files (any path not found: the page)."""
        index = self.web_dir / "index.html"
        if not index.exists():
            return web.Response(
                content_type="text/html",
                text="<h1>Starglance agent</h1><p>The web UI isn't built. Run "
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
