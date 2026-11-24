"""The hub end to end: accounts and invites, linking, agent ingest, the viewer feed,
the admin and integration APIs, and the optional Discord sign-in."""

from __future__ import annotations

import asyncio
import contextlib
import json
from pathlib import Path

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestServer
from fleet_agent.capturefile import read_frames
from fleet_agent.normalize import Normalizer
from fleet_hub.app import Hub
from fleet_hub.config import Config
from fleet_hub.db import MIGRATIONS, Database
from fleet_shared import SCHEMA_VERSION

FIXTURES = Path(__file__).parents[2] / "fixtures"


def ship_snapshot() -> dict:
    norm = Normalizer()
    for t, raw in read_frames(FIXTURES / "cruise-nav-scm.jsonl.gz"):
        snap = norm.feed(raw, t)
        if snap.ship and snap.ship.flight.speed:
            return json.loads(snap.model_dump_json(by_alias=True))
    raise AssertionError("no ship in fixture")


@contextlib.asynccontextmanager
async def running_hub(tmp_path: Path, **overrides):
    cfg = Config(**{"data_dir": tmp_path, "dev_login": True, **overrides})
    hub = Hub(cfg)
    server = TestServer(hub.app())
    await server.start_server()
    cfg.hub_url = str(server.make_url("")).rstrip("/")
    hub.refresh_setup()  # the setup link has the real address now
    try:
        yield hub, server
    finally:
        await server.close()
        hub.db.close()


def browser() -> aiohttp.ClientSession:
    return aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))


async def sign_in(http: aiohttp.ClientSession, hub: Hub, name: str) -> None:
    """Test sign-in by name. The first name used on a hub becomes its admin."""
    async with http.get(f"{hub.cfg.hub_url}/auth/dev", params={"name": name}) as resp:
        assert resp.status == 200  # followed the redirect to the page


def post(http: aiohttp.ClientSession, hub: Hub, path: str, body: dict | None = None, **kw):
    """A write from our own page (it carries our Origin)."""
    return http.post(
        f"{hub.cfg.hub_url}{path}", json=body or {}, headers={"Origin": hub.cfg.origin}, **kw
    )


async def link_agent(hub: Hub, viewer: aiohttp.ClientSession) -> str:
    """Link a PC to the signed-in member: the agent shows a code, they confirm it."""
    url = hub.cfg.hub_url
    async with aiohttp.ClientSession() as agent:
        start = await (
            await agent.post(f"{url}/api/agent/link/start", json={"machine": "RIG"})
        ).json()
        poll = await agent.post(f"{url}/api/agent/link/poll", json=start)
        assert (await poll.json())["status"] == "pending"
        info = await (await viewer.get(f"{url}/api/link/{start['user_code'].lower()}")).json()
        assert info["machine"] == "RIG" and not info["confirmed"]
        ok = await post(viewer, hub, f"/api/link/{start['user_code']}/confirm")
        assert ok.status == 200
        linked = await (await agent.post(f"{url}/api/agent/link/poll", json=start)).json()
        assert linked["status"] == "linked" and linked["token"]
        again = await agent.post(f"{url}/api/agent/link/poll", json=start)
        assert again.status == 410, "the token is handed out once"
        return linked["token"]


async def make_invite(admin: aiohttp.ClientSession, hub: Hub, **body) -> str:
    resp = await post(admin, hub, "/api/admin/invites", body)
    assert resp.status == 201, await resp.text()
    url = (await resp.json())["url"]
    return url.rsplit("/join/", 1)[1]


async def agent_join(hub: Hub, code: str, name: str) -> tuple[int, dict]:
    async with aiohttp.ClientSession() as agent:
        resp = await agent.post(
            f"{hub.cfg.hub_url}/api/agent/join",
            json={"invite": code, "name": name, "machine": f"{name}-PC"},
        )
        return resp.status, await resp.json()


async def until(ws, pred, timeout: float = 5.0) -> dict:
    async def loop():
        while True:
            msg = await ws.receive()
            if msg.type != aiohttp.WSMsgType.TEXT:
                raise AssertionError(f"socket closed: {msg}")
            data = json.loads(msg.data)
            if pred(data):
                return data

    return await asyncio.wait_for(loop(), timeout)


def ws_url(hub: Hub, path: str) -> str:
    return hub.cfg.hub_url.replace("http://", "ws://") + path


def agent_socket(http: aiohttp.ClientSession, hub: Hub, token: str):
    return http.ws_connect(ws_url(hub, "/ws/agent"), headers={"Authorization": f"Bearer {token}"})


