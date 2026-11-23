"""Switch the game's local telemetry server on and off in a channel's ``user.cfg``.

Rules (spec §2.2):
- Back up ``user.cfg`` before our first edit (``user.cfg.bak-<timestamp>``).
- Idempotent: update our keys in place, never duplicate them, and leave every
  other line (settings, comments, blank lines, line endings, BOM) untouched.
- "Switch off" puts each of our keys back the way it was: removed if we added
  it, or its earlier value restored if the user already had it.

What each key looked like before we touched it is remembered in a small JSON
state file in the agent's data folder, keyed by the cfg path.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

TELEMETRY_SETTINGS: dict[str, str] = {
    "grpc.client.server.enabled": "1",
    "grpc.client.server.port": "50051",
    "server.game.telemetry.enabled": "1",
}
"""Turns on the local gRPC server and the telemetry stream."""

ACTION_SETTINGS: dict[str, str] = {
    "server.game.telemetry.trigger.actions.enabled": "1",
}
"""Game actions (button box, spec §7). Later phase; off unless asked for."""

MANAGED_KEYS = (*TELEMETRY_SETTINGS, *ACTION_SETTINGS)

BACKUP_PREFIX = "user.cfg.bak-"

# `key = value`. Keys start with a letter, so comment lines (`--`, `;`, `//`, `#`)
# and blank lines never match and are kept verbatim.
_SETTING = re.compile(
    r"^(?P<lead>\s*)(?P<key>[A-Za-z_][A-Za-z0-9_.]*)(?P<sep>\s*=\s*)(?P<value>.*?)(?P<trail>\s*)$"
)


class CfgWriteError(RuntimeError):
    """user.cfg couldn't be written (usually permissions)."""


# ---------------------------------------------------------------- file model


@dataclass
class CfgFile:
    lines: list[str] = field(default_factory=list)
    newline: str = "\r\n"
    bom: bool = False
    trailing_newline: bool = True

    @classmethod
    def parse(cls, raw: bytes) -> CfgFile:
        bom = raw.startswith(b"\xef\xbb\xbf")
        text = (
            raw[3:].decode("utf-8", errors="surrogateescape")
            if bom
            else raw.decode("utf-8", errors="surrogateescape")
        )
        if not text:
            return cls(bom=bom)
        newline = "\r\n" if "\r\n" in text else "\n"
        trailing = text.endswith(("\n", "\r"))
        lines = text.splitlines()
        return cls(lines=lines, newline=newline, bom=bom, trailing_newline=trailing)

    @classmethod
    def read(cls, path: Path) -> CfgFile:
        if not path.exists():
            return cls()
        return cls.parse(path.read_bytes())

    def render(self) -> bytes:
        text = self.newline.join(self.lines)
        if self.lines and self.trailing_newline:
            text += self.newline
        body = text.encode("utf-8", errors="surrogateescape")
        return (b"\xef\xbb\xbf" + body) if self.bom else body

    # -- settings

    def find(self, key: str) -> list[int]:
        """Line indexes that set ``key`` (case-insensitive, like the game's cvars)."""
        wanted = key.lower()
        hits = []
        for i, line in enumerate(self.lines):
            m = _SETTING.match(line)
            if m and m.group("key").lower() == wanted:
                hits.append(i)
        return hits

    def get(self, key: str) -> str | None:
        """The effective value: the last line that sets ``key`` wins."""
        hits = self.find(key)
        if not hits:
            return None
        m = _SETTING.match(self.lines[hits[-1]])
        assert m
        return m.group("value")

    def set(self, key: str, value: str) -> None:
        """Update every line that sets ``key`` (keeps its formatting), or append one."""
        hits = self.find(key)
        if not hits:
            self.trailing_newline = True
            self.lines.append(f"{key} = {value}")
            return
        for i in hits:
            m = _SETTING.match(self.lines[i])
            assert m
            self.lines[i] = f"{m['lead']}{m['key']}{m['sep']}{value}{m['trail']}"

    def remove(self, key: str, only_value: str | None = None) -> None:
        """Delete lines that set ``key`` (only those with ``only_value``, if given)."""
        keep = []
        for line in self.lines:
            m = _SETTING.match(line)
            if (
                m
                and m.group("key").lower() == key.lower()
                and (only_value is None or m.group("value") == only_value)
            ):
                continue
            keep.append(line)
        self.lines = keep


# ---------------------------------------------------------------- state file


