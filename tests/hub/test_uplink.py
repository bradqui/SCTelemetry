"""Agent -> hub: the link command, then a recording played through the real pipeline and uplink."""

from __future__ import annotations

import asyncio
import json

import aiohttp
from starglance import fleetlink
from starglance.capturefile import read_frames
from starglance.runtime import Pipeline
from starglance.uplink import Uplink
from starglance_shared import apply_sharing, event_shared

from .test_hub import FIXTURES, browser, running_hub, sign_in, until, ws_url


async def link_with_command(hub, viewer) -> str:
    """``starglance link``: shows a code, the member confirms it in the browser."""
    codes: asyncio.Queue[str] = asyncio.Queue()

    def say(line: str) -> None:
        if line.startswith("Your code: "):
            codes.put_nowait(line.removeprefix("Your code: "))

    task = asyncio.create_task(
        fleetlink.link(hub.cfg.hub_url, machine="TEST-PC", open_browser=False, say=say)
    )
    code = await asyncio.wait_for(codes.get(), 5)
    resp = await viewer.post(
        f"{hub.cfg.hub_url}/api/link/{code}/confirm", headers={"Origin": hub.cfg.origin}
    )
    assert resp.status == 200
    settings = await asyncio.wait_for(task, 15)
    assert settings.member_name == "Rook" and settings.hub_url == hub.cfg.hub_url
    token = fleetlink.load_token(hub.cfg.hub_url)
    assert token
    return token


def test_replay_through_pipeline_and_uplink(tmp_path, monkeypatch):
    monkeypatch.setenv("STARGLANCE_HOME", str(tmp_path / "agent"))

    async def main():
        async with running_hub(tmp_path / "hub") as (hub, _srv), browser() as viewer:
            await sign_in(viewer, hub, "Rook")
            token = await link_with_command(hub, viewer)

            pipeline = Pipeline()
            share = {"status", "ship", "weapons", "combat"}  # vitals, location... off
            uplink = Uplink(pipeline, hub.cfg.hub_url, token, share, channel="LIVE", rate_hz=20)
            uplink.start()
            async with viewer.ws_connect(
                ws_url(hub, "/ws/view"), headers={"Origin": hub.cfg.origin}
            ) as view:
                roster = await until(view, lambda d: d["type"] == "roster")
                (mid,) = roster["members"]
                await view.send_json({"type": "focus", "member": mid})

                frames = list(read_frames(FIXTURES / "cruise-nav-scm.jsonl.gz"))[:600]
                for i, (t, raw) in enumerate(frames):
                    pipeline.on_frame(raw, t)
                    if i % 20 == 0:
                        await asyncio.sleep(0.02)
                await asyncio.sleep(0.5)

                # The hub holds exactly what the agent would share, nothing more.
                expected = json.loads(
                    apply_sharing(pipeline.latest, share).model_dump_json(by_alias=True)
                )
                assert hub.fleet.member_state(mid) == expected
                assert uplink.sent["snapshot"] >= 1 and uplink.sent["delta"] > 5
                assert uplink.status["state"] == "connected" and uplink.status["member"] == "Rook"
                sent = [e.kind for e in pipeline.recent if event_shared(e, share)]
                assert sent and [e["kind"] for e in hub.fleet.recent] == sent

                # The viewer that has this member open received their ship.
                member = await until(view, lambda d: d["type"] in ("member", "member_delta"))
                assert member["id"] == mid

                pipeline.on_disconnect("Game stream ended")
                await until(
                    view,
                    lambda d: (
                        d["type"] == "roster_delta"
                        and d["patch"].get(mid, {}).get("presence") == "idle"
                    ),
                )
            await uplink.stop()

    asyncio.run(main())


def test_uplink_gives_up_on_a_revoked_token(tmp_path):
    async def main():
        async with running_hub(tmp_path) as (hub, _srv):
            uplink = Uplink(Pipeline(), hub.cfg.hub_url, "not-a-token", {"status"})
            uplink.start()
            await asyncio.wait_for(uplink._task, 5)
            assert uplink.status["state"] == "rejected"

    asyncio.run(main())


