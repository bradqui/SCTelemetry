"""Show on other devices: pairing, view only, removal, and who may connect."""

import asyncio
import json
import socket
from pathlib import Path

import aiohttp
import pytest
from starglance import lanview
from starglance.control import AgentControl
from starglance.lanview import LanView, host_ok
from starglance.localserver import LocalServer
from starglance.runtime import Pipeline


@pytest.fixture(autouse=True)
def _home(tmp_path, monkeypatch):
    monkeypatch.setenv("STARGLANCE_HOME", str(tmp_path))


async def _agent(work):
    pipeline = Pipeline()
    server = LocalServer(pipeline, port=0, web_dir=Path("does-not-exist"))
    await server.start()
    control = AgentControl(pipeline, server, install=None, uplink_wanted=False, announce=str)
    lan = control.lan = LanView(server, announce=str)
    lan.settings.port = 0
    try:
        return await work(server, lan)
    finally:
        await lan.stop()
        await server.stop()


async def _settings(http, server, path, body):
    async with http.post(f"http://127.0.0.1:{server.port}/api/agent/{path}", json=body) as r:
        assert r.status == 200, await r.text()
        return (await r.json())["lan"]


def test_off_by_default():
    async def work(server, lan):
        url = f"http://127.0.0.1:{server.port}/api/agent/settings"
        async with aiohttp.ClientSession() as http, http.get(url) as r:
            state = (await r.json())["lan"]
        return state, lan.running

    state, running = asyncio.run(_agent(work))
    assert state["enabled"] is False and running is False and state["devices"] == []


def test_pair_watch_and_remove():
    async def work(server, lan):
        local = aiohttp.ClientSession()
        device = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))
        out = {}
        try:
            state = await _settings(local, server, "lan", {"on": True})
            assert state["running"] and lan.port
            url = f"http://127.0.0.1:{lan.port}"

            # Not paired: the page sends you to pair; the data and feeds refuse.
            async with device.get(f"{url}/", allow_redirects=False) as r:
                out["unpaired_page"] = (r.status, r.headers.get("Location"))
            async with device.get(f"{url}/api/state") as r:
                out["unpaired_state"] = r.status
            with pytest.raises(aiohttp.WSServerHandshakeError) as refused:
                await device.ws_connect(f"{url}/ws")
            out["unpaired_ws"] = refused.value.status
            async with device.post(f"{url}/pair", data={"code": "123456"}) as r:
                out["no_code"] = (r.status, "No code is waiting" in await r.text())

            # The PC shows a code; a wrong one costs a try, the right one pairs.
            code = (await _settings(local, server, "lan/code", {}))["code"]["code"]
            wrong = "000000" if code != "000000" else "111111"
            async with device.post(f"{url}/pair", data={"code": wrong}) as r:
                out["wrong"] = (r.status, "4 tries left" in await r.text())
            async with device.post(
                f"{url}/pair",
                data={"code": f"{code[:3]} {code[3:]}"},
                headers={"User-Agent": "Mozilla/5.0 (iPad; CPU OS 17_0) Safari/604.1"},
                allow_redirects=False,
            ) as r:
                out["paired"] = (r.status, r.headers.get("Location"))
            state = await _settings(local, server, "lan/code", {"cancel": True})
            out["devices"] = state["devices"]
            out["code_after"] = state["code"]
            out["file"] = lanview.settings_file().read_text(encoding="utf-8")
            out["cookie"] = next(iter(device.cookie_jar)).value

            # Paired: the page, the state and the feed, marked remote.
            async with device.get(f"{url}/api/mode") as r:
                out["mode"] = await r.json()
            async with device.get(f"{url}/api/state") as r:
                out["state"] = r.status
            ws = await device.ws_connect(f"{url}/ws")
            out["hello"] = json.loads((await ws.receive()).data)
            await asyncio.sleep(0.1)
            out["online"] = (await _settings(local, server, "lan/code", {"cancel": True}))[
                "devices"
            ][0]["online"]

            # Nothing that changes anything is here.
            for method, path in [
                ("POST", "/api/agent/share"),
                ("POST", "/api/agent/telemetry"),
                ("POST", "/api/agent/lan"),
                ("GET", "/api/agent/settings"),
                ("POST", "/api/fleet/open"),
                ("POST", "/api/app/show"),
            ]:
                async with device.request(method, f"{url}{path}", json={}) as r:
                    out.setdefault("blocked", []).append(r.status)

            # Removing the device cuts it off at once.
            device_id = out["devices"][0]["id"]
            state = await _settings(local, server, "lan/forget", {"id": device_id})
            out["after_forget"] = state["devices"]
            while (msg := await asyncio.wait_for(ws.receive(), 5)).type == aiohttp.WSMsgType.TEXT:
                pass  # what was already on its way
            out["ws_closed"] = msg.type
            async with device.get(f"{url}/api/state") as r:
                out["state_after"] = r.status

            # Off: nothing listens.
            await _settings(local, server, "lan", {"on": False})
            with pytest.raises(aiohttp.ClientConnectionError):
                await device.get(f"{url}/api/state")
            out["running_after"] = lan.running
        finally:
            await local.close()
            await device.close()
        return out

    out = asyncio.run(_agent(work))
    assert out["unpaired_page"] == (303, "/pair")
    assert out["unpaired_state"] == 401 and out["unpaired_ws"] == 401
    assert out["no_code"] == (400, True)
    assert out["wrong"] == (400, True)
    assert out["paired"] == (303, "/")
    assert out["code_after"] is None
    [d] = out["devices"]
    assert d["name"] == "Safari on iPad"
    key = out["cookie"].split(".", 1)[1]
    assert key not in out["file"], "only the key's hash is kept"
    assert out["mode"] == {
        "mode": "local",
        "remote": True,
        "agent_version": out["mode"]["agent_version"],
    }
    assert out["state"] == 200
    assert out["hello"]["type"] == "hello" and out["hello"]["remote"] is True
    assert out["online"] is True
    assert all(s in (404, 405) for s in out["blocked"]), out["blocked"]
    assert out["after_forget"] == []
    assert out["ws_closed"] in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED)
    assert out["state_after"] == 401
    assert out["running_after"] is False


