# Starglance

**Your Star Citizen ship and crew, at a glance.**

Starglance reads the game's own telemetry on your PC and turns it into a cockpit dashboard for a second monitor, a tablet or a VR overlay: flight, ship, warnings, fuel, weapons, vitals, location, contracts. On its own, that's all it does: nothing leaves your PC.

Play with others? Join your org's fleet and everyone sees everyone at a glance: who's flying what (and who's aboard whose ship), in which mode, where, with which warnings, and anyone's full dashboard a click away. The fleet view is in your cockpit page, and on your org's own hub (a small self-hosted server) for phones and other screens.

> **Not affiliated with Cloud Imperium Games.** Star Citizen is a trademark of Cloud Imperium Rights LLC. This project only reads what the game itself offers for this purpose: its local telemetry stream (switched on in `user.cfg`) and its `Game.log` text file. It doesn't touch game memory or Easy Anti-Cheat, never sends anything to the game, and has no world coordinates.

**Status:** the agent and the hub work and are tested against real recorded sessions; early days, expect changes. Windows agent only (that's where the game runs).

## How it fits together

- **Agent** (Windows, each player): reads the game's local telemetry gRPC stream and a few lines of `Game.log` (location, contracts, kills, quantum routes), turns them into a compact status, shows the cockpit view on `127.0.0.1`, and sends what the player shares to their org's hub.
- **Hub** (one Docker container per org): accounts and invites, the fleet page, and an API for bots and scripts. Each org runs its own; see [deploy/README.md](deploy/README.md).
- **Web**: one page, two homes. The agent serves the cockpit view, which also shows the fleet: the agent signs in to the hub with the PC's link and relays it. The hub serves the fleet page to browsers and phones.

Discord is optional: members join with invite links; a hub can also offer "Sign in with Discord" and keep members in step with a Discord role. Bots talk to the hub through its [integration API](docs/HUB_API.md).

## For players

Download **starglance.exe** from the [latest release](https://github.com/bradqui/starglance/releases/latest) and double-click it. Your cockpit view opens in the browser (`http://127.0.0.1:8740`); keep the agent's window open while you play.

Then open **Settings → Agent** (the sliders button, top right):

1. **Game telemetry → Switch on**, then restart the game. It reads the setting at startup. Switching it off later puts the game's `user.cfg` back exactly as it was.
2. **Fleet**: paste the invite link from your org's admin and pick your display name (your in-game handle by default).
3. **What you share**: everything is on by default; switch off anything you'd rather keep to yourself.

Everything there is also on the command line (`starglance.exe --help`, or `uv run python -m starglance` from the source):

```
starglance on                 # switch the game's telemetry on (backs up user.cfg)
starglance link <invite>      # join with the invite link from your org's admin
starglance run --open         # cockpit view, and sends to the fleet
```

**Fleet** in the cockpit view's top bar shows the whole fleet in the same page, and the **Wingmates** panel (Pilot and Combat layouts, or add it in Customize) keeps everyone's ship, mode, speed and altitude next to your own dashboard. **Open on the hub** in the fleet view, or `starglance open`, opens the hub's fleet page in your browser, signed in.

**What you share** is up to you (Settings → Agent, or `starglance share --off vitals uec`). Anything switched off never leaves your PC. Whoever runs your org's hub can see what you share. The agent talks to the game on your PC and to your org's hub, nothing else: see [PRIVACY.md](PRIVACY.md). `unlink` stops sending; **Your account** on the hub's fleet page can unlink PCs or delete your account and history.

**On your phone** (or any other device): on the hub's fleet page, open **Your account → Sign in on another device**. It shows a short code; on the phone, open the hub's address, choose "I have a code" and type it. The code works once, for 10 minutes. **Signed-in devices** on the same page lists every browser signed in as you; sign out a lost phone there, or all of them but the one you're on. If the hub offers Discord, "Sign in with Discord" works on any device too.

To undo the game setting: Settings → Agent → Switch off, or `starglance off`. It restores `user.cfg` exactly.

**Code signing policy**: release builds of `starglance.exe` are signed: free code signing provided by [SignPath.io](https://about.signpath.io), certificate by [SignPath Foundation](https://signpath.org) (from the first release after the project is accepted). See [docs/CODE_SIGNING.md](docs/CODE_SIGNING.md) for what's signed, how it's built, and who approves it.

## For org admins

Run a hub: [deploy/README.md](deploy/README.md). Docker (a released image, `ghcr.io/bradqui/starglance-hub`), a domain, a reverse proxy with https, about ten minutes. The first start logs a one-time link that makes you admin; then create invite links for your members on the fleet page.

## The cockpit view

Without the game, replay real recordings:

```
uv run python -m starglance run --replay --open            # the bundled recordings
uv run python -m starglance run --replay captures/x.jsonl  # or your own capture
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

Releases (the exe, the hub image, signing): [docs/RELEASING.md](docs/RELEASING.md). The field reference (what the game actually sends): [docs/FIELDS.md](docs/FIELDS.md). The original design and its decisions: [docs/SC_FLEET_TELEMETRY_SPEC.md](docs/SC_FLEET_TELEMETRY_SPEC.md).

### Capturing telemetry

```
uv run python -m starglance installs              # finds LIVE/PTU/... and shows on/off
uv run python -m starglance probe                 # optional: is the game's server up?
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
agent/     Windows agent (starglance)
hub/       the fleet hub (starglance_hub, Dockerfile)
deploy/    docker-compose.yml and how to run a hub
web/       the page: cockpit view and fleet page (Svelte 5)
shared/    the wire schema (Pydantic) and merge patches
tools/     capture, summarize_capture, make_fixture, replay, logscan, demo_fleet
fixtures/  scrubbed slices of real captures (gzipped JSONL)
docs/      field reference, hub API, themes, design spec
```

## License

MIT, see [LICENSE](LICENSE).
