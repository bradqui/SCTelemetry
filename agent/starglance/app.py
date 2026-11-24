"""Starglance as a Windows app: a tray icon and its own window, no console.

``starglance.exe`` with no arguments (or ``python -m starglance app``). The agent runs on
a background thread (``__main__.serve``); the cockpit view shows in a window of its own
(pywebview on Windows' Edge WebView2: no address bar, no tabs). Closing the window hides
it to the tray; Quit in the tray menu stops everything. Starting it again brings the
window back instead of running twice. Window size, position and "always on top" are
remembered (app.json in the agent's folder); the page's own storage (dashboard layouts,
themes) lives in its WebView2 profile there too. Output goes to logs/starglance.log.

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


# ---------------------------------------------------------------- the app


class Api:
    """What the page may ask of the app (window.pywebview.api)."""

    def open_external(self, url: str) -> bool:
        """Open a link in the default browser: http(s) only."""
        if isinstance(url, str) and url.startswith(("https://", "http://")):
            webbrowser.open(url)
            return True
        return False


class App:
    def __init__(self, args) -> None:
        self.args = args
        self.port = args.ui_port
        self.loop: asyncio.AbstractEventLoop | None = None
        self.stop: asyncio.Event | None = None
        self.server = None
        self.ready = threading.Event()
        self.failed: str | None = None
        self.window = None
        self.icon = None
        self.quitting = False
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

    def _remember(self) -> None:
        w = self.window
        if w is None:
            return
        with contextlib.suppress(Exception):
            if w.width > 200 and w.height > 100:
                self.prefs.update(x=w.x, y=w.y, width=w.width, height=w.height)
        save_prefs(self.prefs)

    def _on_closing(self) -> bool:
        if self.quitting:
            return True
        self._remember()
        self.window.hide()  # to the tray: the agent keeps running
        return False

    def set_on_top(self, on: bool) -> None:
        self.prefs["on_top"] = on
        save_prefs(self.prefs)
        if self.window is not None:
            self.window.on_top = on

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
                    visible=self.window is not None,
                ),
                item("Open in browser", lambda: webbrowser.open(self.url())),
                item("Logs folder", lambda: _open_folder(paths.logs_dir())),
                pystray.Menu.SEPARATOR,
                item("Quit Starglance", self.quit),
            ),
        )

    # -- run

    def run(self) -> int:
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
        p = self.prefs
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
        self.window = webview.create_window(
            APP_NAME,
            self.url(),
            js_api=Api(),
            width=int(p.get("width", 1280)),
            height=int(p.get("height", 800)),
            x=p.get("x"),
            y=p.get("y"),
            min_size=(420, 320),
            on_top=bool(p.get("on_top", False)),
            hidden=bool(getattr(self.args, "hidden", False)),
            background_color=BG,
        )
        self.window.events.closing += self._on_closing
        self.window.events.loaded += lambda: log.info("Window loaded %s", self.url())
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
        self.quit()  # the window is gone: stop the agent and the tray
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


def run_app(args) -> None:
    _log_to_file(getattr(args, "verbose", False))
    log.info("Starglance %s starting", __version__)
    if already_running(args.ui_port):
        log.info("Already running: showed its window")
        return
    sys.exit(App(args).run())