async def mode(http: aiohttp.ClientSession, hub: Hub) -> dict:
    return await (await http.get(f"{hub.cfg.hub_url}/api/mode")).json()


# ---------------------------------------------------------------- telemetry


def test_link_then_watch_a_member_live(tmp_path):
    async def main():
        async with running_hub(tmp_path) as (hub, _srv), browser() as viewer:
            await sign_in(viewer, hub, "Rook")
            token = await link_agent(hub, viewer)
            snap = ship_snapshot()
            async with aiohttp.ClientSession() as http, agent_socket(http, hub, token) as agent:
                welcome = await until(agent, lambda d: True)
                assert welcome["type"] == "welcome" and welcome["member"]["name"] == "Rook"
                await agent.send_json(
                    {"type": "hello", "v": 1, "agent_version": "t", "channel": "LIVE"}
                )
                await agent.send_json(snap)

                async with viewer.ws_connect(
                    ws_url(hub, "/ws/view"), headers={"Origin": hub.cfg.origin}
                ) as view:
                    hello = await until(view, lambda d: d["type"] == "hello")
                    assert hello["me"]["name"] == "Rook"
                    roster = await until(view, lambda d: d["type"] == "roster")
                    (member_id,) = roster["members"]
                    row = roster["members"][member_id]
                    assert row["presence"] == "live"
                    assert row["ship"]["model"] == snap["ship"]["model"]
                    assert row["ship"]["speed"] == round(snap["ship"]["flight"]["speed"])
                    assert {"alt", "agl", "vsi", "heading", "g"} <= row["ship"].keys()
                    assert {"health", "oxygen", "hunger", "thirst"} <= row["vitals"].keys()

                    await view.send_json({"type": "focus", "member": member_id})
                    full = await until(view, lambda d: d["type"] == "member")
                    assert full["snapshot"]["ship"]["class"] == snap["ship"]["class"]

                    t = snap["t"] + 100
                    patch = {"t": t, "ship": {"flight": {"speed": 321.5}}}
                    await agent.send_json({"type": "delta", "v": 1, "t": t, "patch": patch})
                    delta = await until(view, lambda d: d["type"] == "member_delta")
                    assert delta["patch"]["ship"]["flight"]["speed"] == 321.5

                    await agent.send_json(
                        {"type": "event", "v": 1, "t": snap["t"], "kind": "takeoff", "data": {}}
                    )
                    event = await until(view, lambda d: d["type"] == "event")
                    assert event["member"] == member_id and event["kind"] == "takeoff"

                    await agent.send_json({"type": "heartbeat", "v": 1, "t": 0, "in_game": False})
                    idle = await until(
                        view,
                        lambda d: (
                            d["type"] == "roster_delta"
                            and d["patch"].get(member_id, {}).get("presence") == "idle"
                        ),
                    )
                    assert idle["patch"][member_id]["ship"] is None

    asyncio.run(main())


def test_hub_enforces_sharing(tmp_path):
    async def main():
        async with running_hub(tmp_path) as (hub, _srv), browser() as viewer:
            await sign_in(viewer, hub, "Ace")
            token = await link_agent(hub, viewer)
            snap = ship_snapshot()
            snap["location"] = {"armistice": True, "jurisdiction": "UEE"}
            snap["session"] = {"kills": 2, "earned": 5000}
            async with aiohttp.ClientSession() as http, agent_socket(http, hub, token) as agent:
                await until(agent, lambda d: d["type"] == "welcome")
                share = ["status", "ship", "combat"]  # no location, vitals or uec
                await agent.send_json(
                    {"type": "hello", "v": 1, "agent_version": "t", "share": share}
                )
                await agent.send_json(snap)
                for kind in ("armistice_enter", "injury", "kill"):
                    await agent.send_json({"type": "event", "v": 1, "t": 1, "kind": kind})
                await agent.send_json(
                    {"type": "delta", "v": 1, "t": 2, "patch": {"location": {"armistice": False}}}
                )
                await asyncio.sleep(0.3)
            (mid,) = hub.fleet.members
            state = hub.fleet.member_state(mid)
            assert state["location"] is None and state["vitals"] is None
            assert state["session"]["kills"] == 2 and state["session"]["earned"] == 0
            assert [e["kind"] for e in hub.fleet.recent] == ["kill"]

    asyncio.run(main())


