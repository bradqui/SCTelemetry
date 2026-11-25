# Starglance: design

The design record: what Starglance is for, how it's built, and the decisions behind it. Section numbers are stable (code comments cite them, e.g. "spec §4"); later decisions (§11) override earlier sections. What the game really sends is in [FIELDS.md](FIELDS.md); the hub's API for bots is in [HUB_API.md](HUB_API.md).

## 1. Goal

Let Star Citizen players see their own live status, and, if they play in an org, each other's:

1. **Their own second monitor, tablet or VR overlay:** a full-rate cockpit view of their own ship and character.
2. **The fleet:** everyone in the org at a glance (ship, mode, location, warnings), in the cockpit view or on any browser.
3. **Bots and other tools:** an integration API on the org's hub (Discord bots, dashboards).

Data comes from Star Citizen's local game telemetry server (unofficial, see §2) and its `Game.log`. Each player runs a small Windows **agent** that reads their game, shows the cockpit view, and, in a fleet, sends what they choose to share to their org's **hub**, which the org runs itself.

### Non-goals
- No world coordinates or map: the game doesn't expose them (§2.5). Location in game terms (zone, jurisdiction, server, star system, quantum destination) comes from Game.log (decision 10).
- No remote control of anyone's game. Game actions, if ever built, are **local only** (§7).
- No memory reading, injection, or anything touching Easy Anti-Cheat.

---

## 2. The data source: Star Citizen local game telemetry

Community reference: https://github.com/TheBanjolorian/7hills-link/blob/main/docs/TELEMETRY.md. It has **no license**: don't copy its code; Starglance implements the documented behaviour independently. **CIG may change any of this in any patch.**

### 2.1 Transport
- **gRPC**, plaintext, on `127.0.0.1` only, no auth. The port (2942 on LIVE so far) is announced in `Game.log`; the agent reads it from there.
- Service `sc.game.telemetry.v1.GameTelemetryService`:

| Method | Type | Notes |
|---|---|---|
| `TelemetryStream` | server streaming | frames at ~17/s, only once loaded into the game |
| `ListTriggerableActions` | unary | not on LIVE so far |
| `TriggerGameAction` | unary | not on LIVE so far |

### 2.2 Switching it on
- One line in the channel's `user.cfg` (`...\StarCitizen\<CHANNEL>\user.cfg`; LIVE, PTU, EPTU, TECH-PREVIEW, HOTFIX): `grpc.client.server.enabled = 1`. Read at startup: restart the game (not the launcher).
- The agent's switch (Settings → Agent, or `starglance on` / `off`) backs the file up first, edits idempotently (updates its own key in place, keeps everything else), and switching off restores the file exactly.
- Installs are found from the usual paths and the launcher's records, with a manual path as fallback.

### 2.3 The message definitions
The `.proto` files aren't published and the server has no reflection. The agent extracts them from `StarCitizen.exe` (the serialized `FileDescriptorProto`s around `sc/game/telemetry`), validates them, builds message classes at runtime, and caches the result keyed on the exe, so it re-extracts after every patch (`starglance/protoset.py`). It also writes a `.protoset` for `grpcurl` when debugging.

### 2.4 Frame contents
The real schema, field by field, with what's been observed in play: [FIELDS.md](FIELDS.md). The normalizer treats every field as optional.

### 2.5 Known gaps
Today (LIVE, November 2026) the stream has **no hull health, shield levels or master mode (NAV/SCM)**, and no world position, doors, per-component damage, other players or targets. Several values are inferred instead (NAV/SCM, quantum travel, seat changes): FIELDS.md has the details and the evidence, and the README's *Know before you use it* says what that means for players.

