from datetime import datetime
from pathlib import Path

import pytest
from fleet_agent import gamecfg
from fleet_agent.gamecfg import ACTION_SETTINGS, TELEMETRY_SETTINGS, CfgState

NOW = datetime(2026, 11, 23, 12, 0, 0)


@pytest.fixture
def cfg(tmp_path: Path) -> Path:
    path = tmp_path / "LIVE" / "user.cfg"
    path.parent.mkdir()
    return path


@pytest.fixture
def state(tmp_path: Path) -> CfgState:
    return CfgState(tmp_path / "state" / "cfg-state.json")


def lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def test_enable_appends_keys_and_keeps_everything_else(cfg, state):
    original = "-- my settings\r\ng_language = english\r\n\r\nr_DisplayInfo = 2\r\n"
    cfg.write_bytes(original.encode())
    change = gamecfg.enable(cfg, state, now=NOW)

    assert change.changed
    raw = cfg.read_bytes()
    assert raw.startswith(original.encode()), "existing lines must be untouched"
    assert b"\n" not in raw.replace(b"\r\n", b""), "CRLF line endings preserved"
    for key, value in TELEMETRY_SETTINGS.items():
        assert f"{key} = {value}" in lines(cfg)
    assert not any(k in raw.decode() for k in ACTION_SETTINGS), "actions stay off by default"


def test_enable_is_idempotent(cfg, state):
    cfg.write_text("g_language = english\n", encoding="utf-8")
    gamecfg.enable(cfg, state, now=NOW)
    once = cfg.read_bytes()
    second = gamecfg.enable(cfg, state, now=NOW)
    assert not second.changed
    assert cfg.read_bytes() == once
    for key in TELEMETRY_SETTINGS:
        assert len(CfgStateless(cfg).find(key)) == 1


def CfgStateless(path: Path) -> gamecfg.CfgFile:
    return gamecfg.CfgFile.read(path)


def test_backup_made_once_before_first_edit(cfg, state):
    cfg.write_text("g_language = english\n", encoding="utf-8")
    change = gamecfg.enable(cfg, state, now=NOW)
    assert change.backup == cfg.with_name("user.cfg.bak-20261123-120000")
    assert change.backup.read_text(encoding="utf-8") == "g_language = english\n"

    gamecfg.disable(cfg, state, now=NOW)
    gamecfg.enable(cfg, state, now=datetime(2026, 12, 1))
    assert len(gamecfg.existing_backups(cfg)) == 1


def test_disable_restores_file_exactly(cfg, state):
    original = b"; comment\r\ng_language = english\r\nsys_maxfps = 144\r\n"
    cfg.write_bytes(original)
    gamecfg.enable(cfg, state, now=NOW)
    gamecfg.disable(cfg, state, now=NOW)
    assert cfg.read_bytes() == original


def test_existing_values_updated_in_place_and_restored(cfg, state):
    original = (
        "grpc.client.server.port=12345\ng_language = english\nGRPC.Client.Server.Enabled = 0\n"
    )
    cfg.write_text(original, encoding="utf-8")
    gamecfg.enable(cfg, state, now=NOW)

    text = lines(cfg)
    assert text[0] == "grpc.client.server.port=50051", "formatting of the user's line kept"
    assert text[2] == "GRPC.Client.Server.Enabled = 1", "keys match case-insensitively"
    assert sum("grpc.client.server.enabled" in line.lower() for line in text) == 1

    gamecfg.disable(cfg, state, now=NOW)
    assert cfg.read_text(encoding="utf-8") == original


def test_duplicate_lines_all_updated(cfg, state):
    cfg.write_text("server.game.telemetry.enabled = 0\nserver.game.telemetry.enabled = 0\n")
    gamecfg.enable(cfg, state, now=NOW)
    assert lines(cfg)[:2] == ["server.game.telemetry.enabled = 1"] * 2
    assert gamecfg.status(cfg).telemetry_enabled


def test_missing_cfg_is_created_and_removed_lines_on_disable(cfg, state):
    assert not cfg.exists()
    change = gamecfg.enable(cfg, state, now=NOW)
    assert change.changed and change.backup is None
    assert gamecfg.status(cfg).telemetry_enabled
    gamecfg.disable(cfg, state, now=NOW)
    assert cfg.read_text() == ""


def test_no_trailing_newline_handled(cfg, state):
    cfg.write_bytes(b"g_language = english")
    gamecfg.enable(cfg, state, now=NOW)
    assert lines(cfg)[0] == "g_language = english"
    assert lines(cfg)[1] == "grpc.client.server.enabled = 1"


def test_bom_preserved(cfg, state):
    cfg.write_bytes(b"\xef\xbb\xbfg_language = english\r\n")
    gamecfg.enable(cfg, state, now=NOW)
    assert cfg.read_bytes().startswith(b"\xef\xbb\xbfg_language = english\r\n")
    gamecfg.disable(cfg, state, now=NOW)
    assert cfg.read_bytes() == b"\xef\xbb\xbfg_language = english\r\n"


def test_actions_on_then_off(cfg, state):
    cfg.write_text("g_language = english\n")
    gamecfg.enable(cfg, state, actions=True, now=NOW)
    assert gamecfg.status(cfg).actions_enabled
    gamecfg.enable(cfg, state, actions=False, now=NOW)
    st = gamecfg.status(cfg)
    assert st.telemetry_enabled and not st.actions_enabled
    assert "trigger.actions" not in cfg.read_text()


def test_disable_without_state_removes_only_our_exact_values(cfg, tmp_path):
    cfg.write_text(
        "g_language = english\n"
        "grpc.client.server.enabled = 1\n"
        "grpc.client.server.port = 6000\n"  # not our value: left alone
        "server.game.telemetry.enabled = 1\n"
    )
    gamecfg.disable(cfg, CfgState(tmp_path / "fresh.json"), now=NOW)
    assert lines(cfg) == ["g_language = english", "grpc.client.server.port = 6000"]


def test_state_survives_reload(cfg, tmp_path):
    cfg.write_text("grpc.client.server.port = 7777\n")
    state_file = tmp_path / "s.json"
    gamecfg.enable(cfg, CfgState(state_file), now=NOW)
    gamecfg.disable(cfg, CfgState(state_file), now=NOW)  # new process, same state file
    assert cfg.read_text() == "grpc.client.server.port = 7777\n"


def test_comments_that_mention_keys_are_not_settings(cfg, state):
    cfg.write_text("-- grpc.client.server.enabled = 0\n")
    gamecfg.enable(cfg, state, now=NOW)
    assert lines(cfg)[0] == "-- grpc.client.server.enabled = 0"
    gamecfg.disable(cfg, state, now=NOW)
    assert cfg.read_text() == "-- grpc.client.server.enabled = 0\n"
