# Star Citizen Org Fleet Telemetry — Build Spec

> Handoff document for Claude Code. Working name: **Fleet Telemetry** (rename freely).
> Owner: Brad. Status: greenfield — nothing built yet.

## 1. Goal

Let members of our Star Citizen org see each other's live in-game status (ship, shields, fuel, hull, crew role, etc.) on:

1. **Their own second monitor / VR overlay** — full-rate local view of their own data.
2. **Phone / tablet** — a web app (PWA) showing the whole fleet.
3. **Discord** — via our existing bot **ButlerBot** (Red-DiscordBot + custom cogs): fleet roster, pre-op readiness checks, alerts.

Data comes from Star Citizen's local game telemetry gRPC server (unofficial, see §2). Each member runs a small Windows **agent** that reads their game and pushes to a central **hub** hosted on Brad's server, alongside ButlerBot.

### Non-goals
- No world position / map (the game does not expose it — see §2.5).
- No remote control of anyone's game. Game actions, if ever implemented, are **local-only** (§7).
- No memory reading, injection, or anything touching Easy Anti-Cheat.

---

## 2. The data source: Star Citizen local game telemetry

Reference: https://github.com/TheBanjolorian/7hills-link/blob/main/docs/TELEMETRY.md
(Community-documented, found by reading the game's own API definitions; tested on LIVE and PTU, Nov 2026. **CIG may change it in any patch.**)

**Licensing note:** the 7hills-link repo has **no license**. Do NOT copy its code. Implement independently from the documented behavior below.

### 2.1 Transport
- **gRPC**, plaintext, `127.0.0.1:50051` (localhost only, no auth).
- Service: `sc.game.telemetry.v1.GameTelemetryService`

| Method | Type | Notes |
|---|---|---|
| `TelemetryStream` | server streaming | `TelemetryStreamResponse` frames, ~17/sec, only once loaded into the game |
| `ListTriggerableActions` | unary | returns `action_name`, `category`, `holdable` |
| `TriggerGameAction` | unary | args `action_name`, `hold_ms`; returns a `status` |

### 2.2 Enabling it (agent must automate this)
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
│ Hub container (FastAPI, SQLite on a volume)                          │
│   ├─ public:   ingest WS /ws/agent, viewer WS /ws/view, REST /api/*, │
│   │            PWA static assets                                     │
│   ├─ internal: REST /internal/*, event WS /internal/events           │
│   │            (Docker network only, shared-secret header)           │
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
| Hub | Python 3.12, FastAPI + uvicorn, SQLAlchemy 2 on **SQLite** (file on a Docker volume), Discord OAuth2. No Redis: events go to the cog over the hub's internal WebSocket. |
| Web UI | **Svelte 5 + Vite + TypeScript**, hand-written CSS with design tokens (no UI kit), built to static files. Svelte's compiled, fine-grained reactivity keeps 17 Hz local updates cheap and the bundle small for phones. Same bundle served by hub (fleet mode) and agent (local mode). |
| Cog | Red-DiscordBot cog on **Python 3.11** (ButlerBot's runtime), `aiohttp` (already a Red dependency) for the hub's internal REST and event WebSocket. Declare any extra deps in `info.json` `requirements`. |
| Infra | `docker-compose.yml` with **one service: the hub**, plus a volume for the SQLite file. The hub publishes its port on `127.0.0.1` only and joins ButlerBot's Docker network so the cog can reach `/internal/*`. HTTPS is terminated by the Virtualmin-managed Apache vhost (Let's Encrypt) with a proxy path to the hub, WebSocket upgrade enabled. |

Single language (Python) across agent, hub, and cog so `shared/` models can be reused.

### 3.2 Repo layout (monorepo)
```
/agent        Windows agent (gRPC client, normalizer, uplink, local UI, cfg writer)
/hub          FastAPI service
/web          PWA source (builds to /web/dist)
/cog          Red cog: telemetry/
/shared       Pydantic models for the wire schema (§4), version constants
/tools        replay.py (fake game server from captured JSONL), capture.py
/fixtures     captured frames (JSONL), scrubbed of aUEC
/docs         this spec, ops notes
docker-compose.yml
.github/workflows/  agent exe build + release on v* tags; tests on push
```

---

## 4. Wire protocol (agent → hub)

WebSocket at `wss://<host>/ws/agent`, JSON messages, `Authorization: Bearer <agent_token>` on connect. Every message has `v` (schema version int) and `t` (ms epoch).

```jsonc
// on connect
{"type":"hello","v":1,"agent_version":"0.1.0","channel":"LIVE","game_build":"<exe version or hash>","share":["ship","status","weapons","vitals","uec"]}

// 2–4 Hz while in game (configurable); full normalized snapshot (it's small)
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

Hub → viewers (`/ws/view`): fleet state map keyed by Discord user ID, plus the event stream. Push on change, coalesced to ≤4 Hz per member.

Version handling: hub accepts `v` within a supported range; rejects older agents with a message telling the user to update.

---

## 5. Identity, linking, auth

### 5.1 Agent linking (Discord-based)
1. Member runs `[p]telemetry link` in Discord.
2. Cog calls hub internal API `POST /internal/link-codes {discord_user_id}` → hub returns a short one-time code (e.g. `7K4-PQ9`, 10-min TTL, single use).
3. Bot DMs the code.
4. Member enters code in the agent → agent `POST /api/agent/link {code, machine_name}` → hub returns a long random `agent_token`.
5. Agent stores token in Windows Credential Manager (`keyring`). Hub stores **only a hash** of the token.
6. `[p]telemetry unlink` / hub admin can revoke tokens. One member may have multiple agents (multiple PCs).

### 5.2 Viewer auth (web)
- Discord OAuth2 login (`identify` + `guilds.members.read`).
- Allow only members of the configured Discord server (initially the Friday Night Club server) who hold the configured org member role. Re-check the role on session refresh.
- Server ID and role ID are settings, not hard-coded: the hub reads defaults from env (`DISCORD_GUILD_ID`, `DISCORD_MEMBER_ROLE_ID`), and the cog's admin commands can change the role at runtime via the internal API (stored in the hub DB).
- Session cookie, HttpOnly, Secure, SameSite=Lax.

### 5.3 Internal API (cog ↔ hub)
- Bound to the Docker network only (not exposed via the proxy). Shared secret header as defense in depth.

---

## 6. Components — requirements

### 6.1 Agent (Windows)
- Tray app + small window: Switch on/off (cfg writer), link status, sharing toggles, channel picker, "Open local view".
- Connects to `127.0.0.1:50051`; on failure, retry with backoff (game not running / still loading is normal).
- Normalizer: raw dict → `shared` model. Must tolerate missing/renamed fields without crashing (log unknown shapes once per session).
- Local UI on `127.0.0.1:<port>` only (never 0.0.0.0) at full ~17 Hz via local WebSocket. Compact layout option for VR overlays (OVR Toolkit / XSOverlay).
- Uplink: reconnecting WSS client; drop snapshots if backpressured (latest-wins), never queue unbounded; events are buffered (bounded) and sent on reconnect.
- **Sharing defaults:** everything ON (ship, status, weapons, vitals, aUEC). Each category can be switched off by the member in the agent; switched-off fields are never transmitted.
- Update check: hub exposes `/api/agent/latest`; agent shows a banner when newer.
- Logging to `%LOCALAPPDATA%\FleetTelemetry\logs`, rotating. A "Capture 60s of raw frames" button for bug reports (aUEC scrubbed).

### 6.2 Hub
- Live state in memory; mark member stale after 10s without snapshot/heartbeat; offline after 60s.
- History: store events always; store downsampled snapshots (e.g. 1 per 5s) for sessions; configurable retention (default 30 days).
- "Ops": an op = a named time window (start/stop via cog) — used for after-action summaries (who flew what, duration, min hull, events).
- Rate limit per agent token; reject oversized messages.
- Health endpoint for monitoring.

### 6.3 Web UI (PWA)
- **Fleet board:** card per online member — name, ship class, role, hull bar, shield bar, fuel, master mode, warning icons, landed/flying, last-seen.
- **Member detail:** everything that member shares, live.
- **Local mode** (served by agent): single-pilot cockpit view, large type, dark, high contrast; compact VR variant.
- Installable (manifest + service worker), works on phone/tablet.

### 6.4 ButlerBot cog (`telemetry`)
Commands (prefix `[p]`):
- `telemetry link` / `telemetry unlink`
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
- Ingest WS, live state, viewer WS, fleet board, Discord OAuth, link-code flow (temporary admin endpoint to mint codes until cog exists).
- docker-compose; deploy behind proxy. Test with 2–3 members on a Friday night.

**Phase 3 — Cog**
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
- [ ] Agent local servers bind 127.0.0.1 only.
- [ ] No inbound command path to the game from network.
- [ ] Agent tokens random ≥32 bytes, hashed at rest, revocable.
- [ ] TLS everywhere off-box; internal API not exposed publicly.
- [ ] Privacy toggles enforced client-side (everything shared by default; per-category opt-out).
- [ ] Message size limits + rate limits on ingest.
- [ ] user.cfg backed up before edits; revert supported.
- [ ] Unsigned exe: distribute only via our GitHub releases; publish SHA-256.

## 11. Decisions (2026-11-22)
1. **Repo:** `bradqui/SCTelemetry`, private for now (may go public later). Hub hostname: TBD.
2. **Hosting:** Brad's public web server (Webmin/Virtualmin), hub in Docker on a `127.0.0.1` port. HTTPS via a Virtualmin subdomain (Let's Encrypt) with an Apache proxy path to the hub, WebSocket upgrade on. No separate proxy container.
3. **Database:** SQLite. **No Redis** — the cog gets events from the hub's internal WebSocket. Deployment is one container plus the SQLite volume.
4. **Discord:** server is configurable (Friday Night Club to start); access is a configurable org member role; admin commands and ops require server admin. Alerts channel is configurable: `#lab` while testing, later `#star-citizen`.
5. **ButlerBot container:** same host as the hub, separate container. Red 3.5.24, Python 3.11, `phasecorex/red-discordbot`; custom cogs deploy by `git pull` of the ButlerBot repo. Docker setup is not in Git. ButlerBot's Docker network name: open (needed for the hub's compose file).
6. **Default sharing:** everything on; each member can switch off any category (e.g. aUEC, vitals) in the agent, and switched-off data is never sent.
7. **Frontend:** Svelte 5 + Vite + TypeScript (see §3.1).
8. **Code signing:** deferred until Phase 5.
