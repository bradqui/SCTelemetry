# CLAUDE.md

Star Citizen org fleet telemetry: Windows agent → FastAPI hub → PWA + ButlerBot cog. The build spec is [docs/SC_FLEET_TELEMETRY_SPEC.md](docs/SC_FLEET_TELEMETRY_SPEC.md); read it before starting any phase.

## Hard rules (from the spec)

- Do **not** copy code from `TheBanjolorian/7hills-link`. It has no license, so implement from the documented behavior only.
- Agent local servers bind `127.0.0.1` only. There is no command path from the network to the game, ever.
- Everything is shared by default, but any category a member switches off never leaves the agent.
- Fixtures must be scrubbed of aUEC before they are committed. Raw captures go in the gitignored `captures/` folder.

## ButlerBot integration facts

ButlerBot is the public repo `bradqui/ButlerBot`. Its `CLAUDE.md` is the authority on the points below; these are summarized from it (2026-11-22):

- Red-DiscordBot **3.5.24**, discord.py 2.7.1, **Python 3.11**, Docker image `phasecorex/red-discordbot`, JSON Config storage, prefix `!`.
  → The cog, and anything in `shared/` that the cog imports, must run on **Python 3.11** (the spec suggests 3.12 for the agent and hub, which is fine).
- Custom cogs live in `data/cogs/CogManager/cogs/<cog>/` and deploy by `git pull` of the ButlerBot repo on the server, then `!reload`/`!load`. Dependencies go in the cog's `info.json` `requirements` and are installed with `!pipinstall`.
- Cog conventions: Red `Config` with a fixed identifier, `logging.getLogger("red.<cog>")`, cancel background tasks in `cog_unload`, cards and colors from the shared `_shared/butlerui.py` module (loaded by file path with `_load_butlerui()`), and a real prefix in user-facing hints (never a literal `[p]`).
- Tests there run on an offline harness with stubbed `redbot` (`tests/harness.py`), on GitHub Actions with Python 3.11.
- ButlerBot's repo doesn't document Redis, the reverse proxy, or the Docker network name. Ask Brad (spec §11).

**Still undecided:** whether the `telemetry` cog ships inside the ButlerBot repo (matches how the server already deploys and gives it `butlerui`) or stays in this repo's `cog/` and gets copied or synced over.
