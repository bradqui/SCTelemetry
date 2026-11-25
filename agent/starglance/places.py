"""Place names from the player's own game files, for "At Lorville" and "Flying at Daymar".

Game.log names places by the game's internal ids (``Stanton1_Lorville``, ``RR_P6_LEO``,
``Stanton1_HurdynMining_HDMSPinewood``, ``OOC_Stanton_2b_Daymar``). The names players
see are in the game's own text file, ``Data\\Localization\\english\\global.ini``, inside
``Data.p4k`` next to the exe. So, like the telemetry definitions from ``StarCitizen.exe``
(protoset.py), we read it from the installed game, read-only, and keep what we need per
game build: names follow each patch, and no game data ships with Starglance.

``Data.p4k`` is a ZIP64 archive (about 160 GB) whose entries are stored or zstd
compressed (method 100), with extra fields of its own that Python's zipfile refuses. We
read its central directory ourselves (about 2 s for 1.4 million entries) and then the one
entry, about 10 MB.

Resolving an id (``Names.place``), first match wins:
1. the id, then the id with parts trimmed off the end, as a key (``RR_P6_LEO`` → ``RR_P6``
   is Ruin Station);
2. gateways by their pair of systems (``RR_JP_StantonPyro`` is Pyro Gateway, in Stanton);
3. the station above a planet (``RR_HUR_LEO`` is Stanton1's ``_Transfer`` station);
4. the words of the id against short names under the same planet or moon's keys
   (``HDMSPinewood`` is "HDMS-Pinewood", ``Shubin_SM0_18`` is "Shubin Mining Facility
   SM0-18");
5. nothing: the caller falls back to the planet or moon in the id.
"""

from __future__ import annotations

import gzip
import json
import logging
import re
import struct
from dataclasses import dataclass
from pathlib import Path

from . import paths

log = logging.getLogger(__name__)

GLOBAL_INI = "data\\localization\\english\\global.ini"
MAX_NAME = 48
"""Longer values are descriptions, not names."""
_NOT_A_NAME = re.compile(
    r"desc|mission|title|_obj|contract|dfm|^ui_|shop|marker|_info|comms|tutorial|_hint|_note",
    re.I,
)
_STOP = {"and", "the", "of"}
PLANET_CODES = {"HUR": "stanton1", "CRU": "stanton2", "ARC": "stanton3", "MIC": "stanton4"}
_BODY = re.compile(r"^(?:OOC_)?(Stanton|Pyro|Nyx|Castra|Magnus|Terra)_?(\d+[a-f]?)?", re.I)


class P4kError(RuntimeError):
    pass


# ---------------------------------------------------------------- the archive


@dataclass
class Entry:
    name: str
    method: int
    csize: int
    size: int
    offset: int


def p4k_entries(path: Path) -> list[Entry]:
    """Every entry in the archive's central directory."""
    with open(path, "rb") as f:
        f.seek(0, 2)
        end = f.tell()
        f.seek(max(0, end - 65536 - 22))
        tail = f.read()
        i = tail.rfind(b"PK\x06\x07")  # ZIP64 end of central directory locator
        if i < 0:
            raise P4kError("Not a ZIP64 archive.")
        (eocd_at,) = struct.unpack_from("<Q", tail, i + 8)
        f.seek(eocd_at)
        eocd = f.read(56)
        if eocd[:4] != b"PK\x06\x06":
            raise P4kError("No ZIP64 end of central directory.")
        count, cd_size, cd_at = struct.unpack_from("<QQQ", eocd, 32)
        f.seek(cd_at)
        cd = f.read(cd_size)
    out: list[Entry] = []
    p = 0
    for _ in range(count):
        if cd[p : p + 4] != b"PK\x01\x02":
            raise P4kError("Damaged central directory.")
        (method,) = struct.unpack_from("<H", cd, p + 10)
        csize, size = struct.unpack_from("<II", cd, p + 20)
        nlen, xlen, clen = struct.unpack_from("<HHH", cd, p + 28)
        (offset,) = struct.unpack_from("<I", cd, p + 42)
        name = cd[p + 46 : p + 46 + nlen].decode("utf-8", "replace")
        extra = cd[p + 46 + nlen : p + 46 + nlen + xlen]
        q = 0
        while q + 4 <= len(extra):  # ZIP64 sizes and offset (the archive's own fields skipped)
            tag, ln = struct.unpack_from("<HH", extra, q)
            if tag == 0x0001:
                body, r = extra[q + 4 : q + 4 + ln], 0
                vals = []
                for big in (size == 0xFFFFFFFF, csize == 0xFFFFFFFF, offset == 0xFFFFFFFF):
                    if big and r + 8 <= len(body):
                        vals.append(struct.unpack_from("<Q", body, r)[0])
                        r += 8
                    else:
                        vals.append(None)
                size = vals[0] if vals[0] is not None else size
                csize = vals[1] if vals[1] is not None else csize
                offset = vals[2] if vals[2] is not None else offset
            q += 4 + ln
        out.append(Entry(name, method, csize, size, offset))
        p += 46 + nlen + xlen + clen
    return out