def test_old_agents_are_told_to_update(tmp_path):
    async def main():
        async with running_hub(tmp_path) as (hub, _srv), browser() as viewer:
            await sign_in(viewer, hub, "Rook")
            token = await link_agent(hub, viewer)
            async with aiohttp.ClientSession() as http, agent_socket(http, hub, token) as agent:
                await until(agent, lambda d: d["type"] == "welcome")
                await agent.send_json(
                    {"type": "hello", "v": SCHEMA_VERSION + 1, "agent_version": "9"}
                )
                error = await until(agent, lambda d: d["type"] == "error")
                assert error["code"] == "version"
                closed = await agent.receive()
                assert closed.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED)

    asyncio.run(main())


# ---------------------------------------------------------------- accounts


def test_first_admin_comes_from_the_setup_link(tmp_path):
    async def main():
        async with running_hub(tmp_path, dev_login=False) as (hub, _srv), browser() as http:
            assert hub.setup_url, "a hub with no admin logs a setup link"
            code = hub.setup_url.rsplit("/join/", 1)[1]
            info = await (await http.get(f"{hub.cfg.hub_url}/api/invite/{code}")).json()
            assert info["role"] == "admin"
            assert (await mode(http, hub))["setup"] is True

            joined = await post(http, hub, "/api/join", {"code": code, "name": "Founder"})
            assert joined.status == 200
            me = (await mode(http, hub))["me"]
            assert me["name"] == "Founder" and me["role"] == "admin"
            assert hub.setup_url is None and (await mode(http, hub))["setup"] is False

            async with browser() as other:
                again = await post(other, hub, "/api/join", {"code": code, "name": "Thief"})
                assert again.status == 410, "the setup link works once"

    asyncio.run(main())


def test_invites_from_the_agent_and_the_browser(tmp_path):
    async def main():
        async with running_hub(tmp_path) as (hub, _srv), browser() as admin:
            await sign_in(admin, hub, "Admin")
            code = await make_invite(admin, hub, uses=5, days=7, note="Friday crew")

            # A player joins from their PC: account and link in one step, no browser.
            status, body = await agent_join(hub, code, "Kestrel")
            assert status == 200 and body["member"]["name"] == "Kestrel"
            async with (
                aiohttp.ClientSession() as http,
                agent_socket(http, hub, body["token"]) as agent,
            ):
                welcome = await until(agent, lambda d: d["type"] == "welcome")
                assert welcome["member"]["name"] == "Kestrel"

            # A viewer without the game joins in the browser with the same invite.
            async with browser() as phone:
                resp = await post(phone, hub, "/api/join", {"code": code, "name": "Ops Lead"})
                assert resp.status == 200
                me = (await mode(phone, hub))["me"]
                assert me["name"] == "Ops Lead" and me["role"] == "member"
                assert (await phone.get(f"{hub.cfg.hub_url}/api/admin/members")).status == 403
                no = await post(phone, hub, "/api/admin/invites", {})
                assert no.status == 403, "members can't make invites"

            invites = await (await admin.get(f"{hub.cfg.hub_url}/api/admin/invites")).json()
            (invite,) = invites
            assert invite["uses"] == 2 and invite["note"] == "Friday crew"
            gone = await admin.delete(
                f"{hub.cfg.hub_url}/api/admin/invites/{invite['id']}",
                headers={"Origin": hub.cfg.origin},
            )
            assert gone.status == 200
            status, _ = await agent_join(hub, code, "Late")
            assert status == 410, "a revoked invite stops working"

            single = await make_invite(admin, hub, uses=1)
            assert (await agent_join(hub, single, "One"))[0] == 200
            assert (await agent_join(hub, single, "Two"))[0] == 410

    asyncio.run(main())


def test_add_a_device_and_open_from_the_agent(tmp_path):
    async def main():
        async with running_hub(tmp_path) as (hub, _srv), browser() as pc:
            await sign_in(pc, hub, "Rook")
            token = await link_agent(hub, pc)

            # "Add a device": the signed-in browser shows a code; the phone types it.
            code = (await (await post(pc, hub, "/api/me/device-code")).json())["code"]
            async with browser() as phone:
                ok = await post(phone, hub, "/api/signin/code", {"code": code.lower()})
                assert ok.status == 200
                assert (await mode(phone, hub))["me"]["name"] == "Rook"
            async with browser() as other:
                again = await post(other, hub, "/api/signin/code", {"code": code})
                assert again.status == 404, "a device code works once"

            # `fleet_agent open`: a one-time link signs a browser in.
            async with aiohttp.ClientSession() as agent:
                resp = await agent.post(
                    f"{hub.cfg.hub_url}/api/agent/login-link",
                    headers={"Authorization": f"Bearer {token}"},
                )
                url = (await resp.json())["url"]
            async with browser() as fresh:
                assert (await fresh.get(url)).status == 200
                assert (await mode(fresh, hub))["me"]["name"] == "Rook"
                assert (await fresh.get(url, allow_redirects=False)).status == 410

            # Rename yourself; the roster follows.
            renamed = await pc.patch(
                f"{hub.cfg.hub_url}/api/me",
                json={"name": "Rook 2"},
                headers={"Origin": hub.cfg.origin},
            )
            assert (await renamed.json())["name"] == "Rook 2"
            assert [m["name"] for m in hub.fleet.roster.values()] == ["Rook 2"]

    asyncio.run(main())


