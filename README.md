# Starglance

**Your Star Citizen ship and crew, at a glance.**

**[📖 Docs and guide](https://bradqui.github.io/starglance/)** · **[▶ Live demo: cockpit view](https://bradqui.github.io/starglance/demo/cockpit.html)** · **[▶ Live demo: fleet page](https://bradqui.github.io/starglance/demo/)** · **[⬇ Download](https://github.com/bradqui/starglance/releases/latest)**

Starglance reads the game's own telemetry on your PC and turns it into a cockpit dashboard for a second monitor, a tablet or a VR overlay: flight, ship, warnings, fuel, weapons, vitals, location, contracts. On its own, that's all it does: nothing leaves your PC.

Play with others? Join your org's fleet and everyone sees everyone at a glance: who's flying what (and who's aboard whose ship), in which mode, where, with which warnings, and anyone's full dashboard a click away. The fleet view is in your cockpit page, and on your org's own hub (a small self-hosted server) for phones and other screens.

> **Not affiliated with Cloud Imperium Games.** Star Citizen is a trademark of Cloud Imperium Rights LLC. This project only reads what the game itself offers for this purpose: its local telemetry stream (switched on in `user.cfg`) and its `Game.log` text file. It doesn't touch game memory or Easy Anti-Cheat, never sends anything to the game, and has no world coordinates.

**Status:** the agent and the hub work and are tested against real recorded sessions; early days, expect changes. Read [Know before you use it](#know-before-you-use-it) for what the game does and doesn't send. Windows agent only (that's where the game runs).

## How it fits together

- **Agent** (Windows, each player): reads the game's local telemetry gRPC stream and a few lines of `Game.log` (location, contracts, kills, quantum routes), turns them into a compact status, shows the cockpit view on `127.0.0.1` (and, if you switch it on, view only to devices you pair on your home network), and sends what the player shares to their org's hub.
- **Hub** (one Docker container per org): accounts and invites, the fleet page, and an API for bots and scripts. Each org runs its own; see [deploy/README.md](deploy/README.md).
- **Web**: one page, two homes. The agent serves the cockpit view, which also shows the fleet: the agent signs in to the hub with the PC's link and relays it. The hub serves the fleet page to browsers and phones.

Discord is optional: members join with invite links; a hub can also offer "Sign in with Discord" and keep members in step with a Discord role. Bots talk to the hub through its [integration API](docs/HUB_API.md).

## For players

Download **starglance.exe** from the [latest release](https://github.com/bradqui/starglance/releases/latest) and double-click it. It isn't code-signed, so Windows may warn the first time: choose **More info → Run anyway** (to check the file first, see [docs/CODE_SIGNING.md](docs/CODE_SIGNING.md)). Starglance opens in its own window, with an icon in the system tray: closing the window keeps it running there (right-click the icon for Fleet, Settings, *Always on top*, *Hide the title bar*, *Start with Windows*, or Quit). Starting it again just brings the window back. With the title bar hidden, drag the window by its top bar; minimize, maximize and close move there. The same view is at `http://127.0.0.1:8740` for a browser, a second screen or a VR overlay.

**Updating:** when a new version is out, an **Update** button appears in the top bar (Starglance asks this project's GitHub page when it starts and every few hours, and your fleet's hub says so too). Heard about a release before Starglance has? **Settings → Agent → Updates → Check now**. Click it: Starglance downloads the new version from this project's releases, checks it, and restarts in a few seconds, with your settings as they were. **Settings → Agent → Updates → Update automatically** does it by itself while the game isn't running. Switched off **Check for new versions**? Then only your fleet's hub tells it, or the [releases page](https://github.com/bradqui/starglance/releases).

Then open **Settings → Agent** (the sliders button, top right):

1. **Game telemetry → Switch on**, then restart the game. It reads the setting at startup. Switching it off later puts the game's `user.cfg` back exactly as it was.
2. **Fleet**: paste the invite link from your org's admin and pick your display name (your in-game handle by default). Play with more than one org? **Join another fleet** with the other org's invite: Starglance sends to each, and the Fleet view and Wingmates panel have a picker.
3. **What you share**, per fleet: everything is on by default; switch off anything you'd rather keep to yourself, for that org. A fleet's switch pauses sending to it without leaving.

**On a tablet or another PC at home:** in **Settings → Agent → Other devices**, switch on *Show on other devices* and choose **Pair a device**. On the device, open the address shown (like `http://192.168.1.20:8741`) and type the code, or scan the QR code. The device then shows the cockpit view and the fleet, view only: it can't change settings or reach the game. It's off until you switch it on, only paired devices get in, and you can remove one at any time. Windows asks once whether Starglance may use your network: allow it on private networks. It's plain HTTP, so use it on your home network, not on public Wi-Fi.

Everything there is also on the command line, from a terminal (`starglance.exe --help`, or `uv run python -m starglance` from the source):

```
starglance on                 # switch the game's telemetry on (backs up user.cfg)
starglance link <invite>      # join with the invite link from your org's admin
starglance run --open         # cockpit view, and sends to the fleet
```

`starglance.exe` is a windowed app, so in PowerShell or cmd the prompt can come back before its output: `start /wait starglance.exe installs` waits for it.

**Fleet** in the cockpit view's top bar shows the whole fleet in the same page, and the **Wingmates** panel (Pilot and Combat layouts, or add it in Customize) keeps everyone's ship, mode, speed and altitude next to your own dashboard. **Open on the hub** in the fleet view, or `starglance open`, opens the hub's fleet page in your browser, signed in.

**What you share** is up to you (Settings → Agent, or `starglance share --off vitals uec`). Anything switched off never leaves your PC. Whoever runs your org's hub can see what you share. The agent talks to the game on your PC and to your org's hub, nothing else: see [PRIVACY.md](PRIVACY.md). `unlink` stops sending; **Your account** on the hub's fleet page can unlink PCs or delete your account and history.

**On your phone** (or any other device): on the hub's fleet page, open **Your account → Sign in on another device**. It shows a short code; on the phone, open the hub's address, choose "I have a code" and type it. The code works once, for 10 minutes. **Signed-in devices** on the same page lists every browser signed in as you; sign out a lost phone there, or all of them but the one you're on. If the hub offers Discord, "Sign in with Discord" works on any device too. To keep a phone or tablet's screen on beside the game, tick **Keep the screen awake** in the page's settings (on iPhone and iPad, iOS 18.4 or later when it's on the Home Screen).

To undo the game setting: Settings → Agent → Switch off, or `starglance off`. It restores `user.cfg` exactly.

**Code signing:** release builds of `starglance.exe` aren't code-signed. Each one is built by this repository's release workflow on GitHub, which records a build attestation for it: `gh attestation verify starglance.exe --repo bradqui/starglance` shows the tag and commit it was built from. If your antivirus flags it, that's a false positive common with PyInstaller programs; [docs/CODE_SIGNING.md](docs/CODE_SIGNING.md) says how to check the file and report it.

## For org admins

Run a hub: [deploy/README.md](deploy/README.md). Docker (a released image, `ghcr.io/bradqui/starglance-hub`), a domain, a reverse proxy with https, about ten minutes. The first start logs a one-time link that makes you admin; then create invite links for your members on the fleet page.

## The cockpit view

Without the game, replay real recordings:

```
uv run python -m starglance run --replay --open            # the bundled recordings
uv run python -m starglance run --replay captures/x.jsonl  # or your own capture
```

A timeline at the bottom has every event on it (seat changes, takeoff, landing, NAV/SCM, warnings, kills, contracts). Click a marker, use **Events** to pick one, or press ← / → to jump to the previous or next event. Space plays and pauses, Shift+← / → moves 10 s, `,` / `.` step one frame while paused. `--speed 4` starts it faster.

The sliders button (top right) customizes the dashboard: a theme from each ship maker (Drake, Anvil, Origin, Aegis and 13 more), dark or light, and whether it follows the ship you're in; layouts (Pilot, Combat, Explorer, Minimal); show, hide, resize and drag panels (including Wingmates, when linked to a fleet); HUD effects; units. See [docs/THEMES.md](docs/THEMES.md). `?compact=1` or **Compact** gives a narrow view for VR overlays (OVR Toolkit, XSOverlay). The cockpit view only accepts connections from the same PC.

## Know before you use it

Starglance is a fan-made tool built on data the game doesn't promise to keep. We make a best effort to keep up with the game and fix things as we learn more, but some of what you see is a good guess, and any patch can change it.

**The game can change under it.**
- **The telemetry stream is an undocumented game feature.** It's off unless switched on in the game's `user.cfg`, and CIG can change, rename or remove it in any patch. Starglance re-reads the stream's layout whenever the game's exe changes and treats every field as optional, so a change should leave gaps rather than crash it. Gaps can still last until we update.
- **`Game.log` isn't an interface either.** Location, contracts, kills and losses, quantum routes and who's aboard which ship come from its text lines, and CIG can reword them at any time. When that happens, those parts go quiet until Starglance learns the new wording.

**What the game doesn't send today** (Star Citizen LIVE, as of November 2026):
- **Hull health, shield levels and the master mode (NAV/SCM) aren't in the stream.** NAV/SCM is worked out from the quantum drive light and shield power. Hull and shields show the warning lights and power state, not percentages.
- **The COOL light is never lit by the game,** so Starglance shows it from whether the coolers have power.
- **Seat events are unreliable.** Seating is worked out from the state instead. Ship data arrives about 5 seconds after you sit down, after the animation.

**What's inferred, and can be wrong:**
- **Quantum travel is the biggest guess.** The game sends no "in quantum" signal at all, so Starglance works it out from three things together: the THR warning light coming on, the quantum drive being lit (NAV mode), and the speed and G-force freezing while you travel. The jump ends when the light clears, G-force comes back or the speed starts moving again. That means:
  - A jump can start or end a moment late on the dashboard.
  - Each leg of a multi-leg route counts as its own jump.
  - Ships that don't send the THR light fall back to an older, rougher rule: speed frozen while the heading moves, or a plotted route with the drive lit. It can mistake sitting still, spooled with a route plotted, for a jump, and it can miss a leg.
  - The destination comes from `Game.log`'s route lines, so if the log wording changes, jumps still show but the destination goes blank.
- **Who's aboard a ship** comes from its comms channel. The game doesn't always log leaving one, so you can show as aboard a ship you've left until something else ends it: another channel, a server change, death or a new game.
- **On foot and EVA** flicker around airlocks; Starglance smooths that over, so changes can show up a moment late.

**Other things to know:**
- **Don't fly by it.** It's a second screen, not a replacement for the game's own HUD, and it can lag or be wrong.
- **Not endorsed by CIG.** It only uses what the game offers on your PC: no game memory, no Easy Anti-Cheat, nothing sent to the game. CIG hasn't approved it, though, so using it is your call. The software comes as is, without warranty (MIT license).
- **In a fleet, whoever runs your org's hub sees everything you share** ([PRIVACY.md](PRIVACY.md)). Everyone else sees only what you share, when you're online.

**Something looks wrong?** Starglance keeps the last 30 minutes of what the game sent, on your PC only, so you can report it afterwards. Flag the moment with the flag button in the top bar (or a hotkey from inside the game: **Settings → Agent → Problem reports**), then click **⚑ marked** in the top bar, or **Report a problem** in that section or the tray menu. Pick the moment, say what happened, and read the report (names, IDs and addresses are taken out). Then **Send to your fleet's admins**, through the hub you already use, or **Save for a GitHub issue**: the file goes to Downloads and **Open a GitHub issue** opens the form filled in, ready for it (issues are public, and need a free GitHub account). Admins find reports under **Admin → Reports** on the hub's page, and can forward one to GitHub the same way. The details of what the game sends, and what we've seen it do, are in [docs/FIELDS.md](docs/FIELDS.md).

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

Releases (the exe, the hub image, signing) and the docs site: [docs/RELEASING.md](docs/RELEASING.md). The field reference (what the game actually sends): [docs/FIELDS.md](docs/FIELDS.md). The design and its decisions: [docs/SPEC.md](docs/SPEC.md). Contributing: [CONTRIBUTING.md](CONTRIBUTING.md).

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
