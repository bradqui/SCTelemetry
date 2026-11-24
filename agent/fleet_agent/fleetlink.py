"""Linking this PC to the fleet hub, and what it shares (spec §5.1, §6.1).

Linking works like signing a TV into an app: the agent asks the hub for a short
code, opens the browser at the hub, the member signs in with Discord and
confirms, and the agent (polling meanwhile) receives its token.

The token is kept in Windows Credential Manager. With ``FLEET_TELEMETRY_HOME``
set (tests, portable use), or where no credential store exists, it goes in a
file in the agent's data folder instead.

Sharing: every category is on by default; each can be switched off and is then
never sent (``fleet_shared.apply_sharing``).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import platform
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import aiohttp
from fleet_shared import SHARE_CATEGORIES

from . import paths

DEFAULT_HUB = "https://fleet.fridaynightclub.xyz"
KEYRING_SERVICE = "FleetTelemetry"
TOKEN_FILE = "hub-token"


class LinkError(Exception):
    pass


# ---------------------------------------------------------------- settings


@dataclass
class FleetSettings:
    hub_url: str = DEFAULT_HUB
    member_name: str | None = None
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
    s.hub_url = str(fleet.get("hub_url") or DEFAULT_HUB).rstrip("/")
    s.member_name = fleet.get("member_name")
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
        "agent_id": s.agent_id,
        "share": s.share,
    }
    paths.settings_file().write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- token


def _use_keyring() -> bool:
    if os.environ.get("FLEET_TELEMETRY_HOME"):
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
    try:
        data = json.loads(_token_file().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return data.get("token") if data.get("hub_url") == hub_url else None


def forget_token(hub_url: str) -> None:
    if _use_keyring():
        import keyring

        with contextlib.suppress(Exception):
            keyring.delete_password(KEYRING_SERVICE, hub_url)
    with contextlib.suppress(FileNotFoundError):
        _token_file().unlink()


# ---------------------------------------------------------------- the link flow


def machine_name() -> str:
    return (platform.node() or "PC")[:64]


async def link(
    hub_url: str,
    *,
    machine: str | None = None,
    open_browser: bool = True,
    say: Callable[[str], None] = print,
    timeout_s: float = 600,
) -> FleetSettings:
    """Link this PC to the hub. Returns the saved settings (token stored separately)."""
    hub_url = hub_url.rstrip("/")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as http:
        try:
            async with http.post(
                f"{hub_url}/api/agent/link/start", json={"machine": machine or machine_name()}
            ) as resp:
                if resp.status != 200:
                    raise LinkError(f"The hub refused ({resp.status}): {await resp.text()}")
                start = await resp.json()
        except aiohttp.ClientError as exc:
            raise LinkError(f"Can't reach the hub at {hub_url}: {exc}") from exc
        say(f"Your code: {start['user_code']}")
        say(f"Confirm it at {start['verify_url']}")
        if open_browser:
            webbrowser.open(start["verify_url"])
        loop = asyncio.get_running_loop()
        deadline = loop.time() + min(timeout_s, float(start.get("expires_in", 600)))
        while loop.time() < deadline:
            await asyncio.sleep(float(start.get("interval", 3)))
            try:
                async with http.post(
                    f"{hub_url}/api/agent/link/poll", json={"device_code": start["device_code"]}
                ) as resp:
                    result = await resp.json()
            except (aiohttp.ClientError, json.JSONDecodeError):
                continue  # a blip; keep polling
            if result.get("status") == "linked":
                save_token(hub_url, result["token"])
                settings = load_settings()
                settings.hub_url = hub_url
                settings.agent_id = result.get("agent_id")
                settings.member_name = (result.get("member") or {}).get("name")
                save_settings(settings)
                return settings
            if result.get("status") == "expired":
                break
        raise LinkError("The code expired before it was confirmed. Run link again.")


def unlink() -> FleetSettings:
    settings = load_settings()
    forget_token(settings.hub_url)
    settings.member_name = None
    settings.agent_id = None
    save_settings(settings)
    return settings
