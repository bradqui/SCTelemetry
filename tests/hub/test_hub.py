"""The hub end to end: sign-in, linking, agent ingest, the viewer feed, the internal API."""

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
    cfg = Config(
        **{"data_dir": tmp_path, "dev_login": True, "internal_secret": "s3cret", **overrides}
    )
    hub = Hub(cfg)
    public = TestServer(hub.public_app())
    await public.start_server()
    cfg.hub_url = str(public.make_url("")).rstrip("/")
    internal = TestServer(hub.internal_app())
    await internal.start_server()
    try:
        yield hub, public, internal
    finally:
        await internal.close()
        await public.close()
        hub.db.close()


def browser() -> aiohttp.ClientSession:
    return aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))


async def sign_in(http: aiohttp.ClientSession, hub: Hub, name: str) -> None:
    async with http.get(f"{hub.cfg.hub_url}/auth/dev", params={"name": name}) as resp:
        assert resp.status == 200  # followed the redirect to the page


async def link_agent(hub: Hub, viewer: aiohttp.ClientSession) -> str:
    url = hub.cfg.hub_url
    async with aiohttp.ClientSession() as agent:
        start = await (
            await agent.post(f"{url}/api/agent/link/start", json={"machine": "RIG"})
        ).json()
        poll = await agent.post(f"{url}/api/agent/link/poll", json=start)
        assert (await poll.json())["status"] == "pending"
        info = await (await viewer.get(f"{url}/api/link/{start['user_code'].lower()}")).json()
        assert info["machine"] == "RIG" and not info["confirmed"]
        ok = await viewer.post(
            f"{url}/api/link/{start['user_code']}/confirm", headers={"Origin": hub.cfg.origin}
        )
        assert ok.status == 200
        linked = await (await agent.post(f"{url}/api/agent/link/poll", json=start)).json()
        assert linked["status"] == "linked" and linked["token"]
        again = await agent.post(f"{url}/api/agent/link/poll", json=start)
        assert again.status == 410, "the token is handed out once"
        return linked["token"]


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


# ---------------------------------------------------------------- tests


def test_link_then_watch_a_member_live(tmp_path):
    async def main():
        async with running_hub(tmp_path) as (hub, _pub, _int), browser() as viewer:
            await sign_in(viewer, hub, "Rook")
            token = await link_agent(hub, viewer)
            snap = ship_snapshot()
            async with (
                aiohttp.ClientSession() as http,
                http.ws_connect(
                    ws_url(hub, "/ws/agent"), headers={"Authorization": f"Bearer {token}"}
                ) as agent,
            ):
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

                    await view.send_json({"type": "focus", "member": member_id})
                    full = await until(view, lambda d: d["type"] == "member")
                    assert full["snapshot"]["ship"]["class"] == snap["ship"]["class"]

                    await agent.send_json(
                        {
                            "type": "delta",
                            "v": 1,
                            "t": snap["t"] + 100,
                            "patch": {"t": snap["t"] + 100, "ship": {"flight": {"speed": 321.5}}},
                        }
                    )
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
        async with running_hub(tmp_path) as (hub, _pub, _int), browser() as viewer:
            await sign_in(viewer, hub, "Ace")
            token = await link_agent(hub, viewer)
            snap = ship_snapshot()
            snap["location"] = {"armistice": True, "jurisdiction": "UEE"}
            snap["session"] = {"kills": 2, "earned": 5000}
            async with (
                aiohttp.ClientSession() as http,
                http.ws_connect(
                    ws_url(hub, "/ws/agent"), headers={"Authorization": f"Bearer {token}"}
                ) as agent,
            ):
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


def test_refusals(tmp_path):
    async def main():
        async with running_hub(tmp_path) as (hub, _pub, internal), browser() as viewer:
            url = hub.cfg.hub_url
            async with aiohttp.ClientSession() as anon:
                assert (await anon.get(f"{url}/api/link/ABC-DEF")).status == 401
                assert (await (await anon.get(f"{url}/api/mode")).json())["me"] is None
                bad = await anon.get(ws_url(hub, "/ws/view"))
                assert bad.status == 401
                bad = await anon.get(f"{url}/ws/agent", headers={"Authorization": "Bearer nope"})
                assert bad.status == 401
                internal_url = str(internal.make_url("/internal/fleet"))
                assert (await anon.get(internal_url)).status == 403
                wrong = await anon.get(internal_url, headers={"X-Internal-Secret": "guess"})
                assert wrong.status == 403
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


def test_revoking_a_pc_disconnects_it(tmp_path):
    async def main():
        async with running_hub(tmp_path) as (hub, _pub, _int), browser() as viewer:
            await sign_in(viewer, hub, "Rook")
            token = await link_agent(hub, viewer)
            headers = {"Authorization": f"Bearer {token}"}
            async with aiohttp.ClientSession() as http:
                async with http.ws_connect(ws_url(hub, "/ws/agent"), headers=headers) as agent:
                    await until(agent, lambda d: d["type"] == "welcome")
                    (pc,) = await (await viewer.get(f"{hub.cfg.hub_url}/api/me/agents")).json()
                    assert pc["machine"] == "RIG" and pc["connected"]
                    resp = await viewer.post(
                        f"{hub.cfg.hub_url}/api/me/agents/{pc['id']}/revoke",
                        headers={"Origin": hub.cfg.origin},
                    )
                    assert resp.status == 200
                    error = await until(agent, lambda d: d["type"] == "error")
                    assert error["code"] == "revoked"
                again = await http.get(f"{hub.cfg.hub_url}/ws/agent", headers=headers)
                assert again.status == 401

    asyncio.run(main())


