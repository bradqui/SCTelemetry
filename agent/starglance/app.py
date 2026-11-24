"""Starglance as a Windows app: a tray icon and its own window, no console.

``starglance.exe`` with no arguments (or ``python -m starglance app``). The agent runs on
a background thread (``__main__.serve``); the cockpit view shows in a window of its own
(pywebview on Windows' Edge WebView2: no address bar, no tabs), with Windows' title bar or
without (the page's top bar then drags the window and has its own buttons). Closing the
window hides it to the tray; Quit in the tray menu stops everything. Starting it again
brings the window back instead of running twice. Window size, position, "always on top"
and the title bar choice are remembered (app.json in the agent's folder); the page's own
storage (dashboard layouts, themes) lives in its WebView2 profile there too. "Start with
Windows" (off unless switched on) is one value under HKCU\\...\\Run. Output goes to
logs/starglance.log. Updates (selfupdate.py) put the new exe in place, start it with
``--updated`` and quit; it waits for this one to go, then deletes the old file.

Without WebView2 (very old Windows 10), the view opens in the default browser and the tray
icon still works.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import logging.handlers
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.request import Request, urlopen

from . import __version__, paths

log = logging.getLogger(__name__)

APP_NAME = "Starglance"
BG = "#0b0f14"  # the page's dark background, so the window doesn't flash white
FRAMELESS_DEFAULT = True
"""No Windows title bar unless switched back on (Settings -> Agent -> Window, or the tray)."""


# ---------------------------------------------------------------- the icon


def draw_icon(size: int = 64):
    """The logo (the page's triangle and dot) on a dark rounded square, for the tray."""
    from PIL import Image, ImageDraw

    s = size * 4  # draw big, scale down: smooth edges
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=s // 5, fill=(11, 18, 30, 255))
    cyan = (70, 211, 255, 255)
    k = s / 32
    w = max(2, round(2.6 * k))
    d.line(
        [(16 * k, 5 * k), (28 * k, 26.5 * k), (4 * k, 26.5 * k), (16 * k, 5 * k)],
        fill=cyan,
        width=w,
        joint="curve",
    )
    r = 3.2 * k
    d.ellipse((16 * k - r, 19.5 * k - r, 16 * k + r, 19.5 * k + r), fill=cyan)
    return img.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------- one at a time


def _local(port: int, path: str, method: str = "GET", timeout: float = 1.0) -> dict | None:
    req = Request(f"http://127.0.0.1:{port}{path}", method=method)
    if method == "POST":
        req.add_header("Content-Type", "application/json")
        req.data = b"{}"
    try:
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 (our own 127.0.0.1)
            return json.loads(resp.read() or b"{}")
    except (OSError, ValueError):
        return None


def already_running(port: int) -> bool:
    """Another Starglance on this port: ask it to show its window."""
    mode = _local(port, "/api/mode")
    if not mode or mode.get("mode") != "local":
        return False
    if _local(port, "/api/app/show", "POST") is None:
        webbrowser.open(f"http://127.0.0.1:{port}/")  # a plain `run`: open it in the browser
    return True


# ---------------------------------------------------------------- remembered window


def _prefs_file() -> Path:
    return paths.data_dir() / "app.json"


def load_prefs() -> dict:
    try:
        data = json.loads(_prefs_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return data if isinstance(data, dict) else {}


def save_prefs(prefs: dict) -> None:
    with contextlib.suppress(OSError):
        _prefs_file().write_text(json.dumps(prefs, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- start with Windows


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
"""Start with Windows: one value here (this user only), only while it's switched on."""


def autostart_command() -> str | None:
    """What Windows runs at sign-in: this exe, in the tray. None when running from source."""
    if not getattr(sys, "frozen", False) or sys.platform != "win32":
        return None
    return f'"{sys.executable}" app --hidden'


def autostart_enabled() -> bool | None:
    """On, off, or None when it isn't available (running from source, not Windows)."""
    if autostart_command() is None:
        return None
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
        return True
    except OSError:
        return False


def set_autostart(on: bool) -> bool | None:
    command = autostart_command()
    if command is None:
        return None
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if on:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
        else:
            with contextlib.suppress(FileNotFoundError):
                winreg.DeleteValue(key, APP_NAME)
    return autostart_enabled()


def _refresh_autostart() -> None:
    """Switched on, and the exe has moved or been replaced by a newer one: point at it."""
    command = autostart_command()
    if command is None or not autostart_enabled():
        return
    import winreg

    with contextlib.suppress(OSError):
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            current, _ = winreg.QueryValueEx(key, APP_NAME)
        if current != command:
            set_autostart(True)


# ---------------------------------------------------------------- the app


class Api:
    """What the page may ask of the app (window.pywebview.api): its window, and links."""

    def __init__(self, app: App | None = None) -> None:
        self._app = app

    def open_external(self, url: str) -> bool:
        """Open a link in the default browser: http(s) only."""
        if isinstance(url, str) and url.startswith(("https://", "http://")):
            webbrowser.open(url)
            return True
        return False

    def state(self) -> dict:
        a = self._app
        return {
            "frameless": bool(a and a.prefs.get("frameless", FRAMELESS_DEFAULT)),
            "on_top": bool(a and a.prefs.get("on_top", False)),
            "maximized": bool(a and a.maximized),
            "autostart": autostart_enabled(),
        }

    def minimize(self) -> None:
        if self._app and self._app.window:
            self._app.window.minimize()

    def toggle_maximize(self) -> dict:
        if self._app and self._app.window:
            if self._app.maximized:
                self._app.window.restore()
            else:
                self._app.window.maximize()
        return self.state()

    def hide(self) -> None:
        """The page's close button: to the tray, like the title bar's."""
        if self._app and self._app.window:
            self._app._remember()
            self._app.window.hide()
            self._app.hidden = True

    def set_on_top(self, on: bool) -> dict:
        if self._app:
            self._app.set_on_top(bool(on))
        return self.state()

    def set_frameless(self, on: bool) -> dict:
        if self._app:
            self._app.set_frameless(bool(on))
        return self.state()

    def set_autostart(self, on: bool) -> dict:
        set_autostart(bool(on))
        return self.state()


class App:
    def __init__(self, args) -> None:
        self.args = args
        self.port = args.ui_port
        self.loop: asyncio.AbstractEventLoop | None = None
        self.stop: asyncio.Event | None = None
        self.server = None
        self.ready = threading.Event()
        self.failed: str | None = None
        self.webview = None
        self.window = None
        self.maximized = False
        self.icon = None
        self.quitting = False
        self.hidden = bool(getattr(args, "hidden", False))
        """The window is in the tray (an update restarts it the same way)."""
        self.prefs = load_prefs()

    # -- the agent, on its own thread

    def _agent(self) -> None:
        from .__main__ import serve

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.loop = loop
        self.stop = asyncio.Event()

        def ready(server) -> None:
            self.server = server
            server.on_show = lambda: self.show()
            updater = getattr(server.control, "updater", None)
            if updater is not None and getattr(sys, "frozen", False):
                updater.relaunch = self.relaunch
            self.ready.set()

        try:
            loop.run_until_complete(serve(self.args, stop=self.stop, on_ready=ready, say=log.info))
        except BaseException as exc:  # noqa: BLE001 (the port is taken, ...)
            log.exception("The agent stopped")
            self.failed = str(exc) or exc.__class__.__name__
            self.ready.set()
        finally:
            loop.close()

    def url(self, hash_: str = "") -> str:
        return f"http://127.0.0.1:{self.port}/{hash_}"

    # -- window

    def _create_window(self, *, hidden: bool):
        """The window. Frameless (no title bar): the page's top bar is the drag area, with
        its own minimize, maximize and close buttons (WindowButtons.svelte)."""
        p = self.prefs
        window = self.webview.create_window(
            APP_NAME,
            self.url(),
            js_api=Api(self),
            width=int(p.get("width", 1280)),
            height=int(p.get("height", 800)),
            x=p.get("x"),
            y=p.get("y"),
            min_size=(420, 320),
            on_top=bool(p.get("on_top", False)),
            frameless=bool(p.get("frameless", FRAMELESS_DEFAULT)),
            easy_drag=False,  # only the top bar drags (dragging panels must still work)
            hidden=hidden,
            background_color=BG,
        )
        window.events.closing += lambda: self._on_closing(window)
        size = (int(p.get("width", 1280)), int(p.get("height", 800)))
        window.events.shown += lambda: self._measure_frame(window, size)
        window.events.loaded += lambda: log.info("Window loaded %s", self.url())
        window.events.maximized += lambda: self._set_maximized(True)
        window.events.restored += lambda: self._set_maximized(False)
        return window

    def _set_maximized(self, on: bool) -> None:
        self.maximized = on

    def show(self, hash_: str | None = None, script: str | None = None) -> None:
        if self.window is None:
            webbrowser.open(self.url(hash_ or ""))
            return
        if hash_ is not None:
            self.window.evaluate_js(f"location.hash = {json.dumps(hash_)}")
        if script:
            self.window.evaluate_js(script)
        self.window.show()
        self.window.restore()
        self.hidden = False

    def _measure_frame(self, window, asked: tuple[int, int]) -> None:
        """A window is made at its outer size but reports its inner size (no borders or
        title bar): remember the difference, or it would shrink a little every launch."""
        with contextlib.suppress(Exception):
            dw, dh = asked[0] - window.width, asked[1] - window.height
            if 0 <= dw <= 80 and 0 <= dh <= 120:
                self._frame = (dw, dh)

    def _remember(self) -> None:
        w = self.window
        if w is None:
            return
        dw, dh = getattr(self, "_frame", (0, 0))
        with contextlib.suppress(Exception):
            if w.width > 200 and w.height > 100 and not self.maximized:
                self.prefs.update(x=w.x, y=w.y, width=w.width + dw, height=w.height + dh)
        save_prefs(self.prefs)

    def _on_closing(self, window) -> bool:
        if self.quitting or window is not self.window:
            return True  # quitting, or an old window being replaced
        self._remember()
        window.hide()  # to the tray: the agent keeps running
        self.hidden = True
        return False

    def set_on_top(self, on: bool) -> None:
        self.prefs["on_top"] = on
        save_prefs(self.prefs)
        if self.window is not None:
            self.window.on_top = on

    def set_frameless(self, on: bool) -> None:
        """Title bar on or off: Windows can't change that on an open window, so open a new
        one in the same place and close the old."""
        if bool(self.prefs.get("frameless", FRAMELESS_DEFAULT)) == on or self.window is None:
            self.prefs["frameless"] = on
            save_prefs(self.prefs)
            return
        self._remember()
        self.prefs["frameless"] = on
        save_prefs(self.prefs)
        old = self.window
        self.window = self._create_window(hidden=False)
        with contextlib.suppress(Exception):
            old.destroy()

    # -- after an update (selfupdate): the new exe is in place

    def relaunch(self) -> None:
        """Start the new exe (it waits for this one to let go of the port), then quit.
        The window comes back as it was: open, or in the tray."""
        import os
        import subprocess

        args = [sys.executable, "app", "--updated", "--ui-port", str(self.port)]
        if self.hidden:
            args.append("--hidden")
        # A one-file exe started from another must unpack itself afresh, not reuse ours.
        env = {**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"}
        flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(args, env=env, close_fds=True, creationflags=flags)  # noqa: S603
        log.info("Started the new version; quitting this one")
        self.quit()

    # -- quit

    def quit(self) -> None:
        if self.quitting:
            return
        self.quitting = True
        self._remember()
        if self.icon is not None:
            with contextlib.suppress(Exception):
                self.icon.stop()
        if self.loop is not None and self.stop is not None:
            self.loop.call_soon_threadsafe(self.stop.set)
        if self.window is not None:
            with contextlib.suppress(Exception):
                self.window.destroy()

    # -- tray

    def _tray(self):
        import pystray

        settings = "dispatchEvent(new CustomEvent('ft:settings', { detail: 'agent' }))"
        item = pystray.MenuItem
        windowed = self.window is not None
        return pystray.Icon(
            APP_NAME,
            draw_icon(64),
            f"{APP_NAME} {__version__}",
            menu=pystray.Menu(
                item("Open Starglance", lambda: self.show(""), default=True),
                item("Fleet", lambda: self.show("#fleet")),
                item("Settings", lambda: self.show("", settings)),
                pystray.Menu.SEPARATOR,
                item(
                    "Always on top",
                    lambda: self.set_on_top(not self.prefs.get("on_top", False)),
                    checked=lambda _i: bool(self.prefs.get("on_top", False)),
                    visible=windowed,
                ),
                item(
                    "Hide the title bar",
                    lambda: self.set_frameless(not self.prefs.get("frameless", FRAMELESS_DEFAULT)),
                    checked=lambda _i: bool(self.prefs.get("frameless", FRAMELESS_DEFAULT)),
                    visible=windowed,
                ),
                item(
                    "Start with Windows",
                    lambda: set_autostart(not autostart_enabled()),
                    checked=lambda _i: bool(autostart_enabled()),
                    visible=autostart_command() is not None,
                ),
                pystray.Menu.SEPARATOR,
                item("Open in browser", lambda: webbrowser.open(self.url())),
                item("Logs folder", lambda: _open_folder(paths.logs_dir())),
                pystray.Menu.SEPARATOR,
                item("Quit Starglance", self.quit),
            ),
        )

    # -- run

    def run(self) -> int:
        _refresh_autostart()
        self.agent_thread = threading.Thread(target=self._agent, name="agent", daemon=True)
        self.agent_thread.start()
        self.ready.wait(60)
        if self.server is None:
            _message(
                f"Starglance couldn't start: {self.failed or 'it took too long'}.\n\n"
                f"Details are in {paths.logs_dir() / 'starglance.log'}."
            )
            return 1
        try:
            import webview
        except Exception:  # noqa: BLE001 (not installed: tray and browser only)
            log.exception("No pywebview")
            webview = None
        if webview is not None:
            try:
                return self._run_window(webview)
            except Exception:  # noqa: BLE001 (no WebView2 runtime, ...)
                log.exception("No window (WebView2?): using the browser")
                self.window = None
        if not getattr(self.args, "hidden", False):
            webbrowser.open(self.url())
        try:
            self.icon = self._tray()
        except ImportError:  # from source without the desktop extra: browser only
            log.warning("No tray icon: install the desktop parts with uv sync --extra app")
            self.agent_thread.join()
            return 0
        self.icon.run()  # until Quit
        self.quit()
        return 0

    def _run_window(self, webview) -> int:
        self.webview = webview
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
        # Frameless: drag by the top bar itself, not by the buttons and chips on it.
        webview.settings["DRAG_REGION_DIRECT_TARGET_ONLY"] = True
        self.window = self._create_window(hidden=bool(getattr(self.args, "hidden", False)))
        self.icon = self._tray()
        self.icon.run_detached()
        storage = paths.data_dir() / "webview"
        storage.mkdir(exist_ok=True)
        icon_file = Path(getattr(sys, "_MEIPASS", "")) / "starglance.ico"
        webview.start(
            gui="edgechromium",
            private_mode=False,  # keep the page's storage: layouts, themes, settings
            storage_path=str(storage),
            icon=str(icon_file) if icon_file.exists() else None,
        )
        self.quit()  # the last window is gone: stop the agent and the tray
        return 0


def _open_folder(path: Path) -> None:
    if sys.platform == "win32":
        import os

        os.startfile(path)  # noqa: S606 (Explorer, on our own folder)
    else:
        webbrowser.open(path.as_uri())


def _message(text: str) -> None:
    """A Windows message box (the app has no console to print to)."""
    log.error(text)
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, text, APP_NAME, 0x10)
    else:
        print(text, file=sys.stderr)


def _log_to_file(verbose: bool) -> None:
    handler = logging.handlers.RotatingFileHandler(
        paths.logs_dir() / "starglance.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    for noisy in ("aiohttp.access", "PIL", "pywebview"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _after_update(port: int) -> None:
    """Started by the previous version after it put this exe in place: wait for it to quit
    (it holds the port), then delete it in the background."""
    import time

    from .selfupdate import remove_old

    for _ in range(120):
        if _local(port, "/api/mode", timeout=0.5) is None:
            break
        time.sleep(0.5)
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        threading.Thread(target=remove_old, args=(exe,), name="remove-old", daemon=True).start()


def run_app(args) -> None:
    _log_to_file(getattr(args, "verbose", False))
    log.info("Starglance %s starting", __version__)
    if getattr(args, "updated", False):
        log.info("Updated: waiting for the previous version to quit")
        _after_update(args.ui_port)
    if already_running(args.ui_port):
        log.info("Already running: showed its window")
        return
    sys.exit(App(args).run())
