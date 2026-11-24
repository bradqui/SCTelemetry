"""Hub settings from the environment (see deploy/.env.example).

Only what's needed before anyone can sign in lives here. Everything an admin
might change later (the org name, Discord auto-join) is set on the admin page
and stored in the database; the environment only gives defaults.
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
    discord_client_id: str | None = None
    discord_client_secret: str | None = None
    discord_guild_id: str | None = None
    discord_member_role_id: str | None = None
    """With Discord on: only holders of this role (when set) may sign in with Discord, and
    a member who loses it is suspended."""
    discord_api: str = "https://discord.com/api/v10"
    discord_authorize: str = "https://discord.com/oauth2/authorize"

    dev_login: bool = False
    """Sign in by name without anything else (``/auth/dev``). Local testing only; refused
    on an https hub."""

    stale_after_s: float = 10.0
    """In game, an agent sends several times a second: this long silent is "Connection lost"."""
    idle_stale_after_s: float = 40.0
    """Not in game, an agent only sends a heartbeat (every 8 s; 25 s before 0.6.1)."""
    offline_after_s: float = 60.0
    event_retention_days: int = 30

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
            dev_login=_env("HUB_DEV_LOGIN", "0") == "1",
            event_retention_days=int(_env("HUB_EVENT_RETENTION_DAYS", "30") or 30),
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
                "DISCORD_GUILD_ID together; it's off."
            )
        if not self.secure and not self.hub_url.startswith("http://127.0.0.1"):
            out.append(f"HUB_URL is {self.hub_url}: use https for anything but local testing.")
        return out
