""" "Link this PC" from the hub's page: the page makes a one-time starglance:// link, the app
asks the hub whose it is, the person confirms, and only then is the PC linked."""

from __future__ import annotations

import asyncio

import aiohttp
import pytest
from starglance import fleetlink

from .test_hub import browser, mode, post, running_hub, sign_in


async def new_pc_link(viewer: aiohttp.ClientSession, hub) -> str:
    resp = await post(viewer, hub, "/api/me/pc-link")
    assert resp.status == 200, await resp.text()
    return (await resp.json())["url"]


def test_app_links_are_checked_before_use():
    hub, code = fleetlink.parse_app_link(
        "starglance://link?hub=https%3A%2F%2Ffleet.example.org%2Fo%2Falpha%2F&code=" + "a" * 43
    )
    assert (hub, code) == ("https://fleet.example.org/o/alpha", "a" * 43)
    assert fleetlink.is_app_link(" Starglance://link?x") and not fleetlink.is_app_link("https://x")
    ok = "a" * 43
    for bad in (
        f"https://link?hub=https://fleet.example.org&code={ok}",  # not our scheme
        f"starglance://open?hub=https://fleet.example.org&code={ok}",  # not "link"
        f"starglance://link?hub=http://fleet.example.org&code={ok}",  # plain http, public
        f"starglance://link?hub=ftp://fleet.example.org&code={ok}",
        f"starglance://link?hub=https://user:pw@fleet.example.org&code={ok}",
        "starglance://link?hub=https://fleet.example.org&code=short",
        f"starglance://link?code={ok}",
    ):
        with pytest.raises(fleetlink.LinkError):
            fleetlink.parse_app_link(bad)
    for local in ("http://127.0.0.1:8100", "http://192.168.1.20:8100", "http://hub.local"):
        assert fleetlink.parse_app_link(f"starglance://link?hub={local}&code={ok}")[0] == local


def test_link_this_pc_from_the_page(tmp_path, monkeypatch):
    monkeypatch.setenv("STARGLANCE_HOME", str(tmp_path / "agent"))

    async def main():
        async with running_hub(tmp_path / "hub", org_name="Alpha") as (hub, _srv), browser() as me:
            await sign_in(me, hub, "Rook")
            m = await mode(me, hub)
            assert m["me"]["pcs"] == 0 and m["download_url"].endswith("/download/starglance.exe")
            assert m["discord_join"] is False

            refused = await me.post(f"{hub.cfg.hub_url}/api/me/pc-link")  # no Origin
            assert refused.status == 403, "only the hub's own page makes links"
            async with aiohttp.ClientSession() as stranger:
                r = await post(stranger, hub, "/api/me/pc-link")
                assert r.status == 401

            hub_url, code = fleetlink.parse_app_link(await new_pc_link(me, hub))
            assert hub_url == hub.cfg.hub_url
            info = await fleetlink.check_pc_link(hub_url, code)
            assert info["org"] == "Alpha" and info["member"]["name"] == "Rook"
            info = await fleetlink.check_pc_link(hub_url, code)  # checking doesn't use it up

            fleet = await fleetlink.redeem_pc_link(hub_url, code, machine="RIG")
            assert fleet.member_name == "Rook" and fleet.org == "Alpha"
            assert fleetlink.load_token(hub_url)
            assert (await mode(me, hub))["me"]["pcs"] == 1
            with pytest.raises(fleetlink.LinkError, match="expired"):
                await fleetlink.redeem_pc_link(hub_url, code)
            with pytest.raises(fleetlink.LinkError, match="expired"):
                await fleetlink.check_pc_link(hub_url, "b" * 43)

            # Linked again (a fresh link): the hub forgets the PC's old key.
            old = fleetlink.load_token(hub_url)
            _hub, code2 = fleetlink.parse_app_link(await new_pc_link(me, hub))
            await fleetlink.redeem_pc_link(hub_url, code2, machine="RIG")
            assert fleetlink.load_token(hub_url) != old
            pcs = await (await me.get(f"{hub.cfg.hub_url}/api/me/agents")).json()
            assert [p["machine"] for p in pcs] == ["RIG"]

            # A suspended member's links stop working.
            _hub, code3 = fleetlink.parse_app_link(await new_pc_link(me, hub))
            member = next(x for x in hub.db.members() if x.name == "Rook")
            hub.db.set_active(member.id, False)
            with pytest.raises(fleetlink.LinkError, match="expired"):
                await fleetlink.check_pc_link(hub_url, code3)

    asyncio.run(main())


