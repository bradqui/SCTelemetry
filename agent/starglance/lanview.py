"""Show on other devices: the cockpit view on your home network, view only (opt-in).

Off by default (Settings -> Agent -> Other devices). When on, a second server listens on
your network (``http://<this PC>:8741``) beside the local one, which stays on 127.0.0.1.
It serves the page, the live feed and the fleet view, and nothing else: no Agent
settings, no telemetry switch, no fleet sign-in links, no replay controls. Anything a
device sends is ignored except which fleet member it has open, as on the PC itself.
Nothing reaches the game from here.

Pairing: a device that isn't paired gets a page asking for a code. The PC shows one
(Pair a device): 6 digits, for 5 minutes and 5 tries. The device then keeps a random key
in a cookie; this PC keeps only its hash, with a rough name ("Safari on iPad") and when it
was last seen, and can remove it (which also cuts it off at once).

The address must be an IP address or this PC's name, so a website can't reach this server
through DNS rebinding; a browser's Origin must be the address itself.

It's plain HTTP: anyone who can watch your network's traffic could see the telemetry, or
copy a device's key and watch too. View only, so that's the most they get. Windows asks
the first time whether Starglance may accept connections; allow it on private networks.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import ipaddress
import json
import logging
import secrets
import socket
import time
from dataclasses import asdict, dataclass, field
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from aiohttp import web
from starglance_shared import device_label

from . import __version__, paths

if TYPE_CHECKING:
    from .localserver import LocalServer

log = logging.getLogger(__name__)

LAN_PORT = 8741
CODE_TTL_S = 300
CODE_TRIES = 5
MAX_DEVICES = 20
COOKIE = "sg_device"
COOKIE_MAX_AGE = 400 * 86400  # browsers keep cookies at most 400 days
SEEN_SAVE_MS = 60_000
_LAN_SUFFIXES = {"local", "lan", "home", "home.arpa", "localdomain"}


def settings_file() -> Path:
    return paths.data_dir() / "other-devices.json"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


@dataclass
class Device:
    id: str
    name: str
    key_hash: str
    paired: int
    seen: int


DEVICE = web.RequestKey("device", Device)


@dataclass
class LanSettings:
    enabled: bool = False
    port: int = LAN_PORT
    devices: list[Device] = field(default_factory=list)


def load_settings() -> LanSettings:
    try:
        data = json.loads(settings_file().read_text(encoding="utf-8"))
        return LanSettings(
            enabled=bool(data.get("enabled", False)),
            port=int(data.get("port", LAN_PORT)),
            devices=[Device(**d) for d in data.get("devices", [])],
        )
    except (OSError, ValueError, TypeError):
        return LanSettings()


def save_settings(s: LanSettings) -> None:
    settings_file().write_text(json.dumps(asdict(s), indent=2), encoding="utf-8")


def lan_addresses() -> list[str]:
    """This PC's addresses on private networks, the one its default route uses first."""
    found: list[str] = []
    with contextlib.suppress(OSError), socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("192.0.2.1", 9))  # UDP: nothing is sent, it only picks the interface
        found.append(s.getsockname()[0])
    with contextlib.suppress(OSError):
        found += [i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)]
    keep = []
    for ip in dict.fromkeys(found):
        a = ipaddress.ip_address(ip)
        if a.is_private and not (a.is_loopback or a.is_link_local):
            keep.append(ip)
    return keep


def host_ok(host: str) -> bool:
    """An IP address, or this PC's name (alone or with a home network's suffix)."""
    if host.startswith("["):
        name = host[1:].split("]", 1)[0]
    else:
        name = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    with contextlib.suppress(ValueError):
        ipaddress.ip_address(name)
        return True
    name = name.lower().rstrip(".")
    pc = socket.gethostname().lower()
    first, _, rest = name.partition(".")
    return bool(pc) and first == pc and (not rest or rest in _LAN_SUFFIXES)


@dataclass
class _Code:
    code: str
    expires: float
    tries: int = CODE_TRIES

    def left(self) -> int:
        return max(0, round(self.expires - time.monotonic()))


