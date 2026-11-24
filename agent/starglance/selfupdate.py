"""Updating the Windows app in place: one click on Update, or by itself (spec decision 22).

The hub says which agent version is current (``uplink.update_notice``). Updating to it:

1. downloads that version's ``starglance.exe`` and ``SHA256SUMS.txt`` from this project's
   GitHub release. The address is fixed here, built from the version number: never one a
   hub names, so a hub can't hand out software. It's only ever a newer official release;
2. checks the checksum, and, when this exe is signed, that the new one is signed by the
   same publisher (Windows' Authenticode check). A broken signature is always refused;
3. renames the running exe to ``<name>.old.exe`` (Windows allows renaming a running exe),
   puts the new one in its place under the same name, starts it and quits. The new one
   waits for the old to let go of the port, then deletes the old file. Start with Windows
   points at the same path, so it carries on.

Only in the packaged app (``starglance.exe``); from source, Update opens the releases page.
Automatic updates are off unless switched on, and then only happen while the game isn't
running. Nothing here asks GitHub whether there's an update: only the hub says so.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import aiohttp
from starglance_shared import RELEASES_URL, version_tuple

from . import __version__, paths

log = logging.getLogger(__name__)

DOWNLOAD = "https://github.com/bradqui/starglance/releases/download/v{version}/{name}"
EXE_NAME = "starglance.exe"
SUMS_NAME = "SHA256SUMS.txt"
AUTO_EVERY_S = 60
_VERSION = re.compile(r"\d{1,4}\.\d{1,4}\.\d{1,4}")
_NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW: no console flashing up from the windowed app


class UpdateError(Exception):
    pass


def settings_file() -> Path:
    return paths.data_dir() / "updates.json"


def _load() -> dict:
    try:
        data = json.loads(settings_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(**changes) -> None:
    settings_file().write_text(json.dumps({**_load(), **changes}, indent=2), encoding="utf-8")


def load_auto() -> bool:
    return bool(_load().get("auto", False))


def save_auto(on: bool) -> None:
    _save(auto=on)


def download_url(version: str, name: str) -> str:
    """The official release's file: only a plain version number goes in the address."""
    if not _VERSION.fullmatch(version or ""):
        raise UpdateError(f"Not a version number: {version!r}")
    return DOWNLOAD.format(version=version, name=name)


def expected_sum(sums: str, name: str = EXE_NAME) -> str:
    """``SHA256SUMS.txt`` (``<hash>  <file>`` per line) -> that file's hash."""
    for line in sums.splitlines():
        parts = line.strip().split()
        if (
            len(parts) == 2
            and parts[1].lstrip("*") == name
            and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0])
        ):
            return parts[0].lower()
    raise UpdateError(f"The release's checksums don't list {name}.")


