"""Agent settings while it runs: the cockpit page's Agent tab (localserver /api/agent/*).

Joins or leaves fleets (a PC can be in several: one per org's hub), switches each on or
off, chooses what's shared with each, and switches the game's telemetry on or off,
without a restart. Owns the hub uplinks, one per fleet that's on: starts them, restarts
one when its sharing changes (the hub learns the categories from the uplink's hello),
stops it on leaving. The same files and functions as the command line (fleetlink, switch), so either
can be used.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable

import aiohttp
from starglance_shared import SHARE_CATEGORIES

from . import __version__, gamecfg, installs, switch
from .fleetlink import (
    Fleet,
    FleetSettings,
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
    """One uplink per fleet that's switched on (a PC can be in several orgs' fleets)."""

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
        self.hub_override = (hub_override or "").rstrip("/") or None
        """`run --hub X`: send only to that fleet."""
        self.uplink_wanted = uplink_wanted
        self.announce = announce
        self.uplinks: dict = {}
        """Hub URL -> its running Uplink."""
        self._lock = asyncio.Lock()
        self._joining: str | None = None
        self.lan = None
        """Show on other devices (lanview.LanView), when the agent serves one."""
        self.updater = None
        """Updating the app in place (selfupdate.Updater)."""
        self.reports = None
        """Problem reports: the recent buffer, marks, the hotkey (report.Reports)."""
        server.control = self
        server.fleet_open = self.login_link
        server.fleet_view = self.fleet_view

    # -- the uplinks

    def start_uplinks(self) -> int:
        """Send to every fleet that's linked and switched on. Returns how many."""
        if not self.uplink_wanted:
            return 0
        for fleet in load_settings().fleets:
            if fleet.enabled and (self.hub_override in (None, fleet.hub_url)):
                self._start(fleet)
        return len(self.uplinks)

    def _start(self, fleet: Fleet) -> bool:
        from .uplink import Uplink

        if not self.uplink_wanted or fleet.hub_url in self.uplinks:
            return False
        token = load_token(fleet.hub_url)
        if not token:
            return False
        off = sorted(set(SHARE_CATEGORIES) - fleet.shared)
        not_shared = f" (not sharing: {', '.join(off)})" if off else ""
        self.announce(f"Fleet {fleet.label}: sending to {fleet.hub_url}{not_shared}")

        def status(s: dict) -> None:
            self.pipeline._notify("uplink", s)
            if s.get("state") in ("connected", "rejected"):
                who = f" as {s['member']}" if s.get("member") else ""
                self.announce(
                    f"Fleet {fleet.label}: {s['state']}{who}. {s.get('message') or ''}".rstrip()
                )
            update = s.get("update")
            if update and s.get("state") == "connected":
                self.announce(
                    f"Fleet {fleet.label}: agent {update['version']} is out: {update['url']}"
                )

        uplink = Uplink(
            self.pipeline,
            fleet.hub_url,
            token,
            fleet.shared,
            channel=self.install.channel if self.install else None,
            on_status=status,
        )
        uplink.status["org"] = fleet.org
        uplink.start()
        self.uplinks[fleet.hub_url] = uplink
        return True

    async def _stop(self, hub_url: str, *, unlinked: bool = False) -> None:
        uplink = self.uplinks.pop(hub_url, None)
        if uplink is not None:
            await uplink.stop()
        if unlinked or uplink is not None:
            # The page drops this fleet's chip (it isn't sending any more).
            self.pipeline._notify("uplink", {"state": "unlinked", "hub": hub_url, "member": None})

    async def stop_uplinks(self) -> None:
        for hub in list(self.uplinks):
            uplink = self.uplinks.pop(hub)
            await uplink.stop()

    # -- the fleet views (localserver /api/fleet/open and /ws/fleet)

    def _uplink(self, hub_url: str | None):
        if hub_url:
            return self.uplinks.get(hub_url.rstrip("/"))
        return next(iter(self.uplinks.values()), None)

    async def login_link(self, hub_url: str | None = None) -> str:
        uplink = self._uplink(hub_url)
        if uplink is None:
            raise LinkError("Not sending to that fleet.")
        return await uplink.login_link()

    def fleet_view(self, hub_url: str | None = None):
        """An async context giving that hub's fleet stream, or None (not in that fleet)."""
        uplink = self._uplink(hub_url)
        return uplink.fleet_view() if uplink is not None else None

    # -- what the Agent tab shows

    def state(self) -> dict:
        settings = load_settings()
        found = installs.find_installs()
        return {
            "agent_version": __version__,
            "fleets": [
                {
                    "hub": f.hub_url,
                    "org": f.org,
                    "label": f.label,
                    "member": f.member_name,
                    "enabled": f.enabled,
                    "linked": bool(load_token(f.hub_url)),
                    "sending": f.hub_url in self.uplinks,
                    "share": [
                        {"id": c, "label": SHARE_LABEL[c], "help": SHARE_HELP[c], "on": f.share[c]}
                        for c in SHARE_CATEGORIES
                    ],
                }
                for f in settings.fleets
            ],
            "can_send": self.uplink_wanted,
            "joining": self._joining,
            "suggested_name": game_handle(self.install.game_log if self.install else None),
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
            "lan": self.lan.state() if self.lan is not None else None,
            "updates": self.updater.status() if self.updater is not None else None,
            "reports": self.reports.status() if self.reports is not None else None,
        }

    # -- problem reports (report.py): made here, attached to a GitHub issue by the player

    def _reports(self):
        if self.reports is None:
            raise LinkError("Problem reports aren't available here.")
        return self.reports

    # -- updates (selfupdate): told by the hubs or GitHub, only official releases

    def update_now(self) -> dict:
        if self.updater is None:
            raise LinkError("Updates aren't available here.")
        if not self.updater.can:
            raise LinkError(
                "Only the Starglance app updates itself: download it from the releases page."
            )
        if not self.updater.available:
            raise LinkError("No newer version: you're up to date.")
        self.updater.start()
        return self.state()

    def set_auto_update(self, on: bool) -> dict:
        if self.updater is None:
            raise LinkError("Updates aren't available here.")
        self.updater.set_auto(on)
        return self.state()

    async def check_updates_now(self) -> dict:
        if self.updater is None:
            raise LinkError("Updates aren't available here.")
        await self.updater.check_now()
        return self.state()

    def set_check_updates(self, on: bool) -> dict:
        if self.updater is None:
            raise LinkError("Updates aren't available here.")
        self.updater.set_check(on)
        return self.state()

    # -- other devices (lanview): view only, on your network

    def _lan(self):
        if self.lan is None:
            raise LinkError("Other devices aren't available here.")
        return self.lan

    async def set_lan(self, on: bool) -> dict:
        await self._lan().set_enabled(on)
        return self.state()

    def lan_code(self, cancel: bool) -> dict:
        lan = self._lan()
        if cancel:
            lan.cancel_code()
        elif not lan.running:
            raise LinkError("Switch on Show on other devices first.")
        else:
            lan.new_code()
        return self.state()

    async def lan_forget(self, device_id: str | None) -> dict:
        await self._lan().forget(device_id)
        return self.state()

    # -- changes

    def _fleet(self, settings: FleetSettings, hub_url: str) -> Fleet:
        fleet = settings.get(hub_url)
        if fleet is None:
            raise LinkError("This PC isn't in that fleet.")
        return fleet

    async def _restart(self, fleet: Fleet) -> None:
        """Sharing or switch changed: the hub learns the categories from the hello."""
        await self._stop(fleet.hub_url)
        if fleet.enabled and self.hub_override in (None, fleet.hub_url):
            self._start(fleet)

    async def set_share(self, hub_url: str, changes: dict) -> dict:
        async with self._lock:
            settings = load_settings()
            fleet = self._fleet(settings, hub_url)
            for c, on in changes.items():
                if c in SHARE_CATEGORIES and isinstance(on, bool):
                    fleet.share[c] = on
            save_settings(settings)
            if fleet.hub_url in self.uplinks:
                await self._restart(fleet)
        return self.state()

    async def set_enabled(self, hub_url: str, on: bool) -> dict:
        """Send to this fleet or not, staying in it."""
        async with self._lock:
            settings = load_settings()
            fleet = self._fleet(settings, hub_url)
            fleet.enabled = on
            save_settings(settings)
            await self._restart(fleet)
            self.announce(f"Fleet {fleet.label}: {'sending' if on else 'paused'}.")
        return self.state()

    async def join(self, target: str, name: str) -> dict:
        """An invite link (new account) or a hub address (this PC, an existing account: the
        hub's page opens to confirm a code, and this waits until it's confirmed). Adds the
        fleet; the others carry on."""
        async with self._lock:
            hub, invite = parse_target(target)
            if invite:
                name = name.strip() or self.state()["suggested_name"] or ""
                if not name:
                    raise LinkError("Choose a display name.")
                fleet = await join(hub, invite, name)
            else:
                self._joining = hub
                try:
                    fleet = await link(hub, open_browser=True, say=self.announce)
                finally:
                    self._joining = None
            await self._restart(fleet)
            self.announce(f"Fleet {fleet.label}: this PC now sends to {fleet.hub_url}.")
        return self.state()

    async def leave(self, hub_url: str) -> dict:
        """Stop sending to a fleet, tell its hub to forget this PC, forget its key here."""
        async with self._lock:
            settings = load_settings()
            fleet = self._fleet(settings, hub_url)
            token = load_token(fleet.hub_url)
            await self._stop(fleet.hub_url, unlinked=True)
            if token:
                with contextlib.suppress(aiohttp.ClientError, asyncio.TimeoutError):
                    async with aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as http:
                        await http.post(
                            f"{fleet.hub_url}/api/agent/unlink",
                            headers={"Authorization": f"Bearer {token}"},
                        )
            unlink(fleet.hub_url)
            self.announce(f"Fleet {fleet.label}: this PC no longer sends to {fleet.hub_url}.")
        return self.state()

    def set_telemetry(self, channel: str, on: bool) -> dict:
        found = {i.channel: i for i in installs.find_installs()}
        install = found.get(channel)
        if install is None:
            raise LinkError(f"No {channel} install found.")
        result = switch.switch_on(install) if on else switch.switch_off(install)
        return {**self.state(), "changed": result.cfg.changed}
