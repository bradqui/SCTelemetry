"""End to end: replay server -> GameReader -> Pipeline -> LocalServer -> WebSocket client."""

import asyncio
import json
from pathlib import Path

import aiohttp
from fleet_agent.localserver import LocalServer
from fleet_agent.replay import ReplayServer
from fleet_agent.runtime import GameReader, Pipeline

FIXTURES = Path(__file__).parents[2] / "fixtures"


async def _run_agent(fixture: str, work):
    replay = ReplayServer([FIXTURES / fixture], speed=20, loop=True).start()
    pipeline = Pipeline()
    server = LocalServer(pipeline, port=0, web_dir=Path("does-not-exist"))
    await server.start()
    reader = GameReader(pipeline, asyncio.get_running_loop(), install=None, port=replay.port)
    reader.start()
    try:
        return await work(server, pipeline)
    finally:
        reader.stop()
        await server.stop()
        replay.stop()


def test_websocket_streams_snapshots_and_events():
    async def work(server, pipeline):
        url = f"http://127.0.0.1:{server.port}"
        got: dict[str, list] = {}
        async with aiohttp.ClientSession() as http, http.ws_connect(f"{url}/ws") as ws:
            while len(got.get("snapshot", [])) < 40 or "event" not in got:
                msg = await asyncio.wait_for(ws.receive(), timeout=15)
                data = json.loads(msg.data)
                got.setdefault(data["type"], []).append(data)
            async with http.get(f"{url}/api/state") as resp:
                state = await resp.json()
        return got, state

    got, state = asyncio.run(_run_agent("constellation-pilot-copilot-turret.jsonl.gz", work))
    assert got["hello"][0]["mode"] == "local"
    assert any(s.get("streaming") for s in got["state"])
    snap = got["snapshot"][-1]
    assert snap["v"] == 1 and snap["status"]["locomotion"] in {"on_foot", "seated"}
    kinds = {e["kind"] for e in got["event"]}
    assert "game_start" in kinds
    assert state["state"]["streaming"] is True and state["snapshot"] is not None


def test_ship_serializes_class_alias():
    async def work(server, pipeline):
        for _ in range(300):
            if pipeline.latest and pipeline.latest.ship:
                return json.loads(pipeline.latest.model_dump_json(by_alias=True))
            await asyncio.sleep(0.05)
        raise AssertionError("no ship snapshot")

    snap = asyncio.run(_run_agent("cruise-nav-scm.jsonl.gz", work))
    assert snap["ship"]["class"] == "ORIG_m80" and "cls" not in snap["ship"]


def test_foreign_pages_are_refused():
    async def work(server, pipeline):
        url = f"http://127.0.0.1:{server.port}/api/state"
        async with aiohttp.ClientSession() as http:
            ok = await http.get(url)
            other_site = await http.get(url, headers={"Origin": "https://evil.example"})
            rebinding = await http.get(url, headers={"Host": f"evil.example:{server.port}"})
            same_origin = await http.get(url, headers={"Origin": f"http://localhost:{server.port}"})
            return ok.status, other_site.status, rebinding.status, same_origin.status

    assert asyncio.run(_run_agent("on-foot.jsonl.gz", work)) == (200, 403, 403, 200)


def test_missing_ui_shows_build_hint():
    async def work(server, pipeline):
        async with aiohttp.ClientSession() as http:
            resp = await http.get(f"http://127.0.0.1:{server.port}/")
            return resp.status, await resp.text()

    status, text = asyncio.run(_run_agent("on-foot.jsonl.gz", work))
    assert status == 200 and "npm run build" in text
