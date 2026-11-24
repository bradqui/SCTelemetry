# Star Citizen Org Fleet Telemetry — Build Spec

> The original handoff document for Claude Code, kept as the design record. Working name: **Fleet Telemetry**; the project is now **Starglance** (decision 20).
> Later decisions (§11) override earlier sections. Since decisions 15–17 the project is open source and any org can run a hub; there is no ButlerBot cog in this repo (§6.4 and Phase 3 are superseded: bots use the hub's integration API, docs/HUB_API.md), and Discord is optional (§5 is rewritten).

## 1. Goal

Let members of our Star Citizen org see each other's live in-game status (ship, shields, fuel, hull, crew role, etc.) on:

1. **Their own second monitor / VR overlay** — full-rate local view of their own data.
2. **Phone / tablet** — a web app (PWA) showing the whole fleet.
3. **Discord** — via our existing bot **ButlerBot** (Red-DiscordBot + custom cogs): fleet roster, pre-op readiness checks, alerts.

Data comes from Star Citizen's local game telemetry gRPC server (unofficial, see §2). Each member runs a small Windows **agent** that reads their game and pushes to a central **hub** hosted on Brad's server, alongside ButlerBot.

### Non-goals
- No world coordinates / map (the game does not expose them — see §2.5). Location in game terms (zone, jurisdiction, server, star system, quantum destination) comes from Game.log and is shared by default (decision 10).
- No remote control of anyone's game. Game actions, if ever implemented, are **local-only** (§7).
- No memory reading, injection, or anything touching Easy Anti-Cheat.

---

## 2. The data source: Star Citizen local game telemetry

Reference: https://github.com/TheBanjolorian/7hills-link/blob/main/docs/TELEMETRY.md
(Community-documented, found by reading the game's own API definitions; tested on LIVE and PTU, Nov 2026. **CIG may change it in any patch.**)

**Licensing note:** the 7hills-link repo has **no license**. Do NOT copy its code. Implement independently from the documented behavior below.

### 2.1 Transport
- **gRPC**, plaintext, `127.0.0.1:2942` (localhost only, no auth). *Verified 2026-11-23: the port is 2942, not 50051, and is announced in `Game.log`. The agent reads it from there.*
- Service: `sc.game.telemetry.v1.GameTelemetryService`

| Method | Type | Notes |
|---|---|---|
| `TelemetryStream` | server streaming | `TelemetryStreamResponse` frames, ~17/sec, only once loaded into the game |
| `ListTriggerableActions` | unary | returns `action_name`, `category`, `holdable` |
| `TriggerGameAction` | unary | args `action_name`, `hold_ms`; returns a `status` |

### 2.2 Enabling it (agent must automate this)

> **Verified on LIVE (2026-11-23):** only `grpc.client.server.enabled = 1` is needed. The game has no `grpc.client.server.port` or `server.game.telemetry.enabled` setting. The environment variable is ignored once `user.cfg` sets the server, so the agent doesn't set it. Only the **game** needs restarting, not the launcher. The community notes below are kept for reference.

Append to the channel's `user.cfg` (e.g. `...\StarCitizen\LIVE\user.cfg`; support LIVE, PTU, EPTU, TECH-PREVIEW, HOTFIX):

```
grpc.client.server.enabled = 1
grpc.client.server.port = 50051
server.game.telemetry.enabled = 1
```

Only if game actions are enabled (later phase):
```
server.game.telemetry.trigger.actions.enabled = 1
```

Also set **Windows user environment variable** `GRPC_CLIENT_SERVER_ENABLED=true` (HKCU\Environment, then broadcast `WM_SETTINGCHANGE`).

Both are read at startup → the user must **fully quit the RSI Launcher** and restart the game.

Requirements for the agent's config writer:
- Back up `user.cfg` before the first edit (`user.cfg.bak-<timestamp>`).
- Idempotent: update existing keys in place, don't duplicate lines, preserve the user's other settings and comments.
- Provide "Switch off" that reverts our keys.
- Locate installs by checking common paths (`C:\Program Files\Roberts Space Industries\StarCitizen\<CHANNEL>`) plus a "Browse…" fallback. Remember the chosen path.

### 2.3 Getting the protobuf definitions

> **Verified (2026-11-23):** the game's server has no reflection (`UNIMPLEMENTED`). Extraction from `StarCitizen.exe` works and takes under a second (`starglance/protoset.py`).

The `.proto` files aren't published. Two approaches, try in order:

1. **Server reflection** — first test `grpcurl -plaintext 127.0.0.1:50051 list`. If reflection works, use it at runtime (`grpcio-reflection` client) and skip step 2.
2. **Extract from the game binary** (the approach 7hills-link describes): scan `StarCitizen.exe` for the string `sc/game/telemetry`, locate the surrounding serialized `FileDescriptorProto`s, validate each by parsing with `descriptor_pb2.FileDescriptorProto.FromString` (check name/package/dependencies resolve), and assemble a `FileDescriptorSet`. Load at runtime into a `descriptor_pool.DescriptorPool` and build message classes with `message_factory.GetMessageClass`. Cache the protoset keyed on exe size + mtime (or hash) so it re-extracts after patches.

Either way, also emit a `.protoset` file usable with `grpcurl -protoset` for debugging.

Convert frames with `json_format.MessageToDict(msg, preserving_proto_field_name=True)`.

### 2.4 Frame contents (documented paths)

> **Superseded by [FIELDS.md](FIELDS.md)** (2026-11-23), which lists the real schema extracted from the LIVE exe. Notably, LIVE has **no vehicle hull health, shields, or master mode**, and no game-action RPCs. The community notes below are kept for reference.

Top-level keys: `actor`, `vehicle`, `weapons`, `events`, `turret`, `force_feedback`.

```
actor:
  state:       locomotion (walking/seated/EVA), seat_name, crew_role, uec_balance
  vitals:      health, oxygen, hunger, thirst, body_temperature  (each {current,max})
               heart_rate, pressure, gravity, intoxication_level
  environment: external_temperature, breathable_atmosphere, ambient_radiation_rate
vehicle:        (ONLY while seated; empty immediately on leaving seat)
  state:
    name (unique per ship instance), class_name, manufacturer, type, health,
    lights_enabled, master_mode{mode (NAV/SCM), spooled},
    shields{level, faces[]},
    power{...}  on/off for power plants, engines, weapons, coolers, life support,
                sensors, gravity generators, shield generators, shield emitters
    annunciators{pwr, wpn, thr, shld, cool, qdrv, radr, prox, hit, misl}
    flight:
      state{gear, vtol, is_landed}
      settings{ifcs_spacebreak_enables_boost, course_prediction,
               ifcs_g_safe_disabled_by_boost, advanced_hud_enabled_scm,
               advanced_hud_enabled_nav, advanced_hud_labels,
               flight_light_amplification}
      instruments{speed, altitude, radar_altitude, heading,
                  vertical_speed_indicator, g_meter{current,max},
                  hydrogen_fuel, quantum_fuel, boost{reserve, engaged, output, critical}}
weapons: preset_index, preset_name, settings{gimbals_locked},
         weapons[] (name, powered, ready_to_fire, in active group),
         countermeasures[] (type, remaining)
events:  events[].type   (e.g. seat enter/leave)
turret, force_feedback:  undocumented — log and inspect
```

Exact sub-field names inside `{...}` are not fully documented. **Phase 0 must capture real frames** and the normalizer must be written against them.

### 2.5 Known quirks and gaps

> See **Observed in a real session** in [FIELDS.md](FIELDS.md) for verified behaviour. It confirms FLT_MAX altitude, zero quantum fuel and gear transitions. It also adds: seat events are unreliable (derive them from state), the co-pilot seat reports `PILOT`, and NAV/SCM can be inferred from the quantum drive light plus shield power.

- Altitude in space = FLT_MAX (~3.4e38) → treat as `null`.
- Quantum fuel always reads 0 so far → show as "n/a" unless nonzero ever observed.
- G-load can read 0 and heading 360 while stationary.
- Gear/VTOL report transitional `DEPLOYING` / `RETRACTING`.
- Vehicle section disappears instantly when leaving a seat; absent on foot.
- Decoupled mode, G-safe, proximity assist: **not reported**.
- **Not in the stream at all:** world position, doors, fuses, per-component damage, other players/targets, other crew members' actions, engineering panels.

### 2.6 Game actions (later phase only)
- ~112 actions on PTU (Nov 2026): lights/player, emotes (34), seat/operator modes, ship general, flight, power, other. `v_invoke_ping` is the only holdable one.
- Behave like key presses — cannot set values.
- Ship actions need a seat that controls the ship; player actions need you on foot.
- The gRPC call succeeds even if the game refuses; check `status`: `OK`, `FILTERED` (blocked right now), `MAP_INACTIVE` (wrong control context), `FAILED` (seen for all door/port actions).

---

## 3. Architecture

```
┌──────────── Member PC (Windows) ────────────┐
│ StarCitizen.exe ──gRPC 127.0.0.1:50051──▶ Agent                     │
│                                            ├─ local web UI @17Hz     │
│                                            │  (127.0.0.1 only)       │
│                                            └─ uplink (WSS, outbound) │
└──────────────────────────────────────────────┼──────────────────────┘
                                               ▼
┌──────────── Brad's web server (Virtualmin + Docker) ─────────────────┐
│ Apache (Virtualmin, Let's Encrypt, fleet.<domain>)                   │
│   └─ ProxyPass + WebSocket upgrade ─▶ 127.0.0.1:<port>               │
│ Hub container (aiohttp, SQLite on a volume)                          │
│   ├─ public:   ingest WS /ws/agent, viewer WS /ws/view, REST /api/*, │
│   │            PWA static assets                                     │
│   ├─ internal: REST /internal/*, event WS /internal/events           │
│   │            (own port on 127.0.0.1, shared-secret header)         │
│   └─ live state (in-memory) + history DB (SQLite)                    │
│ ButlerBot container (Red) ── telemetry cog ──▶ hub internal API      │
│                              (subscribes to /internal/events)        │
└──────────────────────────────────────────────────────────────────────┘
```

Key principles:
- **Agents only connect outbound.** Members never open ports or install Tailscale.
- **Agent normalizes** raw frames into our own compact schema (§4) — the hub never sees raw protobuf JSON. This isolates CIG schema churn to the agent.
- **Privacy enforced at the agent**: unshared fields are never transmitted.
- **No command path from server to game.** Ever.

### 3.1 Tech choices (recommended; adjust if there's a good reason)
| Component | Stack |
|---|---|
| Agent | Python 3.12, `grpcio`, `protobuf`, `websockets` or `httpx`, `keyring` (Windows Credential Manager), `pystray` for tray icon, small local HTTP server (`aiohttp` or FastAPI) serving the same web UI bundle. Packaged with **PyInstaller** into a single `.exe` via GitHub Actions. |
| Hub | Python 3.12, **aiohttp** (as the agent's local server) and the standard library's `sqlite3` on **SQLite** (file on a Docker volume), Discord OAuth2. No Redis: events go to the cog over the hub's internal WebSocket. (Decision 14: not FastAPI/SQLAlchemy.) |
| Web UI | **Svelte 5 + Vite + TypeScript**, hand-written CSS with design tokens (no UI kit), built to static files. Svelte's compiled, fine-grained reactivity keeps 17 Hz local updates cheap and the bundle small for phones. Same bundle served by hub (fleet mode) and agent (local mode). |
| Cog | Red-DiscordBot cog on **Python 3.11** (ButlerBot's runtime), `aiohttp` (already a Red dependency) for the hub's internal REST and event WebSocket. Declare any extra deps in `info.json` `requirements`. |
| Infra | `docker-compose.yml` with **one service: the hub**, plus a volume for the SQLite file. The hub publishes two ports on `127.0.0.1` only: the public app (proxied by Apache) and the internal API (never proxied). ButlerBot uses host networking, so the cog reaches the internal port at `127.0.0.1` directly; no shared Docker network. HTTPS is terminated by the Virtualmin-managed Apache vhost (Let's Encrypt) with a proxy path to the hub, WebSocket upgrade enabled. |

Single language (Python) across agent, hub, and cog so `shared/` models can be reused.

### 3.2 Repo layout (monorepo)
```
/agent        Windows agent (gRPC client, normalizer, uplink, local UI, cfg writer)
/hub          the hub (starglance_hub package, Dockerfile)
/deploy       docker-compose.yml, .env.example, server setup steps
/web          PWA source (builds to /web/dist)
/cog          Red cog: telemetry/
/shared       Pydantic models for the wire schema (§4), version constants
/tools        replay.py (fake game server from captured JSONL), capture.py
/fixtures     captured frames (JSONL), scrubbed of aUEC
/docs         this spec, ops notes
.github/workflows/  agent exe build + release on v* tags; tests on push
```

---

## 4. Wire protocol (agent → hub)

WebSocket at `wss://<host>/ws/agent`, JSON messages, `Authorization: Bearer <agent_token>` on connect. Every message has `v` (schema version int) and `t` (ms epoch).

```jsonc
// on connect
{"type":"hello","v":1,"agent_version":"0.1.0","channel":"LIVE","game_build":"<exe version or hash>","share":["ship","status","weapons","vitals","uec"]}

// Full normalized snapshot on connect and every 30 s; in between, only the
// fields that changed ("delta"), up to 10 Hz while in game (decision 13).
{"type":"snapshot","v":1,"t":0,
 "status":{"in_game":true,"locomotion":"seated","seat":"pilot","crew_role":"pilot"},
 "ship":{"id":"<vehicle.state.name>","class":"ANVL_Asgard","manufacturer":"Anvil","hull":0.92,
         "master_mode":"SCM","qt_spooled":false,"gear":"RETRACTED","landed":false,
         "shields":{"level":0.8,"faces":[0.8,0.8,0.7,0.9]},
         "power":{"engines":true,"shields":true,"weapons":true,"...":true},
         "warnings":["shld"],
         "flight":{"speed":212.4,"alt":null,"heading":118,"g":1.2,"h2_fuel":0.66,"boost":0.4}},
 "weapons":{"preset":"Group 1","gimbals_locked":false,"ready":4,"total":4,
            "countermeasures":[{"type":"decoy","remaining":12}]},
 "vitals":null,   // only if shared
 "uec":null}      // only if shared

// immediately on change, not throttled
{"type":"event","v":1,"t":0,"kind":"seat_enter|seat_leave|ship_change|warning_on|warning_off|hull_threshold|game_start|game_exit","data":{}}

// every 30s when nothing else sent (e.g. game closed)
{"type":"heartbeat","v":1,"t":0,"in_game":false}
```

Agent-side derived events (computed from snapshot diffs): ship change, warning on/off per annunciator, hull crossing 75/50/25%, fuel crossing 25/10%, landed/takeoff, game start/exit.

Hub → agent: `{"type":"welcome","member":{...}}` on connect; `{"type":"resync"}` asks for a full snapshot (the hub restarted, or a delta didn't apply); `{"type":"error","code":"version"|"revoked"|...,"message":...}`. `version` and `revoked` are final: the agent stops retrying. Close codes: 4001 revoked, 4002 protocol error. Agents may send up to 40 messages/s and 64 KB per message; over that, messages are dropped.

Hub → viewers (`/ws/view`): `hello` (who you are), `roster` (every linked member's summary, keyed by Discord user ID), `history` (recent fleet events), then `roster_delta`, `event`, and for the member the page has open (`{"type":"focus","member":id}`), `member` (full state) and `member_delta`. Fleet state keyed by Discord user ID, plus the event stream. Each viewer subscribes to what it shows: a **summary** of every member (roster fields) and the **full** state of the member it has open, both at up to 10 Hz (the roster was 2 Hz until the Cards view and Wingmates panel showed everyone's speed and altitude, 2026-11-24; summaries are rounded, so a member sitting still costs nothing). Deltas after an initial full state, as on the uplink. Measured on the combat fixture: full snapshot ≈1.7 KB, a 250 ms delta ≈130 B (160 B at the 90th percentile).

Transport is WebSocket over TLS throughout. UDP was considered and rejected (decision 13).

Version handling: hub accepts `v` within a supported range; rejects older agents with a message telling the user to update.

---

## 5. Identity, linking, auth

(Rewritten for decisions 15–16. The first version required Discord for everything.)

### 5.1 Accounts and invites
- Members are the hub's own accounts: a random id, a display name, a role (`member` or `admin`). No passwords anywhere.
- **First admin:** while a hub has no admin it logs a one-time setup link (`<hub>/join/<code>`, admin role, single use). Using it creates the admin.
- **Invites:** admins (or integrations with the `invites` scope, members only) create links with a use limit (1, 5, 25, unlimited) and expiry (1, 7, 30 days, never). Only a hash of the code is stored; the link is shown once.
- **Joining from the agent:** `starglance link <invite link>` → `POST /api/agent/join {invite, name, machine}` creates the account and returns the PC's token in one step. The link carries the hub's address, so one agent build serves every org. The name defaults to the in-game handle from Game.log.
- **Joining from a browser** (watchers without the game): the invite page creates the account and signs the browser in.

### 5.2 PCs
- Token per PC (long random; Windows Credential Manager on the agent; hash only on the hub).
- **Another PC** for an existing member: `starglance link <hub>` → the agent shows a short code (10 min) and opens `<hub>/link?code=...`; the member confirms it while signed in; the agent, polling with a secret, receives its token once.
- Revoke from **Your account** (own PCs) or by an admin removing or suspending the member.

### 5.3 Browsers
- **From the agent:** `starglance open` (or **Open on the hub** in the cockpit page's fleet view) asks `POST /api/agent/login-link` (bearer token) for a one-time link (2 min) that signs the browser in.
- **The cockpit page itself** needs no browser sign-in to show the fleet: the agent opens the hub's `/ws/view` with the PC's token and relays it on `127.0.0.1` (decision 19).
- **Another device:** a signed-in browser shows a short code (10 min, single use); the other device types it on the sign-in page.
- **Discord (optional):** with `DISCORD_*` set, invite pages offer "Join with Discord", members can connect Discord, and connected members can sign in with it. Admins may let holders of the member role join without an invite. Members who connected Discord are re-checked hourly with their own token (`guilds.members.read`): losing the role suspends them, regaining it restores them. Members without Discord are managed by admins only.
- Session cookie: random id (hash stored), HttpOnly, Secure on https, SameSite=Lax, 30 days. Browser writes must carry the hub's own Origin.
- **Signed-in devices** (Your account): each session records a rough device name from the User-Agent, how it signed in and when it was last active. A member can sign out one device (a lost phone) or every other one; that also closes the device's open fleet view.

### 5.4 Integrations
- Admins create API keys (scopes `read`, `invites`) on the page; bearer auth on `/api/v1/*`. Documented in docs/HUB_API.md. This replaces the internal port and shared secret of the first design.

---

## 6. Components — requirements

### 6.1 Agent (Windows)
- Tray app + small window: Switch on/off (cfg writer), link status, sharing toggles, channel picker, "Open local view".
- Connects to `127.0.0.1:50051`; on failure, retry with backoff (game not running / still loading is normal).
- Normalizer: raw dict → `shared` model. Must tolerate missing/renamed fields without crashing (log unknown shapes once per session).
- Local UI on `127.0.0.1:<port>` only (never 0.0.0.0) at full ~17 Hz via local WebSocket. The one exception is opt-in and view only: *Show on other devices* (decision 21). Compact layout option for VR overlays (OVR Toolkit / XSOverlay).
- Uplink: reconnecting WSS client; drop snapshots if backpressured (latest-wins), never queue unbounded; events are buffered (bounded) and sent on reconnect.
- **Sharing defaults:** everything ON (ship, status, weapons, vitals, aUEC). Each category can be switched off by the member in the agent; switched-off fields are never transmitted.
- Update check: hub exposes `/api/agent/latest`; agent shows a banner when newer.
- Logging to `%LOCALAPPDATA%\Starglance\logs`, rotating. A "Capture 60s of raw frames" button for bug reports (aUEC scrubbed).

### 6.2 Hub
- Live state in memory; mark member stale after 10s without snapshot/heartbeat; offline after 60s.
- History: store events always; store downsampled snapshots (e.g. 1 per 5s) for sessions; configurable retention (default 30 days).
- "Ops": an op = a named time window (start/stop via cog) — used for after-action summaries (who flew what, duration, min hull, events).
- Rate limit per agent token; reject oversized messages.
- Health endpoint for monitoring.

### 6.3 Web UI (PWA)
- **Fleet board:** a dense roster that is always visible, one row per member: online/in-game state, name, ship and seat, mode or QT destination, zone chip, hull/shield/fuel mini-bars, warning icon, last seen. Grouping: by **ship** (crews under their pilot, found automatically from a shared ship id), by **server** (same shard as you highlighted), or by **op wing**. Header: online/in-ship counts, op timer, fleet-wide alarms (any member's master warning, incapacitation, ship loss) that jump to that member. Fleet activity feed merged across members.
- **Member detail:** clicking a roster row opens that member's live dashboard (the same panels as the local view) beside the roster, which stays visible. On a phone, the roster is the main screen and a member opens full screen.
- **Wingmates panel** (local view): a compact strip with crew or wing status, fed by the agent's hub connection. A normal panel in Customize, so on/off and placement are per user; it can show crew, wing or everyone online.
- **Local mode** (served by agent): single-pilot cockpit view, large type, dark, high contrast; compact VR variant.
- Installable (manifest + service worker), works on phone/tablet.

### 6.4 ButlerBot cog (`telemetry`): superseded

Not part of this repo (decision 16). A bot uses the integration API (docs/HUB_API.md); the commands below remain a good wish list for one.
Commands (prefix `[p]`):
- `telemetry link` (optional shortcut: DMs a link to the browser flow) / `telemetry unlink`
- `fleet` — embed of who's online, ship, role, hull/shield/fuel summary
- `ready [@role]` — readiness check: lists members in-game, seated, shields up, gear/landing state; flags anyone not ready
- `op start <name>` / `op stop` — marks an op window in the hub; `op stop` posts an after-action summary
- Admin: `telemetry alerts #channel`, `telemetry alerts thresholds`, `telemetry role @Role` (org member role: web access and fleet membership)

Admin commands and `op start`/`op stop` require **server admin** (Red's `admin_or_permissions(administrator=True)`).

The cog only acts in the configured Discord server (same server ID as the hub); commands elsewhere reply that telemetry isn't set up there.

Alerts (rate-limited): hull below threshold, fuel low, member joins/leaves game during an active op. Posted to the configured alerts channel: **#lab** during testing, later **#star-citizen**. Changed with `telemetry alerts #channel`; no alerts until a channel is set.

Cog holds a reconnecting WebSocket to the hub's `/internal/events` and uses the hub internal API for queries. Red Config stores guild settings (alerts channel, thresholds).

---

## 7. Game actions / button box (LATER phase, local only)

- Only the agent's **local** UI (127.0.0.1) may call `TriggerGameAction`. No hub/Discord path, no exceptions.
- Hard blocklist: `v_self_destruct`, `v_eject`, emergency exit, door-lock actions — never exposed.
- Optional: bridge from joystick/HOTAS virtual buttons (Joystick Gremlin, Virpil/VKB) → actions, and LED/feedback from the stream.
- Show `status` results to the user (`FILTERED`, `MAP_INACTIVE`, etc.).
- Policy: CIG's stance on automating actions is unclear. Treat it as a button box, never a bot (no macros/sequences on timers).

---

## 8. Build phases

**Phase 0 — Spike (do first, needs Brad's gaming PC with SC running)**
- Enable telemetry manually; test `grpcurl -plaintext 127.0.0.1:50051 list` (reflection?).
- Implement protoset extraction if reflection is absent.
- `tools/capture.py`: dump frames to JSONL across scenarios: on foot, seated pilot, seated turret/non-pilot, SCM/NAV, QT spool, landing (gear transitions), taking damage, shields down, leaving seat, ship swap.
- Commit scrubbed fixtures. Write `docs/FIELDS.md` with real field names.

**Phase 1 — Agent, local only**
- cfg writer (+ revert), install locator, gRPC stream client, normalizer, local web UI.
- `tools/replay.py`: a fake `GameTelemetryService` gRPC server that replays fixtures → lets all development/testing happen on Linux without the game.
- Tests: normalizer against every fixture; cfg writer idempotency; quirk handling (§2.5).

**Phase 2 — Hub MVP + linking**
- Ingest WS (deltas), live state, viewer WS with subscriptions, Discord OAuth, browser link flow (§5.1), agent uplink and sharing toggles.
- Fleet board and member detail first; then the Wingmates panel for the local view (decision 13).
- docker-compose; deploy behind proxy. Test with 2–3 members on a Friday night.

**Phase 3 — Cog** (superseded by decision 16: bots live in their own projects and use the integration API)
- link/unlink, fleet, ready, alerts.

**Phase 4 — History & ops**
- op windows, after-action summaries, retention job.

**Phase 5 — Polish**
- PyInstaller CI release, update check, VR compact view, PWA install.

**Phase 6 — Button box (optional)**
- per §7.

---

## 9. Testing & dev notes
- Most dev happens without the game: use `tools/replay.py` + fixtures.
- Unit tests: normalizer, event derivation (diff logic), protocol models, link flow, privacy filtering (assert unshared fields never leave the agent).
- Integration: replay server → agent → hub (docker) → fake viewer client → assertions.
- Lint/format: ruff. Type-check: mypy or pyright on `shared/` and `hub/`.

## 10. Security checklist
- [ ] Agent local servers bind 127.0.0.1 only, except the opt-in, view-only, paired-devices server (decision 21).
- [ ] No inbound command path to the game from network.
- [ ] Agent tokens random ≥32 bytes, hashed at rest, revocable.
- [ ] TLS everywhere off-box; internal API not exposed publicly.
- [ ] Privacy toggles enforced client-side (everything shared by default; per-category opt-out).
- [ ] Message size limits + rate limits on ingest.
- [ ] user.cfg backed up before edits; revert supported.
- [ ] Unsigned exe: distribute only via our GitHub releases; publish SHA-256.

## 11. Decisions (2026-11-22)
1. **Repo:** `bradqui/SCTelemetry`, public since 2026-11-23 (history checked first: no player names, addresses or secrets). Hub hostname: `fleet.fridaynightclub.xyz` (a setting, `HUB_URL`, not hard-coded). Discord OAuth redirect: `https://<host>/auth/callback`.
2. **Hosting:** Brad's public web server (Webmin/Virtualmin), hub in Docker on a `127.0.0.1` port. HTTPS via a Virtualmin subdomain (Let's Encrypt) with an Apache proxy path to the hub, WebSocket upgrade on. No separate proxy container. Ports (checked free 2026-11-23): **8100** public app (proxied), **8101** internal API (never proxied), both on `127.0.0.1`. Apache 2.4.58 with `proxy_http` and `proxy_wstunnel` enabled, so `ProxyPass ... upgrade=websocket` works.
3. **Database:** SQLite. **No Redis** — the cog gets events from the hub's internal WebSocket. Deployment is one container plus the SQLite volume.
4. **Discord:** server is configurable (Friday Night Club to start); access is a configurable org member role; admin commands and ops require server admin. Alerts channel is configurable: `#lab` while testing, later `#star-citizen`.
5. **ButlerBot container:** same host as the hub, separate container. Red 3.5.24, Python 3.11, `phasecorex/red-discordbot`; custom cogs deploy by `git pull` of the ButlerBot repo. Docker setup is not in Git. ButlerBot runs with `network_mode: host` (checked 2026-11-23), so there is no network to join: the cog calls the hub's internal port on `127.0.0.1`. Server: Ubuntu 24.04, Docker 29, Compose v5.
6. **Default sharing:** everything on; each member can switch off any category (e.g. aUEC, vitals) in the agent, and switched-off data is never sent.
7. **Frontend:** Svelte 5 + Vite + TypeScript (see §3.1).
8. **Code signing:** deferred until Phase 5.
10. **Game.log and location (2026-11-23):** the agent also reads the game's Game.log (read-only) for location, quantum routes, contracts, kills, injuries and the server (docs/FIELDS.md, "Game.log"); comms/party chatter is left out. This is org-internal game data, so it goes to the fleet. Location is shared by default like everything else; members can opt out per category: `location` (zone, jurisdiction, server, system, quantum destination), `mission` (contracts), `combat` (kills, losses, session counts), alongside `status`, `ship`, `weapons`, `vitals` and `uec` (which also covers contract rewards).
11. **One org per hub (2026-11-23):** a hub serves one org: the configured Discord server plus member role. No standing sub-fleets: an op has ad-hoc **wings** set up by the ops lead from the web page, and **crews** are found automatically (members reporting the same ship). Tables carry an `org_id` anyway so multi-org hosting stays possible.
12. **Linking without the bot (2026-11-23):** agents link through browser sign-in with Discord (§5.1). ButlerBot is a side feature; nothing in the hub depends on it.
13. **Rates and transport (2026-11-23):** WebSocket over TLS for agent→hub and hub→viewer. UDP rejected: browsers can't use it, the Apache proxy can't carry it, we'd rebuild encryption and auth, and status data doesn't need it. Instead the uplink sends deltas at up to 10 Hz (≈1.5 KB/s per member) and viewers subscribe to summaries for the board and full rate for the member they have open. Fleet board vs cockpit Wingmates panel is a per-user layout choice (the panel lives in Customize); the board is built first because the panel uses the same feed.
14. **Hub stack (2026-11-23):** aiohttp and `sqlite3` instead of FastAPI, uvicorn and SQLAlchemy: one web framework across agent and hub (no new dependencies), a handful of tables with single-statement queries, and a smaller image. Live state stays in memory; SQLite holds members, sessions, linked PCs (token hashes only), link codes and the 30-day event log.
15. **Accounts without Discord (2026-11-23):** members are the hub's own accounts, brought in by invite links; the agent is the key for signing browsers in (one-time links, device codes). Discord is an optional extra: sign-in, auto-join for a role, suspension on losing it. Rationale: players shouldn't need Discord, and other orgs may not use it (§5).
16. **Bots outside this repo (2026-11-23):** no ButlerBot cog here. The hub exposes a versioned integration API with admin-made API keys (read the fleet, live event stream, create invites); ButlerBot or any bot builds on that in its own project. The internal port and shared secret are gone; the hub is one port.
17. **Open source (2026-11-23):** public repo under MIT. Nothing org-specific in code (the hub address comes from the invite, the org name from hub settings); a disclaimer that it's not affiliated with CIG; scrubbed fixtures only. Each org runs its own hub (deploy/README.md); whoever runs it sees what members share, which the docs say plainly.
18. **Who's aboard (2026-11-24):** boarding a ship joins its comms channel, and Game.log names it `"<Manufacturer Model> : <owner handle>"`. The agent reports it as `location.aboard`, so crew on foot are placed with the ship they're on. The hub matches the owner to a member by handle (sent as `status.handle`), then by display name. Leaving isn't always logged, so another channel, a server change, death or a new game also end it.
19. **The fleet in the cockpit page (2026-11-24):** the cockpit view shows the fleet too: a Fleet view (the same board as the hub's page) and a Wingmates panel. The agent relays the hub's viewer stream with the PC's token, only while one is on screen; the page may only send which member is open. The hub's page stays for phones, other screens, accounts and admin. Cost: the UI ships with the agent, so UI changes reach members when they update it.
20. **Renamed Starglance (2026-11-24):** the agent works on its own as a personal dashboard; the fleet is the big extra, not a requirement, so the name covers both. Repo `bradqui/starglance` (old URLs redirect), `starglance.exe`, image `ghcr.io/bradqui/starglance-hub`, packages `starglance` (agent), `starglance_hub`, `starglance_shared`. The agent moves `%LOCALAPPDATA%\FleetTelemetry` and its Credential Manager entry over on first start. Checked for clashes first: no GitHub repos or software named Starglance, no US trademarks for it or "Star Glance" (only marks on the plain word GLANCE, none for game software).
21. **Show on other devices (2026-11-24):** a tablet or a second PC at home can show the cockpit view without the hub. Opt-in (Settings → Agent, off by default): a second server on all interfaces, port 8741, beside the 127.0.0.1 one, which stays as it was. It serves only the page, the live feed (`/ws`, marked `remote`; whatever the page sends is ignored), `/api/state` and the fleet relay (`/ws/fleet`, `focus` only); every other `/api/` path is 404, so no settings, telemetry switch, fleet sign-in links or replay controls. Devices pair with a 6-digit code shown on the PC (5 minutes, 5 tries; a QR code carries the address and the code) and then hold a random key in an HttpOnly, SameSite=Strict cookie; the agent keeps its hash and can remove a device, which closes its sockets at once. The Host must be an IP address or the PC's name (DNS rebinding) and a browser's Origin must match it. Plain HTTP on the home network: someone watching its traffic could see the view or copy a key, which gets them the view and nothing more; the docs say to use it at home. The hub's page stays the way to watch from anywhere else.
22. **Updates without an installer (2026-11-24):** frequent CIG patches mean frequent releases, so updating must be one click. The bare exe updates itself (`selfupdate.py`): the hub says which version is current, as before; on **Update** (or automatically, opt-in, only while the game isn't running) the app downloads `starglance.exe` and `SHA256SUMS.txt` from that version's GitHub release (an address fixed in the app; a hub only supplies the version number), checks the checksum, and once releases are signed, that the signer matches its own. It renames itself to `.old.exe`, puts the new one in place under the same name (so Start with Windows keeps working), starts it and quits; the new one waits for the port, then deletes the old file. Settings live in `%LOCALAPPDATA%\Starglance`, so nothing is lost. An installer stays possible later (Start menu, uninstall entry), and would change what's downloaded, not this flow. Signing stays one SignPath request per release.
9. **Hull/shield bars (2026-11-23):** LIVE doesn't send hull health or shield levels (see FIELDS.md). The fleet board keeps hull and shield bars in the design anyway, alongside shield power and warning lights. Final call near the end of the build.
