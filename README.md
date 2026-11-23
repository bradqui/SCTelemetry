# SC Fleet Telemetry

Live Star Citizen ship and crew status for our org: shown on each member's second monitor or VR overlay, on phones as a PWA, and in Discord through ButlerBot.

**Status:** Phase 0 (spike) done. The first real session was captured on LIVE on 2026-11-23. What the game sends is in [docs/FIELDS.md](docs/FIELDS.md), and test slices are in [fixtures/](fixtures/). Next is Phase 1: the normalizer, replay server and local view.

The full build spec is in [docs/SC_FLEET_TELEMETRY_SPEC.md](docs/SC_FLEET_TELEMETRY_SPEC.md).

## How it fits together

- **Agent** (Windows, per member): reads the game's local telemetry gRPC stream (`127.0.0.1:2942`), normalizes it, serves a local cockpit view, and pushes the shared fields outbound to the hub.
- **Hub** (FastAPI + SQLite, one Docker container behind Virtualmin's Apache): ingests agent data, serves the fleet PWA, and streams events to the cog over an internal WebSocket.
- **Web** (PWA): fleet board and member detail; the same bundle is the agent's local view.
- **Cog** (`telemetry`, Red-DiscordBot): `!fleet`, `!ready`, ops, and alerts in ButlerBot.

No world position, no remote control of anyone's game, and nothing that touches memory or Easy Anti-Cheat.

## Development

Requires [uv](https://docs.astral.sh/uv/). Python 3.12.

```
uv sync --python 3.12
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
```

## Capturing telemetry

On the gaming PC:

```
uv run python -m fleet_agent installs              # finds LIVE/PTU/... and shows on/off
uv run python -m fleet_agent on --channel LIVE     # backs up user.cfg, adds one setting
```

Restart the game if it's running; it reads `user.cfg` at startup. Then:

```
uv run python -m fleet_agent probe       # optional: is the server up?
uv run python tools/capture.py           # records the whole session until Ctrl+C
```

Then just play. The capture finds the port in `Game.log`, waits for the game, and keeps going through loading screens and game restarts. It saves to the gitignored `captures/` folder with aUEC scrubbed (about 150 MB per hour). Optionally, type a short note in the terminal and press Enter (e.g. `gear down`) to mark a moment.

Afterwards:

```
uv run python tools/summarize_capture.py captures/<file>.jsonl --timeline
uv run python tools/make_fixture.py captures/<file>.jsonl 8:20 10:30 <fixture-name>
```

To undo the setup: `uv run python -m fleet_agent off --channel LIVE`. It restores `user.cfg` exactly. The untouched original is also kept as `user.cfg.bak-<timestamp>`.

## Layout

```
agent/     Windows agent (fleet_agent package)
hub/       FastAPI service (planned)
web/       PWA source (planned)
cog/       Red cog: telemetry/ (planned)
shared/    Pydantic wire-schema models (planned)
tools/     capture, summarize, make_fixture (replay planned)
fixtures/  scrubbed slices of real captures (gzipped JSONL)
docs/      spec, field reference
```
