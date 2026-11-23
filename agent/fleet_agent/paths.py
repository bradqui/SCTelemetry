"""Where the agent keeps its own files (%LOCALAPPDATA%\\FleetTelemetry)."""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR_NAME = "FleetTelemetry"


def data_dir() -> Path:
    """The agent's data folder. ``FLEET_TELEMETRY_HOME`` overrides it (tests, portable use)."""
    override = os.environ.get("FLEET_TELEMETRY_HOME")
    if override:
        base = Path(override)
    else:
        local = os.environ.get("LOCALAPPDATA")
        base = Path(local) / APP_DIR_NAME if local else Path.home() / f".{APP_DIR_NAME.lower()}"
    base.mkdir(parents=True, exist_ok=True)
    return base


def logs_dir() -> Path:
    path = data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def protoset_cache_dir() -> Path:
    path = data_dir() / "protosets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cfg_state_file() -> Path:
    return data_dir() / "cfg-state.json"


def settings_file() -> Path:
    return data_dir() / "settings.json"
