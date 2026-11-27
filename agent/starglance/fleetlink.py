"""Joining a fleet hub, linking more PCs, and what this PC shares (spec §5.1, §6.1).

- **Joining** (new member): an admin sends you an invite link
  (``https://<hub>/join/<code>``). ``starglance link <that link>`` creates your
  account with a display name (your in-game handle, unless you pick another)
  and links this PC in one go. The link carries the hub's address, so one
  agent works for any org's hub.
- **Another PC** (existing member): ``starglance link https://<hub>`` shows a
  code and opens the hub's page, where you confirm it while signed in.
- **From the hub's page** (the easy way): signed in on the fleet page, **Link this PC**
  opens a one-time ``starglance://link?hub=<hub>&code=<secret>`` link. Windows hands it
  to the app (app.py registers the ``starglance:`` scheme), which asks the hub whose link
  it is, asks you to confirm, and only then redeems it for this PC's key.
- **Opening the page**: ``starglance open`` (or the Fleet chip in the cockpit
  view) signs a browser in with a one-time link.

The PC's token is kept in Windows Credential Manager. With ``STARGLANCE_HOME``
set (tests, portable use), or where no credential store exists, it goes in a
file in the agent's data folder instead.

A PC can be in several fleets (one per org's hub: you play with more than one org).
Each has its own key, its own sharing and an on/off switch. Sharing: every category is
on by default; each can be switched off, per fleet, and is then never sent to that hub
(``starglance_shared.apply_sharing``).
"""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import json
import os
import platform
import re
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

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


def _all_on() -> dict[str, bool]:
    return dict.fromkeys(SHARE_CATEGORIES, True)


@dataclass
class Fleet:
    """One org's hub this PC is linked to, and what it shares with that org."""

    hub_url: str
    member_name: str | None = None
    org: str | None = None
    agent_id: int | None = None
    enabled: bool = True
    """Send to this fleet now (off: still linked, nothing sent)."""
    share: dict[str, bool] = field(default_factory=_all_on)

    @property
    def shared(self) -> set[str]:
        return {c for c in SHARE_CATEGORIES if self.share.get(c, True)}

    @property
    def label(self) -> str:
        return self.org or urlsplit(self.hub_url).netloc or self.hub_url


@dataclass
class FleetSettings:
    """Every fleet this PC sends to: one org per hub, as many hubs as you play with."""

    fleets: list[Fleet] = field(default_factory=list)

    def get(self, hub_url: str | None) -> Fleet | None:
        hub = (hub_url or "").rstrip("/")
        return next((f for f in self.fleets if f.hub_url == hub), None)

    def add(self, hub_url: str) -> Fleet:
        fleet = self.get(hub_url)
        if fleet is None:
            fleet = Fleet(hub_url=hub_url.rstrip("/"))
            self.fleets.append(fleet)
        return fleet

    def remove(self, hub_url: str) -> Fleet | None:
        fleet = self.get(hub_url)
        if fleet is not None:
            self.fleets.remove(fleet)
        return fleet

    def pick(self, which: str | None) -> Fleet:
        """The fleet a command means: by hub address or org name, or the only one."""
        if not self.fleets:
            raise LinkError("Not in a fleet. Join one with: starglance link <invite link>")
        if which:
            w = which.strip().rstrip("/").lower()
            for f in self.fleets:
                if w in (f.hub_url.lower(), (f.org or "").lower(), urlsplit(f.hub_url).netloc):
                    return f
            raise LinkError(f"No fleet {which!r}. Yours: {', '.join(f.label for f in self.fleets)}")
        if len(self.fleets) == 1:
            return self.fleets[0]
        names = ", ".join(f"{f.label} ({f.hub_url})" for f in self.fleets)
        raise LinkError(f"You're in more than one fleet: say which with --hub. {names}")


