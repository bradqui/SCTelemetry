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
