"""Problem reports: the recent buffer, marks, cleaning, and the report file (docs/REPORTS.md)."""

from __future__ import annotations

import asyncio
import gzip
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from starglance import report as report_mod
from starglance.capturefile import read_frames, read_records
from starglance.recent import KEEP_MS, MARK_KEEP_MS, RecentBuffer
from starglance.redact import Redactor, players_in
from starglance.replay import DEFAULT_PROTOSET, FIXTURES_DIR, Recording
from starglance.report import Reports, utc_stamp
from starglance.runtime import Pipeline

T0 = 1_790_000_000_000 - 1_790_000_000_000 % 60_000  # on a minute


class Clock:
    def __init__(self, t: int = T0) -> None:
        self.t = t

    def __call__(self) -> int:
        return self.t


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("STARGLANCE_HOME", str(tmp_path / "home"))
    return tmp_path


def buffer(tmp_path: Path, clock: Clock) -> RecentBuffer:
    return RecentBuffer(tmp_path / "recent", clock=clock)


# ---------------------------------------------------------------- the rolling buffer


def test_records_come_back_in_their_window(tmp_path):
    clock = Clock()
    b = buffer(tmp_path, clock)
    for i in range(0, 180):  # three minutes, one record a second
        clock.t = T0 + i * 1000
        b.record({"frame": {"i": i}}, clock.t)
    assert len(list((tmp_path / "recent").glob("*.jsonl.gz"))) == 3
    got = b.read(T0 + 30_000, T0 + 90_000)
    assert [r["frame"]["i"] for r in got] == list(range(30, 91))


def test_a_file_cut_off_by_a_crash_still_reads(tmp_path):
    clock = Clock()
    b = buffer(tmp_path, clock)
    for i in range(20):
        b.record({"frame": {"i": i}}, T0 + i * 1000)
    b.flush()  # never closed: no gzip trailer, as after a crash
    path = next((tmp_path / "recent").glob("*.jsonl.gz"))
    data = path.read_bytes()
    path.write_bytes(data + b"\x00garbage")
    fresh = buffer(tmp_path, clock)
    assert [r["frame"]["i"] for r in fresh.read(T0, T0 + 60_000)] == list(range(20))


def test_older_than_30_minutes_is_deleted(tmp_path):
    clock = Clock()
    b = buffer(tmp_path, clock)
    b.record({"frame": {}}, T0)
    for minute in range(1, 40):
        clock.t = T0 + minute * 60_000
        b.record({"frame": {}}, clock.t)
    starts = sorted(int(p.name.split("-")[0]) for p in (tmp_path / "recent").glob("*.jsonl.gz"))
    assert starts[0] >= clock.t - KEEP_MS - 60_000
    assert starts[-1] == clock.t


def test_a_mark_keeps_its_ten_minutes_for_a_day(tmp_path):
    clock = Clock()
    b = buffer(tmp_path, clock)
    for minute in range(0, 20):
        clock.t = T0 + minute * 60_000
        b.record({"frame": {"m": minute}}, clock.t)
    b.mark("hotkey", T0 + 15 * 60_000)
    for minute in range(20, 120):  # well past 30 minutes
        clock.t = T0 + minute * 60_000
        b.record({"frame": {"m": minute}}, clock.t)
    kept = {r["frame"]["m"] for r in b.read(T0, T0 + 20 * 60_000) if "frame" in r}
    assert kept == set(range(7, 17))  # the minutes from 8 before the mark to 2 after
    clock.t = T0 + 15 * 60_000 + MARK_KEEP_MS + 1
    b.prune()
    assert b.marks == []
    assert not [r for r in b.read(T0, T0 + 20 * 60_000) if "frame" in r]


def test_marks_survive_a_restart_and_can_be_forgotten(tmp_path):
    clock = Clock()
    b = buffer(tmp_path, clock)
    m = b.mark("app")
    assert m is not None
    again = buffer(tmp_path, clock)
    assert [x.id for x in again.marks] == [m.id]
    again.forget_mark(m.id)
    assert buffer(tmp_path, clock).marks == []


