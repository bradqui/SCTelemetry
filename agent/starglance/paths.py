"""Where the agent keeps its own files (%LOCALAPPDATA%\\Starglance)."""

from __future__ import annotations

import contextlib
import os
import shutil
import sys
from pathlib import Path

APP_DIR_NAME = "Starglance"
OLD_APP_DIR_NAME = "FleetTelemetry"
"""The folder's name before the project was renamed (2026-11-24): moved over once."""


def data_dir() -> Path:
    """The agent's data folder. ``STARGLANCE_HOME`` overrides it (tests, portable use)."""
    override = os.environ.get("STARGLANCE_HOME")
    if override:
        base = Path(override)
    else:
        local = os.environ.get("LOCALAPPDATA")
        base = Path(local) / APP_DIR_NAME if local else Path.home() / f".{APP_DIR_NAME.lower()}"
        old = base.with_name(OLD_APP_DIR_NAME if local else f".{OLD_APP_DIR_NAME.lower()}")
        if not base.exists() and old.is_dir():
            with contextlib.suppress(OSError):
                shutil.move(str(old), str(base))  # settings, hub link, caches: keep them
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


def web_dist_dir() -> Path:
    """The built web UI: ``STARGLANCE_WEB_DIST``, the PyInstaller bundle, or the repo's web/dist."""
    override = os.environ.get("STARGLANCE_WEB_DIST")
    if override:
        return Path(override)
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle) / "web"
    return Path(__file__).resolve().parents[2] / "web" / "dist"
