# Telemetry fields (from the game's own definitions)

**Source:** extracted from the LIVE `StarCitizen.exe` dated 2026-11-19 (175,570,944 bytes) with `python -m starglance protoset`. Package `sc.game.telemetry.v1`, files `types.proto` and `api.proto`, proto3.

The first half of this document is the **schema**: which fields exist and their types. **Observed in a real session** describes what the game actually sends. A HOTFIX build from 2026-06-12 predates telemetry and has no definitions.

## Service

```
service GameTelemetryService {
  rpc TelemetryStream(TelemetryStreamRequest {})  returns (stream TelemetryStreamResponse);
}
```

The LIVE build has **only `TelemetryStream`**. `ListTriggerableActions` / `TriggerGameAction` (spec §2.6) aren't in it; they appear to be PTU-only for now.

## TelemetryStreamResponse

| Field | Type | Notes |
|---|---|---|
| `vehicle.state` | VehicleState | Only while seated (per community docs) |
| `weapons` | WeaponsFrame | |
| `events.events[]` | GameEvent | |
| `actor` | ActorFrame | `vitals`, `state`, `environment` |
| `force_feedback` | ForceFeedbackFrame | |
| `turret` | TurretFrame | |

### actor
| Path | Type |
|---|---|
| `state.locomotion` | enum `ACTOR_LOCOMOTION_STATE_{ON_FOOT, EVA, SEATED}` |
| `state.crew_role` | enum `ACTOR_CREW_ROLE_{PILOT, GUNNER, CREW}` |
| `state.seat_name` | string |
| `state.uec_balance` | int64 (scrubbed in fixtures) |
| `vitals.health / oxygen / hunger / thirst / body_temperature` | Gauge `{current, max}` |
| `vitals.heart_rate / gravity / pressure` | float |
| `vitals.intoxication_level` | int32 |
| `environment.external_temperature / ambient_radiation_rate` | float |
| `environment.breathable_atmosphere` | bool |

### vehicle.state
| Path | Type |
|---|---|
| `name` / `class_name` / `manufacturer` | string |
| `type` | enum `VEHICLE_TYPE_{SPACESHIP, GROUND, GRAVLEV, BOAT}` |
| `lights_enabled` | bool |
| `doors.open_state` / `doors.lock_state` | enum `OPENED/CLOSED`, `UNLOCKED/LOCKED` |
| `annunciators.{pwr, wpn, thr, shld, cool, qdrv, radr, prox, hit, misl}` | enum `ANNUNCIATOR_STATE_{NOMINAL, OFF, MINOR_FLASHING, MINOR_ON, MAJOR_FLASHING, MAJOR_ON}` |
| `power.{powerplants, engines, weapons, coolers, life_support, gravity_generators, sensors, shield_generators, shield_emitters}` | bool |
| `flight.state.is_landed` | bool |
| `flight.state.gear / vtol / transformation` | enum `..._{RETRACTED, DEPLOYING, DEPLOYED, RETRACTING}` |
| `flight.instruments.speed / altitude / radar_altitude / vertical_speed_indicator / heading / atmospheric_density` | float |
| `flight.instruments.hydrogen_fuel / quantum_fuel` | float |
| `flight.instruments.g_meter` | Gauge |
| `flight.instruments.boost.{engaged, output, reserves, critical}` | bool/float |
| `flight.settings.ifcs_{coupled, esp, gravity_compensation, g_safe, cruise_mode, speed_limiter, proximity_assist, proximity_assist_landing, stability, core, wind_compensation, command_behaviour}` | Availability `{enabled, active}` |
| `flight.settings.{ifcs_spacebreak_enables_boost, ifcs_g_safe_disabled_by_boost, advanced_hud_enabled_scm, advanced_hud_enabled_nav, advanced_hud_labels, course_prediction, flight_light_amplification}` | bool |

### weapons
| Path | Type |
|---|---|
| `preset_index` / `preset_name` | uint32 / string |
| `settings.{gimbals_locked, staggered_fire, precision_lines, magnified_ui, fallback_convergence_distance, use_lag_pips, use_single_pips, use_fading_pips}` | bool |
| `weapons[].{name, is_powered, ready_to_fire, contained_in_preset}` | |
| `countermeasures[].type` / `.amount` | enum `COUNTERMEASURE_TYPE_{DECOY, NOISE}` / uint32 |

