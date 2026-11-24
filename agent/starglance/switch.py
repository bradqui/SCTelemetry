"""Switch telemetry on/off for a channel (the ``user.cfg`` setting).

Earlier versions also set the ``GRPC_CLIENT_SERVER_ENABLED`` Windows user
variable, as community notes suggested. The game's log shows it's ignored once
``user.cfg`` sets the same thing, so we no longer set it, and we undo it if an
earlier version did.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import gamecfg, paths, winenv
from .installs import Install

RESTART_NOTE = "Restart the game if it's running. It only reads user.cfg at startup."


@dataclass
class SwitchResult:
    cfg: gamecfg.CfgChange
    env_changed: bool


def switch_on(
    install: Install, *, actions: bool = False, state_path: Path | None = None
) -> SwitchResult:
    state = gamecfg.CfgState(state_path or paths.cfg_state_file())
    change = gamecfg.enable(install.user_cfg, state, actions=actions)
    return SwitchResult(change, _revert_env(state))


def switch_off(install: Install, *, state_path: Path | None = None) -> SwitchResult:
    state = gamecfg.CfgState(state_path or paths.cfg_state_file())
    change = gamecfg.disable(install.user_cfg, state)
    return SwitchResult(change, _revert_env(state))


def _revert_env(state: gamecfg.CfgState) -> bool:
    """Undo the env var if an earlier version of the agent set it."""
    env_state = state.data.get("env")
    if env_state is None:
        return False
    original = env_state.get("original")
    if original is None:
        winenv.delete_user_env()
    else:
        winenv.set_user_env(value=original)
    state.data.pop("env", None)
    state.save()
    return True