def test_agent_token_is_stored_per_hub(tmp_path, monkeypatch):
    monkeypatch.setenv("STARGLANCE_HOME", str(tmp_path))
    fleetlink.save_token("https://fleet.example", "abc")
    assert fleetlink.load_token("https://fleet.example") == "abc"
    assert fleetlink.load_token("https://other.example") is None
    settings = fleetlink.load_settings()
    assert settings.shared == set(settings.share)  # everything on by default
    settings.share["vitals"] = False
    fleetlink.save_settings(settings)
    assert "vitals" not in fleetlink.load_settings().shared
    fleetlink.forget_token("https://fleet.example")
    assert fleetlink.load_token("https://fleet.example") is None
    assert aiohttp  # the agent's only network dependency


def test_invite_links_and_hub_addresses():
    assert fleetlink.parse_target("https://fleet.example.org/join/AbC_12-x") == (
        "https://fleet.example.org",
        "AbC_12-x",
    )
    assert fleetlink.parse_target("fleet.example.org/") == ("https://fleet.example.org", None)
    assert fleetlink.parse_target("https://example.org/fleet/join/xyz") == (
        "https://example.org/fleet",
        "xyz",
    )
    assert fleetlink.parse_target("http://127.0.0.1:8100") == ("http://127.0.0.1:8100", None)


def test_join_with_an_invite_from_the_agent(tmp_path, monkeypatch):
    monkeypatch.setenv("STARGLANCE_HOME", str(tmp_path / "agent"))
    log = tmp_path / "Game.log"
    log.write_text(
        "<2026-11-23T18:13:52.484Z> [Notice] <Legacy login response> [CIG-net] User Login "
        "Success - Handle[TestPilot] - Time[1]\n",
        encoding="utf-8",
    )
    assert fleetlink.game_handle(log) == "TestPilot"

    async def main():
        async with running_hub(tmp_path / "hub") as (hub, _srv), browser() as admin:
            await sign_in(admin, hub, "Admin")
            resp = await admin.post(
                f"{hub.cfg.hub_url}/api/admin/invites",
                json={"uses": 1},
                headers={"Origin": hub.cfg.origin},
            )
            hub_url, code = fleetlink.parse_target((await resp.json())["url"])
            settings = await fleetlink.join(hub_url, code, "TestPilot", machine="RIG")
            assert settings.member_name == "TestPilot" and settings.org == "Fleet"
            token = fleetlink.load_token(hub_url)
            url = await fleetlink.login_link(hub_url, token)
            assert "/auth/token/" in url
            try:
                await fleetlink.join(hub_url, code, "Again")
            except fleetlink.LinkError as exc:
                assert "expired" in str(exc)
            else:
                raise AssertionError("a used invite should fail")

    asyncio.run(main())


def test_update_notice_only_for_a_newer_agent():
    from starglance import __version__
    from starglance.uplink import update_notice
    from starglance_shared import RELEASES_URL, version_tuple

    assert version_tuple("0.2.0") == (0, 2, 0) and version_tuple("v1.10") == (1, 10)
    assert version_tuple("dev") is None and version_tuple(None) is None
    major, minor, patch = version_tuple(__version__)
    newer = f"{major}.{minor}.{patch + 1}"
    notice = update_notice({"latest_agent": newer, "download": "https://example.org/dl"})
    assert notice == {"version": newer, "url": "https://example.org/dl"}
    assert update_notice({"latest_agent": __version__}) is None
    assert update_notice({"latest_agent": "0.0.1"}) is None
    assert update_notice({}) is None
    # Only an https link from the hub; else the project's releases page.
    assert update_notice({"latest_agent": newer, "download": "javascript:x"})["url"] == RELEASES_URL
