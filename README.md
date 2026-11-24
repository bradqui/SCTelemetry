# SC Fleet Telemetry

Live Star Citizen ship and crew status for our org: shown on each member's second monitor or VR overlay, on phones as a PWA, and in Discord through ButlerBot.

**Status:** Phase 1 (agent, local only) built, Phase 2 (hub and fleet board) built and tested locally, not yet deployed. The agent reads the game, normalizes it, serves a live local cockpit view, and sends to the hub once linked. Real field reference: [docs/FIELDS.md](docs/FIELDS.md). Deploying the hub: [deploy/README.md](deploy/README.md).

The full build spec is in [docs/SC_FLEET_TELEMETRY_SPEC.md](docs/SC_FLEET_TELEMETRY_SPEC.md).

## How it fits together

- **Agent** (Windows, per member): reads the game's local telemetry gRPC stream (`127.0.0.1:2942`) plus a few lines of its `Game.log` (quantum route and arrival), normalizes them, serves a local cockpit view, and pushes the shared fields outbound to the hub.
- **Hub** (aiohttp + SQLite, one Docker container behind Virtualmin's Apache): Discord sign-in, links agents, ingests their data, serves the fleet page, and streams events to the cog over an internal WebSocket.
- **Web** (PWA): fleet board and member detail; the same bundle is the agent's local view.
- **Cog** (`telemetry`, Red-DiscordBot): `!fleet`, `!ready`, ops, and alerts in ButlerBot.

No world coordinates, no remote control of anyone's game, and nothing that touches memory or Easy Anti-Cheat. The agent reads two things the game already writes for this kind of use: its local telemetry stream and its `Game.log` text file (location, contracts, kills, quantum routes). Each member can switch off any category they don't want shared: location, contracts, combat, vitals, aUEC and so on.

## Development

Requires [uv](https://docs.astral.sh/uv/). Python 3.12.

```
uv sync --python 3.12
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
```

Web UI (Node 24):

```
cd web
npm install
npm run build        # the agent serves web/dist
npm run dev          # live-reload dev server on :5173, proxying to a running agent on :8740
npm run check        # type check
```

## Running the agent

With the game (telemetry switched on, see below):

```
uv run python -m fleet_agent run --open      # local view at http://127.0.0.1:8740
```

Without the game, replaying real recordings:

```
uv run python -m fleet_agent run --replay --open            # all fixtures
uv run python -m fleet_agent run --replay captures/x.jsonl  # or your own capture
```

A timeline appears at the bottom of the page with every event on it (seat changes, takeoff, landing, NAV/SCM, warnings). Click a marker, use **Events** to pick one from a list, or press ← / → to jump a few seconds before the previous or next event. Space plays and pauses, Shift+← / → moves 10 s, and `,` / `.` step one frame while paused. `--speed 4` starts it faster.

Press the sliders button (top right) to customize the dashboard: pick a layout (Pilot, Combat, Explorer, Minimal), show, hide, resize and drag panels, choose an accent colour, switch HUD effects and the master caution banner, and use m/s or km/h. It's saved in your browser, separately for the full and compact views.

Add `?compact=1` to the URL, or press **Compact**, for a narrow view that fits a VR overlay (OVR Toolkit, XSOverlay). The local view only accepts connections from this PC.

To test the agent's gRPC path against a fake game instead: `uv run python tools/replay.py` (port 2943) and `uv run python -m fleet_agent run --game-port 2943 --open`.

## Joining the fleet

Link this PC once (a browser opens: sign in with Discord, check the code, confirm):

```
uv run python -m fleet_agent link
```

From then on `run` also sends your telemetry to the fleet (`--no-uplink` to stay local). The page at the hub shows everyone: a roster on the left (group it by ship, server or status) and the member you click on the right, with the same panels as your own view.

What you share:

```
uv run python -m fleet_agent share                  # list
uv run python -m fleet_agent share --off vitals uec # stop sharing these
uv run python -m fleet_agent share --on vitals      # share again
```

Everything is shared by default; anything switched off never leaves your PC. `unlink` stops sending and forgets the token; unlink a PC from the hub's page (your name → Your PCs) to revoke it there too.

To try the fleet without Discord or the game: see "Trying it without Discord" in [deploy/README.md](deploy/README.md).

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
hub/       the fleet hub (fleet_hub package, Dockerfile)
deploy/    docker-compose.yml and server setup
web/       the page: cockpit view (agent) and fleet board (hub)
cog/       Red cog: telemetry/ (planned)
shared/    Pydantic wire-schema models
tools/     capture, summarize, make_fixture, replay
fixtures/  scrubbed slices of real captures (gzipped JSONL)
docs/      spec, field reference
```