def test_admins_suspend_and_remove_members(tmp_path):
    async def main():
        async with running_hub(tmp_path) as (hub, _srv), browser() as admin:
            await sign_in(admin, hub, "Admin")
            code = await make_invite(admin, hub, uses=1)
            _status, body = await agent_join(hub, code, "Gone Soon")
            mid, token = body["member"]["id"], body["token"]
            url = hub.cfg.hub_url
            origin = {"Origin": hub.cfg.origin}
            bearer = {"Authorization": f"Bearer {token}"}

            async with aiohttp.ClientSession() as http:
                async with agent_socket(http, hub, token) as agent:
                    await until(agent, lambda d: d["type"] == "welcome")
                    await agent.send_json(
                        {"type": "event", "v": 1, "t": 1, "kind": "takeoff", "data": {}}
                    )
                    await asyncio.sleep(0.2)
                    resp = await admin.patch(
                        f"{url}/api/admin/members/{mid}", json={"active": False}, headers=origin
                    )
                    assert resp.status == 200
                    error = await until(agent, lambda d: d["type"] == "error")
                    assert error["code"] == "revoked"
                refused = await http.get(f"{url}/ws/agent", headers=bearer)
                assert refused.status == 403, "a suspended member's PC is refused"

                members = await (await admin.get(f"{url}/api/admin/members")).json()
                assert {m["name"]: m["active"] for m in members} == {
                    "Admin": True,
                    "Gone Soon": False,
                }

                resp = await admin.delete(f"{url}/api/admin/members/{mid}", headers=origin)
                assert resp.status == 200
                assert hub.db.member(mid) is None
                assert hub.db.recent_events() == [], "their history goes with them"
                assert mid not in hub.fleet.roster
                refused = await http.get(f"{url}/ws/agent", headers=bearer)
                assert refused.status == 401

            # There's always an admin.
            me = (await mode(admin, hub))["me"]
            last = await admin.patch(
                f"{url}/api/admin/members/{me['id']}", json={"role": "member"}, headers=origin
            )
            assert last.status == 409
            assert (await admin.delete(f"{url}/api/me", headers=origin)).status == 409

    asyncio.run(main())


def test_members_can_delete_themselves(tmp_path):
    async def main():
        async with running_hub(tmp_path) as (hub, _srv), browser() as admin:
            await sign_in(admin, hub, "Admin")
            code = await make_invite(admin, hub)
            async with browser() as me:
                await post(me, hub, "/api/join", {"code": code, "name": "Leaving"})
                resp = await me.delete(
                    f"{hub.cfg.hub_url}/api/me", headers={"Origin": hub.cfg.origin}
                )
                assert resp.status == 200
                assert (await mode(me, hub))["me"] is None
            assert [m.name for m in hub.db.members()] == ["Admin"]

    asyncio.run(main())


def test_refusals(tmp_path):
    async def main():
        async with running_hub(tmp_path) as (hub, _srv), browser() as viewer:
            url = hub.cfg.hub_url
            async with aiohttp.ClientSession() as anon:
                assert (await anon.get(f"{url}/api/link/ABC-DEF")).status == 401
                assert (await anon.get(f"{url}/api/me")).status == 401
                assert (await mode(anon, hub))["me"] is None
                assert (await anon.get(ws_url(hub, "/ws/view"))).status == 401
                bad = await anon.get(f"{url}/ws/agent", headers={"Authorization": "Bearer nope"})
                assert bad.status == 401
                assert (await anon.get(f"{url}/api/v1/fleet")).status == 401
                assert (await anon.get(f"{url}/api/invite/nonsense")).status == 410
            await sign_in(viewer, hub, "Rook")
            start = await (await viewer.post(f"{url}/api/agent/link/start", json={})).json()
            evil = await viewer.post(
                f"{url}/api/link/{start['user_code']}/confirm",
                headers={"Origin": "https://evil.example"},
            )
            assert evil.status == 403, "another site can't confirm a link with your cookie"
            no_origin = await viewer.post(f"{url}/api/link/{start['user_code']}/confirm")
            assert no_origin.status == 403

    asyncio.run(main())


