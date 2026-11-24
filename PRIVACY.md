# Privacy

SC Fleet Telemetry has two parts: the **agent**, which runs on your gaming PC, and the **hub**, which your org runs on its own server. Nobody else is involved. There is no central service, no analytics, no ads and no tracking. The project's authors don't receive anything from your agent or your org's hub.

## The agent (fleet-agent.exe)

**What it reads, on your PC only**

- The game's **telemetry stream**, which the game offers on your own PC (`127.0.0.1`) once telemetry is switched on: ship, flight, warning lights, fuel, power, weapons, your vitals, seat and role. If the game's server doesn't describe its messages, the agent reads them from `StarCitizen.exe` (read-only).
- The game's **Game.log** (read-only), for what the stream lacks: your location in game terms (armistice zone, jurisdiction, server, star system), quantum routes, contracts, kills and losses, injuries, the ship you're aboard, and your in-game handle.
- The game's **user.cfg**, only when you switch telemetry on or off (Agent settings, or `fleet_agent on` / `off`). It keeps a backup and restores the file exactly when you switch it off.

It never reads game memory, never touches Easy Anti-Cheat and never sends anything to the game.

**What it sends, and where**

- **Your cockpit view** is served on `127.0.0.1` only and accepts connections from this PC only.
- **To your org's hub, and nowhere else**, once you join a fleet. That's the address in the invite link from your org's admin. It sends:
  - when you join: your display name and your PC's name, so you can tell your PCs apart;
  - while it runs: what you choose to share (Agent settings, or `fleet_agent share`). The categories are status (in game, on foot or seated, your seat, your in-game handle), ship, weapons, vitals, uec, location, mission and combat. Everything is on by default. Anything you switch off never leaves your PC.
- **Update notices** come from your org's hub, which says which agent version is current. The agent doesn't contact GitHub or anyone else to check.

If you never join a fleet, the agent sends nothing anywhere.

**What it stores on your PC**

- The key that links this PC to your org's hub, in Windows Credential Manager.
- Its settings (hub address, what you share, your display name) and caches in `%LOCALAPPDATA%\FleetTelemetry`.
- Recordings, only if you run the capture tool yourself (`tools/capture.py`, from the source code). They stay in a local folder, with aUEC amounts removed.

**Stopping**

- To stop sharing something, switch it off in Agent settings.
- To stop sending anything, use **Leave the fleet** (or `fleet_agent unlink`). That also deletes the key from Credential Manager.
- To switch the game's telemetry off, use Agent settings or `fleet_agent off`.
- To remove the agent, delete `fleet-agent.exe` and the folder `%LOCALAPPDATA%\FleetTelemetry`. It doesn't install anything else.

## The hub (your org's server)

**Whoever runs your org's hub can see everything you share.** The hub keeps:

- your account: display name; your Discord ID and avatar if you connect Discord;
- your linked PCs: name, when last seen, and a hash of each PC's key;
- the browsers signed in as you: a rough device name ("Safari on iPhone"), how and when they signed in, and when they were last active;
- fleet events (seat changes, quantum jumps, contracts, kills…) for 30 days, by default;
- live state (what you share right now) in memory only, while you're online.

Org members see the fleet page. The org's admins can also manage members and invites, and can create API keys for bots, which can read the same fleet information.

On the hub's fleet page, **Your account** lets you unlink PCs, sign out devices and delete your account. Deleting your account removes your history from the hub.

## Questions

Open an issue at https://github.com/bradqui/SCTelemetry/issues. For your org's data, ask whoever runs your hub.