def test_switching_it_off_deletes_everything(tmp_path):
    clock = Clock()
    b = buffer(tmp_path, clock)
    b.record({"frame": {}}, T0)
    b.mark("app")
    b.set_keep(False)
    assert not (tmp_path / "recent").exists()
    assert b.mark("app") is None
    b.record({"frame": {}}, T0)
    assert not (tmp_path / "recent").exists()


# ---------------------------------------------------------------- cleaning


TS = "<2026-11-24T18:16:27.354Z> "


def test_names_ids_and_addresses_are_cleaned():
    lines = [
        f"{TS}[Notice] <Actor Death> CActor::Kill: 'Me_Myself' [1] in zone 'x' killed by "
        "'Bad-Guy_1' [2] using 'gun' [Class gun] with damage type 'Bullet' from direction",
        f"{TS}[Notice] <Actor Death> CActor::Kill: 'Bad-Guy_1' [1] in zone 'x' killed by "
        "'PU_Human_Enemy_GroundCombat_NPC' [2] using 'gun' [Class gun] with damage type 'Bullet'",
        f'{TS}<UpdateNotificationItem> Notification "You have joined channel '
        "'Drake Cutlass Black : Wing_Mate' \" [7], Action: Next",
    ]
    players = players_in(lines, "Me_Myself")
    assert players == ["Bad-Guy_1", "Wing_Mate"]  # NPCs aren't players
    r = Redactor(
        handle="Me_Myself",
        players=players,
        hubs=["https://fleet.example.org"],
        fleets=["Test Org"],
        pc="DESKTOP-1234",
    )
    assert "'<you>'" in r.text(lines[0]) and "'player-1'" in r.text(lines[0])
    assert "'player-1'" in r.text(lines[1]) and "PU_Human_Enemy" in r.text(lines[1])
    assert "Wing_Mate" not in r.text(lines[2]) and "player-2" in r.text(lines[2])
    assert r.text("Bad-Guy_10 and Bad-Guy_1") == "Bad-Guy_10 and player-1"  # whole names only
    s = r.text(
        '<Expect Incoming Connection> nickname="Me_Myself" playerGEID=200012345678 '
        'sessionId="ab12cd" LoginSessionId: 1234-abcd <Join PU> address[34.12.200.7] '
        "port[64355] FileVersion: 4.10.201.48 mail me@example.com "
        r"C:\Users\Someone\AppData https://fleet.example.org/api wss://other.host/x "
        "https://github.com/bradqui/starglance on DESKTOP-1234 for Test Org"
    )
    for gone in ("Me_Myself", "200012345678", "ab12cd", "1234-abcd", "34.12.200.7",
                 "me@example.com", "Someone", "fleet.example.org", "other.host",
                 "DESKTOP-1234", "Test Org"):  # fmt: skip
        assert gone not in s, gone
    assert "FileVersion: 4.10.201.48" in s
    assert "https://github.com/bradqui/starglance" in s
    assert "<hub-1>/api" in s and "<fleet-1>" in s and "<pc>" in s and r"C:\Users\<user>" in s


# ---------------------------------------------------------------- a report, end to end


def _frames() -> list[dict]:
    return [raw for _t, raw in read_frames(FIXTURES_DIR / "quantum-travel.jsonl.gz")][:400]