def test_database_migrations_run_once(tmp_path):
    db = Database(tmp_path / "hub.sqlite3")
    db.new_member("Keep me")
    db.close()
    again = Database(tmp_path / "hub.sqlite3")
    assert again.conn.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)
    assert [m.name for m in again.members()] == ["Keep me"]
    again.close()


# ---------------------------------------------------------------- integrations


def test_integration_api_with_keys(tmp_path):
    async def main():
        async with running_hub(tmp_path) as (hub, _srv), browser() as admin:
            await sign_in(admin, hub, "Admin")
            token = await link_agent(hub, admin)
            url = hub.cfg.hub_url
            made = await post(admin, hub, "/api/admin/keys", {"name": "Bot", "scopes": ["read"]})
            assert made.status == 201
            read_key = (await made.json())["key"]
            keys = await (await admin.get(f"{url}/api/admin/keys")).json()
            assert keys[0]["name"] == "Bot" and "key" not in keys[0], "shown once, never again"

            bot = aiohttp.ClientSession(headers={"Authorization": f"Bearer {read_key}"})
            stream = await bot.ws_connect(ws_url(hub, "/api/v1/events/stream"))
            async with aiohttp.ClientSession() as http, agent_socket(http, hub, token) as agent:
                await until(agent, lambda d: d["type"] == "welcome")
                await agent.send_json(ship_snapshot())
                await agent.send_json(
                    {
                        "type": "event",
                        "v": 1,
                        "t": 5,
                        "kind": "warning_on",
                        "data": {"light": "hit"},
                    }
                )
                got = await until(stream, lambda d: d["type"] == "event")
                assert got["kind"] == "warning_on" and got["data"] == {"light": "hit"}
                await asyncio.sleep(0.6)  # one roster refresh
                fleet = await (await bot.get(f"{url}/api/v1/fleet")).json()
                (row,) = fleet["members"]
                assert row["name"] == "Admin" and row["presence"] == "live"
                one = await (await bot.get(f"{url}/api/v1/members/{row['id']}")).json()
                assert one["snapshot"]["ship"]["model"] == row["ship"]["model"]
                events = await (await bot.get(f"{url}/api/v1/events?since=0")).json()
                assert [e["kind"] for e in events] == ["warning_on"]
            await stream.close()

            assert (await bot.post(f"{url}/api/v1/invites", json={})).status == 403
            await bot.close()

            made = await post(
                admin, hub, "/api/admin/keys", {"name": "Inviter", "scopes": ["invites"]}
            )
            inviter = await made.json()
            async with aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {inviter['key']}"}
            ) as bot2:
                inv = await bot2.post(f"{url}/api/v1/invites", json={"uses": 1, "days": 1})
                assert inv.status == 201 and "/join/" in (await inv.json())["url"]
                admin_inv = await bot2.post(f"{url}/api/v1/invites", json={"role": "admin"})
                assert admin_inv.status == 400, "keys can't make admins"
                gone = await admin.delete(
                    f"{url}/api/admin/keys/{inviter['id']}", headers={"Origin": hub.cfg.origin}
                )
                assert gone.status == 200
                assert (await bot2.post(f"{url}/api/v1/invites", json={})).status == 401

    asyncio.run(main())


# ---------------------------------------------------------------- Discord (optional)


class FakeDiscord:
    """Just enough of Discord's OAuth and guild member endpoints."""

    def __init__(self) -> None:
        # Who's who, by the code Discord would hand back. Anyone else isn't in the server.
        self.roles = {"ace": ["42"], "norole": ["7"], "newbie": ["42"]}
        app = web.Application()
        app.add_routes(
            [
                web.post("/api/oauth2/token", self.token),
                web.get("/api/users/@me/guilds/{guild}/member", self.member),
            ]
        )
        self.server = TestServer(app)

    async def token(self, request: web.Request) -> web.Response:
        form = await request.post()
        who = form.get("code") or str(form.get("refresh_token", "")).removeprefix("refresh-")
        return web.json_response(
            {"access_token": f"tok-{who}", "refresh_token": f"refresh-{who}", "expires_in": 604800}
        )

    async def member(self, request: web.Request) -> web.Response:
        who = request.headers["Authorization"].removeprefix("Bearer tok-")
        if who not in self.roles:
            return web.json_response({"message": "Unknown Guild"}, status=404)
        return web.json_response(
            {
                "user": {"id": f"id-{who}", "username": who, "global_name": who.title()},
                "nick": None,
                "roles": self.roles[who],
            }
        )


