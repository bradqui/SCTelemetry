"""How Game.log line formats have changed: scan every backed-up log for the line
types the agent reads and report when each format was seen.

    uv run python tools/logscan.py              # LIVE install
    uv run python tools/logscan.py --channel PTU

Values are replaced by placeholders before anything is printed, so no names,
ids or addresses appear in the output. Re-run after a big patch and compare with
docs/FIELDS.md ("Game.log").
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "agent"), str(ROOT / "shared")]

from starglance import installs  # noqa: E402

TAGS = {
    "login (handle)": r"<Legacy login response>.*Handle\[",
    "Join PU (shard)": r"<Join PU>",
    "Update Shard Id": r"<Update Shard Id>",
    "EndMission": r"<EndMission>",
    "quantum route": r"<Player Selected Quantum Target",
    "quantum arrived": r"<Quantum Drive Arrived",
    "notifications": r"<UpdateNotificationItem> Notification",
    "Vehicle Destroyed": r"<Vehicle Destroyed>",
    "Actor Death": r"<Actor Death>",
    "Jump Drive": r"<Jump Drive State Changed>",
}


def shape(line: str) -> str:
    s = line.split("> ", 1)[-1] if line.startswith("<") else line
    s = re.sub(r"'[^']*'", "'S'", s)
    s = re.sub(r'"[^"]*"', '"S"', s)
    s = re.sub(r"\[[^\]]*\]", "[X]", s)
    s = re.sub(r"\d+(\.\d+)?", "N", s)
    return re.sub(r"\b[A-Za-z]+_[A-Za-z0-9_]+\b", "ID", s)[:120]


def file_date(p: Path) -> str:
    m = re.search(r"(\d+) (\w+) (\d+) \(", p.name)
    if not m:
        return "current"
    return datetime.strptime(" ".join(m.groups()), "%d %b %y").strftime("%Y-%m-%d")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--channel", default="LIVE")
    args = ap.parse_args()
    inst = next((i for i in installs.find_installs([]) if i.channel == args.channel.upper()), None)
    if inst is None:
        sys.exit(f"No {args.channel} install found.")
    files = sorted(inst.path.glob("logbackups/Game Build*.log")) + [inst.game_log]
    rx = {k: re.compile(v) for k, v in TAGS.items()}
    seen = defaultdict(lambda: defaultdict(lambda: [0, "9999", "0000", set()]))
    for f in files:
        if not f.exists():
            continue
        date = file_date(f)
        build = (re.search(r"Build\((\d+)\)", f.name) or [None, "current"])[1]
        with open(f, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                for tag, r in rx.items():
                    if r.search(line):
                        st = seen[tag][shape(line.rstrip())]
                        st[0] += 1
                        st[1], st[2] = min(st[1], date), max(st[2], date)
                        st[3].add(build)
    print(f"{len(files)} logs scanned in {inst.path}\n")
    for tag in TAGS:
        shapes = seen.get(tag, {})
        if not shapes:
            print(f"{tag}: never seen\n")
            continue
        first = min(v[1] for v in shapes.values())
        last = max(v[2] for v in shapes.values())
        builds = set().union(*(v[3] for v in shapes.values()))
        print(f"{tag}: {first} .. {last}, {len(builds)} builds, {len(shapes)} shapes")
        for s, (n, a, b, bs) in sorted(shapes.items(), key=lambda kv: -kv[1][0])[:3]:
            print(f"   {a}..{b} x{n} ({len(bs)} builds)  {s}")
        print()


if __name__ == "__main__":
    main()
