"""Hub settings, all from the environment (see deploy/.env.example)."""

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
    """The public address, as members' browsers see it (https://fleet.example in production)."""
    bind: str = "127.0.0.1"
    """Where the hub listens. 0.0.0.0 inside Docker; the compose file publishes on 127.0.0.1."""
    port: int = 8100
    internal_port: int = 8101
    """The bot-only API. Never proxied by Apache."""
    data_dir: Path = Path("data")
    web_dir: Path | None = None

    discord_client_id: str | None = None
    discord_client_secret: str | None = None
    discord_guild_id: str | None = None
    discord_member_role_id: str | None = None
    """Org member role. When unset, any member of the Discord server may sign in."""
    discord_api: str = "https://discord.com/api/v10"
    discord_authorize: str = "https://discord.com/oauth2/authorize"

    internal_secret: str | None = None
    """Shared with the ButlerBot cog: required on every internal API call."""

    dev_login: bool = False
    """Sign in without Discord (``/auth/dev``). For local testing only; refused on https."""

    stale_after_s: float = 10.0
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

    @classmethod
    def from_env(cls) -> Config:
        web = _env("HUB_WEB_DIR")
        cfg = cls(
            hub_url=(_env("HUB_URL", cls.hub_url) or cls.hub_url).rstrip("/"),
            bind=_env("HUB_BIND", cls.bind) or cls.bind,
            port=int(_env("HUB_PORT", str(cls.port)) or cls.port),
            internal_port=int(_env("HUB_INTERNAL_PORT", str(cls.internal_port)) or 0),
            data_dir=Path(_env("HUB_DATA_DIR", "data") or "data"),
            web_dir=Path(web) if web else None,
            discord_client_id=_env("DISCORD_CLIENT_ID"),
            discord_client_secret=_env("DISCORD_CLIENT_SECRET"),
            discord_guild_id=_env("DISCORD_GUILD_ID"),
            discord_member_role_id=_env("DISCORD_MEMBER_ROLE_ID"),
            internal_secret=_env("HUB_INTERNAL_SECRET"),
            dev_login=_env("HUB_DEV_LOGIN", "0") == "1",
        )
        return cfg

    def problems(self) -> list[str]:
        """Settings that stop the hub working as intended, for the startup log."""
        out = []
        if not self.discord_ready and not self.dev_login:
            out.append(
                "Discord sign-in isn't configured (DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, "
                "DISCORD_GUILD_ID): nobody can sign in."
            )
        if self.dev_login and self.secure:
            out.append("HUB_DEV_LOGIN is ignored on an https hub.")
        if not self.internal_secret:
            out.append("HUB_INTERNAL_SECRET is unset: the internal API refuses every call.")
        return out