async def discord_sign_in(
    hub: Hub, base: str, who: str, **query
) -> tuple[int, aiohttp.ClientSession]:
    http = browser()
    start = await http.get(f"{hub.cfg.hub_url}/auth/discord", params=query, allow_redirects=False)
    assert start.status == 302 and start.headers["Location"].startswith(base)
    state = start.headers["Location"].split("state=")[1].split("&")[0]
    cb = await http.get(
        f"{hub.cfg.hub_url}/auth/discord/callback",
        params={"code": who, "state": state},
        allow_redirects=False,
    )
    return cb.status, http


def test_discord_is_optional_and_follows_the_role(tmp_path):
    async def main():
        discord = FakeDiscord()
        await discord.server.start_server()
        base = str(discord.server.make_url("")).rstrip("/")
        try:
            async with (
                running_hub(
                    tmp_path,
                    discord_client_id="cid",
                    discord_client_secret="csecret",
                    discord_guild_id="1",
                    discord_member_role_id="42",
                    discord_api=f"{base}/api",
                    discord_authorize=f"{base}/authorize",
                ) as (hub, _srv),
                browser() as admin,
            ):
                await sign_in(admin, hub, "Admin")
                assert (await mode(admin, hub))["discord"] is True
                sessions = []

                # No account and no auto-join: Discord alone doesn't let you in.
                status, http = await discord_sign_in(hub, base, "ace")
                sessions.append(http)
                assert status == 403

                # With an invite, "Use Discord" creates the account and connects it.
                code = await make_invite(admin, hub, uses=5)
                status, ace = await discord_sign_in(hub, base, "ace", mode="join", invite=code)
                sessions.append(ace)
                assert status == 302
                me = (await mode(ace, hub))["me"]
                assert me["name"] == "Ace" and me["discord"] is True

                # Next time, Discord signs them straight in.
                status, again = await discord_sign_in(hub, base, "ace")
                sessions.append(again)
                assert status == 302 and (await mode(again, hub))["me"]["name"] == "Ace"

                # Without the role: refused, invite or not.
                status, http = await discord_sign_in(hub, base, "norole", mode="join", invite=code)
                sessions.append(http)
                assert status == 403

                # Admins can let role holders in without invites.
                await admin.put(
                    f"{hub.cfg.hub_url}/api/admin/settings",
                    json={"discord_autojoin": True},
                    headers={"Origin": hub.cfg.origin},
                )
                status, newbie = await discord_sign_in(hub, base, "newbie")
                sessions.append(newbie)
                assert status == 302 and (await mode(newbie, hub))["me"]["name"] == "Newbie"

                # Losing the role suspends them at the next check; members without
                # Discord (the admin here) are unaffected.
                discord.roles["ace"] = ["7"]
                member = hub.db.member_by_discord("id-ace")
                member = await hub.auth.recheck(member, force=True)
                assert not member.active
                assert (await mode(ace, hub))["me"] is None
                assert (await mode(admin, hub))["me"]["name"] == "Admin"

                # A forged state is refused.
                async with browser() as http:
                    forged = await http.get(
                        f"{hub.cfg.hub_url}/auth/discord/callback",
                        params={"code": "ace", "state": "x"},
                        allow_redirects=False,
                    )
                    assert forged.status == 400
                for session in sessions:
                    await session.close()
        finally:
            await discord.server.close()

    asyncio.run(main())


def test_without_discord_there_is_no_discord_sign_in(tmp_path):
    async def main():
        async with running_hub(tmp_path) as (hub, _srv), browser() as http:
            assert (await mode(http, hub))["discord"] is False
            resp = await http.get(f"{hub.cfg.hub_url}/auth/discord", allow_redirects=False)
            assert resp.status == 404

    asyncio.run(main())


