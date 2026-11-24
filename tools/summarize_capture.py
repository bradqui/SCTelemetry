"""Summarize a capture: which fields the game actually fills in, and how they change.

    uv run python tools/summarize_capture.py captures/session-....jsonl [--timeline]

Prints, for every leaf field path (lists shown as ``[]``): how often it was
present, how many distinct values, numeric min/max, and sample values. With
``--timeline``, also prints every change of the key state fields and events,
with the time since the capture started.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

TIMELINE_PATHS = (
    "actor.state.locomotion",
    "actor.state.crew_role",
    "actor.state.seat_name",
    "vehicle.state.name",
    "vehicle.state.class_name",
    "vehicle.state.type",
    "vehicle.state.flight.state.is_landed",
    "vehicle.state.flight.state.gear",
    "vehicle.state.flight.state.vtol",
    "vehicle.state.lights_enabled",
    "vehicle.state.doors.open_state",
    "vehicle.state.doors.lock_state",
    "weapons.preset_name",
)
TIMELINE_PREFIXES = (
    "vehicle.state.power.",
    "vehicle.state.annunciators.",
    "vehicle.state.flight.settings.",
    "weapons.settings.gimbals_locked",
)


def leaves(value, prefix=""):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from leaves(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(value, list):
        if not value:
            yield f"{prefix}[]", "<empty list>"
        for item in value:
            yield from leaves(item, f"{prefix}[]")
    else:
        yield prefix, value


def fmt_time(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60:3d}:{s % 60:02d}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("--timeline", action="store_true")
    parser.add_argument("--samples", type=int, default=6)
    args = parser.parse_args()

    present: Counter[str] = Counter()
    values: dict[str, Counter] = defaultdict(Counter)
    nums: dict[str, list[float]] = {}
    frames = 0
    t0 = None
    last_t = None
    gaps = []
    notes = []
    timeline = []
    previous: dict[str, object] = {}
    sections: Counter[str] = Counter()

    opener = gzip.open if args.capture.suffix == ".gz" else open
    with opener(args.capture, "rt", encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            t = rec["t"]
            t0 = t if t0 is None else t0
            if "note" in rec:
                notes.append((t - t0, rec["note"]))
                timeline.append((t - t0, "NOTE", rec["note"]))
                continue
            if "log" in rec:  # a Game.log line the capture kept
                timeline.append((t - t0, "LOG", rec["log"][-160:]))
                continue
            if "frame" not in rec:
                continue
            frames += 1
            if last_t is not None and t - last_t > 1000:
                gaps.append((last_t - t0, t - last_t))
            last_t = t
            frame = rec["frame"]
            sections[",".join(sorted(frame))] += 1

            current: dict[str, object] = {}
            for path, value in leaves(frame):
                present[path] += 1
                if len(values[path]) < 200 or value in values[path]:
                    values[path][json.dumps(value)] += 1
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    lo_hi = nums.setdefault(path, [value, value])
                    lo_hi[0] = min(lo_hi[0], value)
                    lo_hi[1] = max(lo_hi[1], value)
                current.setdefault(path, value)

            for ev in frame.get("events", {}).get("events", []):
                timeline.append((t - t0, "EVENT", ev.get("type")))

            watch = {
                p: v
                for p, v in current.items()
                if p in TIMELINE_PATHS or p.startswith(TIMELINE_PREFIXES)
            }
            for p in set(watch) | {p for p in previous if p not in current}:
                old, new = previous.get(p, "<absent>"), watch.get(p, "<absent>")
                if old != new:
                    timeline.append((t - t0, p, f"{old} -> {new}"))
            previous = watch

    duration = (last_t - t0) / 1000 if frames else 0
    print(
        f"{args.capture.name}: {frames} frames over {duration / 60:.1f} min "
        f"({frames / duration:.1f}/s)"
        if duration
        else "no frames"
    )
    print(
        f"gaps > 1s: {len(gaps)}"
        + "".join(f"\n  at {fmt_time(at)} for {gap / 1000:.1f}s" for at, gap in gaps[:20])
    )
    print("top-level section combinations:")
    for combo, n in sections.most_common():
        print(f"  {n:7d}  {combo}")

    print("\nFIELDS  (present% | distinct | min..max | samples)")
    for path in sorted(present):
        pct = 100 * present[path] / frames
        distinct = len(values[path])
        rng = ""
        if path in nums:
            lo, hi = nums[path]
            rng = f"{lo:.6g}..{hi:.6g}"
        samples = ", ".join(v for v, _ in values[path].most_common(args.samples))
        print(
            f"{path:<62} {pct:5.1f}% {distinct:>4}{'+' if distinct >= 200 else ' '} "
            f"{rng:<24} {samples[:110]}"
        )

    if args.timeline:
        print("\nTIMELINE")
        for at, what, detail in timeline:
            print(f"{fmt_time(at)}  {what:<48} {detail}")


if __name__ == "__main__":
    main()
