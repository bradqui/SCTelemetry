"""The per-user Windows environment variable the game checks at startup (spec §2.2).

Written to ``HKCU\\Environment``; then ``WM_SETTINGCHANGE`` is broadcast so newly
started programs (the RSI Launcher) see it. Already-running programs don't, which
is why the user must fully quit the launcher.
"""

from __future__ import annotations

import sys

ENV_NAME = "GRPC_CLIENT_SERVER_ENABLED"
ENV_VALUE = "true"

_IS_WINDOWS = sys.platform == "win32"


def get_user_env(name: str = ENV_NAME) -> str | None:
    if not _IS_WINDOWS:
        return None
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _type = winreg.QueryValueEx(key, name)
            return str(value)
    except FileNotFoundError:
        return None


def set_user_env(name: str = ENV_NAME, value: str = ENV_VALUE) -> None:
    _require_windows()
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
    broadcast_env_change()


def delete_user_env(name: str = ENV_NAME) -> None:
    _require_windows()
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, name)
    except FileNotFoundError:
        return
    broadcast_env_change()


def broadcast_env_change() -> None:
    """Tell running programs (Explorer, launchers) that the environment changed."""
    if not _IS_WINDOWS:
        return
    import ctypes
    from ctypes import wintypes

    HWND_BROADCAST = 0xFFFF
    WM_SETTINGCHANGE = 0x001A
    SMTO_ABORTIFHUNG = 0x0002
    result = wintypes.DWORD()
    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST,
        WM_SETTINGCHANGE,
        0,
        "Environment",
        SMTO_ABORTIFHUNG,
        5000,
        ctypes.byref(result),
    )


def _require_windows() -> None:
    if not _IS_WINDOWS:
        raise OSError("The game's environment variable can only be set on Windows.")