def _setup(home: Path, monkeypatch):
    clock = Clock(T0 + 10 * 60_000)
    game = home / "LIVE"
    game.mkdir()
    log_lines = []

    def at(t: int, text: str) -> str:
        return f"<{utc_stamp(t)}> {text}"

    log_lines.append(at(T0, "FileVersion: 4.10.201.48085"))
    log_lines.append(at(T0, "ProductVersion: 4.10.201.48085"))
    log_lines.append(
        at(T0, "[Notice] <Legacy login response> [CIG-net] User Login Success - Handle[Me_Myself]")
    )
    pipeline = Pipeline()
    reports = Reports(
        pipeline,
        install=SimpleNamespace(game_log=game / "Game.log", channel="LIVE"),
        buffer=RecentBuffer(home / "recent", clock=clock),
    )
    pipeline.on_schema(b"protoset-bytes", "reflection")
    pipeline.on_log(log_lines[-1], T0)  # the login: who "me" is
    start = clock.t
    for i, raw in enumerate(_frames()):
        clock.t = start + i * 100
        pipeline.on_frame(raw, clock.t)
        if i == 200:
            kill = (
                "[Notice] <Actor Death> CActor::Kill: 'Me_Myself' [1] in zone 'x' killed by "
                "'Bad-Guy_1' [2] using 'gun' [Class gun] with damage type 'Bullet' from x"
            )
            log_lines.append(at(clock.t, kill))
            log_lines.append(at(clock.t, "[Notice] <Some New Line> playerGEID=200012345678"))
            pipeline.on_log(at(clock.t, kill), clock.t)
            reports.mark("app")
    (game / "Game.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    downloads = home / "Downloads"
    downloads.mkdir()
    monkeypatch.setattr(report_mod, "downloads_dir", lambda: downloads)
    monkeypatch.setattr(report_mod, "show_in_folder", lambda _p: None)
    return reports, clock, downloads


def test_a_report_has_the_window_cleaned_and_replays(home, monkeypatch):
    reports, clock, downloads = _setup(home, monkeypatch)
    timeline = reports.timeline()
    assert any(e["kind"] == "death" for e in timeline["events"])
    mark = reports.buffer.marks[0]

    preview = asyncio.run(
        reports.preview(
            {
                "t": mark.t,
                "before": 1,
                "after": 1,
                "mark": mark.id,
                "what": "Died, Bad-Guy_1 did it",
            }
        )
    )
    names = {f["name"] for f in preview["files"]}
    assert names == {
        "report.json", "events.jsonl", "gamelog.txt", "agent.log",
        "capture.jsonl.gz", "telemetry.protoset",
    }  # fmt: skip
    texts = preview["texts"]
    assert "<Some New Line>" in texts["gamelog.txt"]  # lines the agent doesn't know, too
    for text in texts.values():
        assert "Me_Myself" not in text and "Bad-Guy_1" not in text and "200012345678" not in text
    report = json.loads(texts["report.json"])
    assert report["game"] == {"channel": "LIVE", "version": "4.10.201.48085"}
    assert report["what"] == "Died, player-1 did it"
    assert report["counts"]["frames"] > 100
    assert report["marks"] and report["schema"] == "reflection"

    saved = reports.save(preview["id"])
    path = Path(saved["path"])
    assert path.parent == downloads and path.name.startswith("Starglance-report-")
    assert reports.buffer.marks == []  # reported: no longer kept past 30 minutes
    q = parse_qs(urlparse(saved["issue_url"]).query)
    assert q["template"] == ["bug_report.yml"] and q["game"] == ["LIVE 4.10.201.48085"]
    assert q["what"] == ["Died, player-1 did it"]

    with zipfile.ZipFile(path) as z:
        assert z.read("telemetry.protoset") == b"protoset-bytes"
        capture = gzip.decompress(z.read("capture.jsonl.gz")).decode()
    assert "Me_Myself" not in capture
    records = list(read_records(path))
    assert any("frame" in r for r in records) and any("mark" in r for r in records)
    rec = Recording.load([path], DEFAULT_PROTOSET)
    assert rec.positions and any(m.kind == "mark" for m in rec.markers)


def test_a_report_needs_what_happened(home, monkeypatch):
    reports, _clock, _downloads = _setup(home, monkeypatch)
    with pytest.raises(ValueError):
        asyncio.run(reports.preview({"what": "  "}))
    with pytest.raises(ValueError):
        asyncio.run(reports.preview({"what": "x", "before": 30}))


def test_a_replay_records_nothing(home):
    pipeline = Pipeline()
    reports = Reports(pipeline, live=False)
    assert pipeline.recorder is None
    assert reports.status()["available"] is False