class CfgState:
    """What our keys looked like before we touched them, per cfg file."""

    def __init__(self, path: Path):
        self.path = path
        try:
            self.data = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            self.data = {}
        self.data.setdefault("cfg", {})

    @staticmethod
    def _key(cfg_path: Path) -> str:
        return str(cfg_path.resolve()).lower()

    def originals(self, cfg_path: Path) -> dict[str, str | None] | None:
        entry = self.data["cfg"].get(self._key(cfg_path))
        return None if entry is None else entry.setdefault("originals", {})

    def remember(self, cfg_path: Path, key: str, original: str | None) -> None:
        entry = self.data["cfg"].setdefault(self._key(cfg_path), {"originals": {}})
        entry["originals"].setdefault(key, original)

    def forget(self, cfg_path: Path) -> None:
        self.data["cfg"].pop(self._key(cfg_path), None)

    def forget_key(self, cfg_path: Path, key: str) -> None:
        originals = self.originals(cfg_path)
        if originals is not None:
            originals.pop(key, None)

    def managed_paths(self) -> list[str]:
        return list(self.data["cfg"])

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- operations


@dataclass
class CfgStatus:
    path: Path
    exists: bool
    telemetry_enabled: bool
    actions_enabled: bool
    values: dict[str, str | None]


@dataclass
class CfgChange:
    path: Path
    changed: bool
    backup: Path | None = None


def status(cfg_path: Path) -> CfgStatus:
    cfg = CfgFile.read(cfg_path)
    values = {k: cfg.get(k) for k in MANAGED_KEYS}
    return CfgStatus(
        path=cfg_path,
        exists=cfg_path.exists(),
        telemetry_enabled=all(values[k] == v for k, v in TELEMETRY_SETTINGS.items()),
        actions_enabled=all(values[k] == v for k, v in ACTION_SETTINGS.items()),
        values=values,
    )


def enable(
    cfg_path: Path, state: CfgState, *, actions: bool = False, now: datetime | None = None
) -> CfgChange:
    """Turn telemetry on (and game actions only if ``actions``). Safe to repeat."""
    cfg = CfgFile.read(cfg_path)
    before = cfg.render() if cfg_path.exists() else None

    desired = dict(TELEMETRY_SETTINGS)
    if actions:
        desired.update(ACTION_SETTINGS)

    for key, value in desired.items():
        state.remember(cfg_path, key, cfg.get(key))
        cfg.set(key, value)

    if not actions:
        # Actions were switched on by us earlier: put that key back.
        originals = state.originals(cfg_path) or {}
        for key in ACTION_SETTINGS:
            if key in originals:
                _restore(cfg, key, originals[key])
                state.forget_key(cfg_path, key)

    change = _write_if_changed(cfg_path, cfg, before, now)
    state.save()
    return change


def disable(cfg_path: Path, state: CfgState, *, now: datetime | None = None) -> CfgChange:
    """Put our keys back the way they were before we first switched telemetry on."""
    if not cfg_path.exists():
        state.forget(cfg_path)
        state.save()
        return CfgChange(cfg_path, changed=False)

    cfg = CfgFile.read(cfg_path)
    before = cfg.render()
    originals = state.originals(cfg_path)

    if originals is None:
        # No record (state lost, or set by hand): remove only lines holding exactly our values.
        for key, value in {**TELEMETRY_SETTINGS, **ACTION_SETTINGS}.items():
            cfg.remove(key, only_value=value)
    else:
        for key, original in originals.items():
            _restore(cfg, key, original)

    change = _write_if_changed(cfg_path, cfg, before, now)
    state.forget(cfg_path)
    state.save()
    return change


def _restore(cfg: CfgFile, key: str, original: str | None) -> None:
    if original is None:
        cfg.remove(key)
    else:
        cfg.set(key, original)


def existing_backups(cfg_path: Path) -> list[Path]:
    return sorted(cfg_path.parent.glob(BACKUP_PREFIX + "*"))


def _write_if_changed(
    cfg_path: Path, cfg: CfgFile, before: bytes | None, now: datetime | None
) -> CfgChange:
    after = cfg.render()
    if after == before:
        return CfgChange(cfg_path, changed=False)

    backup = None
    if before is not None and not existing_backups(cfg_path):
        stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
        backup = cfg_path.with_name(BACKUP_PREFIX + stamp)
        try:
            backup.write_bytes(before)
        except OSError as exc:
            raise CfgWriteError(f"Couldn't back up {cfg_path}: {exc}") from exc

    _atomic_write(cfg_path, after)
    return CfgChange(cfg_path, changed=True, backup=backup)


def _atomic_write(path: Path, data: bytes) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".user.cfg.", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
    except OSError as exc:
        raise CfgWriteError(
            f"Couldn't write {path}: {exc}. If the game is installed under Program Files, "
            "check that your Windows user can modify that folder."
        ) from exc