def test_old_agents_are_told_to_update(tmp_path):
    async def main():
        async with running_hub(tmp_path) as (hub, _pub, _int), browser() as viewer:
            await sign_in(viewer, hub, "Rook")
            token = await link_agent(hub, viewer)
            async with (
                aiohttp.ClientSession() as http,
                http.ws_connect(
                    ws_url(hub, "/ws/agent"), headers={"Authorization": f"Bearer {token}"}
                ) as agent,
            ):
                await until(agent, lambda d: d["type"] == "welcome")
                await agent.send_json(
                    {"type": "hello", "v": SCHEMA_VERSION + 1, "agent_version": "9"}
                )
                error = await until(agent, lambda d: d["type"] == "error")
                assert error["code"] == "version"
                closed = await agent.receive()
                assert closed.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED)

    asyncio.run(main())


def test_internal_api_for_the_cog(tmp_path):
    async def main():
        async with running_hub(tmp_path) as (hub, _pub, internal), browser() as viewer:
            await sign_in(viewer, hub, "Rook")
            token = await link_agent(hub, viewer)
            secret = {"X-Internal-Secret": "s3cret"}
            async with aiohttp.ClientSession(headers=secret) as cog:
                events = await cog.ws_connect(str(internal.make_url("/internal/events")))
                async with (
                    aiohttp.ClientSession() as http,
                    http.ws_connect(
                        ws_url(hub, "/ws/agent"), headers={"Authorization": f"Bearer {token}"}
                    ) as agent,
                ):
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
                    got = await until(events, lambda d: d["type"] == "event")
                    assert got["kind"] == "warning_on" and got["data"] == {"light": "hit"}
                    await asyncio.sleep(0.6)  # one roster refresh
                    fleet = await (await cog.get(str(internal.make_url("/internal/fleet")))).json()
                    (row,) = fleet["members"]
                    assert row["name"] == "Rook" and row["presence"] == "live"
                    one = await (
                        await cog.get(str(internal.make_url(f"/internal/members/{row['id']}")))
                    ).json()
                    assert one["snapshot"]["ship"]["model"] == row["ship"]["model"]
                await events.close()

    asyncio.run(main())


# ---------------------------------------------------------------- Discord sign-in


class FakeDiscord:
    """Just enough of Discord's OAuth and guild member endpoints."""

    def __init__(self) -> None:
        self.roles = {"member": ["42"], "norole": ["7"]}  # by code; anything else: not in server
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


def test_discord_sign_in_needs_the_member_role(tmp_path):
    async def main():
        discord = FakeDiscord()
        await discord.server.start_server()
        base = str(discord.server.make_url("")).rstrip("/")
        try:
            async with running_hub(
                tmp_path,
                dev_login=False,
                discord_client_id="cid",
                discord_client_secret="csecret",
                discord_guild_id="1",
                discord_member_role_id="42",
                discord_api=f"{base}/api",
                discord_authorize=f"{base}/authorize",
            ) as (hub, _pub, _int):
                url = hub.cfg.hub_url

                async def attempt(code: str) -> tuple[int, aiohttp.ClientSession]:
                    http = browser()
                    login = await http.get(
                        f"{url}/auth/login?next=/link?code=X", allow_redirects=False
                    )
                    assert login.status == 302 and login.headers["Location"].startswith(base)
                    state = login.headers["Location"].split("state=")[1].split("&")[0]
                    cb = await http.get(
                        f"{url}/auth/callback",
                        params={"code": code, "state": state},
                        allow_redirects=False,
                    )
                    return cb.status, http

                status, ok = await attempt("member")
                assert status == 302
                me = await (await ok.get(f"{url}/api/mode")).json()
                assert me["me"]["name"] == "Member"

                status, norole = await attempt("norole")
                assert status == 403
                assert (await (await norole.get(f"{url}/api/mode")).json())["me"] is None

                status, outsider = await attempt("outsider")
                assert status == 403

                # Losing the role later: the next re-check signs them out.
                discord.roles["member"] = ["7"]
                member = hub.db.member("id-member")
                member = await hub.auth.recheck(member, force=True)
                assert not member.allowed
                assert (await (await ok.get(f"{url}/api/mode")).json())["me"] is None
                for session in (ok, norole, outsider):
                    await session.close()

                # A forged state is refused.
                async with browser() as http:
                    forged = await http.get(
                        f"{url}/auth/callback",
                        params={"code": "member", "state": "x"},
                        allow_redirects=False,
                    )
                    assert forged.status == 400
        finally:
            await discord.server.close()

    asyncio.run(main())