def authenticode(path: Path) -> tuple[str, str | None]:
    """Windows' verdict on a file's signature: (status, signer), e.g. ("Valid", "CN=...") or
    ("NotSigned", None)."""
    script = (
        "$s = Get-AuthenticodeSignature -LiteralPath $env:SG_FILE; "
        "[Console]::Out.Write($s.Status.ToString() + '|' + $s.SignerCertificate.Subject)"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            env={**os.environ, "SG_FILE": str(path)},
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=_NO_WINDOW if sys.platform == "win32" else 0,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise UpdateError(f"Couldn't check the signature: {exc}") from exc
    status, _, subject = out.partition("|")
    return status.strip() or "Unknown", subject.strip() or None


def check_signature(new: Path, current: Path, *, verdict=authenticode) -> None:
    """A signed app only accepts an update signed by the same publisher; before signing,
    an unsigned one. A signature that's there but broken is always refused."""
    mine, my_signer = verdict(current)
    theirs, their_signer = verdict(new)
    if mine == "Valid":
        if theirs != "Valid" or their_signer != my_signer:
            raise UpdateError(
                f"The download isn't signed by Starglance's publisher ({theirs}): not installed."
            )
    elif theirs not in ("Valid", "NotSigned"):
        raise UpdateError(f"The download's signature is broken ({theirs}): not installed.")


def old_path(exe: Path) -> Path:
    return exe.with_name(f"{exe.stem}.old{exe.suffix}")


def install(new: Path, exe: Path) -> Path:
    """Swap the running exe for the new one (same name). Returns where the old one went."""
    old = old_path(exe)
    with contextlib.suppress(FileNotFoundError):
        old.unlink()
    os.replace(exe, old)
    try:
        os.replace(new, exe)
    except OSError:
        os.replace(old, exe)  # put it back
        raise
    return old


def remove_old(exe: Path, *, tries: int = 30, wait_s: float = 2.0) -> bool:
    """After an update: delete the previous exe once its process has let go of it."""
    import time

    old = old_path(exe)
    for _ in range(tries):
        try:
            old.unlink()
            return True
        except FileNotFoundError:
            return True
        except OSError:
            time.sleep(wait_s)
    return False


def game_running() -> bool:
    """Is Star Citizen running? (Automatic updates wait until it isn't.)"""
    if sys.platform != "win32":
        return False
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq StarCitizen.exe", "/NH"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=_NO_WINDOW,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return True  # can't tell: don't restart under someone's game
    return "starcitizen.exe" in out.lower()


class Updater:
    """The agent's updates: what's available (from the hubs), and installing it."""

    def __init__(
        self,
        pipeline,
        *,
        announce: Callable[[str], None] = print,
        exe: Path | None = None,
        verdict=authenticode,
        is_game_running: Callable[[], bool] = game_running,
    ) -> None:
        self.pipeline = pipeline
        self.announce = announce
        self.exe = exe or (Path(sys.executable) if getattr(sys, "frozen", False) else None)
        """The exe to replace; None from source (Update opens the releases page)."""
        self.verdict = verdict
        self.is_game_running = is_game_running
        self.relaunch: Callable[[], None] | None = None
        """Set by the Windows app: start the new exe and quit. Without it, no updating here."""
        self.available: str | None = None
        self.state = "idle"
        """idle | downloading | checking | installing | error"""
        self.progress: float | None = None
        self.error: str | None = None
        self.auto = load_auto()
        self.tried = _load().get("installed")
        """The last version installed by updating: automatic mode never installs it twice
        (a release whose exe still says the old version would otherwise loop)."""
        self._task: asyncio.Task | None = None
        pipeline.subscribe(self._on)

    # -- what's available

    def _on(self, kind: str, payload: object) -> None:
        if kind != "uplink" or not isinstance(payload, dict):
            return
        update = payload.get("update")
        version = update.get("version") if isinstance(update, dict) else None
        if not isinstance(version, str) or not _VERSION.fullmatch(version):
            return
        if version_tuple(version) <= (version_tuple(__version__) or (0,)):
            return
        if self.available is None or version_tuple(version) > version_tuple(self.available):
            self.available = version
            self._notify()

    @property
    def can(self) -> bool:
        return self.exe is not None and self.relaunch is not None

    def status(self) -> dict:
        return {
            "current": __version__,
            "available": self.available,
            "can": self.can,
            "state": self.state,
            "progress": self.progress,
            "error": self.error,
            "auto": self.auto,
            "releases": RELEASES_URL,
        }

    def _notify(self) -> None:
        self.pipeline._notify("updater", self.status())

    def _set(self, state: str, *, progress: float | None = None, error: str | None = None) -> None:
        self.state, self.progress, self.error = state, progress, error
        self._notify()

    # -- settings

    def set_auto(self, on: bool) -> None:
        self.auto = on
        save_auto(on)
        self._notify()

    # -- updating

    def start(self) -> bool:
        """Update now, in the background. False: nothing to do, or already at it."""
        if (
            not self.can
            or not self.available
            or self.state in ("downloading", "checking", "installing")
        ):
            return False
        self._set("downloading", progress=0.0)  # at once: the page's button shows it
        self._task = asyncio.get_running_loop().create_task(self.update(self.available))
        return True

    async def update(self, version: str) -> None:
        assert self.exe is not None
        new = self.exe.with_name(f"{self.exe.stem}.new{self.exe.suffix}")
        try:
            self._set("downloading", progress=0.0)
            await self._download(version, new)
            self._set("checking")
            await asyncio.to_thread(check_signature, new, self.exe, verdict=self.verdict)
            self._set("installing")
            try:
                install(new, self.exe)
            except PermissionError as exc:
                raise UpdateError(
                    f"Can't replace {self.exe.name} in {self.exe.parent}: Windows won't let "
                    "Starglance write there. Move it to a folder of your own (Documents, say) "
                    "and update again, or download it from the releases page."
                ) from exc
            self.tried = version
            _save(installed=version)
            self.announce(f"Updated to {version}: restarting.")
            if self.relaunch is not None:
                self.relaunch()
        except (TimeoutError, UpdateError, aiohttp.ClientError, OSError) as exc:
            with contextlib.suppress(OSError):
                new.unlink()
            message = str(exc) or exc.__class__.__name__
            if isinstance(exc, (aiohttp.ClientError, asyncio.TimeoutError)):
                message = f"Couldn't download {version} from GitHub ({message})."
            log.warning("Update to %s failed: %s", version, message)
            self._set("error", error=message)

    async def _download(self, version: str, dest: Path) -> None:
        timeout = aiohttp.ClientTimeout(total=600, sock_read=60)
        async with aiohttp.ClientSession(timeout=timeout) as http:
            async with http.get(download_url(version, SUMS_NAME)) as r:
                r.raise_for_status()
                want = expected_sum(await r.text())
            digest = hashlib.sha256()
            async with http.get(download_url(version, EXE_NAME)) as r:
                r.raise_for_status()
                total = r.content_length or 0
                done = 0
                with dest.open("wb") as f:
                    async for chunk in r.content.iter_chunked(1 << 16):
                        f.write(chunk)
                        digest.update(chunk)
                        done += len(chunk)
                        if total:
                            p = round(done / total, 2)
                            if p != self.progress:
                                self.progress = p
                                self._notify()
        if digest.hexdigest() != want:
            raise UpdateError("The download doesn't match the release's checksum: not installed.")

    async def auto_loop(self) -> None:
        """Switched on: update when one's available and the game isn't running."""
        while True:
            await asyncio.sleep(AUTO_EVERY_S)
            # After a failure ("error") it waits for a click or a restart: no retry loop.
            if not (self.auto and self.can and self.available and self.state == "idle"):
                continue
            if self.available == self.tried:
                continue  # installed once already and still offered: not again by itself
            if await asyncio.to_thread(self.is_game_running):
                continue
            self.announce(f"Updating to {self.available} by itself (the game isn't running).")
            self.start()
