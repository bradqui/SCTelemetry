"""Joining a fleet hub, linking more PCs, and what this PC shares (spec §5.1, §6.1).

- **Joining** (new member): an admin sends you an invite link
  (``https://<hub>/join/<code>``). ``starglance link <that link>`` creates your
  account with a display name (your in-game handle, unless you pick another)
  and links this PC in one go. The link carries the hub's address, so one
  agent works for any org's hub.
- **Another PC** (existing member): ``starglance link https://<hub>`` shows a
  code and opens the hub's page, where you confirm it while signed in.
- **Opening the page**: ``starglance open`` (or the Fleet chip in the cockpit
  view) signs a browser in with a one-time link.

The PC's token is kept in Windows Credential Manager. With ``STARGLANCE_HOME``
set (tests, portable use), or where no credential store exists, it goes in a
file in the agent's data folder instead.

Sharing: every category is on by default; each can be switched off and is then
never sent (``starglance_shared.apply_sharing``).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import platform
import re
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import aiohttp
from starglance_shared import SHARE_CATEGORIES

from . import paths

KEYRING_SERVICE = "Starglance"
OLD_KEYRING_SERVICE = "FleetTelemetry"
"""The Credential Manager entry's name before the rename: a key saved there is moved."""
TOKEN_FILE = "hub-token"
_INVITE = re.compile(r"^(https?://[^/]+)(/.*)?/join/([A-Za-z0-9_-]+)/?$")


class LinkError(Exception):
    pass


# ---------------------------------------------------------------- settings


@dataclass
class FleetSettings:
    hub_url: str | None = None
    member_name: str | None = None
    org: str | None = None
    agent_id: int | None = None
    share: dict[str, bool] = field(default_factory=lambda: dict.fromkeys(SHARE_CATEGORIES, True))

    @property
    def shared(self) -> set[str]:
        return {c for c in SHARE_CATEGORIES if self.share.get(c, True)}