def test_too_many_wrong_codes():
    async def work(server, lan):
        async with aiohttp.ClientSession() as http:
            await _settings(http, server, "lan", {"on": True})
            code = (await _settings(http, server, "lan/code", {}))["code"]["code"]
            wrong = "000000" if code != "000000" else "111111"
            texts = []
            for _ in range(5):
                async with http.post(
                    f"http://127.0.0.1:{lan.port}/pair", data={"code": wrong}
                ) as r:
                    texts.append(await r.text())
            async with http.post(f"http://127.0.0.1:{lan.port}/pair", data={"code": code}) as r:
                late = await r.text()
            return texts, late, lan.settings.devices

    texts, late, devices = asyncio.run(_agent(work))
    assert "1 try left" in texts[3] and "Too many tries" in texts[4]
    assert "No code is waiting" in late and devices == []


def test_foreign_sites_are_refused():
    async def work(server, lan):
        async with aiohttp.ClientSession() as http:
            await _settings(http, server, "lan", {"on": True})
            url = f"http://127.0.0.1:{lan.port}/pair"
            rebinding = await http.get(url, headers={"Host": f"evil.example:{lan.port}"})
            other_site = await http.post(
                url, data={"code": "1"}, headers={"Origin": "https://evil.example"}
            )
            same = await http.get(url, headers={"Origin": f"http://127.0.0.1:{lan.port}"})
            return rebinding.status, other_site.status, same.status

    assert asyncio.run(_agent(work)) == (403, 403, 200)


def test_the_pc_name_or_an_ip_only():
    pc = socket.gethostname()
    assert host_ok("192.168.1.20:8741") and host_ok("192.168.1.20")
    assert host_ok("[fe80::1]:8741")
    assert host_ok(f"{pc}:8741") and host_ok(f"{pc.lower()}.local:8741")
    assert not host_ok("evil.example:8741")
    assert not host_ok(f"{pc}.evil.example:8741")
    assert not host_ok("")


def test_the_setting_survives_a_restart():
    async def first(server, lan):
        await lan.set_enabled(True)

    asyncio.run(_agent(first))
    assert lanview.load_settings().enabled is True
