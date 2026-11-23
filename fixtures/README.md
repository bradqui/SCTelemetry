# Fixtures

Slices of real telemetry captures, gzipped JSONL, aUEC scrubbed. Made with `tools/make_fixture.py` from `captures/session-20261123-101902.jsonl` (LIVE, 2026-11-23). Lines are `{"t", "label", "frame"}` or `{"t", "label", "note"}`.

| File | What happens |
|---|---|
| `on-foot` | Standing in a station |
| `on-foot-helmet` | Helmet on and off |
| `sit-power-takeoff-gear` | Sit in an M80 pilot seat, power cycle, ATC, takeoff, gear up/down/up |
| `cruise-nav-scm` | Cruise control, NAV to SCM and back (shield power and qdrv light flip) |
| `quantum-travel` | Spool and quantum jump; shields toggled around it |
| `landing-leave-seat` | Gear down, touchdown, engines off, leave seat |
| `combat` | Ship combat: `hit` light flashing, shields knocked down and back |
| `leave-seat-eva-reseat` | Leave the seat in space, EVA (vacuum, 0 g), back in the seat |
| `hangar-landing-refuel` | Planet hangar landing, repair/refuel/rearm, leave seat |
| `constellation-pilot-copilot-turret` | Constellation: pilot seat (`PILOT`), co-pilot (`PILOT`), right gunner (`CREW`) |

Summarize any of them: `uv run python tools/summarize_capture.py fixtures/<file> --timeline`.
