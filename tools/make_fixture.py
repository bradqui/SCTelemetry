"""Cut a time window out of a capture into a committed, gzipped fixture.

    uv run python tools/make_fixture.py captures/session-....jsonl 8:25 10:30 sit-takeoff

Times are min:sec from the start of the capture (as printed by
summarize_capture.py --timeline). Writes fixtures/<name>.jsonl.gz, with every
frame scrubbed of aUEC again (in case the capture was --raw) and checked.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

from fleet_agent import scrub  # noqa: E402


def parse_time(text: str) -> int:
    minutes, _, seconds = text.partition(":")
    return (int(minutes) * 60 + float(seconds or 0)) * 1000


def assert_scrubbed(value, path="") -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            if scrub.is_uec_key(k) and v != scrub.SCRUBBED:
                raise SystemExit(f"Unscrubbed aUEC at {path}.{k}")
            assert_scrubbed(v, f"{path}.{k}")
    elif isinstance(value, list):
        for v in value:
            assert_scrubbed(v, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("start", help="min:sec")
    parser.add_argument("end", help="min:sec")
    parser.add_argument("name")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "fixtures")
    args = parser.parse_args()

    start, end = parse_time(args.start), parse_time(args.end)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"{args.name}.jsonl.gz"

    t0 = None
    frames = notes = 0
    with args.capture.open(encoding="utf-8") as src, gzip.open(out, "wt", encoding="utf-8") as dst:
        for line in src:
            rec = json.loads(line)
            t0 = rec["t"] if t0 is None else t0
            offset = rec["t"] - t0
            if offset < start:
                continue
            if offset > end:
                break
            rec["label"] = args.name
            if "frame" in rec:
                rec["frame"] = scrub.scrub_uec(rec["frame"])
                assert_scrubbed(rec["frame"])
                frames += 1
            else:
                notes += 1
            dst.write(json.dumps(rec, separators=(",", ":")) + "\n")
    size_kb = out.stat().st_size / 1000
    shown = out.relative_to(ROOT) if out.is_relative_to(ROOT) else out
    print(f"{shown}: {frames} frames, {notes} notes, {size_kb:.0f} kB")


if __name__ == "__main__":
    main()
