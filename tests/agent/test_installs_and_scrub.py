from pathlib import Path

from starglance import installs, scrub


def make_channel(root: Path, channel: str) -> Path:
    exe = root / channel / "Bin64" / "StarCitizen.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"MZ")
    return root / channel


def test_installs_under_finds_known_channels(tmp_path):
    root = tmp_path / "StarCitizen"
    make_channel(root, "LIVE")
    make_channel(root, "HOTFIX")
    (root / "NotAChannel").mkdir()
    found = installs.installs_under(root)
    assert [(i.channel, i.path) for i in found] == [
        ("LIVE", root / "LIVE"),
        ("HOTFIX", root / "HOTFIX"),
    ]
    assert found[0].user_cfg == root / "LIVE" / "user.cfg"


def test_installs_under_accepts_a_channel_folder(tmp_path):
    live = make_channel(tmp_path / "StarCitizen", "PTU")
    assert installs.installs_under(live) == [installs.Install("PTU", live)]


def test_remembered_root(tmp_path, monkeypatch):
    monkeypatch.setenv("STARGLANCE_HOME", str(tmp_path / "home"))
    root = tmp_path / "Games" / "StarCitizen"
    make_channel(root, "LIVE")
    installs.remember_root(root)
    assert installs.remembered_root() == root
    assert installs.Install("LIVE", root / "LIVE") in installs.find_installs()


def test_scrub_uec_nested():
    frame = {
        "actor": {"state": {"uec_balance": 123456, "crew_role": "pilot"}},
        "list": [{"UEC": 1}],
    }
    out = scrub.scrub_uec(frame)
    assert out["actor"]["state"] == {"uec_balance": scrub.SCRUBBED, "crew_role": "pilot"}
    assert out["list"] == [{"UEC": scrub.SCRUBBED}]
    assert frame["actor"]["state"]["uec_balance"] == 123456, "input not modified"
