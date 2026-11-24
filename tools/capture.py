"""Record the game's telemetry stream to JSONL for Phase 0 (spec §8).

    uv run python tools/capture.py                  # one long session, until Ctrl+C
    uv run python tools/capture.py combat           # optional name for the file
    uv run python tools/capture.py --seconds 30

Start it any time (even before the game) and just play. It waits for the game,
keeps recording through loading screens and game restarts (reconnecting into
the same file), and stops on Ctrl+C.

Each line is {"t": <ms epoch>, "label": ..., "frame": {...}}, with field names as
in the game's .proto, or {"t", "label", "note": "..."} for a note: either typed
into the terminal while recording (press Enter), or written by the tool itself
("[capture] ...") when the stream drops and comes back. Game.log lines the
agent understands (quantum route, arrival, obstruction) are recorded as
{"t", "label", "log": "..."}; no other log lines are kept.

aUEC fields are scrubbed unless --raw is given. Captures stay in the gitignored
captures/ folder. Also writes captures/telemetry.protoset for grpcurl.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

import grpc  # noqa: E402
from starglance import client, installs, protoset, scrub  # noqa: E402
from starglance.gamelog import GameLogTail  # noqa: E402

STATUS_EVERY = 10.0  # seconds between progress lines


class Recorder:
    def __init__(self, out_file: Path, label: str):
        self.out_file = out_file
        self.label = label
        self.lock = threading.Lock()
        self.fh = out_file.open("w", encoding="utf-8")
        self.frames = 0

    def write(self, record: dict) -> None:
        line = json.dumps(
            {"t": int(time.time() * 1000), "label": self.label, **record}, separators=(",", ":")
        )
        with self.lock:
            self.fh.write(line + "\n")
            self.fh.flush()

    def note(self, text: str) -> None:
        self.write({"note": text})
        print(f"  [{datetime.now():%H:%M:%S}] noted: {text}")

    def close(self) -> None:
        with self.lock:
            self.fh.close()


def find_install(channel_name: str | None) -> installs.Install | None:
    found = installs.find_installs()
    if channel_name:
        found = [i for i in found if i.channel == channel_name.upper()]
    if not found:
        return None
    return next((i for i in found if i.channel == "LIVE"), found[0])


def read_notes(rec: Recorder) -> None:
    for line in sys.stdin:
        if line.strip():
            rec.note(line.strip())


def record(channel, schema, rec: Recorder, args) -> None:
    started = time.monotonic()
    last_status = started
    while True:
        if not client.wait_ready(channel, timeout=2.0):
            continue
        try:
            for message in client.stream_frames(channel, schema):
                frame = client.frame_to_dict(message)
                if not args.raw:
                    frame = scrub.scrub_uec(frame)
                rec.write({"frame": frame})
                rec.frames += 1

                events = [e.get("type") for e in frame.get("events", {}).get("events", [])]
                if events:
                    print(f"  [{datetime.now():%H:%M:%S}] event: {', '.join(map(str, events))}")
                now = time.monotonic()
                if now - last_status >= STATUS_EVERY:
                    present = ",".join(f.name for f, _ in message.ListFields()) or "-"
                    mins = (now - started) / 60
                    print(f"  {rec.frames} frames ({mins:.1f} min) sections: {present}")
                    last_status = now
                if args.seconds and now - started >= args.seconds:
                    return
            reason = "stream ended"
        except grpc.RpcError as exc:
            reason = f"stream dropped ({exc.code().name})"
        if args.seconds and time.monotonic() - started >= args.seconds:
            return
        rec.note(f"[capture] {reason}; waiting for the game")
        time.sleep(2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("label", nargs="?", default="session", help="Name for the file")
    parser.add_argument("--seconds", type=float, help="Stop after this long (default: Ctrl+C)")
    parser.add_argument("--channel", help="Install whose StarCitizen.exe has the definitions")
    parser.add_argument("--port", type=int, help="Default: read from Game.log, else 2942")
    parser.add_argument("--out-dir", default=str(ROOT / "captures"))
    parser.add_argument("--raw", action="store_true", help="Keep aUEC values (don't commit these)")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    install = find_install(args.channel)
    port = args.port
    print("Waiting for the game (Ctrl+C to give up) ...")
    try:
        while True:
            # The port is announced in Game.log at startup, so re-read it while waiting.
            port = args.port or client.discover_port(install.game_log if install else None)
            channel = client.open_channel(port=port)
            if client.wait_ready(channel, timeout=2.0):
                break
            channel.close()
    except KeyboardInterrupt:
        return
    print(f"Connected on 127.0.0.1:{port}")

    schema = client.load_schema(channel, install.exe if install else None)
    print(schema.describe())
    protoset.write_protoset(schema.file_set, out_dir / "telemetry.protoset")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_file = out_dir / f"{args.label}-{stamp}{'-raw' if args.raw else ''}.jsonl"
    rec = Recorder(out_file, args.label)
    print(f"\nRecording to {out_file}")
    print("Just play. Optional: type a note and press Enter to mark a moment. Ctrl+C stops.\n")
    threading.Thread(target=read_notes, args=(rec,), daemon=True).start()
    tail = None
    if install is not None:
        # Only lines from now on (quiet history is skipped).
        tail = GameLogTail(
            install.game_log, lambda line, quiet: None if quiet else rec.write({"log": line})
        )
        tail.start()

    try:
        record(channel, schema, rec, args)
    except KeyboardInterrupt:
        pass
    finally:
        if tail is not None:
            tail.stop()
        rec.close()
    size_mb = out_file.stat().st_size / 1_000_000
    print(f"\nSaved {rec.frames} frames ({size_mb:.1f} MB) to {out_file}")


if __name__ == "__main__":
    main()
