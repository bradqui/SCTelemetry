"""Find Star Citizen installs and their channels (LIVE, PTU, ...)."""

from __future__ import annotations

import json
import os
import string
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from . import paths

CHANNELS = ("LIVE", "PTU", "EPTU", "TECH-PREVIEW", "HOTFIX")

# Relative to a drive root. The launcher's default is the first one.
_COMMON_ROOTS = (
    r"Program Files\Roberts Space Industries\StarCitizen",
    r"Roberts Space Industries\StarCitizen",
    r"Games\Roberts Space Industries\StarCitizen",
    r"Program Files (x86)\Roberts Space Industries\StarCitizen",
    r"StarCitizen",
)


@dataclass(frozen=True)
class Install:
    channel: str
    path: Path

    @property
    def exe(self) -> Path:
        return self.path / "Bin64" / "StarCitizen.exe"

    @property
    def user_cfg(self) -> Path:
        return self.path / "user.cfg"


def is_channel_dir(path: Path) -> bool:
    return (path / "Bin64" / "StarCitizen.exe").is_file() or (path / "Data.p4k").is_file()


def installs_under(root: Path) -> list[Install]:
    """Channels inside a ``...\\StarCitizen`` folder, or ``root`` itself if it is a channel."""
    found = []
    if is_channel_dir(root):
        found.append(Install(root.name.upper(), root))
        return found
    for channel in CHANNELS:
        candidate = root / channel
        if is_channel_dir(candidate):
            found.append(Install(channel, candidate))
    return found


def _drive_roots() -> list[Path]:
    if os.name != "nt":
        return []
    return [
        Path(f"{letter}:\\") for letter in string.ascii_uppercase if Path(f"{letter}:\\").exists()
    ]


def candidate_roots(extra: Iterable[Path] = ()) -> list[Path]:
    roots: list[Path] = [*extra]
    remembered = remembered_root()
    if remembered:
        roots.insert(0, remembered)
    for drive in _drive_roots():
        roots.extend(drive / rel for rel in _COMMON_ROOTS)
    return roots


def find_installs(extra_roots: Iterable[Path] = ()) -> list[Install]:
    seen: set[str] = set()
    result = []
    for root in candidate_roots(extra_roots):
        try:
            for inst in installs_under(root):
                key = str(inst.path.resolve()).lower()
                if key not in seen:
                    seen.add(key)
                    result.append(inst)
        except OSError:
            continue
    return result


# ---------------------------------------------------------------- remembered path


def remembered_root() -> Path | None:
    try:
        data = json.loads(paths.settings_file().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    value = data.get("install_root")
    return Path(value) if value else None


def remember_root(root: Path) -> None:
    file = paths.settings_file()
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    data["install_root"] = str(root)
    file.write_text(json.dumps(data, indent=2), encoding="utf-8")
