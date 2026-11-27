"""Hub settings from the environment (see deploy/.env.example).

Only what's needed before anyone can sign in lives here. Everything an admin
might change later (the org name, the org's Discord app and server, Discord
auto-join) is set on the admin page and stored in the database; the
environment only gives defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


@dataclass
class Config:
    hub_url: str = "http://127.0.0.1:8100"
    """The public address, as members' browsers and agents see it."""
    bind: str = "127.0.0.1"
    """Where the hub listens. 0.0.0.0 inside Docker; publish the port on 127.0.0.1 there."""
    port: int = 8100
    data_dir: Path = Path("data")
    web_dir: Path | None = None
    org_name: str = "Fleet"
    """Shown on the sign-in and join pages. Admins can change it on the page."""

    # Optional: "Sign in with Discord", and members kept in step with a Discord role.
    # Defaults: the org's admins can set (or change) all four on the admin page.
    discord_client_id: str | None = None
    discord_client_secret: str | None = None
    discord_guild_id: str | None = None
    discord_member_role_id: str | None = None
    """With Discord on: only holders of this role (when set) may sign in with Discord, and
    a member who loses it is suspended."""
    discord_api: str = "https://discord.com/api/v10"
    discord_authorize: str = "https://discord.com/oauth2/authorize"

    # Optional: someone else runs this hub for the org (spec decision 28).
    host_name: str | None = None
    """Shown as "Hosted by <name>" on the sign-in and join pages; turns on Admin → Settings
    → Close this org, a request for the host."""
    host_url: str | None = None
    """The host's page about hosted orgs (privacy, terms), linked beside the name."""

    dev_login: bool = False
    """Sign in by name without anything else (``/auth/dev``). Local testing only; refused
    on an https hub."""

    stale_after_s: float = 10.0
    """In game, an agent sends several times a second: this long silent is "Connection lost"."""
    idle_stale_after_s: float = 40.0
    """Not in game, an agent only sends a heartbeat (every 8 s; 25 s before 0.6.1)."""
    offline_after_s: float = 60.0
    event_retention_days: int = 30
    report_retention_days: int = 30
    """Problem reports members sent to the admins (docs/REPORTS.md)."""

    @property
    def secure(self) -> bool:
        return self.hub_url.startswith("https://")

    @property
    def origin(self) -> str:
        parts = urlsplit(self.hub_url)
        return f"{parts.scheme}://{parts.netloc}"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "hub.sqlite3"

    @property
    def discord_ready(self) -> bool:
        return bool(self.discord_client_id and self.discord_client_secret and self.discord_guild_id)

    @property
    def dev_login_on(self) -> bool:
        return self.dev_login and not self.secure

    @property
    def host(self) -> dict | None:
        """Who hosts this hub for the org, for the page: {"name", "url"}, or None."""
        if not self.host_name:
            return None
        url = self.host_url if _web_url(self.host_url) else None
        return {"name": self.host_name, "url": url}

    @classmethod
    def from_env(cls) -> Config:
        web = _env("HUB_WEB_DIR")
        return cls(
            hub_url=(_env("HUB_URL", cls.hub_url) or cls.hub_url).rstrip("/"),
            bind=_env("HUB_BIND", cls.bind) or cls.bind,
            port=int(_env("HUB_PORT", str(cls.port)) or cls.port),
            data_dir=Path(_env("HUB_DATA_DIR", "data") or "data"),
            web_dir=Path(web) if web else None,
            org_name=_env("HUB_ORG_NAME", cls.org_name) or cls.org_name,
            discord_client_id=_env("DISCORD_CLIENT_ID"),
            discord_client_secret=_env("DISCORD_CLIENT_SECRET"),
            discord_guild_id=_env("DISCORD_GUILD_ID"),
            discord_member_role_id=_env("DISCORD_MEMBER_ROLE_ID"),
            host_name=" ".join((_env("HUB_HOST_NAME") or "").split())[:64] or None,
            host_url=_env("HUB_HOST_URL"),
            dev_login=_env("HUB_DEV_LOGIN", "0") == "1",
            event_retention_days=int(_env("HUB_EVENT_RETENTION_DAYS", "30") or 30),
            report_retention_days=int(_env("HUB_REPORT_RETENTION_DAYS", "30") or 30),
        )

    def problems(self) -> list[str]:
        """Settings worth a warning in the startup log."""
        out = []
        if self.dev_login and self.secure:
            out.append("HUB_DEV_LOGIN is ignored on an https hub.")
        if any([self.discord_client_id, self.discord_client_secret, self.discord_guild_id]) and (
            not self.discord_ready
        ):
            out.append(
                "Discord sign-in needs DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET and "
                "DISCORD_GUILD_ID together (or the rest on the admin page)."
            )
        if not self.secure and not self.hub_url.startswith("http://127.0.0.1"):
            out.append(f"HUB_URL is {self.hub_url}: use https for anything but local testing.")
        if self.host_url and not _web_url(self.host_url):
            out.append("HUB_HOST_URL must start with https:// (or http://); it's not shown.")
        if self.host_url and not self.host_name:
            out.append("HUB_HOST_URL is shown only with HUB_HOST_NAME set.")
        return out


def _web_url(url: str | None) -> bool:
    return bool(url) and urlsplit(url).scheme in ("http", "https") and bool(urlsplit(url).netloc)
