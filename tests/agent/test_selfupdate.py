"""Updating the app in place: only official releases, checked, swapped, restarted."""

import asyncio
import hashlib

import pytest
from aiohttp import web
from starglance import __version__, selfupdate
from starglance.runtime import Pipeline
from starglance.selfupdate import (
    UpdateError,
    Updater,
    check_signature,
    download_url,
    expected_sum,
    install,
    old_path,
    remove_old,
)

NEW = "99.0.0"


@pytest.fixture(autouse=True)
def _home(tmp_path, monkeypatch):
    monkeypatch.setenv("STARGLANCE_HOME", str(tmp_path / "home"))


def test_only_official_releases():
    url = download_url("0.6.1", "starglance.exe")
    assert url == "https://github.com/bradqui/starglance/releases/download/v0.6.1/starglance.exe"
    for bad in ["../../evil", "0.6.1/../../x", "https://evil.example/x.exe", "", "1.2"]:
        with pytest.raises(UpdateError):
            download_url(bad, "starglance.exe")


def test_checksum_file():
    h = "ab" * 32
    sums = f"{'cd' * 32}  other.exe\n{h}  starglance.exe\n"
    assert expected_sum(sums) == h
    assert expected_sum(f"{h.upper()} *starglance.exe") == h
    with pytest.raises(UpdateError):
        expected_sum("nothing here")


def test_signature_rules(tmp_path):
    cur, new = tmp_path / "cur.exe", tmp_path / "new.exe"

    def verdicts(mine, theirs):
        return lambda p: mine if p == cur else theirs

    pub = ("Valid", "CN=Starglance")
    # Before signing: an unsigned update is fine, a signed one too; a broken one never.
    check_signature(new, cur, verdict=verdicts(("NotSigned", None), ("NotSigned", None)))
    check_signature(new, cur, verdict=verdicts(("NotSigned", None), pub))
    with pytest.raises(UpdateError):
        check_signature(new, cur, verdict=verdicts(("NotSigned", None), ("HashMismatch", None)))
    # Signed: only the same publisher.
    check_signature(new, cur, verdict=verdicts(pub, pub))
    for other in [
        ("NotSigned", None),
        ("Valid", "CN=Someone Else"),
        ("HashMismatch", "CN=Starglance"),
    ]:
        with pytest.raises(UpdateError):
            check_signature(new, cur, verdict=verdicts(pub, other))


def test_swap_keeps_the_name(tmp_path):
    exe, new = tmp_path / "starglance.exe", tmp_path / "starglance.new.exe"
    exe.write_bytes(b"old")
    new.write_bytes(b"new")
    old = install(new, exe)
    assert exe.read_bytes() == b"new" and old == old_path(exe) and old.read_bytes() == b"old"
    assert not new.exists()
    assert remove_old(exe, tries=1) and not old.exists()


def test_swap_puts_it_back_if_it_fails(tmp_path):
    exe = tmp_path / "starglance.exe"
    exe.write_bytes(b"old")
    with pytest.raises(OSError):
        install(tmp_path / "missing.new.exe", exe)
    assert exe.read_bytes() == b"old"