### events, force_feedback, turret
- `events.events[].type`: `GAME_EVENT_TYPE_{ACTOR_SPAWN, ACTOR_DEAD, ACTOR_ENTER_SEAT, ACTOR_LEAVE_SEAT, ACTOR_RESPAWN, ACTOR_DOWNED}`
- `force_feedback.{angular, linear}.{x,y,z}.{resistance, damping}`, `gunfire`, `stick_shaker`
- `turret.light_amplification`

## Observed in a real session (LIVE, 2026-11-23, 44 min)

Capture: walking a station and hab, an Origin M80 flight (power cycle, takeoff, gear cycle, cruise, NAV↔SCM, quantum jump, landing), ship combat, EVA, a hangar landing with repair/refuel/rearm, then the pilot, co-pilot and right-gunner seats of a Constellation Mk5 Centaurus. Slices are in [`fixtures/`](../fixtures/).

**Server and stream**
- Served on `127.0.0.1:2942` (the default; no setting found to change it), announced in `Game.log` as `[sc.game.telemetry.v1.GameTelemetryService]: 127.0.0.1:2942 [Insecure]`.
- Only `grpc.client.server.enabled = 1` in `user.cfg` is needed. The Windows environment variable is ignored when `user.cfg` sets it. No server reflection (`UNIMPLEMENTED`).
- A steady 17.4 frames/s, with no gaps over 1 s in 44 minutes, including the quantum jump and loading.

**Which sections arrive**
- `actor` is in every frame.
- `vehicle` and `weapons` are present only while seated.
- `events` is rare.
- `turret` and `force_feedback` were **never sent**, even in a gunner seat.

**Seats (important for the normalizer)**
- **Sitting down:** `locomotion = SEATED` and `seat_name` change at once. `vehicle`, `weapons` and `crew_role` follow about 5–6 s later, after the sit animation. `crew_role` flickers `PILOT → UNSPECIFIED → PILOT` in its first frames.
- **Getting up:** `vehicle` disappears immediately. `locomotion` returns to `ON_FOOT` about 5–7 s later.
- **Events are unreliable:**
  - `ACTOR_LEAVE_SEAT` arrived 6 of 6 times; `ACTOR_ENTER_SEAT` only 3 of 6.
  - No spawn, death or downed events were seen.
  - So **seat events are derived from state changes**, not from `events`.
- **`crew_role` by seat:**
  - pilot seat: `PILOT`;
  - co-pilot seat: **also `PILOT`**;
  - gunner seat: `CREW`. `GUNNER` was never seen.
  The seat type is also in `seat_name`, e.g. `Orig_m80_Seat_Pilot_<id>`, `RSI_Constellation_Mk5_CoPilot_SeatDashboard_<id>`, `RSI_Constellation_Mk5_Gunner_Right_SeatDashboard_<id>`.
- `locomotion` flickers between `EVA` and `ON_FOOT` around airlocks, so debounce it.

**Vehicle identity**
- `name` is `<class_name>_<entity id>` (e.g. `ORIG_m80_944712252115`), which is a good ship id.
- `manufacturer` is always `""`. Derive it from the `class_name` prefix (`ORIG`, `RSI`, ...).
- `type` was always `VEHICLE_TYPE_SPACESHIP`.

**NAV / SCM can be inferred** (no `master_mode` field). Across 9 mode switches:
- **SCM:** `annunciators.qdrv = OFF` and `power.shield_generators/emitters = true`.
- **NAV:** `qdrv = NOMINAL` and shields unpowered.
- **Shields down while in SCM:** shields off while `qdrv` stays `OFF`, as at 30:20 in combat.

**Power**
- Every `power.*` flag goes false when the ship powers down, and back true on power-up.
- `engines` toggles on its own; engines were off after landing.
- `gravity_generators` was always false on the M80.

