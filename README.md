# SC Fleet Telemetry

Live Star Citizen ship and crew status for your org. Each player runs a small agent on their gaming PC that reads the game's own telemetry. They get a cockpit dashboard for a second monitor or VR overlay, and the org gets a fleet view showing everyone at a glance: who's flying what (and who's aboard whose ship), in which mode, where, with which warnings. Click anyone to see their full dashboard. The fleet view is in the cockpit page itself, and on the org's hub for phones and other screens.

> **Not affiliated with Cloud Imperium Games.** Star Citizen is a trademark of Cloud Imperium Rights LLC. This project only reads what the game itself offers for this purpose: its local telemetry stream (switched on in `user.cfg`) and its `Game.log` text file. It doesn't touch game memory or Easy Anti-Cheat, never sends anything to the game, and has no world coordinates.

**Status:** the agent and the hub work and are tested against real recorded sessions; early days, expect changes. Windows agent only (that's where the game runs).

## How it fits together

- **Agent** (Windows, each player): reads the game's local telemetry gRPC stream and a few lines of `Game.log` (location, contracts, kills, quantum routes), turns them into a compact status, shows the cockpit view on `127.0.0.1`, and sends what the player shares to their org's hub.
- **Hub** (one Docker container per org): accounts and invites, the fleet page, and an API for bots and scripts. Each org runs its own; see [deploy/README.md](deploy/README.md).
- **Web**: one page, two homes. The agent serves the cockpit view, which also shows the fleet: the agent signs in to the hub with the PC's link and relays it. The hub serves the fleet page to browsers and phones.

Discord is optional: members join with invite links; a hub can also offer "Sign in with Discord" and keep members in step with a Discord role. Bots talk to the hub through its [integration API](docs/HUB_API.md).

## For players

You need [uv](https://docs.astral.sh/uv/) and this repo (a packaged `.exe` comes later).

```
uv sync --python 3.12
uv run python -m fleet_agent on              # switch the game's telemetry on (backs up user.cfg)
uv run python -m fleet_agent link <invite>   # the invite link from your org's admin
uv run python -m fleet_agent run --open      # cockpit view at http://127.0.0.1:8740, and sends to the fleet
```

Restart the game after `on`; it reads `user.cfg` at startup. `link` asks for your display name (your in-game handle by default).

**Fleet** in the cockpit view's top bar shows the whole fleet in the same page, and the **Wingmates** panel (Pilot and Combat layouts, or add it in Customize) keeps everyone's ship, mode, speed and altitude next to your own dashboard. **Open on the hub** in the fleet view, or `fleet_agent open`, opens the hub's fleet page in your browser, signed in.

**What you share** is up to you. Everything is on by default; anything switched off never leaves your PC:

```
uv run python -m fleet_agent share                  # list: status, ship, weapons, vitals, uec,
                                                    #       location, mission, combat
uv run python -m fleet_agent share --off vitals uec # stop sharing these
```

Whoever runs your org's hub can see what you share. `unlink` stops sending; **Your account** on the hub's fleet page can unlink PCs or delete your account and history.

**On your phone** (or any other device): on the hub's fleet page, open **Your account → Sign in on another device**. It shows a short code; on the phone, open the hub's address, choose "I have a code" and type it. The code works once, for 10 minutes. **Signed-in devices** on the same page lists every browser signed in as you; sign out a lost phone there, or all of them but the one you're on. If the hub offers Discord, "Sign in with Discord" works on any device too.

To undo the game setting: `uv run python -m fleet_agent off`. It restores `user.cfg` exactly.

## For org admins

Run a hub: [deploy/README.md](deploy/README.md). Docker, a domain, a reverse proxy with https, about ten minutes. The first start logs a one-time link that makes you admin; then create invite links for your members on the fleet page.

## The cockpit view

Without the game, replay real recordings:

```
uv run python -m fleet_agent run --replay --open            # the bundled recordings
uv run python -m fleet_agent run --replay captures/x.jsonl  # or your own capture
```

A timeline at the bottom has every event on it (seat changes, takeoff, landing, NAV/SCM, warnings, kills, contracts). Click a marker, use **Events** to pick one, or press ← / → to jump to the previous or next event. Space plays and pauses, Shift+← / → moves 10 s, `,` / `.` step one frame while paused. `--speed 4` starts it faster.

The sliders button (top right) customizes the dashboard: a theme from each ship maker (Drake, Anvil, Origin, Aegis and 12 more), dark or light, and whether it follows the ship you're in; layouts (Pilot, Combat, Explorer, Minimal); show, hide, resize and drag panels (including Wingmates, when linked to a fleet); HUD effects; units. See [docs/THEMES.md](docs/THEMES.md). `?compact=1` or **Compact** gives a narrow view for VR overlays (OVR Toolkit, XSOverlay). The cockpit view only accepts connections from the same PC.

## Development

Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 24 for the page.

```
uv sync --python 3.12
uv run pytest -q
uv run ruff check . && uv run ruff format --check .

cd web
npm install
npm run build        # the agent and hub serve web/dist
npm run dev          # live-reload on :5173, proxying to an agent on :8740
npm run check        # type check
```

The field reference (what the game actually sends): [docs/FIELDS.md](docs/FIELDS.md). The original design and its decisions: [docs/SC_FLEET_TELEMETRY_SPEC.md](docs/SC_FLEET_TELEMETRY_SPEC.md).

### Capturing telemetry

```
uv run python -m fleet_agent installs              # finds LIVE/PTU/... and shows on/off
uv run python -m fleet_agent probe                 # optional: is the game's server up?
uv run python tools/capture.py                     # records the session until Ctrl+C
```

The capture follows the game through loading screens and restarts, saves to the gitignored `captures/` folder with aUEC scrubbed (about 150 MB per hour), keeps the Game.log lines the agent understands, and lets you type a note to mark a moment. Then:

```
uv run python tools/summarize_capture.py captures/<file>.jsonl --timeline
uv run python tools/make_fixture.py captures/<file>.jsonl 8:20 10:30 <fixture-name>
```

Fixtures are committed and the repo is public, so scrub them: aUEC is scrubbed and tests check it; player names (in seat, kill and channel lines) you have to check by hand.

### Layout

```
agent/     Windows agent (fleet_agent)
hub/       the fleet hub (fleet_hub, Dockerfile)
deploy/    docker-compose.yml and how to run a hub
web/       the page: cockpit view and fleet page (Svelte 5)
shared/    the wire schema (Pydantic) and merge patches
tools/     capture, summarize_capture, make_fixture, replay, logscan, demo_fleet
fixtures/  scrubbed slices of real captures (gzipped JSONL)
docs/      field reference, hub API, themes, design spec
```

## License

MIT, see [LICENSE](LICENSE).
