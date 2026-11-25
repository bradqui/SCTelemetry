"""Place names from the game's own files (places.py) and where you are (gamelog.LogState)."""

import struct
import zlib

import zstandard
from starglance import places
from starglance.gamelog import LogState, parse_line
from starglance.places import Names, parse_ini

TS = "<2026-11-25T18:00:00.000Z> "

INI = "\n".join(
    [
        "Stanton1_Lorville=Lorville",
        "Stanton1_Lorville_Desc=The capital of Hurston and a long description",
        "RR_P6=Ruin Station",
        "RR_HUR_L1=HUR-L1 Green Glade Station",
        "Stanton1_Transfer=Everus Harbor",
        "Stanton1_Transfer_Clinic=Everus Harbor Clinic",
        "Stanton2_Transfer=Port Olisar",
        "Stanton2_Transfer_Seraphim=Seraphim Station",
        "Stanton1_Hurdyn_003=HDMS-Pinewood",
        "Stanton4_Shubin_018=Shubin Mining Facility SM0-18",
        "Delamar_Levski,P=Levski",
        "Stanton1=Hurston",
        "Stanton2b=Daymar",
        "Pyro5=Pyro V",
        "mission_title_001=Not a place",
    ]
)


def test_ini_keeps_short_names_only():
    names = parse_ini(INI)
    assert names["stanton1_lorville"] == "Lorville"
    assert "stanton1_lorville_desc" not in names and "mission_title_001" not in names
    assert names["delamar_levski"] == "Levski", "the ,P flag is dropped"


def test_names_from_game_ids():
    n = Names(parse_ini(INI))
    assert n.place("Stanton1_Lorville") == "Lorville"
    assert n.place("RR_P6_LEO") == "Ruin Station", "trimmed to a key"
    assert n.place("RR_HUR_L1") == "HUR-L1 Green Glade Station"
    assert n.place("RR_JP_StantonPyro") == "Pyro Gateway"
    assert n.place("RR_HUR_LEO") == "Everus Harbor", "not its clinic"
    assert n.place("RR_CRU_LEO") == "Seraphim Station", "the newer station"
    assert n.place("Stanton1_HurdynMining_HDMSPinewood") == "HDMS-Pinewood", "by its words"
    assert n.place("Stanton4_Shubin_SM0_18") == "Shubin Mining Facility SM0-18"
    assert n.place("Nyx_Levski") == "Levski", "filed under another prefix"
    assert n.place("Stanton2b_ASD_Delve_Facility_005") is None
    assert n.body("Stanton2b_ASD_Delve_Facility_005") == "Daymar", "the moon instead"
    assert n.body("OOC_Stanton_2b_Daymar") == "Daymar"
    assert n.body("pyro5") == "Pyro V"
    assert n.body("AsteroidClusterBase_Pyro_Dungeon_001") is None


def _p4k(path, files):
    """A small archive shaped like Data.p4k: ZIP64 records, zstd entries (method 100),
    and an extra field of the game's own that Python's zipfile rejects."""
    body, central = bytearray(), bytearray()
    for name, data in files.items():
        raw = name.encode()
        packed = zstandard.ZstdCompressor().compress(data)
        crc = zlib.crc32(data)
        offset = len(body)
        body += struct.pack(
            "<IHHHHHIIIHH", 0x04034B50, 45, 0, 100, 0, 0, crc, len(packed), len(data), len(raw), 0
        )
        body += raw + packed
        zip64 = struct.pack("<HHQQQ", 0x0001, 24, len(data), len(packed), offset)
        own = struct.pack("<HH", 0x5000, 4) + b"\x99\x99\x99\x99"  # length lies, like the game's
        extra = zip64 + own
        central += struct.pack(
            "<IHHHHHHIIIHHHHHII",
            0x02014B50, 45, 45, 0, 100, 0, 0, crc,
            0xFFFFFFFF, 0xFFFFFFFF, len(raw), len(extra), 0, 0, 0, 0, 0xFFFFFFFF,
        )  # fmt: skip
        central += raw + extra
    cd_at = len(body)
    eocd64_at = cd_at + len(central)
    eocd64 = struct.pack(
        "<IQHHIIQQQQ", 0x06064B50, 44, 45, 45, 0, 0, len(files), len(files), len(central), cd_at
    )
    locator = struct.pack("<IIQI", 0x07064B50, 0, eocd64_at, 1)
    eocd = struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, 0xFFFF, 0xFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0)
    path.write_bytes(bytes(body + central + eocd64 + locator + eocd))


