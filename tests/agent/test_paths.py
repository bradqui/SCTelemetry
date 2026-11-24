"""The agent's data folder, and moving it over from the name before the rename."""

from starglance import paths


def test_the_old_folder_moves_over_once(tmp_path, monkeypatch):
    monkeypatch.delenv("STARGLANCE_HOME", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    old = tmp_path / "FleetTelemetry"
    old.mkdir()
    (old / "settings.json").write_text('{"fleet": {"hub_url": "https://hub"}}', encoding="utf-8")
    base = paths.data_dir()
    assert base == tmp_path / "Starglance"
    assert (base / "settings.json").read_text(encoding="utf-8").startswith('{"fleet"')
    assert not old.exists()
    # A new folder is never replaced by an old one that turns up later.
    old.mkdir()
    assert paths.data_dir() == base and old.exists()


def test_override(tmp_path, monkeypatch):
    monkeypatch.setenv("STARGLANCE_HOME", str(tmp_path / "x"))
    assert paths.data_dir() == tmp_path / "x"