def _read_settings() -> dict:
    try:
        data = json.loads(paths.settings_file().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _fleet_from(d: dict) -> Fleet | None:
    hub = (d.get("hub_url") or "").rstrip("/")
    if not hub:
        return None
    saved = d.get("share") or {}
    return Fleet(
        hub_url=hub,
        member_name=d.get("member_name"),
        org=d.get("org"),
        agent_id=d.get("agent_id"),
        enabled=bool(d.get("enabled", True)),
        share={c: bool(saved.get(c, True)) for c in SHARE_CATEGORIES},  # new ones: on
    )


def load_settings() -> FleetSettings:
    data = _read_settings()
    raw = data.get("fleets")
    if not isinstance(raw, list):
        raw = [data["fleet"]] if isinstance(data.get("fleet"), dict) else []  # one fleet, 0.3
    fleets = [f for f in (_fleet_from(d) for d in raw if isinstance(d, dict)) if f]
    return FleetSettings(fleets=fleets)


def save_settings(s: FleetSettings) -> None:
    data = _read_settings()
    data.pop("fleet", None)
    data["fleets"] = [
        {
            "hub_url": f.hub_url,
            "member_name": f.member_name,
            "org": f.org,
            "agent_id": f.agent_id,
            "enabled": f.enabled,
            "share": f.share,
        }
        for f in s.fleets
    ]
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


def _file_tokens() -> dict[str, str]:
    """The token file: {hub URL: token}. (Up to 0.3 it held one: {"hub_url", "token"}.)"""
    try:
        data = json.loads(_token_file().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    if "hub_url" in data and "token" in data:
        return {str(data["hub_url"]): str(data["token"])}
    return {str(k): str(v) for k, v in data.items() if isinstance(v, str)}


def _write_file_tokens(tokens: dict[str, str]) -> None:
    path = _token_file()
    if not tokens:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()
        return
    path.write_text(json.dumps(tokens), encoding="utf-8")
    with contextlib.suppress(OSError):
        path.chmod(0o600)


def save_token(hub_url: str, token: str) -> None:
    if _use_keyring():
        import keyring

        with contextlib.suppress(Exception):
            keyring.set_password(KEYRING_SERVICE, hub_url, token)
            return
    _write_file_tokens({**_file_tokens(), hub_url: token})


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
    return _file_tokens().get(hub_url)


def forget_token(hub_url: str) -> None:
    if _use_keyring():
        import keyring

        for service in (KEYRING_SERVICE, OLD_KEYRING_SERVICE):
            with contextlib.suppress(Exception):
                keyring.delete_password(service, hub_url)
    tokens = _file_tokens()
    if tokens.pop(hub_url, None) is not None:
        _write_file_tokens(tokens)


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


APP_LINK_SCHEME = "starglance"


def is_app_link(target: str) -> bool:
    return target.strip().lower().startswith(f"{APP_LINK_SCHEME}:")


def _local_host(host: str) -> bool:
    """Loopback or a private address: a hub on this PC or the LAN, which may be plain http."""
    if host in ("localhost",) or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private or ip.is_link_local


def parse_app_link(url: str) -> tuple[str, str]:
    """``starglance://link?hub=<hub address>&code=<secret>`` -> (hub URL, code).

    Any website can open such a link, so this only checks its shape: the app shows the hub
    and asks before anything is sent. Hubs must be https, except on this PC or the LAN."""
    parts = urlsplit(url.strip())
    if parts.scheme.lower() != APP_LINK_SCHEME or (parts.netloc or parts.path.strip("/")) != "link":
        raise LinkError("That isn't a Starglance link.")
    query = parse_qs(parts.query)
    hub = (query.get("hub") or [""])[0].strip().rstrip("/")
    code = (query.get("code") or [""])[0].strip()
    hub_parts = urlsplit(hub)
    if (
        hub_parts.scheme not in ("https", "http")
        or not hub_parts.hostname
        or hub_parts.query
        or hub_parts.fragment
        or hub_parts.username
        or hub_parts.password
    ):
        raise LinkError("The link doesn't name a hub.")
    if hub_parts.scheme == "http" and not _local_host(hub_parts.hostname):
        raise LinkError("The hub in that link isn't secure (https).")
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", code):
        raise LinkError("The link is incomplete: open it again from the fleet page.")
    return hub, code


def machine_name() -> str:
    return (platform.node() or "PC")[:32]


def _save_link(hub_url: str, result: dict) -> Fleet:
    """Linked to a hub: add it to this PC's fleets (or refresh it, keeping its sharing)."""
    save_token(hub_url, result["token"])
    settings = load_settings()
    fleet = settings.add(hub_url)
    fleet.agent_id = result.get("agent_id")
    fleet.member_name = (result.get("member") or {}).get("name")
    fleet.org = result.get("org") or fleet.org
    fleet.enabled = True
    save_settings(settings)
    return fleet


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


async def join(hub_url: str, invite: str, name: str, *, machine: str | None = None) -> Fleet:
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
) -> Fleet:
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


async def check_pc_link(hub_url: str, code: str) -> dict:
    """Whose link this is (org, member), from the hub, before you confirm it."""
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as http:
        status, body = await _post(http, f"{hub_url}/api/agent/pc-link/check", {"code": code})
    if status != 200:
        raise LinkError(body.get("error") or f"The hub refused ({status}).")
    return body


async def redeem_pc_link(hub_url: str, code: str, *, machine: str | None = None) -> Fleet:
    """You confirmed a link from the hub's page: this PC gets its key (the link works once)."""
    old = load_token(hub_url)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as http:
        status, body = await _post(
            http,
            f"{hub_url}/api/agent/pc-link/redeem",
            {"code": code, "machine": machine or machine_name()},
        )
        if status != 200:
            raise LinkError(body.get("error") or f"The hub refused ({status}).")
        if old:  # linked again (another account, or a fresh start): the hub forgets the old key
            with contextlib.suppress(aiohttp.ClientError, asyncio.TimeoutError):
                await http.post(
                    f"{hub_url}/api/agent/unlink", headers={"Authorization": f"Bearer {old}"}
                )
    return _save_link(hub_url, body)


def unlink(hub_url: str) -> Fleet | None:
    """Forget a fleet: its key and its settings. (Telling the hub is the caller's job.)"""
    settings = load_settings()
    fleet = settings.remove(hub_url)
    forget_token(hub_url)
    save_settings(settings)
    return fleet


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
