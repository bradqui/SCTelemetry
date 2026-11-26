"""The hub's web server (spec §5, §6.2; the HTTP API is in docs/HUB_API.md).

One port (8100), behind a reverse proxy that terminates https.

- ``/``, ``/join/<code>``, ``/link``        the page (web/dist), in fleet mode
- ``/api/mode``                          who's signed in, the org's name
- ``/api/join``, ``/api/signin/code``,   becoming a member and signing a browser in
  ``/auth/*``
- ``/api/agent/*``, ``/ws/agent``        agents: join, link, telemetry (bearer token)
- ``/api/me/*``, ``/api/link/<code>``    the signed-in member's account and PCs
- ``/api/admin/*``                       admins: members, invites, settings, API keys,
                                         problem reports
- ``/api/v1/*``                          integrations (bots, scripts): API key
- ``/ws/view``                           pages watch the fleet (session cookie)
"""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import json
import logging
import time
from collections import defaultdict, deque
from pathlib import Path

import aiohttp
from aiohttp import WSMsgType, web
from starglance_shared import RELEASES_URL

from . import MIN_AGENT_VERSION, __version__
from . import reports as reports_mod
from .auth import SESSION_COOKIE, Auth, Discord, page, valid_next
from .config import Config
from .db import API_SCOPES, ROLES, Database, Member, clean_name, now_ms
from .fleet import Fleet, ProtocolError, Viewer

log = logging.getLogger(__name__)

HUB = web.AppKey("hub", "Hub")
AGENT_MAX_MESSAGE = 64 * 1024
AGENT_RATE = 40.0
"""Messages per second an agent may send (10 Hz deltas plus bursts of events)."""
MEMBERSHIP_CHECK_S = 900
INVITE_DAYS = {1, 7, 30}
INVITE_USES = {1, 5, 25}


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


def _proxied(peer: str) -> bool:
    """A peer that can only be our reverse proxy: loopback, or a private address (in Docker
    the proxy's connections arrive from the bridge, 172.x.0.1, not loopback). The hub's
    port is published on 127.0.0.1 only (deploy/docker-compose.yml), so nobody else can
    connect from there to set a forwarded address."""
    try:
        ip = ipaddress.ip_address(peer)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


def client_ip(request: web.Request) -> str:
    """The visitor's address, for rate limits: behind the proxy (and maybe Cloudflare), from
    its forwarded headers; otherwise the peer."""
    peer = request.remote or ""
    if _proxied(peer):
        forwarded = (
            request.headers.get("CF-Connecting-IP")
            or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        )
        return forwarded or peer
    return peer


def default_web_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "web" / "dist"


def _json_error(status: int, message: str) -> web.HTTPException:
    if status == 413:
        return web.HTTPRequestEntityTooLarge(
            max_size=reports_mod.MAX_BYTES,
            actual_size=0,
            text=json.dumps({"error": message}),
            content_type="application/json",
        )
    cls = {
        400: web.HTTPBadRequest,
        401: web.HTTPUnauthorized,
        403: web.HTTPForbidden,
        404: web.HTTPNotFound,
        409: web.HTTPConflict,
        410: web.HTTPGone,
        429: web.HTTPTooManyRequests,
    }[status]
    return cls(text=json.dumps({"error": message}), content_type="application/json")


async def _body(request: web.Request) -> dict:
    try:
        body = await request.json()
    except (ValueError, UnicodeDecodeError):
        raise _json_error(400, "expected JSON") from None
    if not isinstance(body, dict):
        raise _json_error(400, "expected a JSON object")
    return body


def _bearer(request: web.Request) -> str:
    header = request.headers.get("Authorization", "")
    return header[7:].strip() if header.startswith("Bearer ") else ""