class LanView:
    """The view-only server for other devices, and its paired devices."""

    def __init__(self, local: LocalServer, *, announce=print) -> None:
        self.local = local
        self.announce = announce
        self.settings = load_settings()
        self.code: _Code | None = None
        self.error: str | None = None
        self.port: int | None = None
        """The port while running."""
        self._runner: web.AppRunner | None = None
        self._sockets: dict[str, set[web.WebSocketResponse]] = {}
        self._saved = 0
        self.app = web.Application(middlewares=[self._guard])
        self.app.add_routes(
            [
                web.get("/pair", self._pair_page),
                web.post("/pair", self._pair),
                web.get("/ws", self._ws),
                web.get("/ws/fleet", self._fleet_ws),
                web.get("/api/mode", self._mode),
                web.get("/api/state", local.api_state),
                web.route("*", "/api/{tail:.*}", self._not_here),
                web.get("/{tail:.*}", local.static),
            ]
        )

    # -- who may connect

    def _device(self, request: web.Request) -> Device | None:
        did, _, key = request.cookies.get(COOKIE, "").partition(".")
        if not did or not key:
            return None
        h = _hash(key)
        for d in self.settings.devices:
            if d.id == did and hmac.compare_digest(d.key_hash, h):
                return d
        return None

    @web.middleware
    async def _guard(self, request: web.Request, handler):
        if not host_ok(request.host or ""):
            return web.Response(status=403, text="Use this PC's address (its IP or name).")
        origin = request.headers.get("Origin")
        if origin is not None and origin != f"http://{request.host}":
            return web.Response(status=403, text="Cross-origin access refused.")
        if request.path == "/pair":
            return await handler(request)
        device = self._device(request)
        if device is None:
            if request.path.startswith(("/api/", "/ws")):
                return web.json_response({"error": "This device isn't paired."}, status=401)
            raise web.HTTPSeeOther("/pair")
        request[DEVICE] = device
        self._seen(device)
        return await handler(request)

    def _seen(self, device: Device) -> None:
        device.seen = _now_ms()
        if device.seen - self._saved > SEEN_SAVE_MS:
            self._saved = device.seen
            save_settings(self.settings)

    # -- pairing

    def new_code(self) -> None:
        self.code = _Code(f"{secrets.randbelow(10**6):06d}", time.monotonic() + CODE_TTL_S)

    def cancel_code(self) -> None:
        self.code = None

    def _waiting(self) -> _Code | None:
        if self.code and self.code.left() <= 0:
            self.code = None
        return self.code

    async def _pair_page(self, request: web.Request) -> web.Response:
        if self._device(request) is not None:
            raise web.HTTPSeeOther("/")
        return _page(code=request.query.get("code", ""))

    async def _pair(self, request: web.Request) -> web.Response:
        form = await request.post()
        given = "".join(ch for ch in str(form.get("code", "")) if ch.isdigit())
        code = self._waiting()
        if code is None:
            return _page(
                error="No code is waiting. On the PC: Settings → Agent → Other devices → "
                "Pair a device.",
                status=400,
            )
        if not hmac.compare_digest(given, code.code):
            code.tries -= 1
            if code.tries <= 0:
                self.code = None
                return _page(error="Too many tries. Make a new code on the PC.", status=400)
            tries = f"{code.tries} {'try' if code.tries == 1 else 'tries'} left"
            return _page(code=given, error=f"That's not the code ({tries}).", status=400)
        if len(self.settings.devices) >= MAX_DEVICES:
            return _page(error="Too many devices. Remove one on the PC first.", status=400)
        self.code = None
        key = secrets.token_urlsafe(32)
        now = _now_ms()
        device = Device(
            id=secrets.token_hex(4),
            name=device_label(request.headers.get("User-Agent", "")) or "A browser",
            key_hash=_hash(key),
            paired=now,
            seen=now,
        )
        self.settings.devices.append(device)
        save_settings(self.settings)
        self.announce(f"Other devices: paired {device.name}.")
        resp = web.HTTPSeeOther("/")
        resp.set_cookie(
            COOKIE,
            f"{device.id}.{key}",
            max_age=COOKIE_MAX_AGE,
            httponly=True,
            samesite="Strict",
            path="/",
        )
        raise resp

    # -- what a paired device gets

    async def _mode(self, _request: web.Request) -> web.Response:
        return web.json_response({"mode": "local", "remote": True, "agent_version": __version__})

    async def _not_here(self, _request: web.Request) -> web.Response:
        return web.json_response({"error": "Only on the PC itself."}, status=404)

    def _track(self, device: Device):
        def track(ws: web.WebSocketResponse):
            self._sockets.setdefault(device.id, set()).add(ws)

            def done() -> None:
                live = self._sockets.get(device.id)
                if live is not None:
                    live.discard(ws)
                    if not live:
                        self._sockets.pop(device.id, None)

            return done

        return track

    async def _ws(self, request: web.Request) -> web.WebSocketResponse:
        return await self.local.stream(request, remote=True, track=self._track(request[DEVICE]))

    async def _fleet_ws(self, request: web.Request) -> web.WebSocketResponse:
        return await self.local.fleet_stream(request, track=self._track(request[DEVICE]))

    async def _close(self, device_id: str | None = None) -> None:
        for did in [device_id] if device_id else list(self._sockets):
            for ws in list(self._sockets.pop(did, set())):
                with contextlib.suppress(Exception):
                    await ws.close(code=1008, message=b"removed")

    # -- the switch, and the PC's Settings

    @property
    def running(self) -> bool:
        return self._runner is not None

    async def start(self) -> None:
        if self._runner is not None:
            return
        self.error = None
        runner = web.AppRunner(self.app, access_log=None, shutdown_timeout=2)
        await runner.setup()
        try:
            await web.TCPSite(runner, "0.0.0.0", self.settings.port).start()
        except OSError as exc:
            await runner.cleanup()
            self.error = f"Port {self.settings.port} is in use or blocked ({exc.strerror or exc})."
            log.warning("Other devices: %s", self.error)
            return
        self._runner = runner
        self.port = runner.addresses[0][1]
        urls = ", ".join(f"http://{ip}:{self.port}" for ip in lan_addresses()[:1])
        self.announce(f"Other devices: view only at {urls or f'port {self.port}'}")

    async def stop(self) -> None:
        self.code = None
        await self._close()
        if self._runner is not None:
            runner, self._runner = self._runner, None
            await runner.cleanup()
            self.port = None
        save_settings(self.settings)

    async def set_enabled(self, on: bool) -> None:
        self.settings.enabled = on
        save_settings(self.settings)
        if on:
            await self.start()
        else:
            await self.stop()
            self.announce("Other devices: off.")

    async def forget(self, device_id: str | None) -> None:
        """Remove one device (or all, with None) and cut it off now."""
        keep = [d for d in self.settings.devices if device_id and d.id != device_id]
        self.settings.devices = keep
        save_settings(self.settings)
        await self._close(device_id)

    def state(self) -> dict:
        code = self._waiting()
        port = self.port or self.settings.port
        ips = lan_addresses()
        return {
            "enabled": self.settings.enabled,
            "running": self.running,
            "error": self.error,
            "port": port,
            "addresses": [f"http://{ip}:{port}" for ip in ips]
            + [f"http://{socket.gethostname()}:{port}"],
            "code": {"code": code.code, "expires_in": code.left(), "tries": code.tries}
            if code
            else None,
            "devices": [
                {
                    "id": d.id,
                    "name": d.name,
                    "paired": d.paired,
                    "seen": d.seen,
                    "online": d.id in self._sockets,
                }
                for d in sorted(self.settings.devices, key=lambda d: -d.seen)
            ],
        }