def test_reads_names_from_the_games_archive_and_caches_them(tmp_path, monkeypatch):
    monkeypatch.setenv("STARGLANCE_HOME", str(tmp_path / "home"))
    game = tmp_path / "LIVE"
    game.mkdir()
    _p4k(
        game / "Data.p4k",
        {
            "Data\\Objects\\something.cgf": b"x" * 100,
            "Data\\Localization\\english\\global.ini": ("﻿" + INI).encode("utf-8"),
        },
    )
    [_, ini] = places.p4k_entries(game / "Data.p4k")
    assert ini.method == 100 and ini.offset > 0
    names = places.load(game)
    assert names is not None and names.place("Stanton1_Lorville") == "Lorville"
    cache = places.cache_file(game / "Data.p4k")
    assert cache.is_file()
    (game / "Data.p4k").write_bytes((game / "Data.p4k").read_bytes())  # same size, new mtime
    assert not places.cache_file(game / "Data.p4k").is_file(), "a patched game is read again"
    assert places.load(tmp_path / "nowhere") is None


# -- where you are, from Game.log


LANDING = TS + (
    "[Notice] <RequestLocationInventory> Player[Someone] requested inventory for "
    "Location[Stanton1_Lorville] [Team_CoreGameplayFeatures][Inventory]"
)
ENTER = TS + (
    "[Notice] <Update Inventory Location> Player [Someone] is changing location. "
    "Landing [0] -> [123456789]. Location [0] -> [987654321]. Pending [0] [Inventory]"
)
LEAVE = ENTER.replace("Landing [0] -> [123456789]", "Landing [123456789] -> [0]")
START = TS + (
    "[Notice] <Calculate Route> [ItemNavigation][CL][1] | NOT AUTH | RSI_Ship_1[1]|"
    "CSCItemNavigation::CalculateRoute|Projected Start Location is Magda\x7f for route to "
    "destination somewhere.socpak [Team_CGP4]"
)


def cells(body, n, cap=16384, ts="2026-11-25T18:10:00.000Z"):
    return f"<{ts}>   planet cells: {n:4} [{cap:5}] meshes:    0 [    0] name: {body}"


def feed(state, *lines, t=1000):
    out = []
    for line in lines:
        ev = parse_line(line)
        assert ev is not None, line
        out += state.on_log(ev, t)
    return out


def test_parses_the_place_lines():
    assert parse_line(LANDING).data == {"id": "Stanton1_Lorville"}
    assert parse_line(LEAVE).data == {"from": "123456789", "to": "0"}
    assert parse_line(START).data == {"near": "Magda"}, "stray bytes dropped"
    ev = parse_line(cells("OOC_Stanton_2b_Daymar", 12))
    assert ev.kind == "planet_cells" and ev.data["body"] == "OOC_Stanton_2b_Daymar"


def test_landing_area_by_name_and_leaving_it():
    s = LogState()
    s.names = Names(parse_ini(INI))
    [ev] = feed(s, ENTER, LANDING)
    assert ev.kind == "place_enter" and ev.data == {"name": "Lorville"}
    assert feed(s, LANDING) == [], "the game asks again: not news"
    loc = s.location(2000, False)
    assert loc.landing == "Lorville" and loc.body == "Hurston", "and the planet it's on"
    feed(s, LEAVE)
    loc = s.location(3000, False)
    assert loc.landing is None and loc.body == "Hurston", "left the city, still at the planet"


def test_the_busiest_planet_cells_are_where_you_are():
    s = LogState()
    feed(s, cells("OOC_Stanton_1_Hurston", 0), cells("OOC_Stanton_2b_Daymar", 40))
    feed(s, cells("OOC_Stanton_2_Crusader", 3), t=1000)
    assert s.location(5000, False).body == "Daymar", "names from the ids, before the game's"
    later = "2026-11-25T18:20:00.000Z"
    bodies = ("OOC_Stanton_2b_Daymar", "OOC_Stanton_1_Hurston")
    empty = [cells(b, 0, cap=0, ts=later) for b in bodies]
    feed(s, *empty, t=6000)
    assert s.location(9000, False) is None, "deep space: nowhere in particular"


def test_jumps_route_starts_and_servers_move_you():
    s = LogState()
    s.names = Names(parse_ini(INI))
    feed(s, START)
    assert s.location(1000, False).body == "Magda", "where the route was plotted from"
    s.location(1500, True)  # jumping
    assert s.location(1600, False) is None
    selected = TS + (
        "[Notice] <Player Selected Quantum Target - Local> [ItemNavigation][CL][1] | NOT AUTH | "
        "RSI_Ship_1[1]|CSCItemNavigation::OnPlayerSelectedQuantumTarget|Player has selected point "
        "OOC_Stanton_2b_Daymar as their destination, routing locally"
    )
    arrived = TS + (
        "[Notice] <Quantum Drive Arrived - Arrived at Final Destination> [ItemNavigation][CL] | "
        "NOT AUTH | RSI_Ship_1[1]|CSCItemNavigation::OnQuantumDriveArrived|Quantum Drive has "
        "arrived at final destination [Team_CGP4][QuantumTravel]"
    )
    feed(s, selected, arrived, t=2000)
    assert s.location(2100, False).body == "Daymar", "where the jump ended"
    s.respawned()
    assert s.location(2200, False).body is None
