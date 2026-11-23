# CLAUDE.md

Star Citizen org fleet telemetry: Windows agent → FastAPI hub → PWA + ButlerBot cog. The build spec is [docs/SC_FLEET_TELEMETRY_SPEC.md](docs/SC_FLEET_TELEMETRY_SPEC.md); read it before starting any phase.

## Hard rules (from the spec)

- Do **not** copy code from `TheBanjolorian/7hills-link`. It has no license, so implement from the documented behavior only.
- Agent local servers bind `127.0.0.1` only. There is no command path from the network to the game, ever.
- Everything is shared by default, but any category a member switches off never leaves the agent.
- Fixtures must be scrubbed of aUEC before they are committed. Raw captures go in the gitignored `captures/` folder.

## Development

- Python 3.12 via `uv` (`uv sync --python 3.12`, `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format .`). CI runs the same on Ubuntu and Windows.
- Agent code lives in `agent/fleet_agent/` (CLI: `uv run python -m fleet_agent --help`). Tools in `tools/`.
- Set `FLEET_TELEMETRY_HOME` to a scratch folder when experimenting, so the real `%LOCALAPPDATA%\FleetTelemetry` state isn't touched.
- Never switch telemetry on/off in Brad's real `user.cfg` without asking. Read-only commands (`installs`, `status`, `protoset`) are fine.
- Code map:
  - `shared/fleet_shared/models.py`: the wire schema (Python 3.11-safe; CI checks it).
  - `agent/fleet_agent/normalize.py` + `events.py`: raw frames to snapshots and events. Every behaviour has a fixture test in `tests/agent/test_normalize.py`.
  - `runtime.py` + `localserver.py`: the live pipeline and the 127.0.0.1 server.
  - `replay.py`: the fake game over gRPC (`ReplayServer`), plus `Recording` (frames, chapters, event index) and `Playhead` (play/pause/seek/step) for `run --replay`, which `runtime.ReplaySource` feeds straight into the pipeline. A jump (seek, step back, loop) resets the pipeline and the page clears; a new chapter resets the pipeline but keeps the event list.
- Develop without the game: `uv run python -m fleet_agent run --replay --open` (timeline with every event at the bottom of the page; `?customize` opens the Customize drawer on load). To exercise the gRPC path instead: `uv run python tools/replay.py` (port 2943) plus `uv run python -m fleet_agent run --game-port 2943`.
- Web UI: `web/`, Svelte 5 + Vite + TS. `web/src/lib/types.ts` mirrors the Python models, so change both together. The dashboard is panels (`web/src/lib/panels.ts`: registry, presets, layouts) drawn by `Dashboard.svelte`; each panel in `components/panels/` gets one `ctx` (`lib/context.ts`) and adapts to its own width with `@container panel` queries. Preferences (layout, accent, units) live in `lib/prefs.svelte.ts` (localStorage). TypeScript is pinned to 6.x because svelte-check doesn't support TS 7 yet. To check layouts without a browser tool, screenshot with headless Edge (`msedge --headless=new --screenshot=... --window-size=W,H --virtual-time-budget=4000 URL`); its minimum width is 500 px.
- The real schema is in [docs/FIELDS.md](docs/FIELDS.md). The normalizer must treat every field as optional: LIVE lacks hull/shields/master mode today, and CIG can change it in any patch.

## ButlerBot integration facts

ButlerBot is the public repo `bradqui/ButlerBot`. Its `CLAUDE.md` is the authority on the points below; these are summarized from it (2026-11-22):

- Red-DiscordBot **3.5.24**, discord.py 2.7.1, **Python 3.11**, Docker image `phasecorex/red-discordbot`, JSON Config storage, prefix `!`.
  → The cog, and anything in `shared/` that the cog imports, must run on **Python 3.11** (the spec suggests 3.12 for the agent and hub, which is fine).
- Custom cogs live in `data/cogs/CogManager/cogs/<cog>/` and deploy by `git pull` of the ButlerBot repo on the server, then `!reload`/`!load`. Dependencies go in the cog's `info.json` `requirements` and are installed with `!pipinstall`.
- Cog conventions: Red `Config` with a fixed identifier, `logging.getLogger("red.<cog>")`, cancel background tasks in `cog_unload`, cards and colors from the shared `_shared/butlerui.py` module (loaded by file path with `_load_butlerui()`), and a real prefix in user-facing hints (never a literal `[p]`).
- Tests there run on an offline harness with stubbed `redbot` (`tests/harness.py`), on GitHub Actions with Python 3.11.
- ButlerBot runs on the same host as the hub, in its own container. Its Docker setup isn't in Git; the network name is still open (spec §11).
- No Redis: the cog talks to the hub over its internal REST API and `/internal/events` WebSocket.

**Still undecided:** whether the `telemetry` cog ships inside the ButlerBot repo (matches how the server already deploys and gives it `butlerui`) or stays in this repo's `cog/` and gets copied or synced over.
