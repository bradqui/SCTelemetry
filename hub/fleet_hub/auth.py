"""Browser sign-in with Discord (spec §5.2) and the membership check.

A member may sign in when they're in the configured Discord server and hold the
org member role. The role is re-checked at most hourly, with the member's own
Discord token (scope ``guilds.members.read``; refreshed when it expires). A
member who loses the role loses web access and their agents are refused.

Sessions are random ids in an HttpOnly cookie; only their hash is stored.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import aiohttp
from aiohttp import web

from .config import Config
from .db import Database, Member, now_ms

log = logging.getLogger(__name__)

SESSION_COOKIE = "ft_session"
STATE_COOKIE = "ft_oauth"
RECHECK_MS = 3_600_000
SCOPES = "identify guilds.members.read"


@dataclass
class DiscordIdentity:
    id: str
    name: str
    avatar: str | None
    roles: list[str]


class Discord:
    """The few Discord API calls sign-in needs."""

    def __init__(self, cfg: Config, http: aiohttp.ClientSession) -> None:
        self.cfg = cfg
        self.http = http

    @property
    def redirect_uri(self) -> str:
        return f"{self.cfg.hub_url}/auth/callback"

    def authorize_url(self, state: str) -> str:
        query = urlencode(
            {
                "client_id": self.cfg.discord_client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": SCOPES,
                "state": state,
                "prompt": "none",
            }
        )
        return f"{self.cfg.discord_authorize}?{query}"

    async def _token(self, data: dict) -> dict:
        data = {
            "client_id": self.cfg.discord_client_id,
            "client_secret": self.cfg.discord_client_secret,
            **data,
        }
        async with self.http.post(f"{self.cfg.discord_api}/oauth2/token", data=data) as resp:
            if resp.status != 200:
                raise web.HTTPBadGateway(text=f"Discord refused the sign-in ({resp.status}).")
            return await resp.json()

    async def exchange(self, code: str) -> dict:
        return await self._token(
            {"grant_type": "authorization_code", "code": code, "redirect_uri": self.redirect_uri}
        )

    async def refresh(self, refresh_token: str) -> dict:
        return await self._token({"grant_type": "refresh_token", "refresh_token": refresh_token})

    async def guild_member(self, access_token: str) -> DiscordIdentity | None:
        """The member's profile in our Discord server; None if they aren't in it."""
        url = f"{self.cfg.discord_api}/users/@me/guilds/{self.cfg.discord_guild_id}/member"
        headers = {"Authorization": f"Bearer {access_token}"}
        async with self.http.get(url, headers=headers) as resp:
            if resp.status in (403, 404):
                return None
            if resp.status == 401:
                raise PermissionError("Discord token no longer valid")
            if resp.status != 200:
                raise web.HTTPBadGateway(text=f"Discord didn't answer ({resp.status}).")
            body = await resp.json()
        user = body.get("user") or {}
        uid = str(user.get("id"))
        name = body.get("nick") or user.get("global_name") or user.get("username") or uid
        avatar = None
        if body.get("avatar"):
            avatar = (
                f"https://cdn.discordapp.com/guilds/{self.cfg.discord_guild_id}/users/{uid}"
                f"/avatars/{body['avatar']}.png?size=64"
            )
        elif user.get("avatar"):
            avatar = f"https://cdn.discordapp.com/avatars/{uid}/{user['avatar']}.png?size=64"
        return DiscordIdentity(uid, name, avatar, [str(r) for r in body.get("roles") or []])


class Auth:
    def __init__(self, cfg: Config, db: Database, discord: Discord) -> None:
        self.cfg = cfg
        self.db = db
        self.discord = discord

    # -- membership

    def member_role(self) -> str | None:
        """The org member role: set at runtime by the cog, else from the environment."""
        return self.db.setting("member_role_id") or self.cfg.discord_member_role_id

    def is_allowed(self, ident: DiscordIdentity | None) -> bool:
        if ident is None:
            return False
        role = self.member_role()
        return role is None or role in ident.roles

    async def recheck(self, member: Member, *, force: bool = False) -> Member:
        """Re-check the org role if the last check is over an hour old."""
        if not force and now_ms() - member.checked_at < RECHECK_MS:
            return member
        if member.id.startswith("dev-") or not member.refresh_token:
            return member  # dev sign-in, or nothing to check with
        try:
            token = member.access_token
            if not token or (member.token_expires or 0) < now_ms() + 60_000:
                fresh = await self.discord.refresh(member.refresh_token)
                token = fresh["access_token"]
                member = self.db.upsert_member(
                    member.id,
                    member.name,
                    member.avatar,
                    allowed=member.allowed,
                    access_token=token,
                    refresh_token=fresh.get("refresh_token"),
                    token_expires=now_ms() + int(fresh.get("expires_in", 604800)) * 1000,
                )
            ident = await self.discord.guild_member(token or "")
        except (PermissionError, web.HTTPException, aiohttp.ClientError) as exc:
            # Can't ask Discord right now: keep what we knew, try again later.
            log.warning("Couldn't re-check %s: %s", member.id, exc)
            self.db.set_allowed(member.id, member.allowed)
            return self.db.member(member.id) or member
        allowed = self.is_allowed(ident)
        if ident is not None:
            member = self.db.upsert_member(ident.id, ident.name, ident.avatar, allowed=allowed)
        else:
            self.db.set_allowed(member.id, False)
            member = self.db.member(member.id) or member
        if not allowed:
            log.info("%s no longer holds the member role", member.id)
            self.db.end_member_sessions(member.id)
        return member

    async def current(self, request: web.Request) -> Member | None:
        """The signed-in member for this request, if any (and still allowed)."""
        sid = request.cookies.get(SESSION_COOKIE)
        if not sid:
            return None
        member = self.db.session_member(sid)
        if member is None:
            return None
        member = await self.recheck(member)
        return member if member.allowed else None

    # -- routes (wired up in app.py)

    def _set_session(self, resp: web.StreamResponse, member: Member) -> None:
        sid = self.db.new_session(member.id)
        resp.set_cookie(
            SESSION_COOKIE,
            sid,
            max_age=30 * 86400,
            httponly=True,
            secure=self.cfg.secure,
            samesite="Lax",
            path="/",
        )

    async def login(self, request: web.Request) -> web.StreamResponse:
        if not self.cfg.discord_ready:
            if self.cfg.dev_login and not self.cfg.secure:
                raise web.HTTPFound("/auth/dev?" + urlencode({"next": _safe_next(request)}))
            raise web.HTTPServiceUnavailable(text="Discord sign-in isn't set up on this hub yet.")
        state = secrets.token_urlsafe(24)
        resp = web.HTTPFound(self.discord.authorize_url(state))
        resp.set_cookie(
            STATE_COOKIE,
            f"{state}|{_safe_next(request)}",
            max_age=600,
            httponly=True,
            secure=self.cfg.secure,
            samesite="Lax",
            path="/auth/",
        )
        raise resp

    async def callback(self, request: web.Request) -> web.StreamResponse:
        saved = request.cookies.get(STATE_COOKIE, "")
        state, _, next_url = saved.partition("|")
        if not state or not secrets.compare_digest(state, request.query.get("state", "")):
            return _page(400, "Sign-in expired", "Please go back and sign in again.")
        if "error" in request.query:
            # prompt=none fails if the member hasn't approved the app yet: ask properly.
            if request.query["error"] in ("consent_required", "interaction_required"):
                url = self.discord.authorize_url(state).replace("&prompt=none", "")
                raise web.HTTPFound(url)
            return _page(403, "Sign-in cancelled", "Discord didn't sign you in.")
        token = await self.discord.exchange(request.query.get("code", ""))
        try:
            ident = await self.discord.guild_member(token["access_token"])
        except PermissionError:
            return _page(403, "Sign-in failed", "Discord didn't accept the sign-in.")
        if ident is None:
            return _page(
                403, "Not in the server", "Sign in with the Discord account you use in our server."
            )
        allowed = self.is_allowed(ident)
        member = self.db.upsert_member(
            ident.id,
            ident.name,
            ident.avatar,
            allowed=allowed,
            access_token=token["access_token"],
            refresh_token=token.get("refresh_token"),
            token_expires=now_ms() + int(token.get("expires_in", 604800)) * 1000,
        )
        if not allowed:
            return _page(
                403,
                "Members only",
                "Your Discord account doesn't have the org member role. Ask an officer.",
            )
        resp = web.HTTPFound(_valid_next(next_url))
        self._set_session(resp, member)
        resp.del_cookie(STATE_COOKIE, path="/auth/")
        log.info("Signed in: %s", member.id)
        raise resp

    async def logout(self, request: web.Request) -> web.StreamResponse:
        sid = request.cookies.get(SESSION_COOKIE)
        if sid:
            self.db.end_session(sid)
        resp = web.json_response({"ok": True})
        resp.del_cookie(SESSION_COOKIE, path="/")
        return resp

    async def dev_login(self, request: web.Request) -> web.StreamResponse:
        """Sign in as a made-up member. Only with HUB_DEV_LOGIN=1 on a plain-http hub."""
        if not self.cfg.dev_login or self.cfg.secure:
            raise web.HTTPNotFound()
        name = (request.query.get("name") or "Dev Pilot").strip()[:32] or "Dev Pilot"
        slug = "".join(ch for ch in name.lower() if ch.isalnum())[:24] or "pilot"
        member = self.db.upsert_member(f"dev-{slug}", name, None, allowed=True)
        resp = web.HTTPFound(_valid_next(request.query.get("next", "/")))
        self._set_session(resp, member)
        raise resp


def _safe_next(request: web.Request) -> str:
    return _valid_next(request.query.get("next", "/"))


def _valid_next(value: str) -> str:
    """Only same-site paths: never redirect off the hub after sign-in."""
    if not value.startswith("/") or value.startswith("//") or "\\" in value:
        return "/"
    return value


def _page(status: int, title: str, text: str) -> web.Response:
    html = f"""<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · Fleet Telemetry</title>
<style>body{{font:15px system-ui,sans-serif;background:#0a0f16;color:#dbe6f2;display:grid;
place-items:center;min-height:90vh;margin:0}}main{{max-width:40ch;padding:24px;
border:1px solid #23303f;border-radius:6px;background:#101823}}h1{{font-size:1.2rem;margin:0 0 8px}}
a{{color:#46d3ff}}</style>
<main><h1>{title}</h1><p>{text}</p><p><a href="/">Back to the fleet</a></p></main>"""
    return web.Response(status=status, text=html, content_type="text/html")
