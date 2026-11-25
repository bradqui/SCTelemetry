"""A global hotkey that marks a moment for a problem report, from inside the game.

Windows' RegisterHotKey on a thread of its own with a message loop: the key works
whichever window has focus. Off by default, and one of a few presets, since a hotkey
takes the key away from every other program (the game included) while it's on. If
another program already has it, registering fails and the page says so.
"""

from __future__ import annotations

import logging
import sys
import threading
from collections.abc import Callable

log = logging.getLogger(__name__)

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x4000
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012

PRESETS: dict[str, tuple[str, int, int]] = {
    "ctrl+alt+m": ("Ctrl+Alt+M", MOD_CONTROL | MOD_ALT, ord("M")),
    "ctrl+shift+f12": ("Ctrl+Shift+F12", MOD_CONTROL | MOD_SHIFT, 0x7B),
    "ctrl+alt+f9": ("Ctrl+Alt+F9", MOD_CONTROL | MOD_ALT, 0x78),
}


def label(key: str | None) -> str | None:
    return PRESETS[key][0] if key in PRESETS else None


class Hotkey:
    def __init__(self, on_press: Callable[[], None]) -> None:
        self.on_press = on_press
        self.key: str | None = None
        self.error: str | None = None
        self._thread: threading.Thread | None = None
        self._tid: int | None = None

    def set(self, key: str | None) -> str | None:
        """Use this preset (None: none). Returns why it couldn't be registered, if so."""
        self.stop()
        self.key, self.error = None, None
        if key is None:
            return None
        if key not in PRESETS:
            self.error = "Unknown key."
            return self.error
        if sys.platform != "win32":
            self.error = "Only on Windows."
            return self.error
        ready = threading.Event()
        result: dict = {}
        self._thread = threading.Thread(
            target=self._run, args=(key, ready, result), name="hotkey", daemon=True
        )
        self._thread.start()
        ready.wait(5)
        if not result.get("ok"):
            self.error = result.get("error") or "Couldn't register the key."
            self._thread.join(timeout=1)
            self._thread = None
            return self.error
        self.key = key
        return None

    def stop(self) -> None:
        if self._thread is None:
            return
        if self._tid is not None:
            import ctypes

            ctypes.windll.user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
        self._thread.join(timeout=2)
        self._thread = None
        self._tid = None
        self.key = None

    def _run(self, key: str, ready: threading.Event, result: dict) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        name, mods, vk = PRESETS[key]
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # make this thread's queue
        self._tid = ctypes.windll.kernel32.GetCurrentThreadId()
        if not user32.RegisterHotKey(None, 1, mods | MOD_NOREPEAT, vk):
            result["error"] = f"{name} is already used by another program. Pick another."
            ready.set()
            return
        result["ok"] = True
        ready.set()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    try:
                        self.on_press()
                    except Exception:
                        log.exception("Hotkey handler failed")
        finally:
            user32.UnregisterHotKey(None, 1)


def chime() -> None:
    """A short sound: marked (you're in the game, not looking at the page)."""
    if sys.platform == "win32":
        import winsound

        winsound.MessageBeep(winsound.MB_ICONASTERISK)
