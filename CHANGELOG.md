# Changelog

What changed in each release of Starglance: the app (`starglance.exe`) and the hub. They share one version number; update the hub along with the app.

Each release's notes on GitHub, and its announcement, come from its section here (see [docs/RELEASING.md](docs/RELEASING.md)).

## 0.10.9 (2026-11-28)

The fleet page and *Show on other devices* on a phone's Home Screen, like an app.

- **Add it to your Home Screen** and it opens full screen with the Starglance icon: on iPhone and iPad, **Share → Add to Home Screen**; on Android, **Install app** in Chrome's menu. Android installs only https pages, so on *Show on other devices* (a plain `http://` address) it adds a shortcut instead, which opens in Chrome.
- On a phone, the page keeps clear of the notch and the home bar, its status bar follows your colour theme, text fields no longer zoom in on iPhone, and small buttons are easier to tap.

## 0.10.8 (2026-11-27)

Joining a fleet now starts in your browser, with nothing to copy or paste.

### Hub

- **Sign in, then set up Starglance from the page.** Open your org's link (an invite, or the hub's address if your org lets its Discord members join), join with Discord or a name, and the page walks you through it: **Download**, **Open it**, **Link this PC**. It tells you when your PC is linked. **Skip for now** if you only want to watch.
- With **Holders of the member role can join without an invite** on, the sign-in page leads with **Sign in with Discord**: post the hub's address in your Discord and that's all anyone needs.
- Another PC later: open the hub's `/setup` page on it.

### App

- **Link this PC** on your fleet's page opens Starglance, which asks you to confirm (the fleet, its address, your name) and can switch on the game's telemetry in the same click. Starglance registers itself for these links when it starts.
- Settings → Agent → Fleet explains this instead of asking for a link; you can still enter the hub's address (or an invite) there.
- Settings → Agent no longer gets stuck on "Loading…" when two installs share a channel (Star Citizen on two drives).

## 0.10.7 (2026-11-26)

- **A new logo**: the Starglance wings, a star in a diamond between two sets of wings. You'll see it in the system tray, on `starglance.exe`, in the cockpit and fleet pages, and on the hub. It follows your colour theme in the app.

## 0.10.6 (2026-11-26)

### Hub

- **Admins set up Discord sign-in themselves**, under Admin → Settings → Discord: your org's own Discord application, server and member role, with the redirect to add and a short guide. Nobody needs to edit the hub's settings file any more, so this works for hubs someone else runs for you. The client secret is checked with Discord when you save, and never shown again. `DISCORD_*` settings in `.env` still work, as defaults.
- **Download everything** leaves out Discord credentials: the org's client secret and members' Discord sign-in tokens.

## 0.10.5 (2026-11-26)

### Hub

- **Download everything** (Admin → Settings): the hub's whole database as one file, as a backup or to move your org to another hub.
- **Hubs run for an org by someone else**: the sign-in and join pages say who hosts the hub, and the org's admins can ask the host to close the org.

## 0.10.4 (2026-11-25)

### Hub

- Busy fleets: the hub works out each roster change once for every open fleet page, instead of once per page.
- `tools/loadtest.py` estimates whether your server can handle your org.

## 0.10.3 (2026-11-25)

- A **Wallet** tile.
- The G gauge no longer loops round on big jumps.

## 0.10.2 (2026-11-25)

- Contracts keep every objective, each with its own state, instead of only the last one.
- **aUEC earned** counts from your balance, so hauling payouts are no longer missed.

## 0.10.1 (2026-11-25)

- The dashboard and fleet pages fill 1440p and 4K screens, and are tidier when narrow.

## 0.10.0 (2026-11-25)

- New instruments and the **Deep Space** house theme, with instrument styles per ship maker and a full-height altitude tape.
- Flight shows climb rate and G at the speed dial's scale.
- Flight and Ship side by side, with their history under the gauges.
- Fleet cards get gauges, and you can follow a member's flight.

## 0.9.0 (2026-11-25)

- **Where you are**: the landing area and the planet or moon you're at, named from the game's own files.

## 0.8.0 (2026-11-25)

- Mark a moment from a tablet or phone.
- Fleet cards show each member's last arrival.
- A new Hull & shields ring.
- Releases are unsigned for now, and each `starglance.exe` comes with a build attestation you can check.

## 0.7.0 (2026-11-24)

- **Problem reports**: mark a moment while you play, then send it to your fleet's admins or as a GitHub issue.

## 0.6.4 (2026-11-24)

- **Check now** for updates.

## 0.6.3 (2026-11-24)

- A quantum trip counts as one jump, however many legs it has.

## 0.6.2 (2026-11-24)

- A fleet feed, keep-awake, a regular update check, and resizing without a title bar.

## 0.6.1 (2026-11-24)

- "Connection lost" no longer flickers for fleet members who aren't in game.

## 0.6.0 (2026-11-24)

- **Self-update**: one click on Update (or automatically) replaces the app in place.

## 0.5.0 (2026-11-24)

- **Header alerts**: choose which warning lights show in your top bar and the fleet header.
- **Show on other devices**: the cockpit view on your home network, view only.
- Hub: runs as its own user in Docker, with per-visitor rate limits.

## 0.4.0 (2026-11-24)

- **Several fleets at once.**
- Fleet cards stay put: A to Z, or your own order.
- No title bar by default.

## 0.3.0 (2026-11-24)

- `starglance.exe` is a Windows app: its own window, and an icon in the system tray.
- Optional: no title bar, always on top, and Start with Windows (in Settings).

## 0.2.0 (2026-11-24)

- The first release: the cockpit view of your own ship from the game's telemetry, and fleets, where your org sees each other through its own hub.
