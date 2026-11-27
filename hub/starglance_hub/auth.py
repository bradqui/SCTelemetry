"""Who is this browser? Sessions, and the optional Discord sign-in (spec §5, decision 15).

Members are the hub's own accounts. A browser gets signed in by:

- an invite link (``/join/<code>``: creates the account),
- a one-time link the member's agent opens (``/auth/token/<t>``),
- a short code shown on a device that's already signed in ("Add a device"),
- Discord, when the hub has it set up and the member connected it (or the
  admins let holders of the Discord role join without an invite).

Sessions are random ids in an HttpOnly cookie; only their hash is stored.

The org's admins set up Discord on the admin page (the org's own Discord application and
server); the DISCORD_* environment settings are only defaults (spec decision 29).

With Discord set up and a member role configured, members who connected
Discord are re-checked at most hourly with their own token (scope
``guilds.members.read``): losing the role suspends them, getting it back
restores them. Members who never connected Discord are managed by admins only.
"""

from __future__ import annotations

import logging
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlencode

import aiohttp
from aiohttp import web
from starglance_shared import device_label

from .config import Config
from .db import Database, Member, now_ms

log = logging.getLogger(__name__)

SESSION_COOKIE = "ft_session"

STATE_COOKIE = "ft_oauth"
RECHECK_MS = 3_600_000
SCOPES = "identify guilds.members.read"


@dataclass(frozen=True)
class DiscordApp:
    """The org's Discord application and server, as set up now."""

    client_id: str | None
    client_secret: str | None
    guild_id: str | None

    @property
    def ready(self) -> bool:
        return bool(self.client_id and self.client_secret and self.guild_id)


SNOWFLAKE = re.compile(r"^[0-9]{1,25}$")
"""Discord ids (application, server, role): numbers."""


@dataclass
class DiscordIdentity:
    id: str
    name: str
    avatar: str | None
    roles: list[str]


class Discord:
    """The few Discord API calls sign-in needs."""

    def __init__(
        self, cfg: Config, http: aiohttp.ClientSession, app: Callable[[], DiscordApp]
    ) -> None:
        self.cfg = cfg
        self.http = http
        self.app = app

    @property
    def redirect_uri(self) -> str:
        return f"{self.cfg.hub_url}/auth/discord/callback"

    def authorize_url(self, state: str, *, prompt: bool = False) -> str:
        query = {
            "client_id": self.app().client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": SCOPES,
            "state": state,
        }
        if not prompt:
            query["prompt"] = "none"
        return f"{self.cfg.discord_authorize}?{urlencode(query)}"

    async def _token(self, data: dict) -> dict:
        app = self.app()
        data = {"client_id": app.client_id, "client_secret": app.client_secret, **data}
        async with self.http.post(f"{self.cfg.discord_api}/oauth2/token", data=data) as resp:
            if resp.status != 200:
                raise web.HTTPBadGateway(text=f"Discord refused the sign-in ({resp.status}).")
            return await resp.json()

    async def accepts(self, client_id: str, client_secret: str) -> bool | None:
        """Does Discord know this application id and secret? None: couldn't tell."""
        form = {
            "grant_type": "client_credentials",
            "scope": "identify",
            "client_id": client_id,
            "client_secret": client_secret,
        }
        try:
            async with self.http.post(f"{self.cfg.discord_api}/oauth2/token", data=form) as resp:
                if resp.status == 200:
                    return True
                if resp.status == 401:
                    return False
                log.info("Discord answered %s checking application %s", resp.status, client_id)
                return None
        except (aiohttp.ClientError, TimeoutError) as exc:
            log.warning("Couldn't check the Discord application with Discord: %s", exc)
            return None

    async def exchange(self, code: str) -> dict:
        return await self._token(
            {"grant_type": "authorization_code", "code": code, "redirect_uri": self.redirect_uri}
        )

    async def refresh(self, refresh_token: str) -> dict:
        return await self._token({"grant_type": "refresh_token", "refresh_token": refresh_token})

    async def guild_member(self, access_token: str) -> DiscordIdentity | None:
        """The member's profile in the configured Discord server; None if they aren't in it."""
        url = f"{self.cfg.discord_api}/users/@me/guilds/{self.app().guild_id}/member"
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
        if user.get("avatar"):
            avatar = f"https://cdn.discordapp.com/avatars/{uid}/{user['avatar']}.png?size=64"
        return DiscordIdentity(uid, name, avatar, [str(r) for r in body.get("roles") or []])