def test_the_local_fleet_view_through_the_agent(tmp_path):
    """A linked PC's agent opens the fleet stream with its token and relays it to its
    local page; the page may only choose who's open. Without a link: "unlinked"."""
    from fleet_agent.localserver import LocalServer
    from fleet_agent.runtime import Pipeline
    from fleet_agent.uplink import Uplink

    async def main():
        async with running_hub(tmp_path) as (hub, _srv), browser() as viewer:
            await sign_in(viewer, hub, "Rook")
            token = await link_agent(hub, viewer)
            snap = ship_snapshot()
            async with aiohttp.ClientSession() as http, agent_socket(http, hub, token) as agent:
                await until(agent, lambda d: True)
                await agent.send_json({"type": "hello", "v": 1, "agent_version": "t"})
                await agent.send_json(snap)

                pipeline = Pipeline()
                server = LocalServer(pipeline, port=0, web_dir=tmp_path / "none")
                await server.start()
                try:
                    url = f"http://127.0.0.1:{server.port}/ws/fleet"
                    async with http.ws_connect(url) as page:
                        assert (await page.receive_json())["type"] == "unlinked"

                    uplink = Uplink(pipeline, hub.cfg.hub_url, token, set())
                    server.fleet_view = uplink.fleet_view
                    async with http.ws_connect(url) as page:
                        hello = await until(page, lambda d: d["type"] == "hello")
                        assert hello["me"]["name"] == "Rook" and hello["org"]
                        roster = await until(page, lambda d: d["type"] == "roster")
                        (member_id,) = roster["members"]
                        await page.send_json({"type": "nonsense"})  # not passed on
                        await page.send_json({"type": "focus", "member": member_id})
                        full = await until(page, lambda d: d["type"] == "member")
                        assert full["snapshot"]["ship"]["class"] == snap["ship"]["class"]

                    # A revoked token: the page hears why.
                    server.fleet_view = Uplink(pipeline, hub.cfg.hub_url, "bogus", set()).fleet_view
                    async with http.ws_connect(url) as page:
                        err = await until(page, lambda d: d["type"] == "error")
                        assert "link it again" in err["message"]
                finally:
                    await server.stop()

    asyncio.run(main())


IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15"
    " (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
)
EDGE = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
)


def test_device_labels():
    from fleet_hub.auth import device_label

    assert device_label(IPHONE) == "Safari on iPhone"
    assert device_label(EDGE) == "Edge on Windows"
    assert device_label("") is None


def test_signed_in_devices_and_signing_them_out(tmp_path):
    """See where you're signed in; sign out a lost phone, or everything but here."""

    async def main():
        async with running_hub(tmp_path) as (hub, _srv):
            pc = aiohttp.ClientSession(
                cookie_jar=aiohttp.CookieJar(unsafe=True), headers={"User-Agent": EDGE}
            )
            phone = aiohttp.ClientSession(
                cookie_jar=aiohttp.CookieJar(unsafe=True), headers={"User-Agent": IPHONE}
            )
            tablet = browser()
            async with pc, phone, tablet:
                for http in (pc, phone, tablet):
                    await sign_in(http, hub, "Rook")
                url = f"{hub.cfg.hub_url}/api/me/sessions"
                devices = await (await pc.get(url)).json()
                assert {d["label"] for d in devices} >= {"Edge on Windows", "Safari on iPhone"}
                assert [d["current"] for d in devices].count(True) == 1
                here = next(d for d in devices if d["current"])
                assert here["label"] == "Edge on Windows" and here["how"] == "dev"
                phone_id = next(d["id"] for d in devices if d["label"] == "Safari on iPhone")

                # The phone's open fleet view closes when it's signed out.
                async with phone.ws_connect(
                    ws_url(hub, "/ws/view"), headers={"Origin": hub.cfg.origin}
                ) as view:
                    await until(view, lambda d: d["type"] == "hello")
                    async with post(pc, hub, f"/api/me/sessions/{phone_id}/end") as r:
                        assert r.status == 200

                    async def closed():
                        while (await view.receive()).type == aiohttp.WSMsgType.TEXT:
                            pass  # what was already queued

                    await asyncio.wait_for(closed(), 5)
                assert (await phone.get(f"{hub.cfg.hub_url}/api/me")).status == 401
                async with post(pc, hub, "/api/me/sessions/nothere12345678/end") as r:
                    assert r.status == 404

                async with post(pc, hub, "/api/me/sessions/others/end") as r:
                    assert (await r.json())["ended"] == 1  # the tablet
                assert (await tablet.get(f"{hub.cfg.hub_url}/api/me")).status == 401
                assert (await pc.get(f"{hub.cfg.hub_url}/api/me")).status == 200

                # Signing out this device from the list signs you out here.
                (only,) = await (await pc.get(url)).json()
                async with post(pc, hub, f"/api/me/sessions/{only['id']}/end") as r:
                    assert r.status == 200
                assert (await pc.get(f"{hub.cfg.hub_url}/api/me")).status == 401

    asyncio.run(main())


