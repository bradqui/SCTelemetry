"""Recover the game's telemetry ``.proto`` definitions from ``StarCitizen.exe`` (spec §2.3).

Programs built with protobuf carry each of their ``.proto`` files as a serialized
``FileDescriptorProto``. One of those always starts with field 1 (the file name),
so on disk it begins with ``0x0A <length> sc/game/telemetry/....proto``.

To recover one we find that prefix, then walk forward over top-level fields
for as long as they are valid ``FileDescriptorProto`` fields. The walk stops at
the first byte that can't start one (usually padding after the embedded array).
Then we parse the span and check the name. Dependencies are resolved the same
way by name; Google's well-known types come from the protobuf package itself.

The result is a ``FileDescriptorSet``: usable with ``grpcurl -protoset`` and
loadable into a ``DescriptorPool`` at runtime. It is cached per exe size+mtime,
so it is re-extracted after a game patch.

This only reads the game's file on disk. It never touches the running game.
"""

from __future__ import annotations

import mmap
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from google.protobuf import descriptor_pb2, descriptor_pool
from google.protobuf.message import DecodeError

SERVICE_NAME = "sc.game.telemetry.v1.GameTelemetryService"
NAME_PATTERN = re.compile(rb"sc/game/telemetry[A-Za-z0-9_./-]{0,200}?\.proto")
MAX_FILE_BYTES = 4 * 1024 * 1024

# FileDescriptorProto top-level fields -> allowed wire types.
# 1 name, 2 package, 3 dependency, 4 message_type, 5 enum_type, 6 service,
# 7 extension, 8 options, 9 source_code_info, 10 public_dependency,
# 11 weak_dependency, 12 syntax, 13 (legacy edition string), 14 edition.
_FDP_FIELDS: dict[int, frozenset[int]] = {
    **{n: frozenset({2}) for n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 13)},
    10: frozenset({0, 2}),
    11: frozenset({0, 2}),
    14: frozenset({0}),
}


class ExtractionError(RuntimeError):
    pass


# ---------------------------------------------------------------- wire helpers


def encode_varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _read_varint(buf, pos: int, limit: int) -> tuple[int, int]:
    result = 0
    for shift in range(0, 70, 7):
        if pos >= limit:
            raise ValueError("truncated varint")
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
    raise ValueError("varint too long")


def _field_ends(buf, start: int, limit: int) -> list[int]:
    """End offset of each top-level field, until bytes stop looking like a FileDescriptorProto."""
    ends: list[int] = []
    pos = start
    seen_name = False
    while pos < limit:
        try:
            tag, p = _read_varint(buf, pos, limit)
            number, wire_type = tag >> 3, tag & 7
            if wire_type not in _FDP_FIELDS.get(number, ()):
                break
            if number == 1:
                if seen_name:  # a second name means the next file started
                    break
                seen_name = True
            if wire_type == 2:
                length, p = _read_varint(buf, p, limit)
                if p + length > limit:
                    break
                p += length
            else:
                _, p = _read_varint(buf, p, limit)
        except ValueError:
            break
        ends.append(p)
        pos = p
    return ends


# ---------------------------------------------------------------- scanning


def parse_candidates(buf, start: int, name: str) -> list[descriptor_pb2.FileDescriptorProto]:
    """Plausible parses of the file starting at ``start``, longest first."""
    limit = min(len(buf), start + MAX_FILE_BYTES)
    out = []
    for end in reversed(_field_ends(buf, start, limit)):
        try:
            fdp = descriptor_pb2.FileDescriptorProto.FromString(bytes(buf[start:end]))
        except DecodeError:
            continue
        if fdp.name == name:
            out.append(fdp)
    return out


def find_file(buf, name: str) -> list[descriptor_pb2.FileDescriptorProto]:
    """Every plausible embedded copy of the file called ``name``, best first, deduplicated."""
    needle = b"\x0a" + encode_varint(len(name.encode())) + name.encode()
    found: list[descriptor_pb2.FileDescriptorProto] = []
    seen: set[bytes] = set()
    pos = buf.find(needle)
    while pos != -1:
        for fdp in parse_candidates(buf, pos, name):
            key = fdp.SerializeToString()
            if key not in seen:
                seen.add(key)
                found.append(fdp)
        pos = buf.find(needle, pos + 1)
    found.sort(key=lambda f: _richness(f), reverse=True)
    return found


def _richness(fdp: descriptor_pb2.FileDescriptorProto) -> tuple[int, int]:
    return (len(fdp.message_type) + len(fdp.enum_type) + len(fdp.service), fdp.ByteSize())


