"""Problem reports sent to a fleet's admins: the agent uploads, the hub checks and keeps,
admins read, download, mark and delete, members see and delete their own."""

from __future__ import annotations

import asyncio
import io
import json
import zipfile
from types import SimpleNamespace

import aiohttp
from starglance import fleetlink
from starglance.capturefile import read_frames
from starglance.recent import RecentBuffer
from starglance.report import Reports
from starglance.runtime import Pipeline
from starglance_hub import reports as hub_reports

from tests.hub.test_hub import FIXTURES, browser, make_invite, post, running_hub, sign_in


def a_report(what: str = "Quantum counted twice", **extra_files: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "report.json",
            json.dumps(
                {
                    "format": 1,
                    "agent": {"version": "0.7.0", "windows": "Windows-11"},
                    "game": {"channel": "LIVE", "version": "4.10.201.48085"},
                    "window": {"start": 1, "end": 2},
                    "what": what,
                    "expected": "Once",
                    "part": "The app or cockpit view (on my PC)",
                }
            ),
        )
        z.writestr("gamelog.txt", "<2026-11-24T18:16:27.354Z> a line\n")
        for name, data in extra_files.items():
            z.writestr(name, data)
    return buf.getvalue()


def test_the_hub_checks_what_it_is_sent():
    assert hub_reports.check(a_report())["game"] == "LIVE 4.10.201.48085"
    for bad in (
        b"not a zip",
        a_report(**{"evil.exe": b"MZ"}),  # only a report's own files
        b"PK\x05\x06" + b"\x00" * 18,  # an empty zip: no report.json
    ):
        try:
            hub_reports.check(bad)
        except hub_reports.BadReport:
            continue
        raise AssertionError("accepted a bad report")


def test_a_report_goes_to_the_fleets_admins(tmp_path, monkeypatch):
    monkeypatch.setenv("STARGLANCE_HOME", str(tmp_path / "agent"))
    (tmp_path / "agent").mkdir()

    async def main():
        async with (
            running_hub(tmp_path / "hub", org_name="Alpha") as (hub, _srv),
            browser() as admin,
        ):
            await sign_in(admin, hub, "Admin")
            url = hub.cfg.hub_url
            code = await make_invite(admin, hub, uses=1)
            await fleetlink.join(url, code, "Pilot", machine="RIG")

            # The player's agent: some telemetry, then a report sent to the fleet.
            pipeline = Pipeline()
            clock = SimpleNamespace(t=1_790_000_000_000)
            reports = Reports(
                pipeline,
                install=None,
                buffer=RecentBuffer(tmp_path / "recent", clock=lambda: clock.t),
            )
            for i, (_t, raw) in enumerate(read_frames(FIXTURES / "quantum-travel.jsonl.gz")):
                if i == 100:
                    break
                clock.t += 100
                pipeline.on_frame(raw, clock.t)
            assert reports.timeline()["fleets"] == [{"hub": url, "label": "Alpha"}]
            preview = await reports.preview({"t": clock.t, "what": "It said I left quantum twice"})
            sent = await reports.send(preview["id"], url)
            assert sent == {"ok": True, "hub": url, "label": "Alpha"}

            # The admins' list, one report, its files, the download.
            listed = await (await admin.get(f"{url}/api/admin/reports")).json()
            assert len(listed) == 1
            r = listed[0]
            assert r["member"]["name"] == "Pilot" and r["machine"] == "RIG"
            assert r["what"] == "It said I left quantum twice" and r["status"] == "new"
            assert r["agent_version"] and "zip" not in r
            one = await (await admin.get(f"{url}/api/admin/reports/{r['id']}")).json()
            assert json.loads(one["texts"]["report.json"])["what"] == r["what"]
            dl = await admin.get(f"{url}/api/admin/reports/{r['id']}/download")
            assert dl.status == 200 and dl.headers["Content-Type"] == "application/zip"
            assert "attachment" in dl.headers["Content-Disposition"]
            with zipfile.ZipFile(io.BytesIO(await dl.read())) as z:
                assert "capture.jsonl.gz" in z.namelist()

            # Marking it, from our own page only.
            done = await post(admin, hub, f"/api/admin/reports/{r['id']}", None)
            assert done.status == 405  # PATCH, not POST
            patch = await admin.patch(
                f"{url}/api/admin/reports/{r['id']}",
                json={"status": "forwarded"},
                headers={"Origin": hub.cfg.origin},
            )
            assert patch.status == 200
            cross = await admin.patch(
                f"{url}/api/admin/reports/{r['id']}",
                json={"status": "new"},
                headers={"Origin": "https://elsewhere.example"},
            )
            assert cross.status == 403
            listed = await (await admin.get(f"{url}/api/admin/reports")).json()
            assert listed[0]["status"] == "forwarded"

            # The member sees theirs and can delete it; others can't see admins' list.
            token = fleetlink.load_token(url)
            async with browser() as player:
                login = await (
                    await player.post(
                        f"{url}/api/agent/login-link", headers={"Authorization": f"Bearer {token}"}
                    )
                ).json()
                await player.get(login["url"])
                mine = await (await player.get(f"{url}/api/me/reports")).json()
                assert [m["id"] for m in mine] == [r["id"]]
                assert (await player.get(f"{url}/api/admin/reports")).status == 403
                gone = await player.delete(
                    f"{url}/api/me/reports/{r['id']}", headers={"Origin": hub.cfg.origin}
                )
                assert gone.status == 200
            assert await (await admin.get(f"{url}/api/admin/reports")).json() == []

    asyncio.run(main())


def test_the_hub_refuses_bad_and_too_many_reports(tmp_path):
    async def main():
        async with running_hub(tmp_path) as (hub, _srv), browser() as admin:
            await sign_in(admin, hub, "Admin")
            url = hub.cfg.hub_url
            code = await make_invite(admin, hub, uses=1)
            async with aiohttp.ClientSession() as agent:
                joined = await (
                    await agent.post(
                        f"{url}/api/agent/join",
                        json={"invite": code, "name": "Pilot", "machine": "RIG"},
                    )
                ).json()
                auth = {"Authorization": f"Bearer {joined['token']}"}
                nobody = await agent.post(f"{url}/api/agent/report", data=a_report())
                assert nobody.status == 401
                junk = await agent.post(f"{url}/api/agent/report", data=b"junk", headers=auth)
                assert junk.status == 400
                huge = await agent.post(
                    f"{url}/api/agent/report",
                    data=b"x" * (hub_reports.MAX_BYTES + 10),
                    headers=auth,
                )
                assert huge.status == 413
                for i in range(hub_reports.PER_DAY):
                    ok = await agent.post(
                        f"{url}/api/agent/report", data=a_report(f"#{i}"), headers=auth
                    )
                    assert ok.status == 200, await ok.text()
                more = await agent.post(f"{url}/api/agent/report", data=a_report(), headers=auth)
                assert more.status == 429
            hub.db.conn.execute("UPDATE reports SET created_at = 0")
            hub.db.prune(30, 30)
            assert hub.db.reports() == []

    asyncio.run(main())