def test_agents_hear_the_current_version_and_old_ones_are_refused(tmp_path):
    from fleet_hub import MIN_AGENT_VERSION, __version__

    async def main():
        async with running_hub(tmp_path) as (hub, _srv), browser() as viewer:
            await sign_in(viewer, hub, "Rook")
            token = await link_agent(hub, viewer)
            async with aiohttp.ClientSession() as http, agent_socket(http, hub, token) as agent:
                welcome = await until(agent, lambda d: d["type"] == "welcome")
                assert welcome["latest_agent"] == __version__
                assert welcome["min_agent"] == MIN_AGENT_VERSION
                assert welcome["download"].startswith("https://github.com/")
                await agent.send_json({"type": "hello", "v": 1, "agent_version": "0.0.9"})
                error = await until(agent, lambda d: d["type"] == "error")
                assert error["code"] == "version" and "Download the latest" in error["message"]
            # A development build (not a plain version number) is never refused.
            async with aiohttp.ClientSession() as http, agent_socket(http, hub, token) as agent:
                await until(agent, lambda d: d["type"] == "welcome")
                await agent.send_json({"type": "hello", "v": 1, "agent_version": "dev"})
                await agent.send_json(ship_snapshot())
                with contextlib.suppress(asyncio.TimeoutError):
                    bad = await until(agent, lambda d: d["type"] == "error", timeout=0.5)
                    raise AssertionError(bad)

    asyncio.run(main())


def test_agent_settings_join_share_and_leave(tmp_path, monkeypatch):
    """The cockpit's Agent tab: join a fleet with an invite link, stop sharing something
    (the hub hears at once), leave (the hub forgets this PC). No restart."""
    from fleet_agent.control import AgentControl
    from fleet_agent.localserver import LocalServer
    from fleet_agent.runtime import Pipeline

    monkeypatch.setenv("FLEET_TELEMETRY_HOME", str(tmp_path / "agent"))
    (tmp_path / "agent").mkdir()

    async def main():
        async with running_hub(tmp_path) as (hub, _srv), browser() as admin:
            await sign_in(admin, hub, "Admin")
            code = await make_invite(admin, hub)
            invite = f"{hub.cfg.hub_url}/join/{code}"
            pipeline = Pipeline()
            server = LocalServer(pipeline, port=0, web_dir=tmp_path / "none")
            control = AgentControl(pipeline, server, install=None, announce=lambda _m: None)
            await server.start()
            base = f"http://127.0.0.1:{server.port}/api/agent"
            try:
                async with aiohttp.ClientSession() as page:
                    state = await (await page.get(f"{base}/settings")).json()
                    assert state["linked"] is False and len(state["share"]) == 8

                    r = await page.post(f"{base}/join", json={"target": invite, "name": ""})
                    assert r.status == 400, "a name is needed (no Game.log to suggest one)"
                    r = await page.post(f"{base}/join", json={"target": invite, "name": "Wren"})
                    state = await r.json()
                    assert r.status == 200, state
                    assert state["linked"] and state["member"] == "Wren" and state["sending"]

                    (member_id,) = [m.id for m in hub.db.members() if m.name == "Wren"]
                    live = hub.fleet.members

                    async def until_true(pred):
                        for _ in range(100):
                            if pred():
                                return
                            await asyncio.sleep(0.05)
                        raise AssertionError("timed out")

                    await until_true(lambda: member_id in live and live[member_id].connected)
                    r = await page.post(f"{base}/share", json={"share": {"vitals": False}})
                    shares = {s["id"]: s["on"] for s in (await r.json())["share"]}
                    assert shares["vitals"] is False and shares["ship"] is True
                    await until_true(
                        lambda: live[member_id].connected and "vitals" not in live[member_id].share
                    )

                    # Not JSON (a form post from some other page): refused.
                    r = await page.post(f"{base}/share", data="share=x")
                    assert r.status == 415

                    state = await (await page.post(f"{base}/leave", json={})).json()
                    assert state["linked"] is False and state["sending"] is False
                    assert hub.db.agents_of(member_id) == [], "the hub forgot this PC"
                    assert control.uplink is None

                    r = await page.post(f"{base}/telemetry", json={"channel": "NOPE", "on": True})
                    assert r.status == 400
            finally:
                await control.stop_uplink()
                await server.stop()

    asyncio.run(main())