def expires_at(token: dict) -> int:
    return now_ms() + int(token.get("expires_in", 604800)) * 1000


class Auth:
    def __init__(self, cfg: Config, db: Database, http: aiohttp.ClientSession | None) -> None:
        self.cfg = cfg
        self.db = db
        self.client = Discord(cfg, http, self.discord_app) if http is not None else None

    @property
    def discord(self) -> Discord | None:
        """Discord sign-in, when the org's Discord app and server are set up."""
        return self.client if self.client is not None and self.discord_app().ready else None

    # -- settings an admin can change

    def org_name(self) -> str:
        return self.db.setting("org_name") or self.cfg.org_name

    def discord_autojoin(self) -> bool:
        """Holders of the Discord member role may sign in without an invite."""
        return self.db.setting("discord_autojoin") == "1"

    def member_role(self) -> str | None:
        return self.db.setting("discord_member_role_id") or self.cfg.discord_member_role_id

    def discord_app(self) -> DiscordApp:
        """Set on the admin page, else from the environment."""
        return DiscordApp(
            self.db.setting("discord_client_id") or self.cfg.discord_client_id,
            self.db.setting("discord_client_secret") or self.cfg.discord_client_secret,
            self.db.setting("discord_guild_id") or self.cfg.discord_guild_id,
        )

    def role_ok(self, ident: DiscordIdentity | None) -> bool:
        if ident is None:
            return False
        role = self.member_role()
        return role is None or role in ident.roles

    # -- sessions

    def sign_in(
        self,
        resp: web.StreamResponse,
        member: Member,
        request: web.Request | None = None,
        how: str | None = None,
    ) -> None:
        agent = request.headers.get("User-Agent", "") if request is not None else ""
        sid = self.db.new_session(member.id, device_label(agent), how)
        resp.set_cookie(
            SESSION_COOKIE,
            sid,
            max_age=30 * 86400,
            httponly=True,
            secure=self.cfg.secure,
            samesite="Lax",
            path="/",
        )

    async def current(self, request: web.Request) -> Member | None:
        """The signed-in, active member for this request, if any."""
        sid = request.cookies.get(SESSION_COOKIE)
        member = self.db.session_member(sid) if sid else None
        if member is None:
            return None
        self.db.touch_session(sid)
        member = await self.recheck(member)
        return member if member.active else None

    async def recheck(self, member: Member, *, force: bool = False) -> Member:
        """Keep a Discord-connected member in step with the org role (hourly)."""
        if (
            self.discord is None
            or member.discord_id is None
            or self.member_role() is None
            or member.discord_refresh is None
        ):
            return member
        if not force and now_ms() - (member.discord_checked or 0) < RECHECK_MS:
            return member
        try:
            token = member.discord_access
            if not token or (member.discord_expires or 0) < now_ms() + 60_000:
                fresh = await self.discord.refresh(member.discord_refresh)
                token = fresh["access_token"]
                self.db.discord_checked(
                    member.id,
                    access=token,
                    refresh=fresh.get("refresh_token"),
                    expires=expires_at(fresh),
                )
            ident = await self.discord.guild_member(token or "")
        except (PermissionError, web.HTTPException, aiohttp.ClientError) as exc:
            # Can't ask Discord right now: keep what we knew, try again later.
            log.warning("Couldn't re-check %s with Discord: %s", member.id, exc)
            self.db.discord_checked(member.id)
            return self.db.member(member.id) or member
        self.db.discord_checked(member.id)
        ok = self.role_ok(ident)
        if ok != bool(member.active):
            log.info("%s %s the Discord member role", member.id, "regained" if ok else "lost")
            self.db.set_active(member.id, ok)
            if not ok:
                self.db.end_member_sessions(member.id)
        return self.db.member(member.id) or member

    # -- Discord sign-in (optional)

    async def discord_start(self, request: web.Request) -> web.StreamResponse:
        """``/auth/discord?next=/&mode=signin|connect&invite=<code>``"""
        if self.discord is None:
            raise web.HTTPNotFound(text="Discord sign-in isn't set up on this hub.")
        mode = request.query.get("mode", "signin")
        if mode not in ("signin", "connect", "join"):
            mode = "signin"
        invite = request.query.get("invite", "")[:64] if mode == "join" else ""
        state = secrets.token_urlsafe(24)
        resp = web.HTTPFound(self.discord.authorize_url(state, prompt=mode != "signin"))
        resp.set_cookie(
            STATE_COOKIE,
            "|".join([state, mode, invite, valid_next(request.query.get("next", "/"))]),
            max_age=600,
            httponly=True,
            secure=self.cfg.secure,
            samesite="Lax",
            path="/auth/",
        )
        raise resp

    async def discord_callback(self, request: web.Request) -> web.StreamResponse:
        if self.discord is None:
            raise web.HTTPNotFound()
        state, mode, invite_code, next_url = (request.cookies.get(STATE_COOKIE, "") + "|||").split(
            "|"
        )[:4]
        if not state or not secrets.compare_digest(state, request.query.get("state", "")):
            return page(400, "Sign-in expired", "Please go back and try again.")
        if "error" in request.query:
            if request.query["error"] in ("consent_required", "interaction_required"):
                # prompt=none fails until the app is approved once: ask properly.
                raise web.HTTPFound(self.discord.authorize_url(state, prompt=True))
            return page(403, "Sign-in cancelled", "Discord didn't sign you in.")
        token = await self.discord.exchange(request.query.get("code", ""))
        try:
            ident = await self.discord.guild_member(token["access_token"])
        except PermissionError:
            ident = None
        if ident is None:
            return page(
                403,
                "Not in the server",
                "Use the Discord account that's in the org's Discord server.",
            )
        tokens = {
            "access": token["access_token"],
            "refresh": token.get("refresh_token"),
            "expires": expires_at(token),
        }
        if self.member_role() and not self.role_ok(ident):
            return page(
                403, "Members only", "Your Discord account doesn't have the org's member role."
            )
        existing = self.db.member_by_discord(ident.id)

        if mode == "connect":
            me = await self.current(request)
            if me is None:
                return page(401, "Not signed in", "Sign in first, then connect Discord.")
            if existing is not None and existing.id != me.id:
                return page(
                    409, "Already connected", "That Discord account belongs to another member."
                )
            self.db.set_discord(me.id, ident.id, avatar=ident.avatar, **tokens)
            member = self.db.member(me.id)
        elif existing is not None:
            if not existing.active:
                self.db.set_active(existing.id, True)  # role checked just above
            self.db.discord_checked(existing.id, **tokens)
            member = self.db.member(existing.id)
        elif mode == "join" and invite_code:
            invite = self.db.use_invite(invite_code)
            if invite is None:
                return page(410, "Invite expired", "Ask for a new invite link.")
            member = self.db.new_member(ident.name, role=invite.role, avatar=ident.avatar)
            self.db.set_discord(member.id, ident.id, avatar=ident.avatar, **tokens)
        elif self.discord_autojoin():
            member = self.db.new_member(ident.name, avatar=ident.avatar)
            self.db.set_discord(member.id, ident.id, avatar=ident.avatar, **tokens)
            log.info("New member from Discord: %s", member.id)
        else:
            return page(
                403,
                "No account yet",
                "Ask an admin for an invite link, then choose “Use Discord” on it.",
            )
        assert member is not None
        resp = web.HTTPFound(valid_next(next_url or "/"))
        self.sign_in(resp, member, request, "discord")
        resp.del_cookie(STATE_COOKIE, path="/auth/")
        raise resp


def valid_next(value: str) -> str:
    """Only same-site paths: never redirect off the hub after sign-in."""
    if not value.startswith("/") or value.startswith("//") or "\\" in value:
        return "/"
    return value


def page(status: int, title: str, text: str) -> web.Response:
    """A plain message page (sign-in errors). Titles and texts are ours, never user input."""
    html = f"""<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · Starglance</title>
<style>body{{font:15px system-ui,sans-serif;background:#0a0f16;color:#dbe6f2;display:grid;
place-items:center;min-height:90vh;margin:0}}main{{max-width:40ch;padding:24px;
border:1px solid #23303f;border-radius:6px;background:#101823}}h1{{font-size:1.2rem;margin:0 0 8px}}
a{{color:#46d3ff}}</style>
<main><h1>{title}</h1><p>{text}</p><p><a href="/">Back to the fleet</a></p></main>"""
    return web.Response(status=status, text=html, content_type="text/html")