### 2.6 Game actions
Community notes describe ~112 triggerable actions (key-press-like, can't set values, each returning a status such as `OK`, `FILTERED` or `MAP_INACTIVE`). LIVE doesn't offer them so far. See §7 for the rules if they're ever used.

---

## 3. Architecture

```
┌──────────── Player's PC (Windows) ─────────────────────────────────┐
│ StarCitizen.exe ──gRPC, 127.0.0.1──▶ Agent ◀── Game.log (read-only)  │
│                                        ├─ cockpit view, 127.0.0.1    │
│                                        │  (opt-in: view only to      │
│                                        │   paired devices, decision 21)│
│                                        └─ uplink (WSS, outbound only)│
└─────────────────────────────────────────┼──────────────────────────┘
                                          ▼
┌──────────── The org's server ──────────────────────────────────────┐
│ Reverse proxy with https (any: Caddy, nginx, Apache, Cloudflare)     │
│   └─▶ Hub container on 127.0.0.1 (aiohttp, SQLite on a volume)       │
│        ├─ agents /ws/agent · browsers /ws/view, pages, /api/*        │
│        ├─ integrations /api/v1/* (API keys)                          │
│        └─ live state in memory, accounts and 30 days of events       │
└──────────────────────────────────────────────────────────────────────┘
   Bots and tools anywhere ──https──▶ /api/v1 (HUB_API.md)
```

Key principles:
- **Agents only connect outbound.** Players never open ports.
- **The agent normalizes** raw frames into Starglance's own compact schema (§4): the hub never sees raw game data, which keeps CIG's changes in the agent.
- **Privacy is enforced at the agent:** anything a player doesn't share is never sent.
- **No command path from the network to the game.** Ever.

### 3.1 Tech
| Component | Stack |
|---|---|
| Agent | Python 3.12: `grpcio`/`protobuf`, `aiohttp` (local server and uplink), `keyring` (Windows Credential Manager). The Windows app: `pywebview` (Edge WebView2) and `pystray`. Packaged with **PyInstaller** into one `.exe` by GitHub Actions. |
| Hub | Python 3.12, **aiohttp** and the standard library's `sqlite3` (decision 14). Discord sign-in is optional (decision 15). One Docker image. |
| Web UI | **Svelte 5 + Vite + TypeScript**, hand-written CSS with design tokens. One bundle, served by the agent (cockpit view) and the hub (fleet page). |
| Shared | `starglance_shared`: Pydantic models for the wire schema (§4) and the merge patches; Python 3.11-safe so bots can use it. |

### 3.2 Repo layout
```
agent/       the Windows agent (starglance): game reader, normalizer, cockpit server, uplink, app
hub/         the hub (starglance_hub) and its Dockerfile
shared/      the wire schema (starglance_shared)
web/         the page (Svelte), built into web/dist
deploy/      docker-compose.yml, .env.example, how to run a hub
packaging/   the PyInstaller spec for starglance.exe
tools/       capture.py (record a session), replay.py (a fake game from a recording), demo_fleet.py
fixtures/    recorded sessions, scrubbed of aUEC and player names
docs/        this design, FIELDS.md, HUB_API.md, RELEASING.md, CODE_SIGNING.md, THEMES.md
.github/     tests on every push; releases on v* tags
```

---

## 4. Wire protocol (agent → hub)

WebSocket at `wss://<hub>/ws/agent`, JSON, `Authorization: Bearer <PC token>`. Every message has `v` (schema version) and `t` (ms epoch). The models are in `shared/starglance_shared/models.py`.

```jsonc
// on connect: who, which game channel, what's shared
{"type":"hello","v":1,"agent_version":"0.6.0","channel":"LIVE","share":["status","ship","weapons","vitals","uec","location","mission","combat"]}

// a full snapshot on connect and every 30 s; in between, merge patches of what
// changed ("delta"), up to 10 Hz while in game (decision 13)
{"type":"snapshot","v":1,"t":0,"status":{...},"ship":{...},"weapons":{...},"vitals":{...},"location":{...},...}
{"type":"delta","v":1,"t":0,"patch":{"ship":{"flight":{"speed":212}}}}

// events immediately: seat changes, takeoff/landing, warnings, quantum jumps, contracts, kills...
{"type":"event","v":1,"t":0,"kind":"warning_on","data":{...}}

// when nothing else is sent (game closed)
{"type":"heartbeat","v":1,"t":0,"in_game":false}
```

Categories a player switched off are removed before anything is sent (`apply_sharing`, `event_shared`).

Hub → agent: `welcome` on connect (the member, and the current agent version, used for update notices); `resync` asks for a full snapshot; `error` with `version` or `revoked` is final. Agents may send up to 40 messages/s and 64 KB per message.

Hub → browsers (`/ws/view`): `hello`, the `roster` (a rounded summary of every member), recent `history`, then `roster_delta` and `event`; for the member a page has open (`focus`), `member` and `member_delta`. All at up to 10 Hz; summaries are rounded so a member sitting still costs nothing. Measured: a full snapshot is about 1.7 KB, a delta about 130 B.

UDP was considered and rejected (decision 13).

---

## 5. Identity, linking, auth

### 5.1 Accounts and invites
- Members are the hub's own accounts: a random id, a display name, a role (`member` or `admin`). No passwords anywhere.
- **First admin:** a hub with no admin logs a one-time setup link.
- **Invites:** admins (or integrations with the `invites` scope, members only) make links with a use limit and an expiry. Only a hash of the code is stored.
- **Joining from the agent:** paste the invite link in Settings → Agent (or `starglance link <invite>`): one call creates the account and returns the PC's token. The link carries the hub's address, so one agent build serves every org. The name defaults to the in-game handle.
- **Joining from a browser** (watchers without the game): the invite page creates the account and signs the browser in.

### 5.2 PCs
- One token per PC (random; Windows Credential Manager on the PC, a hash on the hub). A PC can be in several orgs' fleets, each with its own token and sharing.
- **Another PC** for an existing member: the agent shows a short code and opens the hub's page, where the member confirms it while signed in.
- Revoked from **Your account**, or by an admin removing or suspending the member.

### 5.3 Browsers
- **From the agent:** a one-time link (2 minutes) signs a browser in (`starglance open`, or **Open on the hub**).
- **The cockpit view** needs no sign-in to show the fleet: the agent relays the hub's viewer stream with its own token (decision 19).
- **Another device:** a signed-in browser shows a short code that the other device types in.
- **Discord (optional):** "Join with Discord" and sign-in with Discord; admins may let holders of a Discord role join without an invite, re-checked hourly (losing the role suspends the member).
- Session cookie: random id (hash stored), HttpOnly, Secure on https, SameSite=Lax, 30 days. Browser writes must carry the hub's own Origin. **Signed-in devices** lists each browser and can sign any of them out.

### 5.4 Integrations
Admins create API keys (scopes `read`, `invites`) for bots: [HUB_API.md](HUB_API.md).

---

## 6. Components

### 6.1 Agent (Windows)
- **The app:** `starglance.exe` opens its own window (no title bar by default) with a tray icon; closing hides it to the tray; a second launch brings it back. Optional: always on top, start with Windows.
- **The game:** connects to the telemetry server when it appears, retrying quietly; follows Game.log (read-only) for location, contracts, combat and who's aboard which ship (decision 18).
- **The normalizer** turns raw frames into the shared model, tolerating missing or renamed fields (log unknown shapes once).
- **The cockpit view** on `127.0.0.1` at the full ~17 Hz, with a compact layout for VR overlays. The one exception to "this PC only" is opt-in and view only: *Show on other devices* (decision 21).
- **The uplink**, one per fleet: reconnecting, latest-wins for snapshots, bounded event buffer; each fleet gets only what the player shares with it.
- **Sharing:** everything on by default; any category can be switched off per fleet and is then never sent.
- **Updates:** GitHub's latest release and the hub say which version is current; the app updates itself in one click (decisions 22, 23).
- Logs in `%LOCALAPPDATA%\Starglance\logs`, rotating. `tools/capture.py` records sessions for bug reports (aUEC scrubbed).

### 6.2 Hub
- Live state in memory. A member is stale ("Connection lost") after 10 s without a message while in game, or 40 s while not in game (the agent then only sends a heartbeat, every 8 s), and offline after 60 s.
- Events stored for 30 days (configurable); accounts, PCs, sessions, invites and API keys in SQLite (secrets as hashes only).
- Roster summaries for the board, held warning lights for the fleet header, crews found from shared ships and "aboard" channels.
- Rate limits per token and per visitor; oversized messages rejected. `/api/health` for monitoring.

### 6.3 Web UI
- **Fleet board:** the roster (by ship, server, status or A–Z), cards in a steady order (A–Z or your own), the fleet header with the warning lights each browser chooses, and anyone's full dashboard a click away.
- **Cockpit view:** panels in layouts the player customizes (themes per manufacturer, compact mode for VR), the Wingmates panel, and the fleet view inside it (decision 19).
- Works on phones and tablets.

### 6.4 Bots
Bots live in their own projects and use the integration API (decision 16). Ideas for one: a fleet roster in chat, a readiness check before an op (who's in game, seated, shields up), alerts when someone's hit or lands somewhere hostile, after-action summaries.

---

## 7. Game actions (a button box; not built)

- Only the agent's **local** cockpit view (127.0.0.1) may ever trigger an action. No path from the hub, a bot or another device, no exceptions.
- Never exposed: self-destruct, eject, emergency exit, door locks.
- A button box, never a bot: no macros or timed sequences. CIG's stance on automating actions is unclear.

---

## 8. Build phases

**Phase 0, done:** capture real frames (`tools/capture.py`) across on foot, piloting, turret, NAV/SCM, quantum, landing, damage; extract the protoset; write FIELDS.md.

**Phase 1, done:** the agent on its own: game switch, install finder, gRPC client, normalizer, cockpit view. `tools/replay.py` replays recordings as a fake game, so development and tests run without the game. Tests: the normalizer against every recording, the cfg writer, the quirks.

**Phase 2, done:** the hub: accounts and invites, agent uplink with deltas, the viewer stream, the fleet board and member view, then the Wingmates panel and the fleet inside the cockpit view.

**Phase 3, done:** the integration API for bots (replacing a bot built into this repo, decision 16).

**Phase 4, done:** releases: `starglance.exe` and the hub image from tags, update notices and one-click updates. Releases are unsigned, with a build attestation for each exe (decision 8).

**Next** (not designed yet; open questions below each):

- **Wings.** A small group inside a fleet that flies together: someone starts a wing ("Alpha"), others join it, one member leads. Members see their wing first: a wing section at the top of the roster, a wing filter on the cards, the Wingmates panel showing the wing before the rest of the fleet, and the wing's alarms in the header. A wing lasts until its lead closes it or everyone leaves.
  - Who may start one: the admin decides, in **Admin → Settings**: admins only, admins and officers, or every member. Anyone can join a wing without asking; the lead can remove people (decided 2026-11-25).
  - Does a wing see more than the fleet does (for example location when someone shares it only with their wing), or exactly the same? Sharing stays per fleet unless we decide otherwise.
  - Is a wing tied to a Discord voice channel (a link on the wing), or kept separate?
- **Events (ops).** Admins or officers schedule an op on the hub: title, time, meeting point, notes. Members sign up with a role and a ship. When it starts, wings form from the sign-ups, and the page has an event view of just the people in it. When it ends, an **after-action summary**: who flew, how long, kills, ships lost, contracts, quantum trips, and the timeline, from the events the hub already logs.
  - **Officers** (decided 2026-11-25): a role between member and admin, set under Admin → Members. Officers schedule and run events and, if the admin allows it, start wings; they don't manage members, invites, keys or settings.
  - **Reminders go out through the bot API** (decided 2026-11-25): the hub emits `event_scheduled`, `event_starting` (a set time before) and `event_ended` (with the summary) on the integration API's event stream, and a Discord bot posts them. The hub itself sends nothing anywhere.
  - How long are summaries kept (the event log keeps 30 days by default)?
- More Game.log lines as the game adds them; hull and shield levels if CIG starts sending them (the normalizer and the Hull & shields panel already show them when they're there).

**Maybe:** the button box (§7).

---

## 9. Testing and development
- Most development happens without the game: `tools/replay.py` and the recordings in `fixtures/`.
- Unit tests: normalizer, event derivation, models and patches, linking, privacy filtering (unshared categories never leave the agent).
- Integration: a real hub plus agents replaying recordings, and a fake Discord.
- Lint and format with ruff; the page is type-checked with svelte-check. CI runs everything on Windows and Ubuntu, and builds and starts the hub image.

## 10. Security checklist
- Agent servers bind 127.0.0.1 only, except the opt-in, view-only, paired-devices server (decision 21).
- No command path from the network to the game.
- Tokens and keys random (≥32 bytes), stored as hashes, revocable.
- TLS for everything off the PC (the hub behind a reverse proxy with https).
- Privacy enforced at the agent (everything shared by default, per-category opt-out).
- Message size and rate limits on the hub.
- `user.cfg` backed up before edits; switching off restores it.
- The exe is published only on the project's GitHub releases, with SHA-256 checksums, and signed once code signing is set up; updates check both.

## 11. Decisions
1. **Open repo, no fixed address (2026-11-22):** the hub's address is a setting (`HUB_URL`), never in code; agents learn it from the invite link.
2. **Hosting (2026-11-22):** a hub is one Docker container publishing one port on `127.0.0.1`, behind whatever reverse proxy with https the org already has (deploy/README.md has Caddy, nginx and Apache examples). No proxy container of our own.
3. **Database (2026-11-22):** SQLite on a volume. No Redis. One container plus its data.
4. **Discord (2026-11-22, revised by 15):** optional; when used, the server and member role are settings.
5. *(Withdrawn: hosting details for a bot built into this repo; see 16.)*
6. **Default sharing:** everything on; each member can switch off any category, and switched-off data is never sent.
7. **Frontend:** Svelte 5 + Vite + TypeScript (§3.1).
8. **Code signing:** not for now (2026-11-25). SignPath's free program wants a wider following first, and a paid certificate isn't worth it for a small fan-made tool. Releases are unsigned and say so; each one has a GitHub build attestation that ties the exe to the tag and workflow that built it (docs/CODE_SIGNING.md). The SignPath step stays in the release workflow, off, for reapplying later.
9. **Hull/shield bars (2026-11-23):** LIVE doesn't send hull health or shield levels (FIELDS.md). The design keeps room for them beside shield power and the warning lights, in case CIG adds them.
10. **Game.log and location (2026-11-23):** the agent also reads Game.log (read-only) for location, quantum routes, contracts, kills, injuries and the server (FIELDS.md, "Game.log"); comms and party chatter are left out. It goes to the fleet like the rest, under its own categories, each of which a member can switch off: `location` (zone, jurisdiction, server, system, quantum destination), `mission` (contracts) and `combat` (kills, losses, session counts), alongside `status`, `ship`, `weapons`, `vitals` and `uec` (which also covers contract rewards).
11. **One org per hub (2026-11-23):** a hub serves one org. **Crews** are found automatically (members reporting the same ship). Tables carry an `org_id` anyway, so hosting several orgs stays possible.
12. **Linking without a bot (2026-11-23):** agents link through the hub itself (§5); nothing in the hub depends on a bot.
13. **Rates and transport (2026-11-23):** WebSocket over TLS, agent → hub and hub → browser. UDP rejected: browsers can't use it, common reverse proxies can't carry it, encryption and auth would have to be rebuilt, and status data doesn't need it. Instead the uplink sends deltas at up to 10 Hz (≈1.5 KB/s per member) and browsers get rounded summaries of everyone plus full rate for the member they have open.
14. **Hub stack (2026-11-23):** aiohttp and `sqlite3` instead of FastAPI, uvicorn and SQLAlchemy: one web framework across agent and hub, a handful of tables with simple queries, a smaller image. Live state in memory; SQLite holds members, sessions, PCs (token hashes only), codes and the event log.
15. **Accounts without Discord (2026-11-23):** members are the hub's own accounts, brought in by invite links; the agent is the key for signing browsers in. Discord is an optional extra (sign-in, joining by role, suspension on losing it): players shouldn't need Discord, and many orgs don't use it.
16. **Bots outside this repo (2026-11-23):** the hub has a versioned integration API with admin-made API keys (read the fleet, follow events live, create invites); any bot builds on that in its own project. The hub is one port.
17. **Open source (2026-11-23):** MIT. Nothing org-specific in code (the hub address comes from the invite, the org's name from hub settings); not affiliated with CIG; recordings scrubbed of aUEC and player names. Each org runs its own hub; whoever runs it sees what members share, which the docs say plainly.
18. **Who's aboard (2026-11-24):** boarding a ship joins its comms channel, and Game.log names it `"<Manufacturer Model> : <owner handle>"`. The agent reports it as `location.aboard`, so crew on foot are placed with the ship they're on. The hub matches the owner to a member by handle (`status.handle`), then by display name. Leaving isn't always logged, so another channel, a server change, death or a new game also end it.
19. **The fleet in the cockpit view (2026-11-24):** the cockpit view shows the fleet too: the same board as the hub's page, and a Wingmates panel. The agent relays the hub's viewer stream with the PC's token, only while one is on screen; the page may only say which member is open. The hub's page stays for phones, other screens, accounts and admin. Cost: the page ships with the agent, so page changes reach members when they update.
20. **Named Starglance (2026-11-24):** the agent works on its own as a personal dashboard; the fleet is the big extra, not a requirement, so the name covers both. Packages `starglance` (agent), `starglance_hub`, `starglance_shared`; the exe `starglance.exe`. Earlier builds were called Fleet Telemetry: the agent moves their data folder and Credential Manager entry over on first start. Checked for clashes first: no software or GitHub projects named Starglance, no US trademarks for it.
21. **Show on other devices (2026-11-24):** a tablet or a second PC at home can show the cockpit view without the hub. Opt-in (Settings → Agent, off by default): a second server on all interfaces, port 8741, beside the 127.0.0.1 one, which stays as it was. It serves only the page, the live feed (`/ws`, marked `remote`; whatever the page sends is ignored), `/api/state` and the fleet relay (`/ws/fleet`, `focus` only); every other `/api/` path is 404, so no settings, telemetry switch, fleet sign-in links or replay controls. Devices pair with a 6-digit code shown on the PC (5 minutes, 5 tries; a QR code carries the address and the code) and then hold a random key in an HttpOnly, SameSite=Strict cookie; the agent keeps its hash and can remove a device, which closes its sockets at once. The Host must be an IP address or the PC's name (DNS rebinding) and a browser's Origin must match it. Plain HTTP on the home network: someone watching its traffic could see the view or copy a key, which gets them the view and nothing more; the docs say to use it at home. The hub's page stays the way to watch from anywhere else.
22. **Updates without an installer (2026-11-24):** frequent CIG patches mean frequent releases, so updating must be one click. The bare exe updates itself (`selfupdate.py`): the hub says which version is current, as before; on **Update** (or automatically, opt-in, only while the game isn't running) the app downloads `starglance.exe` and `SHA256SUMS.txt` from that version's GitHub release (an address fixed in the app; a hub only supplies the version number), checks the checksum, and once releases are signed, that the signer matches its own. It renames itself to `.old.exe`, puts the new one in place under the same name (so Start with Windows keeps working), starts it and quits; the new one waits for the port, then deletes the old file. Settings live in `%LOCALAPPDATA%\Starglance`, so nothing is lost. An installer stays possible later (Start menu, uninstall entry), and would change what's downloaded, not this flow. Signing stays one SignPath request per release.
23. **The agent asks GitHub for the latest release (2026-11-24):** the hub announces its own version, so an agent with no hub, or on a hub whose admin hasn't pulled the new image, never heard about an update, and an agent-only fix for a CIG patch waited on every hub admin. The agent now asks `github.com/bradqui/starglance/releases/latest` at start and every 6 hours and reads the version from the redirect (no API, no account; only a plain version number is accepted). On by default, off in Settings → Agent; PRIVACY.md says so. Downloading is unchanged (decision 22).
24. **Problem reports (2026-11-24):** reports should be easy to send and easy to diagnose, and CIG changes Game.log without notice. The agent keeps the last 30 minutes of what it received and did on disk (the capture format, aUEC removed, about 1–2.5 MB), and a mark (top bar, tray, optional hotkey) keeps the 10 minutes around a moment for 24 hours. **Report a problem** cuts a 2–10 minute window into one zip with Game.log's lines for it, the app's log and the protoset, cleans names, IDs and addresses out of all of it, previews it, and then the player sends it to their fleet's admins through the hub (no new account; admins get a Reports tab and can forward one to GitHub with a pre-filled issue) or saves it for a GitHub issue themselves. Nothing goes anywhere else, and nothing goes without the player choosing it. The maintainer replays the zip with `run --replay`. docs/REPORTS.md has the details.
25. **Marks from other devices, and where a jump ended (2026-11-25):** players on a tablet beside the game want to flag a problem as it happens. A paired device may now do one thing besides watch: mark a moment (`POST /api/mark` on lanview, its own Origin required). A mark only keeps minutes that are already on the PC; the report is made and sent there, where the data is, and the device gets the marks but not the report settings. Nothing else on that server changes anything, and nothing reaches the game.
   The fleet cards show where a member's last quantum jump ended ("Arrived Bounty Beacon · 6 min ago"), dimmed, as history rather than a location: the log says when you arrive, not when you leave. It's forgotten on a new route, a server change, death, or after 20 minutes, and comes under the Location category like the quantum destination.

26. **Where you are, named from the game's own files (2026-11-25):** players asked for "At Lorville" and "Flying at Daymar", which the telemetry can't give (no position). Game.log has the landing area you're in (`<RequestLocationInventory>`, left again when `<Update Inventory Location>` goes to landing 0), the planet or moon whose ground is loaded (`planet cells` blocks every 10 minutes; only bodies with loaded cells count), and where a route was plotted from. A jump clears the place and its end sets the destination's body; a server change or death clears it. Names come from the game's own `global.ini` inside the player's `Data.p4k` (places.py: our own reader for its ZIP64 and zstd entries, about 4 s once per game version, cached in `names/`), never a hand-made list or anything shipped with Starglance: ids resolve by trimming, gateways by their pair of systems, planet stations by `<planet>_Transfer`, outposts by their words under the same planet's keys. On real sessions that names about 96% of visits; the rest show their planet or moon. Shared under Location, like the rest of where you are.