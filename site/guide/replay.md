# Replaying recordings

Starglance can play recorded sessions instead of the live game: to try layouts and themes without loading in, or to look again at something that happened. The [live demo](https://bradqui.github.io/starglance/demo/cockpit.html) is exactly this, in your browser.

![The replay bar, with its list of events](/shots/replay-events.jpg)

## The timeline

The bar at the bottom has every event on it, coloured by kind: seat changes, takeoff and landing, NAV and SCM, quantum jumps, warnings, kills, contracts. Each recording is a chapter, named under the timeline.

- **Click a marker** to jump just before it, or drag anywhere on the timeline.
- **Events** lists them all by chapter; pick one to jump to it.
- **Speed**: half speed up to 8×.

| Key | Does |
|---|---|
| Space | play or pause |
| ← / → | previous or next event |
| Shift + ← / → | back or forward 10 seconds |
| `,` / `.` | one frame back or forward, while paused |

After a jump, the view starts fresh from that point, as if you'd just loaded in.

## Running a replay yourself

From a copy of the source code ([Development](https://github.com/bradqui/starglance#development)):

```
uv run python -m starglance run --replay --open            # the bundled recordings
uv run python -m starglance run --replay captures/x.jsonl  # your own capture
```

`--speed 4` starts it faster. Your own captures come from `tools/capture.py` while you play; see the [README](https://github.com/bradqui/starglance#capturing-telemetry).

A [problem report](/guide/problem-reports) can be replayed the same way: `run --replay` takes the report's `.zip`, and the moment that was marked shows on the timeline.