def test_the_app_asks_before_linking(tmp_path, monkeypatch):
    """The link reaches the running app; nothing is linked until the person says yes."""
    from starglance import control as control_mod
    from starglance.control import AgentControl
    from starglance.localserver import LocalServer
    from starglance.runtime import Pipeline

    monkeypatch.setenv("STARGLANCE_HOME", str(tmp_path / "agent"))
    monkeypatch.setattr(control_mod.installs, "find_installs", lambda: [])  # never this PC's game

    async def until(pred):
        for _ in range(100):
            if pred():
                return
            await asyncio.sleep(0.05)
        raise AssertionError("timed out")

    async def main():
        async with running_hub(tmp_path / "hub", org_name="Alpha") as (hub, _srv), browser() as me:
            await sign_in(me, hub, "Rook")
            pipeline = Pipeline()
            heard: list[dict] = []
            pipeline.subscribe(lambda kind, p: heard.append(p) if kind == "offer" else None)
            server = LocalServer(pipeline, port=0, web_dir=tmp_path / "none")
            control = AgentControl(pipeline, server, install=None, announce=lambda _m: None)
            shown = []
            server.on_show = lambda: shown.append(True)
            await server.start()
            base = f"http://127.0.0.1:{server.port}/api"
            try:
                async with aiohttp.ClientSession() as app:
                    # Another website can't hand the running app a link.
                    r = await app.post(
                        f"{base}/app/link",
                        json={"url": "starglance://link"},
                        headers={"Origin": "https://evil.example"},
                    )
                    assert r.status == 403

                    # Saying no: nothing linked.
                    url = await new_pc_link(me, hub)
                    r = await app.post(f"{base}/app/link", json={"url": url})
                    assert r.status == 200 and shown
                    await until(lambda: (control._offer or {}).get("state") == "ready")
                    offer = control._offer
                    assert offer["org"] == "Alpha" and offer["member"] == "Rook"
                    assert offer["hub"] == hub.cfg.hub_url and not offer["already"]
                    assert "code" not in offer and all("code" not in str(h) for h in heard)
                    r = await app.post(f"{base}/agent/offer", json={"id": offer["id"]})
                    assert (await r.json())["offer"] is None
                    assert (await mode(me, hub))["me"]["pcs"] == 0

                    # Saying yes: linked, and the app starts sending.
                    await app.post(f"{base}/app/link", json={"url": await new_pc_link(me, hub)})
                    await until(lambda: (control._offer or {}).get("state") == "ready")
                    r = await app.post(
                        f"{base}/agent/offer", json={"id": control._offer["id"], "accept": True}
                    )
                    state = await r.json()
                    assert r.status == 200, state
                    assert state["offer"]["state"] == "done"
                    assert [f["org"] for f in state["fleets"]] == ["Alpha"]
                    assert state["fleets"][0]["member"] == "Rook"
                    assert (await mode(me, hub))["me"]["pcs"] == 1
                    r = await app.post(f"{base}/agent/offer", json={"id": state["offer"]["id"]})
                    assert (await r.json())["offer"] is None  # closing the dialog

                    # A bad or used link says so, in the dialog.
                    await app.post(f"{base}/app/link", json={"url": "starglance://link?hub=x"})
                    await until(lambda: (control._offer or {}).get("state") == "error")
                    assert "hub" in control._offer["error"]
            finally:
                await control.stop_uplinks()
                await server.stop()

    asyncio.run(main())
