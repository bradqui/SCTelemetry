"""Switch telemetry on/off for a channel: user.cfg keys plus the Windows env var."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import gamecfg, paths, winenv
from .installs import Install

RESTART_NOTE = (
    "Fully quit the RSI Launcher (including from the system tray), then start the game "
    "again. The game only reads these settings at startup."
)


@dataclass
class SwitchResult:
    cfg: gamecfg.CfgChange
    env_changed: bool


def switch_on(
    install: Install, *, actions: bool = False, state_path: Path | None = None
) -> SwitchResult:
    state = gamecfg.CfgState(state_path or paths.cfg_state_file())
    change = gamecfg.enable(install.user_cfg, state, actions=actions)

    env_changed = False
    if winenv.get_user_env() != winenv.ENV_VALUE:
        env_state = state.data.setdefault("env", {})
        env_state.setdefault("original", winenv.get_user_env())
        winenv.set_user_env()
        state.save()
        env_changed = True
    return SwitchResult(change, env_changed)


def switch_off(install: Install, *, state_path: Path | None = None) -> SwitchResult:
    state = gamecfg.CfgState(state_path or paths.cfg_state_file())
    change = gamecfg.disable(install.user_cfg, state)

    # The env var is shared by all channels: only revert it once none are switched on.
    env_changed = False
    env_state = state.data.get("env")
    if env_state is not None and not state.managed_paths():
        original = env_state.get("original")
        if original is None:
            winenv.delete_user_env()
        else:
            winenv.set_user_env(value=original)
        state.data.pop("env", None)
        state.save()
        env_changed = True
    return SwitchResult(change, env_changed)
