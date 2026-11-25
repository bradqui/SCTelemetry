"""Build the cockpit demo's recording from the bundled fixtures.

    uv run python tools/demo_cockpit.py          # writes web/showcase/demo-cockpit.json

The same session ``starglance run --replay`` plays (every fixture, in order), run once
through the real agent pipeline and stored as what the page would have received: a
snapshot every STEP_MS (as merge patches, with a whole one every KEY_EVERY steps so the
page can seek), the events with their positions, and the replay timeline. The page plays
it back with the real replay bar (web/src/lib/demo-live.svelte.ts). Times are ms from
the start of the recording; the page adds its own clock. Fixtures are already scrubbed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "agent"), str(ROOT / "shared")]

from starglance.replay import FIXTURES_DIR, Recording, default_fixtures  # noqa: E402
from starglance.runtime import Pipeline  # noqa: E402
from starglance_shared import make_patch  # noqa: E402

STEP_MS = 100
KEY_EVERY = 100  # a whole snapshot every 10 s
OUT = ROOT / "web" / "showcase" / "demo-cockpit.json"


def main() -> None:
    rec = Recording.load(default_fixtures(FIXTURES_DIR))
    pipeline = Pipeline()
    events: list[dict] = []
    pipeline.subscribe(
        lambda kind, p: (
            kind == "event"
            and p.kind != "game_start"
            and events.append(json.loads(p.model_dump_json(by_alias=True)))
        )
    )
    chapter = 0
    steps: list[dict] = []
    prev: dict | None = None
    latest: dict | None = None
    next_ms = 0
    for i, pos in enumerate(rec.positions):
        c = rec.chapter_at(i)
        if c != chapter:  # the next recording: start fresh, keep the event list (as the agent does)
            pipeline.reset(clear_history=False)
            chapter = c
        t = int(pos * 1000)
        for line, quiet in rec.logs.get(i, ()):
            pipeline.on_log(line, t, quiet)
        pipeline.on_frame(rec.decode(i), t)
        if pipeline.latest is not None:
            latest = json.loads(pipeline.latest.model_dump_json(by_alias=True))
        while next_ms <= t:
            if latest is not None:
                k = len(steps)
                if k % KEY_EVERY == 0:
                    steps.append({"key": latest})
                else:
                    steps.append(make_patch(prev, latest) or {})
                prev = latest
            else:
                steps.append({})
            next_ms += STEP_MS
    index = rec.index()
    data = {
        "step_ms": STEP_MS,
        "key_every": KEY_EVERY,
        "index": index,
        "steps": steps,
        "events": events,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(
        f"{index['duration']:.0f} s, {len(index['chapters'])} chapters, {len(events)} events,"
        f" {len(steps)} steps: wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)"
    )


if __name__ == "__main__":
    main()
