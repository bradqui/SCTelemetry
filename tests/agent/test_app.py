"""The Windows app's pieces that don't need a desktop: one copy at a time, remembered
window, what the page may ask of it. (The window and tray are checked by hand.)"""

import asyncio
import threading
from pathlib import Path

import pytest
from starglance import app
from starglance.localserver import LocalServer
from starglance.runtime import Pipeline


def test_a_second_launch_shows_the_running_one(tmp_path):
    shown = threading.Event()
    port_box = {}
    ready = threading.Event()

    def serve() -> None:
        async def main() -> None:
            server = LocalServer(Pipeline(), port=0, web_dir=tmp_path / "none")
            server.on_show = shown.set
            await server.start()
            port_box["port"] = server.port
            ready.set()
            await asyncio.sleep(3)
            await server.stop()

        asyncio.run(main())

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    assert ready.wait(10)
    assert app.already_running(port_box["port"]) is True
    assert shown.wait(5), "the running app was asked to show its window"
    t.join(10)


def test_nothing_running(monkeypatch):
    opened = []
    monkeypatch.setattr(app.webbrowser, "open", opened.append)
    assert app.already_running(1) is False  # nothing listens on port 1
    assert opened == []


def test_a_plain_run_opens_in_the_browser(tmp_path, monkeypatch):
    """`starglance run` (no app window) is running: show it in the browser instead."""
    opened = []
    monkeypatch.setattr(app.webbrowser, "open", opened.append)
    ready = threading.Event()
    port_box = {}

    def serve() -> None:
        async def main() -> None:
            server = LocalServer(Pipeline(), port=0, web_dir=tmp_path / "none")
            await server.start()
            port_box["port"] = server.port
            ready.set()
            await asyncio.sleep(2)
            await server.stop()

        asyncio.run(main())

    threading.Thread(target=serve, daemon=True).start()
    assert ready.wait(10)
    assert app.already_running(port_box["port"]) is True
    assert opened == [f"http://127.0.0.1:{port_box['port']}/"]


def test_window_prefs_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("STARGLANCE_HOME", str(tmp_path))
    assert app.load_prefs() == {}
    app.save_prefs({"width": 900, "on_top": True})
    assert app.load_prefs() == {"width": 900, "on_top": True}
    (tmp_path / "app.json").write_text("not json", encoding="utf-8")
    assert app.load_prefs() == {}


def test_the_page_may_only_open_web_links(monkeypatch):
    opened = []
    monkeypatch.setattr(app.webbrowser, "open", opened.append)
    api = app.Api()
    assert api.open_external("https://fleet.example.org/auth/token/x") is True
    assert api.open_external("file:///C:/Windows/System32/calc.exe") is False
    assert api.open_external("javascript:alert(1)") is False
    assert api.open_external(42) is False
    assert opened == ["https://fleet.example.org/auth/token/x"]


def test_icon_draws():
    pytest.importorskip("PIL")
    img = app.draw_icon(32)
    assert img.size == (32, 32) and img.mode == "RGBA"


def test_the_app_command_exists():
    from starglance.__main__ import build_parser

    args = build_parser().parse_args(["app", "--hidden"])
    assert args.command == "app" and args.hidden and args.ui_port == 8740
    assert Path(args.func.__code__.co_filename).name == "__main__.py"


def test_autostart_isnt_offered_from_source():
    """Start with Windows registers starglance.exe; running from Python there's nothing to
    register, so the switch says it isn't available."""
    assert app.autostart_command() is None
    assert app.autostart_enabled() is None
    assert app.set_autostart(True) is None


@pytest.mark.skipif(app.sys.platform != "win32", reason="the Windows registry")
def test_autostart_on_and_off(monkeypatch):
    """One value under the Run key while on, gone when off. A scratch key, not the real one."""
    import winreg

    scratch = r"Software\StarglanceTest\Run"
    monkeypatch.setattr(app, "RUN_KEY", scratch)
    command = '"C:/Games/starglance.exe" app --hidden'
    monkeypatch.setattr(app, "autostart_command", lambda: command)
    winreg.CreateKey(winreg.HKEY_CURRENT_USER, scratch).Close()
    try:
        assert app.autostart_enabled() is False
        assert app.set_autostart(True) is True
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, scratch) as key:
            value, _ = winreg.QueryValueEx(key, "Starglance")
        assert value.endswith("app --hidden")
        assert app.set_autostart(False) is False
        assert app.set_autostart(False) is False, "off twice is fine"
    finally:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, scratch)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\StarglanceTest")


def test_page_state_without_a_window():
    state = app.Api().state()
    assert state == {"frameless": False, "on_top": False, "maximized": False, "autostart": None}
