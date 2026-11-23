# SC Fleet Telemetry

Live Star Citizen ship and crew status for our org: shown on each member's second monitor or VR overlay, on phones as a PWA, and in Discord through ButlerBot.

**Status:** Phase 0 (spike). The `user.cfg` switch, install finder, schema extraction and capture tool are built; real frame captures are next. Real field list: [docs/FIELDS.md](docs/FIELDS.md).

The full build spec is in [docs/SC_FLEET_TELEMETRY_SPEC.md](docs/SC_FLEET_TELEMETRY_SPEC.md).

## How it fits together

- **Agent** (Windows, per member): reads the game's local telemetry gRPC stream on `127.0.0.1:50051`, normalizes it, serves a local cockpit view, and pushes the shared fields outbound to the hub.
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

## Phase 0: capturing real frames

On the gaming PC:

```
uv run python -m fleet_agent installs              # finds LIVE/PTU/... and shows on/off
uv run python -m fleet_agent on --channel LIVE     # backs up user.cfg, adds 3 keys, sets the env var
```

Then **fully quit the RSI Launcher** (including the tray icon), start the game and load in.

```
uv run python -m fleet_agent probe                 # is the server up? does it offer reflection?
uv run python tools/capture.py on-foot --seconds 30
uv run python tools/capture.py seated-pilot        # Ctrl+C to stop
```

Captures go to the gitignored `captures/` folder, with aUEC scrubbed. While recording, type a short note in the terminal and press Enter (e.g. `gear down`) to mark the moment in the file.

Suggested recordings: `on-foot`; `full-flight` (sit, power on, take off, SCM/NAV, quantum, land, leave seat); `shields-down` (power shields off/on); `combat` (taking damage); `seated-turret`; `seated-other`; `ship-swap`; `eva`.

To undo the setup: `uv run python -m fleet_agent off --channel LIVE`. It restores the keys exactly as they were. The untouched original is also kept as `user.cfg.bak-<timestamp>`.

## Planned layout

```
agent/     Windows agent
hub/       FastAPI service
web/       PWA source
cog/       Red cog: telemetry/
shared/    Pydantic wire-schema models
tools/     capture.py, replay.py
fixtures/  scrubbed captured frames (JSONL)
docs/      spec and ops notes
```
