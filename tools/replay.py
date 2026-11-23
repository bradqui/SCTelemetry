"""Play captured telemetry back as a fake game server (spec §8 Phase 1).

    uv run python tools/replay.py                       # all fixtures, as one session, looping
    uv run python tools/replay.py fixtures/combat.jsonl.gz --speed 2
    uv run python tools/replay.py captures/session-....jsonl --no-loop

Listens on 127.0.0.1:2943 by default, so it doesn't clash with a running
game on 2942. Point the agent at it with ``--game-port 2943``.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "agent"), str(ROOT / "shared")]

from fleet_agent.replay import DEFAULT_PROTOSET, ReplayServer, default_fixtures  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("files", nargs="*", type=Path, help="Captures/fixtures (default: all)")
    parser.add_argument("--port", type=int, default=2943)
    parser.add_argument("--speed", type=float, default=1.0, help="2 = twice as fast")
    parser.add_argument("--no-loop", action="store_true")
    parser.add_argument("--protoset", type=Path, default=DEFAULT_PROTOSET)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    files = args.files or default_fixtures(ROOT / "fixtures")
    server = ReplayServer(
        files, port=args.port, speed=args.speed, loop=not args.no_loop, protoset=args.protoset
    ).start()
    total = sum(d for d, _ in server.frames) / args.speed
    print(
        f"Replaying {len(server.frames)} frames from {len(files)} file(s) (~{total / 60:.1f} min"
        f"{', looping' if not args.no_loop else ''}) on 127.0.0.1:{server.port}. Ctrl+C stops."
    )
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