async def _release(payload: bytes, *, sums: str | None = None):
    """A stand-in for the GitHub release: SHA256SUMS.txt and starglance.exe."""
    digest = hashlib.sha256(payload).hexdigest()

    async def handle(request):
        name = request.match_info["name"]
        if name == "SHA256SUMS.txt":
            return web.Response(text=sums or f"{digest}  starglance.exe\n")
        if name == "starglance.exe":
            return web.Response(body=payload)
        raise web.HTTPNotFound()

    app = web.Application()
    app.router.add_get("/v{version}/{name}", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    return runner, f"http://127.0.0.1:{port}/v{{version}}/{{name}}"


def _updater(tmp_path, pipeline, relaunched):
    exe = tmp_path / "app" / "starglance.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"the old version")
    u = Updater(
        pipeline,
        announce=str,
        exe=exe,
        verdict=lambda p: ("NotSigned", None),
        is_game_running=lambda: False,
    )
    u.relaunch = lambda: relaunched.append(True)
    return u, exe


def test_update_from_the_hubs_word(tmp_path, monkeypatch):
    async def main():
        runner, url = await _release(b"the new version" * 1000)
        monkeypatch.setattr(selfupdate, "DOWNLOAD", url)
        pipeline = Pipeline()
        seen = []
        pipeline.subscribe(lambda k, p: k == "updater" and seen.append(dict(p)))
        relaunched = []
        u, exe = _updater(tmp_path, pipeline, relaunched)
        try:
            assert u.status()["available"] is None and not u.start()
            # The hub says what's current; an older or equal one is ignored.
            pipeline._notify("uplink", {"state": "connected", "hub": "h", "update": None})
            pipeline._notify(
                "uplink", {"state": "connected", "hub": "h", "update": {"version": __version__}}
            )
            assert u.available is None
            pipeline._notify(
                "uplink",
                {
                    "state": "connected",
                    "hub": "h",
                    "update": {"version": NEW, "url": "https://evil.example/x.exe"},
                },
            )
            assert u.available == NEW
            assert u.start()
            await u._task
            return u, exe, relaunched, seen
        finally:
            await runner.cleanup()

    u, exe, relaunched, seen = asyncio.run(main())
    assert u.error is None, u.error
    assert exe.read_bytes() == b"the new version" * 1000
    assert old_path(exe).read_bytes() == b"the old version"
    assert relaunched == [True]
    states = [s["state"] for s in seen]
    assert "downloading" in states and "checking" in states and "installing" in states


def test_a_bad_download_is_not_installed(tmp_path, monkeypatch):
    async def main():
        runner, url = await _release(b"tampered", sums=f"{'00' * 32}  starglance.exe\n")
        monkeypatch.setattr(selfupdate, "DOWNLOAD", url)
        relaunched = []
        u, exe = _updater(tmp_path, Pipeline(), relaunched)
        u.available = NEW
        try:
            u.start()
            await u._task
            return u, exe, relaunched
        finally:
            await runner.cleanup()

    u, exe, relaunched = asyncio.run(main())
    assert u.state == "error" and "checksum" in u.error
    assert exe.read_bytes() == b"the old version" and not old_path(exe).exists()
    assert not exe.with_name("starglance.new.exe").exists(), "the download is cleaned up"
    assert relaunched == []


def test_a_missing_release_says_so(tmp_path, monkeypatch):
    async def main():
        runner, url = await _release(b"x")
        monkeypatch.setattr(
            selfupdate, "DOWNLOAD", url.replace("/v{version}/", "/nothing/v{version}/")
        )
        u, exe = _updater(tmp_path, Pipeline(), [])
        u.available = NEW
        try:
            u.start()
            await u._task
            return u, exe
        finally:
            await runner.cleanup()

    u, exe = asyncio.run(main())
    assert u.state == "error" and "Couldn't download" in u.error
    assert exe.read_bytes() == b"the old version"


def test_from_source_it_cannot_update_itself(tmp_path):
    u = Updater(Pipeline(), announce=str, exe=None)
    u.available = NEW
    assert u.status()["can"] is False and not u.start()


def test_automatic_waits_for_the_game_to_close(tmp_path, monkeypatch):
    monkeypatch.setattr(selfupdate, "AUTO_EVERY_S", 0.01)

    async def main():
        started = []
        playing = [True]
        u = Updater(
            Pipeline(), announce=str, exe=tmp_path / "s.exe", is_game_running=lambda: playing[0]
        )
        u.relaunch = lambda: None
        u.available = NEW
        monkeypatch.setattr(u, "start", lambda: started.append(True) or True)
        loop = asyncio.create_task(u.auto_loop())
        await asyncio.sleep(0.1)
        assert started == [], "off by default"
        u.set_auto(True)
        await asyncio.sleep(0.1)
        assert started == [], "not while the game runs"
        playing[0] = False
        await asyncio.sleep(0.1)
        loop.cancel()
        return started

    assert asyncio.run(main())
    assert selfupdate.load_auto() is True, "the setting is saved"


def test_automatic_never_installs_the_same_version_twice(tmp_path, monkeypatch):
    """A release whose exe still says the old version must not restart it every minute."""
    monkeypatch.setattr(selfupdate, "AUTO_EVERY_S", 0.01)
    selfupdate._save(auto=True, installed=NEW)

    async def main():
        started = []
        u = Updater(Pipeline(), announce=str, exe=tmp_path / "s.exe", is_game_running=lambda: False)
        u.relaunch = lambda: None
        u.available = NEW
        monkeypatch.setattr(u, "start", lambda: started.append(True) or True)
        loop = asyncio.create_task(u.auto_loop())
        await asyncio.sleep(0.1)
        loop.cancel()
        return started, u

    started, u = asyncio.run(main())
    assert started == [] and u.auto is True