def p4k_read(path: Path, entry: Entry) -> bytes:
    with open(path, "rb") as f:
        f.seek(entry.offset)
        header = f.read(30)
        if header[:4] != b"PK\x03\x04":
            raise P4kError(f"No local header for {entry.name}.")
        nlen, xlen = struct.unpack_from("<HH", header, 26)
        f.seek(entry.offset + 30 + nlen + xlen)
        data = f.read(entry.csize)
    if entry.method == 0:
        return data
    if entry.method in (93, 100):  # zstd (100 in the game's archive)
        import zstandard

        return zstandard.ZstdDecompressor().decompress(data, max_output_size=entry.size)
    raise P4kError(f"{entry.name}: compression method {entry.method} isn't supported.")


# ---------------------------------------------------------------- names


def _words(s: str) -> list[str]:
    s = s.replace("'", "")
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)  # HDMSPinewood -> HDMS Pinewood
    s = re.sub(r"([A-Za-z])(\d)", r"\1 \2", s)
    s = re.sub(r"(\d)([A-Za-z])", r"\1 \2", s)
    return [w for w in re.split(r"[^A-Za-z0-9]+", s.lower()) if w and w not in _STOP]


def parse_ini(text: str) -> dict[str, str]:
    """``key=value`` lines (keys lower-cased, ``,P`` flags dropped): the short ones that
    can be place names, so the cache stays small."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip().split(",")[0].lower()
        value = value.strip()
        if not key or not value or len(value) > MAX_NAME or "\\n" in value:
            continue
        if _NOT_A_NAME.search(key):
            continue
        out.setdefault(key, value)
    return out


def body_key(raw: str) -> str | None:
    """``OOC_Stanton_2b_Daymar`` / ``Stanton2b_...`` / ``pyro5`` → ``stanton2b`` / ``pyro5``."""
    m = _BODY.match(raw)
    if not m:
        return None
    return (m.group(1) + (m.group(2) or "")).lower()


class Names:
    def __init__(self, names: dict[str, str]) -> None:
        self.names = names
        self._words = {k: set(_words(v)) for k, v in names.items()}

    def body(self, raw: str) -> str | None:
        """The planet, moon or system an id is at (``Stanton2b_...`` → Daymar)."""
        key = body_key(raw)
        return self.names.get(key) if key else None

    def place(self, raw: str) -> str | None:
        parts = raw.split("_")
        for n in range(len(parts), 1, -1):
            hit = self.names.get("_".join(parts[:n]).lower())
            if hit:
                return hit
        if m := re.fullmatch(r"RR_JP_([A-Z][a-z]+)([A-Z][a-z]+)", raw):
            return f"{m.group(2)} Gateway"
        if m := re.fullmatch(r"RR_(HUR|CRU|ARC|MIC)_LEO", raw):
            return self._leo(PLANET_CODES[m.group(1)])
        key = body_key(raw)
        rest = raw[len(re.match(r"^(?:OOC_)?[A-Za-z]+_?\d*[a-f]?", raw).group(0)) :] if key else raw
        pool = [k for k in self.names if key is None or k.startswith(key)]
        for words in (_words(rest), _words(rest.rsplit("_", 1)[-1])):
            if not words or not any(len(w) >= 4 and not w.isdigit() for w in words):
                continue
            want = set(words)
            hits = {self.names[k] for k in pool if want <= self._words[k]}
            if not hits:  # filed under another prefix (Levski): only an exact name will do
                hits = {self.names[k] for k in self.names if self._words[k] == want}
            if hits:
                return min(hits, key=len)
        return None

    def _leo(self, planet: str) -> str | None:
        """The station above a planet: ``<planet>_Transfer``, or a newer station filed as
        ``<planet>_Transfer_<name>`` (Seraphim Station replaced Port Olisar)."""
        shape = re.compile(rf"^{planet}_transfer(_[a-z0-9]+)?$")
        rooms = re.compile(r"clinic|medical|hospital|hangar|office|lobby|bar\b|shop", re.I)
        found = {k: v for k, v in self.names.items() if shape.match(k) and not rooms.search(v)}
        newer = [v for k, v in found.items() if k != f"{planet}_transfer" and v.endswith("Station")]
        return newer[0] if newer else found.get(f"{planet}_transfer")


# ---------------------------------------------------------------- per game build


def cache_file(p4k: Path) -> Path:
    st = p4k.stat()
    return paths.data_dir() / "names" / f"names-{st.st_size}-{st.st_mtime_ns}.json.gz"


def load(game_dir: Path) -> Names | None:
    """The names for the game in ``game_dir`` (its channel folder), from the cache or the
    game's archive. None when it can't be read; places then show by their ids."""
    p4k = game_dir / "Data.p4k"
    if not p4k.is_file():
        return None
    try:
        cache = cache_file(p4k)
        if cache.is_file():
            return Names(json.loads(gzip.decompress(cache.read_bytes())))
        entry = next((e for e in p4k_entries(p4k) if e.name.lower() == GLOBAL_INI), None)
        if entry is None:
            log.warning("Places: no %s in %s", GLOBAL_INI, p4k)
            return None
        names = parse_ini(p4k_read(p4k, entry).decode("utf-8-sig", "replace"))
        cache.parent.mkdir(parents=True, exist_ok=True)
        for old in cache.parent.glob("names-*.json.gz"):
            old.unlink(missing_ok=True)
        cache.write_bytes(gzip.compress(json.dumps(names, separators=(",", ":")).encode()))
        log.info("Places: %d names from %s", len(names), p4k)
        return Names(names)
    except (OSError, P4kError, ValueError, ImportError):
        log.warning("Places: can't read names from %s", p4k, exc_info=True)
        return None
