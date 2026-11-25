# Privacy

Starglance has two parts: the **agent** (the app on your gaming PC) and the **hub** (your org's own server). Nobody else is involved: no central service, no analytics, no ads, no tracking. The project's authors receive nothing from your agent or your org's hub.

The full policy, with every file and setting, is [PRIVACY.md](https://github.com/bradqui/starglance/blob/main/PRIVACY.md). In short:

## On your PC

**It reads**, on your PC only:

- the game's telemetry stream, on `127.0.0.1`, once you switch it on;
- the game's `Game.log`, read-only: location, quantum routes, contracts, kills and losses, injuries, the ship you're aboard, your handle;
- the game's `user.cfg`, only when you switch telemetry on or off (it backs it up and restores it exactly).

It never reads game memory, never touches Easy Anti-Cheat, and never sends anything to the game.

**It sends**:

- your cockpit view, to this PC only (and, if you switch on *Show on other devices*, to devices you pair on your home network);
- to the hubs of the fleets you join, and nowhere else: your display name and PC's name when you join, then only what you choose to share with each fleet;
- a question to GitHub every few hours: which version is the latest (nothing about you; you can switch it off);
- update downloads from GitHub, when you update;
- a problem report, only when you click Send, to the fleet you pick.

If you never join a fleet, the agent sends nothing anywhere.

**It keeps**, in `%LOCALAPPDATA%\Starglance`: its settings, your dashboard layout, the last 30 minutes of game data for problem reports (aUEC removed; switch it off any time), and the key that links your PC to a hub (in Windows Credential Manager).

## On your org's hub

**Whoever runs your org's hub can see everything you share.** The hub keeps your account (display name; Discord ID and avatar if you connect Discord), your linked PCs, the browsers signed in as you, fleet events for 30 days, problem reports you sent for 30 days, and your live state in memory only while you're online.

**Your account** on the fleet page lets you unlink PCs, sign out devices, delete your problem reports and delete your account, which removes your history from the hub.

## Stopping

- Stop sharing something: switch it off under **Settings → Agent → What you share**.
- Leave a fleet: **Leave**, or `starglance unlink`.
- Switch the game's telemetry off: **Settings → Agent**, or `starglance off`.
- Remove Starglance: switch off *Start with Windows*, then delete `starglance.exe` and `%LOCALAPPDATA%\Starglance`. It installs nothing else.