**Warning lights**
- Values seen: `NOMINAL`, `OFF`, `MINOR_ON`, `MAJOR_ON` and `MAJOR_FLASHING`.
- `hit` goes `MAJOR_FLASHING` for 1–10 s each time the ship is hit, so it serves as the "taking fire" signal.
- `shld` briefly goes `MAJOR_ON` when shields come up, then `MINOR_ON` or `NOMINAL`.
- `prox`, `radr`, `thr` and `wpn` also change. `prox` is the proximity warning (minor, then major, near objects). `radr` read `MAJOR_ON` for exactly the two minutes hostiles were about (a "Defeat Hostile Ships" objective). `thr` reads `MAJOR_ON` through every quantum jump (see Quantum travel), and for 0.1 s at power-up.
- **`cool` is `OFF` in every frame** (42,781 frames over two sessions), coolers powered or not. The normalizer shows it from `power.coolers` instead.
- `misl` stayed `NOMINAL` through a fight with missiles fired, and nothing else in the stream mentions missiles (no racks in `weapons[]`, no counts, no Game.log lines).
- The steady states are sent as `MINOR_ON`/`MAJOR_ON` and become `minor`/`major` in the snapshot. Until 2026-11-24 the normalizer dropped them, so only `MAJOR_FLASHING` (hit) ever reached the page.

**Flight**
- `altitude` and `radar_altitude` are `3.4028235e38` (FLT_MAX) in space, so they should be treated as null.
- `heading` is a compass bearing over the planet below. **With no planet (altitude FLT_MAX) it freezes**: the game keeps sending the last value however you turn. A whole dogfight read 268.0939° for 6.5 minutes. The normalizer reports it as null there, and the dashboard says "No heading in deep space".
- `atmospheric_density` is about 1.2 at the surface and about 0 in space.
- `speed` peaked at 1111 m/s. Quantum travel did **not** show up in `speed`.
- `g_meter.current` reached 23 g.
- `quantum_fuel` was always 0, as the spec expected.
- `hydrogen_fuel` is a 0–1 fraction. It reads **0 whenever the engines are off**, and briefly after sitting down, so the normalizer reports "unknown" then rather than "empty". It refilled to 1.0 in the hangar.
- `boost.reserves` ranged 0.29–1.
- `gear` moves `DEPLOYED → RETRACTING → RETRACTED → DEPLOYING`, about 4 s per move.
- `vtol` always reads `DEPLOYED`, even on ships without VTOL, so it's meaningless there.
- `transformation` was never sent.
- `is_landed` flips on touchdown and takeoff.

**Flight-assist flags (sent, contrary to the spec)**
- `ifcs_g_safe.active` toggles off while boosting.
- `ifcs_cruise_mode` toggles.
- `ifcs_coupled` was always true, but decoupled mode wasn't tried.
- `ifcs_proximity_assist.active` was false the whole time.