def _read_settings() -> dict:
    try:
        data = json.loads(paths.settings_file().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_settings() -> FleetSettings:
    fleet = _read_settings().get("fleet") or {}
    s = FleetSettings()
    s.hub_url = (fleet.get("hub_url") or "").rstrip("/") or None
    s.member_name = fleet.get("member_name")
    s.org = fleet.get("org")
    s.agent_id = fleet.get("agent_id")
    saved = fleet.get("share") or {}
    for c in SHARE_CATEGORIES:
        s.share[c] = bool(saved.get(c, True))  # new categories default to on
    return s


def save_settings(s: FleetSettings) -> None:
    data = _read_settings()
    data["fleet"] = {
        "hub_url": s.hub_url,
        "member_name": s.member_name,
        "org": s.org,
        "agent_id": s.agent_id,
        "share": s.share,
    }
    paths.settings_file().write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- token


def _use_keyring() -> bool:
    if os.environ.get("STARGLANCE_HOME"):
        return False
    try:
        import keyring  # noqa: F401
    except ImportError:
        return False
    return True


def _token_file() -> Path:
    return paths.data_dir() / TOKEN_FILE


def save_token(hub_url: str, token: str) -> None:
    if _use_keyring():
        import keyring

        with contextlib.suppress(Exception):
            keyring.set_password(KEYRING_SERVICE, hub_url, token)
            return
    path = _token_file()
    path.write_text(json.dumps({"hub_url": hub_url, "token": token}), encoding="utf-8")
    with contextlib.suppress(OSError):
        path.chmod(0o600)


def load_token(hub_url: str) -> str | None:
    if _use_keyring():
        import keyring

        with contextlib.suppress(Exception):
            token = keyring.get_password(KEYRING_SERVICE, hub_url)
            if token:
                return token
        with contextlib.suppress(Exception):  # linked before the rename: move it over
            token = keyring.get_password(OLD_KEYRING_SERVICE, hub_url)
            if token:
                keyring.set_password(KEYRING_SERVICE, hub_url, token)
                keyring.delete_password(OLD_KEYRING_SERVICE, hub_url)
                return token
    try:
        data = json.loads(_token_file().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return data.get("token") if data.get("hub_url") == hub_url else None


def forget_token(hub_url: str) -> None:
    if _use_keyring():
        import keyring

        for service in (KEYRING_SERVICE, OLD_KEYRING_SERVICE):
            with contextlib.suppress(Exception):
                keyring.delete_password(service, hub_url)
    with contextlib.suppress(FileNotFoundError):
        _token_file().unlink()


# ---------------------------------------------------------------- addresses


def parse_target(target: str) -> tuple[str, str | None]:
    """An invite link or a hub address -> (hub URL, invite code or None)."""
    target = target.strip()
    if not re.match(r"^https?://", target):
        target = "https://" + target
    m = _INVITE.match(target)
    if m:
        return (m.group(1) + (m.group(2) or "")).rstrip("/"), m.group(3)
    parts = urlsplit(target)
    if not parts.netloc:
        raise LinkError(f"That doesn't look like a hub address or invite link: {target}")
    return f"{parts.scheme}://{parts.netloc}{parts.path}".rstrip("/"), None


def machine_name() -> str:
    return (platform.node() or "PC")[:32]


def _save_link(hub_url: str, result: dict) -> FleetSettings:
    save_token(hub_url, result["token"])
    settings = load_settings()
    settings.hub_url = hub_url
    settings.agent_id = result.get("agent_id")
    settings.member_name = (result.get("member") or {}).get("name")
    settings.org = result.get("org") or settings.org
    save_settings(settings)
    return settings


async def _post(http: aiohttp.ClientSession, url: str, body: dict) -> tuple[int, dict]:
    try:
        async with http.post(url, json=body) as resp:
            try:
                data = await resp.json(content_type=None)
            except (json.JSONDecodeError, aiohttp.ContentTypeError):
                data = {}
            return resp.status, data if isinstance(data, dict) else {}
    except aiohttp.ClientError as exc:
        raise LinkError(f"Can't reach the hub: {exc}") from exc


# ---------------------------------------------------------------- join / link


async def join(
    hub_url: str, invite: str, name: str, *, machine: str | None = None
) -> FleetSettings:
    """Accept an invite from this PC: creates the account and links the PC."""
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as http:
        status, body = await _post(
            http,
            f"{hub_url}/api/agent/join",
            {"invite": invite, "name": name, "machine": machine or machine_name()},
        )
        if status != 200:
            raise LinkError(body.get("error") or f"The hub refused ({status}).")
        async with http.get(f"{hub_url}/api/mode") as resp:
            with contextlib.suppress(Exception):
                body["org"] = (await resp.json()).get("org")
    return _save_link(hub_url, body)


async def link(
    hub_url: str,
    *,
    machine: str | None = None,
    open_browser: bool = True,
    say: Callable[[str], None] = print,
    timeout_s: float = 600,
) -> FleetSettings:
    """Link this PC to an existing account: confirm the shown code on the hub's page."""
    hub_url = hub_url.rstrip("/")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as http:
        status, start = await _post(
            http, f"{hub_url}/api/agent/link/start", {"machine": machine or machine_name()}
        )
        if status != 200:
            raise LinkError(start.get("error") or f"The hub refused ({status}).")
        say(f"Your code: {start['user_code']}")
        say(f"Confirm it at {start['verify_url']} (sign in there if you need to)")
        if open_browser:
            webbrowser.open(start["verify_url"])
        loop = asyncio.get_running_loop()
        deadline = loop.time() + min(timeout_s, float(start.get("expires_in", 600)))
        while loop.time() < deadline:
            await asyncio.sleep(float(start.get("interval", 3)))
            try:
                _status, result = await _post(
                    http, f"{hub_url}/api/agent/link/poll", {"device_code": start["device_code"]}
                )
            except LinkError:
                continue  # a blip; keep polling
            if result.get("status") == "linked":
                return _save_link(hub_url, result)
            if result.get("status") == "expired":
                break
        raise LinkError("The code expired before it was confirmed. Run link again.")


async def login_link(hub_url: str, token: str) -> str:
    """A one-time address that opens the hub's page signed in as this PC's member."""
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=15), headers={"Authorization": f"Bearer {token}"}
    ) as http:
        status, body = await _post(http, f"{hub_url}/api/agent/login-link", {})
    if status != 200 or "url" not in body:
        raise LinkError(body.get("error") or f"The hub refused ({status}).")
    return body["url"]


def unlink() -> FleetSettings:
    settings = load_settings()
    if settings.hub_url:
        forget_token(settings.hub_url)
    settings.member_name = None
    settings.agent_id = None
    save_settings(settings)
    return settings


def game_handle(game_log: Path | None) -> str | None:
    """Your in-game handle from the game's log, for the default display name."""
    if game_log is None:
        return None
    from .gamelog import _HANDLE

    handle = None
    with contextlib.suppress(OSError), open(game_log, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "Handle[" in line and (m := _HANDLE.search(line)):
                handle = m.group(1)
    return handle
