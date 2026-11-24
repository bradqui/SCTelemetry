"""The hub's two web servers (spec §5, §6.2).

Public (port 8100, behind Apache):
- ``/``                       the web UI in fleet mode (web/dist)
- ``/api/mode``               who's signed in, for the page
- ``/auth/*``                 Discord sign-in
- ``/api/agent/link/*``       agent linking (no cookies; the agent polls)
- ``/api/link/<code>``        the signed-in member confirms a link
- ``/api/me/agents``          their linked PCs, and revoking one
- ``/ws/agent``               agents send telemetry (``Authorization: Bearer <token>``)
- ``/ws/view``                pages watch the fleet (session cookie)

Internal (port 8101, loopback only, never proxied; ``X-Internal-Secret`` header):
- ``/internal/health``, ``/internal/fleet``, ``/internal/members/<id>``
- ``/internal/events``        WebSocket: every fleet event (for the ButlerBot cog)
- ``/internal/settings/member-role``  PUT ``{"role_id": "..."}``
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path

import aiohttp
from aiohttp import WSMsgType, web

from . import __version__
from .auth import Auth, Discord
from .config import Config
from .db import Database, now_ms
from .fleet import Fleet, ProtocolError, Viewer

log = logging.getLogger(__name__)

HUB = web.AppKey("hub", "Hub")
AGENT_MAX_MESSAGE = 64 * 1024
AGENT_RATE = 40.0
"""Messages per second an agent may send (10 Hz deltas plus bursts of events)."""
LINK_STARTS_PER_MIN = 10
MEMBERSHIP_CHECK_S = 900


class RateLimit:
    """Token bucket."""

    def __init__(self, rate: float, burst: float) -> None:
        self.rate, self.burst = rate, burst
        self.tokens, self.at = burst, time.monotonic()

    def take(self) -> bool:
        now = time.monotonic()
        self.tokens = min(self.burst, self.tokens + (now - self.at) * self.rate)
        self.at = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


def client_ip(request: web.Request) -> str:
    """The visitor's address. Behind Apache (and maybe Cloudflare) the peer is loopback."""
    peer = request.remote or ""
    if peer in ("127.0.0.1", "::1"):
        forwarded = (
            request.headers.get("CF-Connecting-IP")
            or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        )
        return forwarded or peer
    return peer


def default_web_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "web" / "dist"


