# Telemetry fields (from the game's own definitions)

**Source:** extracted from the LIVE `StarCitizen.exe` dated 2026-11-19 (175,570,944 bytes) with `python -m fleet_agent protoset`. Package `sc.game.telemetry.v1`, files `types.proto` and `api.proto`, proto3.

The first half of this document is the **schema**: which fields exist and their types. **Observed in a real session** describes what the game actually sends. The HOTFIX build on Brad's PC (2026-06-12) predates telemetry and has no definitions.

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
- `prox`, `radr`, `thr` and `wpn` also change.

**Flight**
- `altitude` and `radar_altitude` are `3.4028235e38` (FLT_MAX) in space, so they should be treated as null.
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
- During a jump the flight instruments **freeze**: `speed` repeats one exact value (0, 0.056, 21.7, whatever it was when the drive engaged; mid-jump it can step once, e.g. to exactly 0) and `g_meter.current` reads exactly 0. The heading still drifts slightly.
- `altitude` keeps updating: it leaped 23 km → 45 km → FLT_MAX in a second on the way out and fell from 11 km on arrival while `speed` read 0.
- `thr` often goes MAJOR_ON and `ifcs_g_safe`/`ifcs_esp` go inactive for parts of the jump, but not consistently.
- A ship stopped dead in space also has a frozen `speed` and G of 0, but its heading is frozen too.

So the normalizer infers `flight.quantum`: speed bit-identical with G exactly 0 for 1 s while the heading moves; it then lasts until G reads anything but 0. In the 44-minute session it found all three routes (one 68 s jump; two routes that were split into two legs around an obstruction) and neither of two dead stops in space. Short legs (~7 s) are only recognised near their end. One more 7 s freeze at 1026 m/s, right after an "obstructed" notice, was also flagged; we can't tell from the data what it was.

**Game.log** records more (read-only, the agent already reads it for the port):
- `<Player Selected Quantum Target - Local> ... Player has selected point <destination> as their destination` when a route is plotted.
- `<Quantum Drive Arrived - Arrived at Final Destination>` at the end of the route (matched the telemetry to the second).
- A notification line when the destination is obstructed.
- No line marks the start of a jump.

**Actor**
- **Unchanged all session:** health 100 (you weren't hurt), hunger/thirst 100, body temperature 36.5, radiation 0, intoxication 0.
- **Varied:**
  - `oxygen` dropped to 0.83;
  - `heart_rate` ranged 58–171;
  - `gravity` read 1.0 in the station, 0.357 on the planet and 0 in space;
  - `pressure` was about 0 in vacuum (`1.7e-38`);
  - `external_temperature` read -273.15 in space;
  - `breathable_atmosphere` turned false outside.

## Differences from the spec (§2.4, §2.5, §4)

**Not in the LIVE schema at all:**
- Vehicle hull `health`.
- `shields{level, faces[]}`.
- `master_mode{mode, spooled}` (NAV/SCM, quantum spool).

So the fleet board's hull and shield bars, master mode and `hull_threshold` events can't be built from LIVE today. What *is* available: the `shld` and `hit` warning lights, shield generator/emitter power, fuel, landed/gear state, and `ACTOR_DOWNED`/`ACTOR_DEAD` events. These may arrive in a later patch (community docs mention them, possibly from PTU). The agent re-extracts the schema whenever the exe changes, so the normalizer should treat them as optional.

**The spec says these aren't reported, but they are:** decoupled mode (`ifcs_coupled`), G-safe and proximity assist, as `{enabled, active}` flags. G-safe and cruise mode were seen changing.

**In the schema but never sent:** doors (`open_state`, `lock_state`).

**Renamed vs. the spec's guesses:**
- countermeasures `remaining` is actually `amount`.
- weapons `powered` / "in active group" are `is_powered` / `contained_in_preset`.
- boost `reserve` is `reserves`.
- Annunciators are a 6-state enum, not booleans.