_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Starglance: pair this device</title>
<style>
:root {{ color-scheme: dark; --bg: #0b1016; --panel: #121a23; --line: #263443; --text: #e6edf3;
  --muted: #8b9bab; --accent: #4cc2ff; --bad: #ff6b6b; }}
@media (prefers-color-scheme: light) {{ :root {{ color-scheme: light; --bg: #f2f5f8;
  --panel: #fff; --line: #cfd8e1; --text: #15202b; --muted: #556677; --accent: #0a6fb0;
  --bad: #c62828; }} }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; padding: 16px;
  background: var(--bg); color: var(--text); font: 16px/1.45 system-ui, sans-serif; }}
main {{ width: min(380px, 100%); display: grid; gap: 14px; padding: 22px;
  background: var(--panel); border: 1px solid var(--line); border-radius: 6px; }}
h1 {{ margin: 0; font-size: 1.15rem; }}
p {{ margin: 0; color: var(--muted); font-size: 0.92rem; }}
b {{ color: var(--text); }}
input {{ width: 100%; padding: 10px; font: 700 1.6rem/1 ui-monospace, monospace;
  letter-spacing: 0.3em; text-align: center; color: var(--text); background: var(--bg);
  border: 1px solid var(--line); border-radius: 4px; }}
button {{ padding: 10px; font: 700 1rem system-ui, sans-serif; color: var(--bg);
  background: var(--accent); border: 0; border-radius: 4px; cursor: pointer; }}
.error {{ color: var(--bad); }}
</style></head>
<body><main>
<h1>Starglance</h1>
<p>To watch this PC's cockpit view here, enter the code it shows: on the PC, open
<b>Settings → Agent → Other devices</b> and choose <b>Pair a device</b>.</p>
{error}
<form method="post" action="/pair" style="display: grid; gap: 10px">
<input name="code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9 ]*"
  maxlength="7" placeholder="000000" value="{code}" aria-label="Pairing code" required autofocus>
<button type="submit">Pair</button>
</form>
<p>View only: nothing on this device can change the PC's settings or the game.</p>
</main></body></html>
"""


def _page(*, code: str = "", error: str = "", status: int = 200) -> web.Response:
    err = f'<p class="error" role="alert">{escape(error)}</p>' if error else ""
    code = "".join(ch for ch in code if ch.isdigit())[:6]
    return web.Response(
        status=status,
        content_type="text/html",
        text=_PAGE.format(error=err, code=escape(code)),
        headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY"},
    )