class Hub:
    def __init__(self, cfg: Config, db: Database | None = None) -> None:
        self.cfg = cfg
        self.db = db or Database(cfg.db_path)
        self.fleet = Fleet(cfg, self.db)
        self.http: aiohttp.ClientSession | None = None
        self.auth: Auth | None = None
        self.web_dir = cfg.web_dir or default_web_dir()
        self._tasks: list[asyncio.Task] = []
        self._link_starts: dict[str, deque[float]] = defaultdict(deque)

    # -- lifecycle (hooked to the public app)

    async def startup(self, _app: web.Application) -> None:
        self.http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        self.auth = Auth(self.cfg, self.db, Discord(self.cfg, self.http))
        self._tasks = [
            asyncio.create_task(self.fleet.run()),
            asyncio.create_task(self._housekeeping()),
        ]
        for problem in self.cfg.problems():
            log.warning(problem)

    async def cleanup(self, _app: web.Application) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        if self.http:
            await self.http.close()

    async def _housekeeping(self) -> None:
        """Every 15 min: re-check connected members' role; hourly: prune old events."""
        rounds = 0
        while True:
            await asyncio.sleep(MEMBERSHIP_CHECK_S)
            rounds += 1
            assert self.auth is not None
            for mid, live in list(self.fleet.members.items()):
                if not live.connected:
                    continue
                member = self.db.member(mid)
                if member is None:
                    continue
                member = await self.auth.recheck(member)
                if not member.allowed:
                    await self.fleet.drop_member(mid, "You no longer have the org member role.")
            if rounds % 4 == 0:
                pruned = self.db.prune(self.cfg.event_retention_days)
                if pruned:
                    log.info("Pruned %d old events", pruned)

    # -- public app

    def public_app(self) -> web.Application:
        app = web.Application(middlewares=[self._headers, self._same_origin])
        app[HUB] = self
        app.on_startup.append(self.startup)
        app.on_cleanup.append(self.cleanup)
        auth_routes = [
            web.get("/auth/login", self._auth("login")),
            web.get("/auth/callback", self._auth("callback")),
            web.post("/auth/logout", self._auth("logout")),
            web.get("/auth/dev", self._auth("dev_login")),
        ]
        app.add_routes(
            [
                *auth_routes,
                web.get("/api/mode", self.api_mode),
                web.get("/api/health", self.api_health),
                web.post("/api/agent/link/start", self.link_start),
                web.post("/api/agent/link/poll", self.link_poll),
                web.get("/api/link/{code}", self.link_info),
                web.post("/api/link/{code}/confirm", self.link_confirm),
                web.get("/api/me/agents", self.my_agents),
                web.post("/api/me/agents/{id}/revoke", self.revoke_agent),
                web.get("/ws/agent", self.ws_agent),
                web.get("/ws/view", self.ws_view),
                web.get("/{tail:.*}", self.static),
            ]
        )
        return app

    def _auth(self, name: str):
        async def handler(request: web.Request) -> web.StreamResponse:
            assert self.auth is not None
            return await getattr(self.auth, name)(request)

        return handler

    @web.middleware
    async def _headers(self, request: web.Request, handler):
        resp = await handler(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        return resp

    @web.middleware
    async def _same_origin(self, request: web.Request, handler):
        """Cookie-authenticated changes must come from our own pages (CSRF)."""
        cookie_write = request.method not in ("GET", "HEAD", "OPTIONS") and not (
            request.path.startswith("/api/agent/")
        )
        if cookie_write and request.headers.get("Origin") != self.cfg.origin:
            return web.json_response({"error": "cross-site request refused"}, status=403)
        return await handler(request)

    async def _member(self, request: web.Request):
        assert self.auth is not None
        member = await self.auth.current(request)
        if member is None:
            raise web.HTTPUnauthorized(
                text=json.dumps({"error": "sign in first", "login": "/auth/login"}),
                content_type="application/json",
            )
        return member

    async def api_mode(self, request: web.Request) -> web.Response:
        assert self.auth is not None
        member = await self.auth.current(request)
        return web.json_response(
            {
                "mode": "fleet",
                "hub_version": __version__,
                "me": member.public() if member else None,
                "login": "/auth/login",
                "discord": self.cfg.discord_ready,
                "dev_login": self.cfg.dev_login and not self.cfg.secure,
            }
        )

    async def api_health(self, _request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "version": __version__})

    # -- linking (spec §5.1)

    async def link_start(self, request: web.Request) -> web.Response:
        ip = client_ip(request)
        starts = self._link_starts[ip]
        now = time.monotonic()
        while starts and now - starts[0] > 60:
            starts.popleft()
        if len(starts) >= LINK_STARTS_PER_MIN:
            return web.json_response({"error": "too many link attempts; wait a minute"}, status=429)
        starts.append(now)
        body = await _json(request)
        machine = str(body.get("machine") or "PC").strip()[:64] or "PC"
        code, device = self.db.new_link_code(machine)
        return web.json_response(
            {
                "user_code": code,
                "device_code": device,
                "verify_url": f"{self.cfg.hub_url}/link?code={code}",
                "interval": 3,
                "expires_in": 600,
            }
        )

    async def link_poll(self, request: web.Request) -> web.Response:
        body = await _json(request)
        status, agent, token = self.db.poll_link(str(body.get("device_code") or ""))
        if status == "expired":
            return web.json_response({"status": "expired"}, status=410)
        if status == "pending":
            return web.json_response({"status": "pending"})
        assert agent is not None
        member = self.db.member(agent.member_id)
        log.info("Linked agent %d (%s) to %s", agent.id, agent.machine, agent.member_id)
        if member is not None:
            self.fleet.live(member)
            self.fleet.refresh_roster()
        return web.json_response(
            {
                "status": "linked",
                "token": token,
                "agent_id": agent.id,
                "member": member.public() if member else None,
            }
        )

    async def link_info(self, request: web.Request) -> web.Response:
        await self._member(request)
        row = self.db.link_code(request.match_info["code"])
        if row is None:
            return web.json_response(
                {"error": "This code has expired or was mistyped."}, status=404
            )
        return web.json_response(
            {
                "code": row["user_code"],
                "machine": row["machine"],
                "expires_at": row["expires_at"],
                "confirmed": row["member_id"] is not None,
            }
        )

    async def link_confirm(self, request: web.Request) -> web.Response:
        member = await self._member(request)
        if not self.db.confirm_link_code(request.match_info["code"], member.id):
            return web.json_response(
                {"error": "This code has expired or was already used."}, status=404
            )
        return web.json_response({"ok": True})

    async def my_agents(self, request: web.Request) -> web.Response:
        member = await self._member(request)
        live = self.fleet.members.get(member.id)
        return web.json_response(
            [
                {
                    "id": a.id,
                    "machine": a.machine,
                    "created_at": a.created_at,
                    "last_seen": a.last_seen,
                    "connected": bool(live and a.id in live.sockets),
                }
                for a in self.db.agents_of(member.id)
            ]
        )

    async def revoke_agent(self, request: web.Request) -> web.Response:
        member = await self._member(request)
        try:
            agent_id = int(request.match_info["id"])
        except ValueError:
            raise web.HTTPNotFound() from None
        if not self.db.revoke_agent(agent_id, member.id):
            raise web.HTTPNotFound()
        await self.fleet.drop_agent(member.id, agent_id, "This PC was unlinked.")
        return web.json_response({"ok": True})

    # -- agents' telemetry

    async def ws_agent(self, request: web.Request) -> web.StreamResponse:
        assert self.auth is not None
        header = request.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else ""
        agent = self.db.agent_by_token(token) if token else None
        if agent is None:
            return web.json_response({"error": "unknown or revoked agent token"}, status=401)
        member = self.db.member(agent.member_id)
        if member is not None:
            member = await self.auth.recheck(member)
        if member is None or not member.allowed:
            return web.json_response({"error": "not an org member"}, status=403)

        ws = web.WebSocketResponse(heartbeat=25, max_msg_size=AGENT_MAX_MESSAGE)
        await ws.prepare(request)
        live = self.fleet.agent_connected(member, agent.id, ws)
        self.db.agent_seen(agent.id)
        await ws.send_json(
            {"type": "welcome", "hub_version": __version__, "member": member.public()}
        )
        limit = RateLimit(AGENT_RATE, AGENT_RATE * 2)
        bad = 0
        try:
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    if msg.type == WSMsgType.ERROR:
                        break
                    continue
                if not limit.take():
                    continue  # over the rate: drop (the next delta catches up)
                try:
                    reply = self.fleet.agent_message(live, json.loads(msg.data))
                except (ProtocolError, ValueError) as exc:
                    fatal = isinstance(exc, ProtocolError) and exc.fatal
                    bad += 1
                    code = exc.code if isinstance(exc, ProtocolError) else "bad_json"
                    await ws.send_json({"type": "error", "code": code, "message": str(exc)})
                    if fatal or bad > 20:
                        await ws.close(code=4002, message=code.encode())
                        break
                    continue
                if reply is not None:
                    await ws.send_json(reply)
        finally:
            self.fleet.agent_disconnected(live, agent.id, ws)
            self.db.agent_seen(agent.id)
        return ws

    # -- viewers

    async def ws_view(self, request: web.Request) -> web.StreamResponse:
        if request.headers.get("Origin") not in (None, self.cfg.origin):
            return web.json_response({"error": "cross-site request refused"}, status=403)
        member = await self._member(request)
        ws = web.WebSocketResponse(heartbeat=25, max_msg_size=4096)
        await ws.prepare(request)
        viewer = Viewer(ws, member)
        fleet = self.fleet
        await ws.send_json(
            {"type": "hello", "mode": "fleet", "hub_version": __version__, "me": member.public()}
        )
        await ws.send_json({"type": "roster", "members": fleet.roster})
        await ws.send_json({"type": "history", "events": list(fleet.recent)})
        viewer.sent_roster, viewer.roster_version = fleet.roster, fleet.roster_version
        fleet.add_viewer(viewer)
        pump = asyncio.create_task(fleet.pump(viewer))
        try:
            async for msg in ws:
                if msg.type == WSMsgType.ERROR:
                    break
                if msg.type != WSMsgType.TEXT:
                    continue
                with contextlib.suppress(ValueError, TypeError, AttributeError):
                    data = json.loads(msg.data)
                    if data.get("type") == "focus":
                        target = data.get("member")
                        fleet.set_focus(viewer, str(target) if target else None)
        finally:
            fleet.remove_viewer(viewer)
            pump.cancel()
        return ws

    # -- the page

    async def static(self, request: web.Request) -> web.StreamResponse:
        index = self.web_dir / "index.html"
        if not index.exists():
            return web.Response(
                content_type="text/html",
                text="<h1>Fleet Telemetry hub</h1><p>The web UI isn't built.</p>",
            )
        rel = request.match_info["tail"]
        if rel.startswith(("api/", "ws/", "auth/")):
            raise web.HTTPNotFound()
        target = (self.web_dir / rel).resolve()
        if rel and target.is_file() and self.web_dir.resolve() in target.parents:
            resp = web.FileResponse(target)
            if "/assets/" in f"/{rel}":
                resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return resp
        resp = web.FileResponse(index)  # SPA fallback (/link, /member/...)
        resp.headers["Cache-Control"] = "no-cache"
        return resp

    # -- internal app (the ButlerBot cog)

    def internal_app(self) -> web.Application:
        app = web.Application(middlewares=[self._internal_guard])
        app[HUB] = self
        app.add_routes(
            [
                web.get("/internal/health", self.api_health),
                web.get("/internal/fleet", self.internal_fleet),
                web.get("/internal/members/{id}", self.internal_member),
                web.get("/internal/events", self.internal_events),
                web.put("/internal/settings/member-role", self.internal_member_role),
            ]
        )
        return app

    @web.middleware
    async def _internal_guard(self, request: web.Request, handler):
        given = request.headers.get("X-Internal-Secret", "")
        if not self.cfg.internal_secret or not secrets.compare_digest(
            given, self.cfg.internal_secret
        ):
            return web.json_response({"error": "forbidden"}, status=403)
        return await handler(request)

    async def internal_fleet(self, _request: web.Request) -> web.Response:
        return web.json_response({"t": now_ms(), "members": list(self.fleet.roster.values())})

    async def internal_member(self, request: web.Request) -> web.Response:
        mid = request.match_info["id"]
        if mid not in self.fleet.members:
            raise web.HTTPNotFound()
        return web.json_response(
            {"summary": self.fleet.roster.get(mid), "snapshot": self.fleet.member_state(mid)}
        )

    async def internal_member_role(self, request: web.Request) -> web.Response:
        body = await _json(request)
        role = body.get("role_id")
        self.db.set_setting("member_role_id", str(role) if role else None)
        return web.json_response({"ok": True, "role_id": role or self.cfg.discord_member_role_id})

    async def internal_events(self, request: web.Request) -> web.StreamResponse:
        ws = web.WebSocketResponse(heartbeat=25)
        await ws.prepare(request)
        queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=500)

        def tap(record: dict) -> None:
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(record)

        self.fleet.taps.add(tap)

        async def send() -> None:
            while True:
                await ws.send_json({"type": "event", **(await queue.get())})

        sender = asyncio.create_task(send())
        try:
            async for _msg in ws:
                pass
        finally:
            self.fleet.taps.discard(tap)
            sender.cancel()
        return ws


async def _json(request: web.Request) -> dict:
    try:
        body = await request.json()
    except (ValueError, UnicodeDecodeError):
        raise web.HTTPBadRequest(text="expected JSON") from None
    if not isinstance(body, dict):
        raise web.HTTPBadRequest(text="expected a JSON object")
    return body


async def serve(cfg: Config) -> None:
    """Run both servers until cancelled."""
    hub = Hub(cfg)
    public = web.AppRunner(hub.public_app(), access_log=None)
    await public.setup()
    await web.TCPSite(public, cfg.bind, cfg.port).start()
    log.info("Hub %s on %s:%d (public: %s)", __version__, cfg.bind, cfg.port, cfg.hub_url)
    internal = None
    if cfg.internal_port:
        internal = web.AppRunner(hub.internal_app(), access_log=None)
        await internal.setup()
        await web.TCPSite(internal, cfg.bind, cfg.internal_port).start()
        log.info("Internal API on %s:%d", cfg.bind, cfg.internal_port)
    try:
        await asyncio.Event().wait()
    finally:
        if internal:
            await internal.cleanup()
        await public.cleanup()
        hub.db.close()