class Hub:
    def __init__(self, cfg: Config, db: Database | None = None) -> None:
        self.cfg = cfg
        self.db = db or Database(cfg.db_path)
        self.fleet = Fleet(cfg, self.db)
        self.http: aiohttp.ClientSession | None = None
        self.auth = Auth(cfg, self.db, None)
        self.web_dir = cfg.web_dir or default_web_dir()
        self.setup_url: str | None = None
        self._tasks: list[asyncio.Task] = []
        self._limits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    # -- lifecycle

    async def startup(self, _app: web.Application) -> None:
        self.http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        self.auth = Auth(self.cfg, self.db, Discord(self.cfg, self.http))
        self._tasks = [
            asyncio.create_task(self.fleet.run()),
            asyncio.create_task(self._housekeeping()),
        ]
        for problem in self.cfg.problems():
            log.warning(problem)
        self.refresh_setup()

    def refresh_setup(self) -> None:
        """No admin yet: make (and log) a one-time link that creates the first admin."""
        code = self.db.setup_invite()
        self.setup_url = f"{self.cfg.hub_url}/join/{code}" if code else None
        if self.setup_url:
            log.warning("No admin yet. Open this link to create the admin account:")
            log.warning("    %s", self.setup_url)

    async def cleanup(self, _app: web.Application) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        if self.http:
            await self.http.close()

    async def _housekeeping(self) -> None:
        """Every 15 min: Discord role re-check for connected members; hourly: prune."""
        rounds = 0
        while True:
            await asyncio.sleep(MEMBERSHIP_CHECK_S)
            rounds += 1
            for mid, live in list(self.fleet.members.items()):
                member = self.db.member(mid)
                if member is None or not live.connected:
                    continue
                member = await self.auth.recheck(member)
                if not member.active:
                    await self.fleet.drop_member(mid, "Your membership is suspended.")
            if rounds % 4 == 0:
                pruned = self.db.prune(
                    self.cfg.event_retention_days, self.cfg.report_retention_days
                )
                if pruned:
                    log.info("Pruned %d old events", pruned)

    def _limited(self, request: web.Request, bucket: str, per_minute: int) -> None:
        """Per-address limit on guessable things (codes, invites)."""
        hits = self._limits[(bucket, client_ip(request))]
        now = time.monotonic()
        while hits and now - hits[0] > 60:
            hits.popleft()
        if len(hits) >= per_minute:
            raise _json_error(429, "too many attempts; wait a minute")
        hits.append(now)

    # -- the app

    def app(self) -> web.Application:
        app = web.Application(middlewares=[self._headers, self._same_origin])
        app[HUB] = self
        app.on_startup.append(self.startup)
        app.on_cleanup.append(self.cleanup)
        app.add_routes(
            [
                web.get("/api/health", self.health),
                web.get("/api/mode", self.mode),
                # becoming a member, signing in
                web.get("/api/invite/{code}", self.invite_info),
                web.post("/api/join", self.join),
                web.post("/api/signin/code", self.signin_code),
                web.get("/auth/token/{token}", self.signin_link),
                web.post("/auth/logout", self.logout),
                web.get("/auth/discord", self._discord("discord_start")),
                web.get("/auth/discord/callback", self._discord("discord_callback")),
                web.get("/auth/dev", self.dev_login),
                # agents
                web.post("/api/agent/join", self.agent_join),
                web.post("/api/agent/link/start", self.link_start),
                web.post("/api/agent/link/poll", self.link_poll),
                web.post("/api/agent/login-link", self.agent_login_link),
                web.post("/api/agent/unlink", self.agent_unlink),
                web.get("/ws/agent", self.ws_agent),
                web.post("/api/agent/report", self.agent_report),
                # the signed-in member
                web.get("/api/link/{code}", self.link_info),
                web.post("/api/link/{code}/confirm", self.link_confirm),
                web.get("/api/me", self.me),
                web.patch("/api/me", self.me_update),
                web.delete("/api/me", self.me_delete),
                web.post("/api/me/device-code", self.device_code),
                web.get("/api/me/sessions", self.my_sessions),
                web.post("/api/me/sessions/others/end", self.end_other_sessions),
                web.post("/api/me/sessions/{id}/end", self.end_session),
                web.post("/api/me/discord/disconnect", self.discord_disconnect),
                web.get("/api/me/agents", self.my_agents),
                web.post("/api/me/agents/{id}/revoke", self.revoke_agent),
                web.get("/api/me/reports", self.my_reports),
                web.delete("/api/me/reports/{id}", self.my_report_delete),
                web.get("/ws/view", self.ws_view),
                # admins
                web.get("/api/admin/members", self.admin_members),
                web.patch("/api/admin/members/{id}", self.admin_member_update),
                web.delete("/api/admin/members/{id}", self.admin_member_delete),
                web.get("/api/admin/invites", self.admin_invites),
                web.post("/api/admin/invites", self.admin_invite_new),
                web.delete("/api/admin/invites/{id}", self.admin_invite_revoke),
                web.get("/api/admin/settings", self.admin_settings),
                web.put("/api/admin/settings", self.admin_settings_update),
                web.get("/api/admin/keys", self.admin_keys),
                web.post("/api/admin/keys", self.admin_key_new),
                web.delete("/api/admin/keys/{id}", self.admin_key_delete),
                web.get("/api/admin/reports", self.admin_reports),
                web.get("/api/admin/reports/{id}", self.admin_report),
                web.get("/api/admin/reports/{id}/download", self.admin_report_download),
                web.patch("/api/admin/reports/{id}", self.admin_report_update),
                web.delete("/api/admin/reports/{id}", self.admin_report_delete),
                # integrations (API key)
                web.get("/api/v1/fleet", self.v1_fleet),
                web.get("/api/v1/members/{id}", self.v1_member),
                web.get("/api/v1/events", self.v1_events),
                web.get("/api/v1/events/stream", self.v1_stream),
                web.post("/api/v1/invites", self.v1_invite),
                # the page
                web.get("/{tail:.*}", self.static),
            ]
        )
        return app

    def _discord(self, name: str):
        async def handler(request: web.Request) -> web.StreamResponse:
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
        """Browser writes must come from our own pages (CSRF). Bearer APIs are exempt."""
        browser_write = request.method not in ("GET", "HEAD", "OPTIONS") and not (
            request.path.startswith(("/api/agent/", "/api/v1/"))
        )
        if browser_write and request.headers.get("Origin") != self.cfg.origin:
            return web.json_response({"error": "cross-site request refused"}, status=403)
        return await handler(request)

    # -- who's asking

    async def _member(self, request: web.Request) -> Member:
        member = await self.auth.current(request)
        if member is None:
            raise _json_error(401, "sign in first")
        return member

    async def _admin(self, request: web.Request) -> Member:
        member = await self._member(request)
        if not member.is_admin:
            raise _json_error(403, "admins only")
        return member

    def _agent_member(self, request: web.Request):
        agent = self.db.agent_by_token(_bearer(request))
        member = self.db.member(agent.member_id) if agent else None
        if agent is None or member is None:
            raise _json_error(401, "unknown or revoked agent token")
        if not member.active:
            raise _json_error(403, "membership suspended")
        return agent, member

    def _api_key(self, request: web.Request, scope: str) -> dict:
        key = self.db.api_key_by_secret(_bearer(request)) if _bearer(request) else None
        if key is None:
            raise _json_error(401, "unknown API key")
        if scope not in key["scopes"]:
            raise _json_error(403, f"this key lacks the {scope!r} scope")
        return key

    # -- basics

    async def health(self, _request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "version": __version__})

    async def mode(self, request: web.Request) -> web.Response:
        member = await self.auth.current(request)
        return web.json_response(
            {
                "mode": "fleet",
                "hub_version": __version__,
                "org": self.auth.org_name(),
                "me": member.account() if member else None,
                "discord": self.auth.discord is not None,
                "dev_login": self.cfg.dev_login_on,
                "setup": self.setup_url is not None,
            }
        )

    # -- joining and signing in

    def _invite_or_error(self, code: str):
        invite = self.db.invite_by_code(code)
        if invite is None or not invite.usable:
            raise _json_error(410, "This invite has expired or was already used.")
        return invite

    async def invite_info(self, request: web.Request) -> web.Response:
        self._limited(request, "invite", 30)
        invite = self._invite_or_error(request.match_info["code"])
        return web.json_response(
            {"org": self.auth.org_name(), "role": invite.role, "expires_at": invite.expires_at}
        )

    def _create_from_invite(self, code: str, name: str) -> Member:
        if not clean_name(name):
            raise _json_error(400, "choose a display name")
        invite = self.db.use_invite(code)
        if invite is None:
            raise _json_error(410, "This invite has expired or was already used.")
        member = self.db.new_member(name, role=invite.role)
        log.info("New member %s (%s) from invite %d", member.id, member.role, invite.id)
        if invite.created_by == "setup":
            self.refresh_setup()
        return member

    async def join(self, request: web.Request) -> web.Response:
        """A browser accepts an invite: creates the account and signs in."""
        self._limited(request, "join", 10)
        body = await _body(request)
        member = self._create_from_invite(str(body.get("code", "")), str(body.get("name", "")))
        resp = web.json_response({"ok": True, "me": member.account()})
        self.auth.sign_in(resp, member, request, "invite")
        return resp

    async def signin_code(self, request: web.Request) -> web.Response:
        """Sign this browser in with a code from a device that's signed in already."""
        self._limited(request, "signin", 10)
        member = self.db.use_signin_code(str((await _body(request)).get("code", "")))
        if member is None or not member.active:
            raise _json_error(404, "That code has expired or was mistyped.")
        resp = web.json_response({"ok": True, "me": member.account()})
        self.auth.sign_in(resp, member, request, "code")
        return resp

    async def signin_link(self, request: web.Request) -> web.StreamResponse:
        """The one-time link the member's agent opened."""
        member = self.db.use_login_link(request.match_info["token"])
        if member is None or not member.active:
            return page(410, "Link expired", "Open the fleet from your agent again.")
        resp = web.HTTPFound(valid_next(request.query.get("next", "/")))
        self.auth.sign_in(resp, member, request, "link")
        raise resp

    async def logout(self, request: web.Request) -> web.Response:
        sid = request.cookies.get(SESSION_COOKIE)
        if sid:
            self.db.end_session(sid)
        resp = web.json_response({"ok": True})
        resp.del_cookie(SESSION_COOKIE, path="/")
        return resp

    async def dev_login(self, request: web.Request) -> web.StreamResponse:
        """Sign in by name. Only with HUB_DEV_LOGIN=1 on a plain-http hub (local testing)."""
        if not self.cfg.dev_login_on:
            raise web.HTTPNotFound()
        name = clean_name(request.query.get("name", "")) or "Dev Pilot"
        member = next((m for m in self.db.members() if m.name == name), None)
        if member is None:
            member = self.db.new_member(name, role="member" if self.db.admin_count() else "admin")
            self.refresh_setup()
        resp = web.HTTPFound(valid_next(request.query.get("next", "/")))
        self.auth.sign_in(resp, member, request, "dev")
        raise resp

    # -- agents: join with an invite, link to an account, open the page

    async def agent_join(self, request: web.Request) -> web.Response:
        """``starglance link <invite link>``: account and PC in one go, no browser."""
        self._limited(request, "join", 10)
        body = await _body(request)
        member = self._create_from_invite(str(body.get("invite", "")), str(body.get("name", "")))
        agent, token = self.db.new_agent(member.id, str(body.get("machine") or "PC"))
        self.fleet.live(member)
        self.fleet.refresh_roster()
        return web.json_response(
            {"status": "linked", "token": token, "agent_id": agent.id, "member": member.public()}
        )

    async def link_start(self, request: web.Request) -> web.Response:
        """An existing member links another PC: the agent shows a code to confirm."""
        self._limited(request, "link", 10)
        body = await _body(request)
        code, secret = self.db.new_link_code(str(body.get("machine") or "PC"))
        return web.json_response(
            {
                "user_code": code,
                "device_code": secret,
                "verify_url": f"{self.cfg.hub_url}/link?code={code}",
                "interval": 3,
                "expires_in": 600,
            }
        )

    async def link_poll(self, request: web.Request) -> web.Response:
        body = await _body(request)
        status, agent, token = self.db.poll_link(str(body.get("device_code") or ""))
        if status == "expired":
            return web.json_response({"status": "expired"}, status=410)
        if status == "pending":
            return web.json_response({"status": "pending"})
        assert agent is not None
        member = self.db.member(agent.member_id)
        log.info("Linked PC %d (%s) to %s", agent.id, agent.machine, agent.member_id)
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

    async def agent_login_link(self, request: web.Request) -> web.Response:
        """The agent opens the fleet page already signed in (``starglance open``)."""
        _agent, member = self._agent_member(request)
        token = self.db.new_login_link(member.id)
        return web.json_response({"url": f"{self.cfg.hub_url}/auth/token/{token}"})

    async def link_info(self, request: web.Request) -> web.Response:
        await self._member(request)
        row = self.db.link_code(request.match_info["code"])
        if row is None:
            raise _json_error(404, "This code has expired or was mistyped.")
        return web.json_response(
            {
                "code": row["code"],
                "machine": row["machine"],
                "expires_at": row["expires_at"],
                "confirmed": row["member_id"] is not None,
            }
        )

    async def link_confirm(self, request: web.Request) -> web.Response:
        member = await self._member(request)
        if not self.db.confirm_link_code(request.match_info["code"], member.id):
            raise _json_error(404, "This code has expired or was already used.")
        return web.json_response({"ok": True})

    # -- your account

    async def me(self, request: web.Request) -> web.Response:
        return web.json_response((await self._member(request)).account())

    async def me_update(self, request: web.Request) -> web.Response:
        member = await self._member(request)
        name = clean_name(str((await _body(request)).get("name", "")))
        if not name:
            raise _json_error(400, "choose a display name")
        self.db.rename(member.id, name)
        updated = self.db.member(member.id)
        assert updated is not None
        self.fleet.rename(updated)
        return web.json_response(updated.account())

    async def me_delete(self, request: web.Request) -> web.Response:
        """Delete my account and everything the hub holds about me."""
        member = await self._member(request)
        if member.is_admin and self.db.admin_count() <= 1:
            raise _json_error(409, "You're the only admin: make someone else admin first.")
        await self._remove(member.id, "Your account was deleted.")
        resp = web.json_response({"ok": True})
        resp.del_cookie(SESSION_COOKIE, path="/")
        return resp

    async def _remove(self, member_id: str, reason: str) -> None:
        await self.fleet.drop_member(member_id, reason, forget=True)
        self.db.delete_member(member_id)
        log.info("Removed member %s", member_id)

    async def device_code(self, request: web.Request) -> web.Response:
        member = await self._member(request)
        return web.json_response({"code": self.db.new_signin_code(member.id), "expires_in": 600})

    async def discord_disconnect(self, request: web.Request) -> web.Response:
        member = await self._member(request)
        self.db.set_discord(member.id, None)
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

    async def my_sessions(self, request: web.Request) -> web.Response:
        """Your signed-in devices (browsers), this one marked."""
        member = await self._member(request)
        here = self.db.session_public_id(request.cookies.get(SESSION_COOKIE, ""))
        return web.json_response(
            [{**s, "current": s["id"] == here} for s in self.db.member_sessions(member.id)]
        )

    async def end_session(self, request: web.Request) -> web.Response:
        """Sign one device out (a lost phone). Ending this one signs you out here too."""
        member = await self._member(request)
        public_id = request.match_info["id"]
        if not self.db.end_member_session(member.id, public_id):
            raise _json_error(404, "no such device")
        await self.fleet.close_viewers(member.id, public_id)
        resp = web.json_response({"ok": True})
        if public_id == self.db.session_public_id(request.cookies.get(SESSION_COOKIE, "")):
            resp.del_cookie(SESSION_COOKIE, path="/")
        return resp

    async def end_other_sessions(self, request: web.Request) -> web.Response:
        """Sign out everywhere but here."""
        member = await self._member(request)
        here = request.cookies.get(SESSION_COOKIE, "")
        ended = self.db.end_other_sessions(member.id, here)
        await self.fleet.close_viewers(member.id, keep=self.db.session_public_id(here))
        return web.json_response({"ok": True, "ended": ended})

    async def agent_unlink(self, request: web.Request) -> web.Response:
        """A PC leaving the fleet (Agent settings: Leave the fleet): its key stops working."""
        agent, member = self._agent_member(request)
        self.db.revoke_agent(agent.id, member.id)
        await self.fleet.drop_agent(member.id, agent.id, "This PC left the fleet.")
        return web.json_response({"ok": True})

    # -- problem reports (docs/REPORTS.md): members send them, admins read them

    async def agent_report(self, request: web.Request) -> web.Response:
        """A member's PC sends a problem report (a zip the agent built and cleaned)."""
        agent, member = self._agent_member(request)
        if (request.content_length or 0) > reports_mod.MAX_BYTES:
            raise _json_error(413, "The report is too big.")
        chunks, total = [], 0
        async for chunk in request.content.iter_chunked(64 * 1024):
            total += len(chunk)
            if total > reports_mod.MAX_BYTES:
                raise _json_error(413, "The report is too big.")
            chunks.append(chunk)
        data = b"".join(chunks)
        if self.db.reports_since(member.id, now_ms() - 86_400_000) >= reports_mod.PER_DAY:
            raise _json_error(429, "That's a lot of reports today: try again tomorrow.")
        try:
            summary = reports_mod.check(data)
        except reports_mod.BadReport as exc:
            raise _json_error(400, str(exc)) from None
        report_id = self.db.add_report(member.id, agent.machine, summary, data)
        log.info("Problem report %d from %s (%d bytes)", report_id, member.name, len(data))
        return web.json_response({"ok": True, "id": report_id, "org": self.auth.org_name()})

    async def my_reports(self, request: web.Request) -> web.Response:
        member = await self._member(request)
        return web.json_response(self.db.reports(member.id))

    async def my_report_delete(self, request: web.Request) -> web.Response:
        member = await self._member(request)
        if not self.db.delete_report(_int(request.match_info["id"]), member.id):
            raise _json_error(404, "no such report")
        return web.json_response({"ok": True})

    def _a_report(self, request: web.Request) -> tuple[dict, bytes]:
        found = self.db.report(_int(request.match_info["id"]))
        if found is None:
            raise _json_error(404, "no such report")
        return found

    async def admin_reports(self, request: web.Request) -> web.Response:
        await self._admin(request)
        return web.json_response(self.db.reports())

    async def admin_report(self, request: web.Request) -> web.Response:
        await self._admin(request)
        meta, data = self._a_report(request)
        files = reports_mod.texts(data)
        return web.json_response({**meta, "texts": files})

    async def admin_report_download(self, request: web.Request) -> web.Response:
        await self._admin(request)
        meta, data = self._a_report(request)
        day = time.strftime("%Y-%m-%d", time.gmtime(meta["created_at"] / 1000))
        return web.Response(
            body=data,
            content_type="application/zip",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="Starglance-report-{day}-{meta["id"]}.zip"'
                ),
                "Cache-Control": "no-store",
            },
        )

    async def admin_report_update(self, request: web.Request) -> web.Response:
        await self._admin(request)
        status = (await _body(request)).get("status")
        if status not in reports_mod.STATUSES:
            raise _json_error(400, "status is new, forwarded or not_a_bug")
        if not self.db.set_report_status(_int(request.match_info["id"]), status):
            raise _json_error(404, "no such report")
        return web.json_response({"ok": True})

    async def admin_report_delete(self, request: web.Request) -> web.Response:
        await self._admin(request)
        if not self.db.delete_report(_int(request.match_info["id"])):
            raise _json_error(404, "no such report")
        return web.json_response({"ok": True})

    async def revoke_agent(self, request: web.Request) -> web.Response:
        member = await self._member(request)
        agent_id = _int(request.match_info["id"])
        if not self.db.revoke_agent(agent_id, member.id):
            raise _json_error(404, "no such PC")
        await self.fleet.drop_agent(member.id, agent_id, "This PC was unlinked.")
        return web.json_response({"ok": True})

    # -- admins

    async def admin_members(self, request: web.Request) -> web.Response:
        await self._admin(request)
        seen = self.db.member_last_seen()
        out = []
        for m in self.db.members():
            live = self.fleet.members.get(m.id)
            out.append(
                {
                    **m.account(),
                    "pcs": len(self.db.agents_of(m.id)),
                    "last_seen": seen.get(m.id),
                    "presence": live.presence(now_ms(), self.cfg) if live else "offline",
                }
            )
        return web.json_response(out)

    async def admin_member_update(self, request: web.Request) -> web.Response:
        admin = await self._admin(request)
        target = self.db.member(request.match_info["id"])
        if target is None:
            raise _json_error(404, "no such member")
        body = await _body(request)
        if "role" in body:
            role = body["role"]
            if role not in ROLES:
                raise _json_error(400, "role is member or admin")
            if target.is_admin and role != "admin" and self.db.admin_count() <= 1:
                raise _json_error(409, "There must be at least one admin.")
            self.db.set_role(target.id, role)
        if "active" in body:
            active = bool(body["active"])
            if target.id == admin.id and not active:
                raise _json_error(409, "You can't suspend yourself.")
            self.db.set_active(target.id, active)
            if not active:
                self.db.end_member_sessions(target.id)
                await self.fleet.drop_member(target.id, "Your membership is suspended.")
        if "name" in body and clean_name(str(body["name"])):
            self.db.rename(target.id, str(body["name"]))
        updated = self.db.member(target.id)
        assert updated is not None
        self.fleet.rename(updated)
        return web.json_response(updated.account())

    async def admin_member_delete(self, request: web.Request) -> web.Response:
        admin = await self._admin(request)
        target = self.db.member(request.match_info["id"])
        if target is None:
            raise _json_error(404, "no such member")
        if target.id == admin.id:
            raise _json_error(409, "Delete your own account from Your account instead.")
        if target.is_admin and self.db.admin_count() <= 1:
            raise _json_error(409, "There must be at least one admin.")
        await self._remove(target.id, "You were removed from the fleet.")
        return web.json_response({"ok": True})

    def _make_invite(self, body: dict, created_by: str, *, allow_admin: bool) -> web.Response:
        role = body.get("role", "member")
        if role not in ROLES or (role == "admin" and not allow_admin):
            raise _json_error(400, "role must be member" + (" or admin" if allow_admin else ""))
        days = body.get("days", 7)
        uses = body.get("uses", 1)
        if days is not None and days not in INVITE_DAYS:
            raise _json_error(400, f"days is one of {sorted(INVITE_DAYS)} or null")
        if uses is not None and uses not in INVITE_USES:
            raise _json_error(400, f"uses is one of {sorted(INVITE_USES)} or null")
        invite, code = self.db.new_invite(
            role=role,
            note=body.get("note"),
            created_by=created_by,
            expires_in_s=days * 86400 if days else None,
            max_uses=uses,
        )
        return web.json_response(
            {**invite.public(), "url": f"{self.cfg.hub_url}/join/{code}"}, status=201
        )

    async def admin_invites(self, request: web.Request) -> web.Response:
        await self._admin(request)
        return web.json_response([i.public() for i in self.db.invites() if i.usable])

    async def admin_invite_new(self, request: web.Request) -> web.Response:
        admin = await self._admin(request)
        return self._make_invite(await _body(request), admin.id, allow_admin=True)

    async def admin_invite_revoke(self, request: web.Request) -> web.Response:
        await self._admin(request)
        if not self.db.revoke_invite(_int(request.match_info["id"])):
            raise _json_error(404, "no such invite")
        return web.json_response({"ok": True})

    async def admin_settings(self, request: web.Request) -> web.Response:
        await self._admin(request)
        return web.json_response(
            {
                "org_name": self.auth.org_name(),
                "discord": self.auth.discord is not None,
                "discord_autojoin": self.auth.discord_autojoin(),
                "discord_member_role_id": self.auth.member_role(),
                "event_retention_days": self.cfg.event_retention_days,
            }
        )

    async def admin_settings_update(self, request: web.Request) -> web.Response:
        await self._admin(request)
        body = await _body(request)
        if "org_name" in body:
            self.db.set_setting("org_name", clean_name(str(body["org_name"])) or None)
        if "discord_autojoin" in body:
            self.db.set_setting("discord_autojoin", "1" if body["discord_autojoin"] else None)
        if "discord_member_role_id" in body:
            role = str(body["discord_member_role_id"] or "").strip()
            self.db.set_setting("discord_member_role_id", role or None)
        return await self.admin_settings(request)

    async def admin_keys(self, request: web.Request) -> web.Response:
        await self._admin(request)
        return web.json_response(self.db.api_keys())

    async def admin_key_new(self, request: web.Request) -> web.Response:
        admin = await self._admin(request)
        body = await _body(request)
        scopes = [s for s in body.get("scopes") or ["read"] if s in API_SCOPES]
        key, secret = self.db.new_api_key(str(body.get("name", "")), scopes, admin.id)
        return web.json_response({**key, "key": secret}, status=201)

    async def admin_key_delete(self, request: web.Request) -> web.Response:
        await self._admin(request)
        if not self.db.delete_api_key(_int(request.match_info["id"])):
            raise _json_error(404, "no such key")
        return web.json_response({"ok": True})

    # -- integrations (docs/HUB_API.md)

    async def v1_fleet(self, request: web.Request) -> web.Response:
        self._api_key(request, "read")
        return web.json_response(
            {
                "t": now_ms(),
                "org": self.auth.org_name(),
                "members": list(self.fleet.roster.values()),
            }
        )

    async def v1_member(self, request: web.Request) -> web.Response:
        self._api_key(request, "read")
        mid = request.match_info["id"]
        if mid not in self.fleet.members:
            raise _json_error(404, "no such member")
        return web.json_response(
            {"summary": self.fleet.roster.get(mid), "snapshot": self.fleet.member_state(mid)}
        )

    async def v1_events(self, request: web.Request) -> web.Response:
        self._api_key(request, "read")
        since = _int(request.query.get("since", "0"))
        limit = max(1, min(500, _int(request.query.get("limit", "100"))))
        return web.json_response(self.db.recent_events(limit, since))

    async def v1_invite(self, request: web.Request) -> web.Response:
        key = self._api_key(request, "invites")
        return self._make_invite(await _body(request), f"api:{key['id']}", allow_admin=False)

    async def v1_stream(self, request: web.Request) -> web.StreamResponse:
        self._api_key(request, "read")
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

    # -- agents' telemetry

    async def ws_agent(self, request: web.Request) -> web.StreamResponse:
        agent, member = self._agent_member(request)
        member = await self.auth.recheck(member)
        if not member.active:
            raise _json_error(403, "membership suspended")
        ws = web.WebSocketResponse(heartbeat=25, max_msg_size=AGENT_MAX_MESSAGE)
        await ws.prepare(request)
        live = self.fleet.agent_connected(member, agent.id, ws)
        self.db.agent_seen(agent.id)
        await ws.send_json(
            {
                "type": "welcome",
                "hub_version": __version__,
                # Agents are released with the hub: this hub's version is the current agent.
                "latest_agent": __version__,
                "min_agent": MIN_AGENT_VERSION,
                "download": RELEASES_URL,
                "org": self.auth.org_name(),
                "member": member.public(),
            }
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
            if self.db.agent(agent.id):
                self.db.agent_seen(agent.id)
        return ws

    # -- viewers

    async def ws_view(self, request: web.Request) -> web.StreamResponse:
        if request.headers.get("Origin") not in (None, self.cfg.origin):
            raise _json_error(403, "cross-site request refused")
        # A browser signs in with its session; a linked PC's agent with its token, for the
        # fleet view in its local dashboard (it relays this stream to 127.0.0.1).
        session = None
        if _bearer(request):
            _, member = self._agent_member(request)
        else:
            member = await self._member(request)
            session = self.db.session_public_id(request.cookies.get(SESSION_COOKIE, ""))
        ws = web.WebSocketResponse(heartbeat=25, max_msg_size=4096)
        await ws.prepare(request)
        viewer = Viewer(ws, member, session)
        fleet = self.fleet
        await ws.send_json(
            {
                "type": "hello",
                "mode": "fleet",
                "hub_version": __version__,
                "org": self.auth.org_name(),
                "me": member.public(),
            }
        )
        # What this page has is the roster sent now: noted before the sends, since the
        # roster can change while they're under way (the pump then catches it up).
        viewer.sent_roster, viewer.roster_version = fleet.roster, fleet.roster_version
        await ws.send_json({"type": "roster", "members": viewer.sent_roster})
        await ws.send_json({"type": "history", "events": list(fleet.recent)})
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
        rel = request.match_info["tail"]
        if rel.startswith(("api/", "ws/", "auth/")):
            raise web.HTTPNotFound()
        if not index.exists():
            return web.Response(
                content_type="text/html",
                text="<h1>Starglance hub</h1><p>The web UI isn't built.</p>",
            )
        target = (self.web_dir / rel).resolve()
        if rel and target.is_file() and self.web_dir.resolve() in target.parents:
            resp = web.FileResponse(target)
            if "/assets/" in f"/{rel}":
                resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return resp
        resp = web.FileResponse(index)  # the page's own routes: /join/..., /link, #m=...
        resp.headers["Cache-Control"] = "no-cache"
        return resp


def _int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise _json_error(400, "expected a number") from None


async def serve(cfg: Config) -> None:
    """Run the hub until cancelled."""
    hub = Hub(cfg)
    runner = web.AppRunner(hub.app(), access_log=None)
    await runner.setup()
    await web.TCPSite(runner, cfg.bind, cfg.port).start()
    log.info("Hub %s on %s:%d (public: %s)", __version__, cfg.bind, cfg.port, cfg.hub_url)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        hub.db.close()