**Never sent, or constant**
- `doors` was never sent.
- `lights_enabled` was always false (we don't know if the lights were switched on).
- `manufacturer` was always `""`.
- `weapons.preset_name` was `""` and `preset_index` was 0.

**Weapons**
- `weapons[]` lists each gun as `<class>_<id>` with `is_powered` and `ready_to_fire`.
- `countermeasures` gives decoy and noise counts, e.g. 48 and 5.
- **No ammo counts and no "firing" signal.** Over 44 minutes, including a fight, nothing in `weapons` changed except gun names (loadout changes) and countermeasure counts. `ready_to_fire` only flickers on power changes. `force_feedback.gunfire` would be the firing signal, but `force_feedback` was never sent.

**Quantum travel**
There is no quantum travel field, and `speed` does not show the jump. What happens instead:
- During a jump the flight instruments **freeze**: `speed` repeats one exact value (0, 0.056, 21.7, 1026, whatever it was when the drive engaged; mid-jump it can step once, e.g. to exactly 0) and `g_meter.current` reads exactly 0. The frozen reading can outlast the jump by seconds (a 1.3 s leg kept reading 1026 m/s for 6 s more while the ship burned hydrogen realigning).
- Near a planet `altitude` keeps updating: it leaped 23 km → 45 km → FLT_MAX in a second on the way out and fell from 80 km to 12 km on arrival while `speed` read 0.0003. In deep space everything is frozen: speed, G, heading, fuel.
- **`thr` reads `MAJOR_ON` for exactly the jump**, leg by leg, back to `NOMINAL` at arrival (within 0.4 s of Game.log's "Arrived at Final Destination"). `ifcs_g_safe`/`ifcs_esp` go inactive with it. Two sessions, every leg (from 0.9 s to 31 s long). It never came on while sitting still with a route plotted and the drive spooled (minutes of it, nudging in between). After some legs it stays `MAJOR_ON` for up to 11 s while the ship falls with its thrusters locked; speed then changes every frame. A few 1–2 s periods with no route or no movement are probably short or aborted jumps.
- A ship stopped dead in space also has a frozen `speed` and G of 0, with or without a route plotted.

So the normalizer infers `flight.quantum` as: `thr` major, `qdrv` lit (NAV), and speed bit-identical with G exactly 0 for 0.3 s. It ends when `thr` clears, G reads anything but 0, or the speed changes on 4 frames in a row. Each leg of a multi-leg route is its own jump. A ship that doesn't send `thr` falls back to the older rule: frozen for 1 s while the heading moves, or, with a Game.log route plotted and `qdrv` lit, without the heading. Before 2026-11-24 that older rule was all there was, and it called every stop with a route plotted a jump.

**Game.log**: see the Game.log section below for the route, arrival and obstruction lines. No line marks the start of a quantum jump.

**Actor**
- **Unchanged all session:** health 100 (you weren't hurt), hunger/thirst 100, body temperature 36.5, radiation 0, intoxication 0.
- **Varied:**
  - `oxygen` dropped to 0.83;
  - `heart_rate` ranged 58–171;
  - `gravity` read 1.0 in the station, 0.357 on the planet and 0 in space;
  - `pressure` was about 0 in vacuum (`1.7e-38`);
  - `external_temperature` read -273.15 in space;
  - `breathable_atmosphere` turned false outside.

## Game.log

The game's own debug log (`<channel>/Game.log`, a new file each launch; older ones in `logbackups/`). It isn't an API, but it carries what the telemetry stream doesn't. `agent/starglance/gamelog.py` follows it read-only and keeps only lines it recognises. Most useful lines are on-screen notifications, written as `<UpdateNotificationItem> Notification "<text>" [n], Action: Next` (then again with `StartFade` and `Remove`; we read only `Next`). Some notification texts contain a newline, so the line continues on the next log line, which starts with a timestamp and no tag; the reader joins them.

**What we use**

| What | Line | Notes |
|---|---|---|
| Your handle | `<Legacy login response> ... Handle[<handle>]` | To tell your kills from others'. Not displayed or sent. |
| Server | `<Join PU> address[..] port[..] shard[pub_use1b_13165946_150]`, `<Update Shard Id> New Shard Id: ...` | Same shard = same universe instance. The address is never kept. |
| Armistice | `Entering Armistice Zone - Combat Prohibited`, `Leaving Armistice Zone - Caution Advised` | Repeated by the game; deduplicated. |
| Jurisdiction | `Entered <name> Jurisdiction` | Hurston Dynamics, UEE, ArcCorp, Crusader Industries, microTech, People's Alliance, Rough & Ready, Ungoverned... |
| Monitored space | `Entered / Exited Monitored Space`, `Monitored Space Down / Restored` (comm array) | |
| Restricted area | `Restricted Area` + text (relocated, or "Vehicles Will Be Impounded"), `Leaving Restricted Area` | |
| Private property | `Entering / Leaving Private Property` | |
| Quantum route | `<Player Selected Quantum Target - Local> ... selected point <id> as their destination` | `OOC_Stanton_1b_Aberdeen` → "Aberdeen". |
| Quantum arrival | `<Quantum Drive Arrived - Arrived at Final Destination>` | End of the whole route (after every leg). |
| Quantum blocked | `Quantum Travel: Your destination is obstructed ...` | |
| Party calibration | `Quantum Travel Calibration Started / Complete By <player>` | |
| Contracts | `Contract Accepted / Shared / Complete / Failed: <title> <EM4>[150 Rep] [BP]*</EM4>` | Tags kept separately. `<EndMission> ... CompletionType[Abandon]` for abandoning (it has an id, not a title). |
| Objectives | `New Objective / Objective Complete / Objective Withdrawn: <text>` | |
| Rewards | `Awarded 1000 aUEC` | Counted under "uec" sharing. |
| Ships destroyed | `<Vehicle Destroyed> Vehicle '<id>' ... class '<class>' ... destroyed: reason [Combat] level [0] -> [2] ... killer '<name>'` | Level 2 = destroyed (1 = disabled). Lists ships near you too, so: yours (lost), by you (kill), by others (nearby). NPC classes end `_PU_AI_CRIM` (hostile), `_AI_CIV` (civilian)... |
| Injuries | `Minor / Moderate / Severe Injury Detected - <body part> - Tier <n> Treatment Required` | Cleared by a medical bed or respawn. |
| Incapacitated | `Incapacitated: ...` | |
| Medical bed | `Medical Bed: The bed has restored your health ...` | The game repeats it every couple of minutes near a bed, with or without anything to heal: `healed` only when it cleared injuries. |
| Hangar | `Hangar Request Completed`, `Joined hangar queue.` | |
| Blueprints | `Received Blueprint: <name>` | |
| Player deaths (old) | `<Actor Death> CActor::Kill: '<victim>' ... killed by '<killer>' using '<weapon>' ... damage type '<type>'` | Parsed in case it returns. |
| Jump drive (old) | `<Jump Drive State Changed> Now <State> \| ... \| <system> \|` | Through a jump point to another star system (not quantum travel). States: Idle, Tuning, EntryChecks, RequestingJump, WaitingForOpen, Entering, Transiting, Exiting. Parsed in case it returns. |

Ship channels (`You have joined channel ...` / `You have left the channel ...`) are read as the ship you're aboard (`location.aboard`); party chatter (`New Member Joined`) is left out. Boarding a ship joins its channel, named `'<Manufacturer Model> : <owner handle>'`, also for other players' ships: in two sessions the join came 12 s, 16 s and 28 s before sitting down (walking aboard), and "You have left the channel ..." a minute after walking off a Constellation. "Left" is often missing: none for an M80 left in a hangar and stored, or before quitting the game.
- `Restricted Area` + `For your safety, you've been relocated.` comes after the game has moved you out, so it ends a restricted area rather than starting one.

**How it has changed** (717 backed-up logs, 69 builds, January 2023 to November 2026):

| Line | Seen | Format |
|---|---|---|
| Login with handle | 2023-09 → now (63 builds) | unchanged |
| `<Join PU>` with shard | 2025-06 → now (29 builds) | unchanged |
| `<EndMission>` | 2025-05 → now | unchanged |
| Quantum route / arrival | 2025-12 → now (19 builds) | unchanged |
| Notifications (`<UpdateNotificationItem>`): zones, contracts, injuries, hangar... | 2026-01 → now | unchanged; the wording of individual texts is what varies |
| `<Actor Death>` | 2024-08 → 2025-10 | **gone** since |
| `<Jump Drive State Changed>` | 2025-02 → 2025-11 | **gone** since |
| `<Vehicle Destroyed>` | 2026-11-20 → now | **new** |

So a line's format tends to stay put for as long as the line exists, but whole line types come and go between patches. Re-run the scan after a big patch: `uv run python tools/logscan.py` (reads every `logbackups/*.log`, groups lines by shape with values replaced, so it prints no names).

 (§2.4, §2.5, §4)

**Not in the LIVE schema at all:**
- Vehicle hull `health`.
- `shields{level, faces[]}`.
- `master_mode{mode, spooled}` (NAV/SCM, quantum spool).

So the fleet board's hull and shield bars, master mode and `hull_threshold` events can't be built from LIVE today. What *is* available: the `shld` and `hit` warning lights, shield generator/emitter power, fuel, landed/gear state, and `ACTOR_DOWNED`/`ACTOR_DEAD` events. These may arrive in a later patch (community docs mention them, possibly from PTU). The agent re-extracts the schema whenever the exe changes, so the normalizer should treat them as optional.

**The spec says these aren't reported, but they are:** decoupled mode (`ifcs_coupled`), G-safe and proximity assist, as `{enabled, active}` flags. G-safe and cruise mode were seen changing.

**In the schema but never sent:** doors (`open_state`, `lock_state`).

**Renamed vs. the community notes' names:**
- countermeasures `remaining` is actually `amount`.
- weapons `powered` / "in active group" are `is_powered` / `contained_in_preset`.
- boost `reserve` is `reserves`.
- Annunciators are a 6-state enum, not booleans.
