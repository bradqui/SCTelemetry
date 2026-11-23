"""Record the game's telemetry stream to JSONL for Phase 0 (spec §8).

    uv run python tools/capture.py seated-pilot              # until Ctrl+C
    uv run python tools/capture.py on-foot --seconds 30
    uv run python tools/capture.py landing --channel LIVE --out-dir captures

Each line is {"t": <ms epoch>, "label": ..., "frame": {...}}, with field names as
in the game's .proto. aUEC fields are scrubbed unless --raw is given (raw
captures should stay in the gitignored captures/ folder).

The first run also writes captures/telemetry.protoset for grpcurl.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

import grpc  # noqa: E402
from fleet_agent import client, installs, protoset, scrub  # noqa: E402

SCENARIOS = (
    "on-foot",
    "seated-pilot",
    "seated-turret",
    "seated-other",
    "scm",
    "nav",
    "qt-spool",
    "landing",
    "taking-damage",
    "shields-down",
    "leaving-seat",
    "ship-swap",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("label", help=f"Scenario name, e.g. {', '.join(SCENARIOS[:4])}, ...")
    parser.add_argument(
        "--seconds", type=float, help="Stop after this long (default: until Ctrl+C)"
    )
    parser.add_argument("--channel", help="Install whose StarCitizen.exe has the definitions")
    parser.add_argument("--port", type=int, default=client.DEFAULT_PORT)
    parser.add_argument("--out-dir", default=str(ROOT / "captures"))
    parser.add_argument("--raw", action="store_true", help="Keep aUEC values (don't commit these)")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    exe = None
    found = installs.find_installs()
    if args.channel:
        found = [i for i in found if i.channel == args.channel.upper()]
    if found:
        exe = next((i for i in found if i.channel == "LIVE"), found[0]).exe

    channel = client.open_channel(port=args.port)
    print(f"Waiting for the game on 127.0.0.1:{args.port} (Ctrl+C to give up) ...")
    while not client.wait_ready(channel, timeout=2.0):
        pass

    schema = client.load_schema(channel, exe)
    print(schema.describe())
    protoset_path = out_dir / "telemetry.protoset"
    protoset.write_protoset(schema.file_set, protoset_path)
    print(f"Wrote {protoset_path}")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_file = out_dir / f"{args.label}-{stamp}{'-raw' if args.raw else ''}.jsonl"
    print(f"Recording to {out_file}. Frames only arrive once you're loaded into the game.")

    started = time.monotonic()
    count = 0
    last_report = started
    try:
        with out_file.open("w", encoding="utf-8") as fh:
            for message in client.stream_frames(channel, schema):
                frame = client.frame_to_dict(message)
                if not args.raw:
                    frame = scrub.scrub_uec(frame)
                fh.write(
                    json.dumps({"t": int(time.time() * 1000), "label": args.label, "frame": frame})
                    + "\n"
                )
                count += 1
                now = time.monotonic()
                if now - last_report >= 2:
                    keys = ",".join(k for k, v in frame.items() if v) or "-"
                    print(f"  {count} frames, {count / (now - started):.1f}/s, non-empty: {keys}")
                    last_report = now
                if args.seconds and now - started >= args.seconds:
                    break
    except KeyboardInterrupt:
        pass
    except grpc.RpcError as exc:
        print(f"Stream ended: {exc.code()} {exc.details()}")
    print(f"Saved {count} frames to {out_file}")


if __name__ == "__main__":
    main()
