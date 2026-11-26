"""The roster to fleet pages: one shared step per change for pages in step, a catch-up
for pages behind. Whatever the timing, every page ends up with the hub's roster."""

from __future__ import annotations

import asyncio
import json

import aiohttp
from starglance_hub.fleet import Viewer
from starglance_shared import apply_patch

from tests.hub.test_hub import (
    agent_socket,
    browser,
    link_agent,
    running_hub,
    ship_snapshot,
    sign_in,
    until,
)


class FakeSocket:
    """A page's socket: keeps what it was sent; ``delay`` makes it a slow connection."""

    def __init__(self, delay: float = 0.0) -> None:
        self.closed = False
        self.delay = delay
        self.texts: list[str] = []

    async def send_str(self, text: str) -> None:
        await asyncio.sleep(self.delay)
        self.texts.append(text)

    async def send_json(self, data: dict) -> None:
        await self.send_str(json.dumps(data))

    def roster(self, start: dict) -> dict:
        """The roster this page would show: what it started with, plus every step."""
        roster = json.loads(json.dumps(start))
        for text in self.texts:
            msg = json.loads(text)
            if msg["type"] == "roster_delta":
                roster = apply_patch(roster, msg["patch"])
        return roster


def test_pages_in_step_and_behind_end_up_with_the_same_roster(tmp_path):
    async def main():
        async with running_hub(tmp_path) as (hub, _srv), browser() as viewer_http:
            await sign_in(viewer_http, hub, "Rook")
            token = await link_agent(hub, viewer_http)
            fleet = hub.fleet
            member = hub.db.members()[0]
            pages = {"in step": FakeSocket(), "slow": FakeSocket(delay=0.35)}
            starts, tasks = {}, []
            for name, sock in pages.items():
                v = Viewer(sock, member)  # type: ignore[arg-type]
                v.sent_roster, v.roster_version = fleet.roster, fleet.roster_version
                starts[name] = fleet.roster
                fleet.add_viewer(v)
                tasks.append(asyncio.create_task(fleet.pump(v)))
            snap = ship_snapshot()
            async with aiohttp.ClientSession() as http, agent_socket(http, hub, token) as agent:
                await until(agent, lambda d: d["type"] == "welcome")
                await agent.send_json(
                    {"type": "hello", "v": 1, "agent_version": "t", "channel": "LIVE"}
                )
                await agent.send_json(snap)
                for k in range(25):  # 2.5 s of flight: the roster changes every tick
                    t = snap["t"] + 100 * (k + 1)
                    patch = {
                        "t": t,
                        "ship": {"flight": {"speed": 100.0 + 7 * k, "alt": 1000.0 + k}},
                    }
                    await agent.send_json({"type": "delta", "v": 1, "t": t, "patch": patch})
                    await asyncio.sleep(0.1)
                # Still connected, no more changes: give the slow page time to catch up.
                # (Checked here: hanging up would change the roster again, to "stale".)
                for _ in range(40):
                    if all(s.roster(starts[n]) == fleet.roster for n, s in pages.items()):
                        break
                    await asyncio.sleep(0.1)
                final, shared = fleet.roster, fleet.roster_delta
                for t in tasks:
                    t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

            in_step, slow = pages["in step"], pages["slow"]
            assert len(in_step.texts) > 10, "the page in step had a step for each change"
            assert len(slow.texts) < len(in_step.texts), "the slow page skipped some (caught up)"
            for name, sock in pages.items():
                assert sock.roster(starts[name]) == final, f"{name}: not the hub's roster"
            # Pages in step get the very same text, worked out once.
            assert shared is not None and shared in in_step.texts

    asyncio.run(main())


def test_a_page_opening_while_the_roster_changes_misses_nothing(tmp_path):
    """A page that opens while the roster is changing ends up with the hub's roster. (The
    roster is noted before the opening sends now, so a change during them isn't lost; the
    window is too small to hit on purpose, so this checks the outcome, not that window.)"""

    async def main():
        async with running_hub(tmp_path) as (hub, _srv), browser() as page:
            await sign_in(page, hub, "Rook")
            token = await link_agent(hub, page)
            snap = ship_snapshot()
            async with aiohttp.ClientSession() as http, agent_socket(http, hub, token) as agent:
                await until(agent, lambda d: d["type"] == "welcome")
                await agent.send_json(
                    {"type": "hello", "v": 1, "agent_version": "t", "channel": "LIVE"}
                )
                await agent.send_json(snap)
                ws_url = hub.cfg.hub_url.replace("http://", "ws://") + "/ws/view"
                async with page.ws_connect(ws_url, headers={"Origin": hub.cfg.origin}) as view:
                    roster = (await until(view, lambda d: d["type"] == "roster"))["members"]
                    for k in range(8):  # changes from the first moment on
                        t = snap["t"] + 100 * (k + 1)
                        patch = {"t": t, "ship": {"flight": {"speed": 300.0 + k}}}
                        await agent.send_json({"type": "delta", "v": 1, "t": t, "patch": patch})
                        await asyncio.sleep(0.05)
                    deadline = asyncio.get_running_loop().time() + 3
                    while (
                        roster != hub.fleet.roster and asyncio.get_running_loop().time() < deadline
                    ):
                        msg = await until(view, lambda d: d["type"] == "roster_delta", timeout=3)
                        roster = apply_patch(roster, msg["patch"])
                    assert roster == hub.fleet.roster

    asyncio.run(main())