def telemetry_file_names(buf) -> list[str]:
    """Names of embedded files under ``sc/game/telemetry`` (only those stored as a file's name)."""
    names: list[str] = []
    for match in NAME_PATTERN.finditer(buf):
        raw = match.group(0)
        prefix = b"\x0a" + encode_varint(len(raw))
        start = match.start() - len(prefix)
        if start >= 0 and bytes(buf[start : match.start()]) == prefix:
            name = raw.decode("ascii")
            if name not in names:
                names.append(name)
    return names


def _well_known(name: str) -> descriptor_pb2.FileDescriptorProto | None:
    """Google's own .proto files, from the installed protobuf package."""
    if not name.startswith("google/protobuf/"):
        return None
    # Importing these registers them in the default pool.
    from google.protobuf import (  # noqa: F401
        any_pb2,
        api_pb2,
        duration_pb2,
        empty_pb2,
        field_mask_pb2,
        source_context_pb2,
        struct_pb2,
        timestamp_pb2,
        type_pb2,
        wrappers_pb2,
    )

    try:
        fd = descriptor_pool.Default().FindFileByName(name)
    except KeyError:
        return None
    fdp = descriptor_pb2.FileDescriptorProto()
    fd.CopyToProto(fdp)
    return fdp


# ---------------------------------------------------------------- assembling


@dataclass
class Extraction:
    file_set: descriptor_pb2.FileDescriptorSet
    service_file: str | None
    missing: list[str] = field(default_factory=list)

    @property
    def has_service(self) -> bool:
        return self.service_file is not None


def extract_from_buffer(buf, root_names: Iterable[str] | None = None) -> Extraction:
    names = list(root_names) if root_names is not None else telemetry_file_names(buf)
    if not names:
        raise ExtractionError("No embedded sc/game/telemetry .proto files were found in the exe.")

    candidates: dict[str, list[descriptor_pb2.FileDescriptorProto]] = {}
    missing: list[str] = []
    queue = list(names)
    while queue:
        name = queue.pop(0)
        if name in candidates or name in missing:
            continue
        known = _well_known(name)
        options = [known] if known else find_file(buf, name)
        if not options:
            missing.append(name)
            continue
        candidates[name] = options
        for dep in options[0].dependency:
            queue.append(dep)

    ordered = _build_validated(candidates)
    file_set = descriptor_pb2.FileDescriptorSet(file=ordered)
    service_file = next(
        (f.name for f in ordered for s in f.service if f"{f.package}.{s.name}" == SERVICE_NAME),
        None,
    )
    return Extraction(file_set=file_set, service_file=service_file, missing=missing)


def _build_validated(
    candidates: dict[str, list[descriptor_pb2.FileDescriptorProto]],
) -> list[descriptor_pb2.FileDescriptorProto]:
    """Pick one parse per file that loads into a pool, in dependency order."""
    pool = descriptor_pool.DescriptorPool()
    chosen: dict[str, descriptor_pb2.FileDescriptorProto] = {}
    order: list[descriptor_pb2.FileDescriptorProto] = []

    def add(name: str, stack: tuple[str, ...] = ()) -> bool:
        if name in chosen:
            return True
        if name in stack or name not in candidates:
            return False
        for option in candidates[name]:
            if not all(add(dep, (*stack, name)) for dep in option.dependency):
                continue
            try:
                pool.AddSerializedFile(option.SerializeToString())
            except (TypeError, ValueError):
                continue
            chosen[name] = option
            order.append(option)
            return True
        return False

    for name in candidates:
        add(name)
    return order


def extract_from_exe(exe: Path) -> Extraction:
    with exe.open("rb") as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as buf:
        return extract_from_buffer(buf)


# ---------------------------------------------------------------- caching / files


def cache_key(exe: Path) -> str:
    st = exe.stat()
    return f"{st.st_size}-{st.st_mtime_ns}"


def load_or_extract(
    exe: Path, cache_dir: Path, *, force: bool = False
) -> tuple[descriptor_pb2.FileDescriptorSet, Path]:
    """The exe's telemetry FileDescriptorSet, from cache when the exe hasn't changed."""
    cached = cache_dir / f"telemetry-{cache_key(exe)}.protoset"
    if cached.exists() and not force:
        return descriptor_pb2.FileDescriptorSet.FromString(cached.read_bytes()), cached
    result = extract_from_exe(exe)
    if not result.has_service:
        raise ExtractionError(
            f"Found {len(result.file_set.file)} telemetry .proto file(s) but not {SERVICE_NAME}."
            + (f" Missing dependencies: {', '.join(result.missing)}" if result.missing else "")
        )
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(result.file_set.SerializeToString())
    return result.file_set, cached


def write_protoset(file_set: descriptor_pb2.FileDescriptorSet, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(file_set.SerializeToString())
