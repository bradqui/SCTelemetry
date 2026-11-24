"""Agent settings while it runs: the cockpit page's Agent tab (localserver /api/agent/*).

Joins or leaves a fleet, chooses what's shared, and switches the game's telemetry on or
off, without a restart. Owns the hub uplink: starts it when linked, restarts it when the
sharing changes (the hub learns the categories from the uplink's hello), stops it on
leaving. The same files and functions as the command line (fleetlink, switch), so either
can be used.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable

import aiohttp
from fleet_shared import SHARE_CATEGORIES

from . import __version__, gamecfg, installs, switch
from .fleetlink import (
    LinkError,
    game_handle,
    join,
    link,
    load_settings,
    load_token,
    parse_target,
    save_settings,
    unlink,
)
from .installs import Install

log = logging.getLogger(__name__)

SHARE_HELP = {
    "status": "In game, on foot or seated, your seat, your in-game handle",
    "ship": "Ship, mode, warning lights, fuel, flight data",
    "weapons": "Guns ready, countermeasures",
    "vitals": "Health, oxygen, food and water, injuries",
    "uec": "aUEC balance and contract rewards",
    "location": "Zone, jurisdiction, server, star system, quantum destination, ship you're aboard",
    "mission": "Current contracts and objectives",
    "combat": "Kills, ships lost, session counts",
}
SHARE_LABEL = {
    "status": "Status",
    "ship": "Ship",
    "weapons": "Weapons",
    "vitals": "Vitals",
    "uec": "aUEC",
    "location": "Location",
    "mission": "Contracts",
    "combat": "Combat",
}


class AgentControl:
    def __init__(
        self,
        pipeline,
        server,
        *,
        install: Install | None,
        hub_override: str | None = None,
        uplink_wanted: bool = True,
        announce: Callable[[str], None] = print,
    ) -> None:
        self.pipeline = pipeline
        self.server = server
        self.install = install
        self.hub_override = hub_override
        self.uplink_wanted = uplink_wanted
        self.announce = announce
        self.uplink = None
        self._lock = asyncio.Lock()
        self._joining: str | None = None
        server.control = self

    # -- the uplink

    def start_uplink(self) -> bool:
        """Send to the fleet if linked (and wanted: a replay only with --uplink)."""
        from .uplink import Uplink

        if not self.uplink_wanted or self.uplink is not None:
            return False
        settings = load_settings()
        hub = (self.hub_override or settings.hub_url or "").rstrip("/")
        token = load_token(hub) if hub else None
        if not token:
            return False
        off = sorted(set(SHARE_CATEGORIES) - settings.shared)
        self.announce(
            f"Fleet: sending to {hub}" + (f" (not sharing: {', '.join(off)})" if off else "")
        )

        def status(s: dict) -> None:
            self.pipeline._notify("uplink", s)
            if s.get("state") in ("connected", "rejected"):
                who = f" as {s['member']}" if s.get("member") else ""
                self.announce(f"Fleet: {s['state']}{who}. {s.get('message') or ''}".rstrip())
            update = s.get("update")
            if update and s.get("state") == "connected":
                self.announce(f"Fleet: agent {update['version']} is out: {update['url']}")

        self.uplink = Uplink(
            self.pipeline,
            hub,
            token,
            settings.shared,
            channel=self.install.channel if self.install else None,
            on_status=status,
        )
        self.uplink.start()
        self.server.fleet_open = self.uplink.login_link
        self.server.fleet_view = self.uplink.fleet_view
        return True

    async def stop_uplink(self, *, unlinked: bool = False) -> None:
        if self.uplink is not None:
            await self.uplink.stop()
            self.uplink = None
        self.server.fleet_open = None
        self.server.fleet_view = None
        if unlinked:
            self.pipeline._notify("uplink", {"state": "unlinked", "hub": None, "member": None})

    # -- what the Agent tab shows

    def state(self) -> dict:
        settings = load_settings()
        linked = bool(settings.hub_url and load_token(settings.hub_url))
        found = installs.find_installs()
        return {
            "agent_version": __version__,
            "linked": linked,
            "hub": settings.hub_url if linked else None,
            "org": settings.org if linked else None,
            "member": settings.member_name if linked else None,
            "sending": self.uplink is not None,
            "joining": self._joining,
            "suggested_name": game_handle(self.install.game_log if self.install else None),
            "share": [
                {"id": c, "label": SHARE_LABEL[c], "help": SHARE_HELP[c], "on": settings.share[c]}
                for c in SHARE_CATEGORIES
            ],
            "installs": [
                {
                    "channel": i.channel,
                    "path": str(i.path),
                    "telemetry": gamecfg.status(i.user_cfg).telemetry_enabled,
                    "current": self.install is not None and i.path == self.install.path,
                }
                for i in found
            ],
            "restart_note": switch.RESTART_NOTE,
        }

    # -- changes

    async def set_share(self, changes: dict) -> dict:
        async with self._lock:
            settings = load_settings()
            for c, on in changes.items():
                if c in SHARE_CATEGORIES and isinstance(on, bool):
                    settings.share[c] = on
            save_settings(settings)
            if self.uplink is not None:  # the hub learns the categories from the hello
                await self.stop_uplink()
                self.start_uplink()
        return self.state()

    async def join(self, target: str, name: str) -> dict:
        """An invite link (new account) or a hub address (this PC, an existing account: the
        hub's page opens to confirm a code, and this waits until it's confirmed)."""
        async with self._lock:
            hub, invite = parse_target(target)
            if invite:
                name = name.strip() or self.state()["suggested_name"] or ""
                if not name:
                    raise LinkError("Choose a display name.")
                settings = await join(hub, invite, name)
            else:
                self._joining = hub
                try:
                    settings = await link(hub, open_browser=True, say=self.announce)
                finally:
                    self._joining = None
            await self.stop_uplink()
            self.start_uplink()
            org = f" ({settings.org})" if settings.org else ""
            self.announce(f"Fleet: this PC now sends to {settings.hub_url}{org}.")
        return self.state()

    async def leave(self) -> dict:
        """Stop sending, tell the hub to forget this PC, and forget its key here."""
        async with self._lock:
            settings = load_settings()
            token = load_token(settings.hub_url) if settings.hub_url else None
            await self.stop_uplink(unlinked=True)
            if settings.hub_url and token:
                with contextlib.suppress(aiohttp.ClientError, asyncio.TimeoutError):
                    async with aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as http:
                        await http.post(
                            f"{settings.hub_url}/api/agent/unlink",
                            headers={"Authorization": f"Bearer {token}"},
                        )
            unlink()
            self.announce(f"Fleet: this PC no longer sends to {settings.hub_url}.")
        return self.state()

    def set_telemetry(self, channel: str, on: bool) -> dict:
        found = {i.channel: i for i in installs.find_installs()}
        install = found.get(channel)
        if install is None:
            raise LinkError(f"No {channel} install found.")
        result = switch.switch_on(install) if on else switch.switch_off(install)
        return {**self.state(), "changed": result.cfg.changed}
