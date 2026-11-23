# Telemetry fields (from the game's own definitions)

**Source:** extracted from the LIVE `StarCitizen.exe` dated 2026-11-19 (175,570,944 bytes) with `python -m fleet_agent protoset`. Package `sc.game.telemetry.v1`, files `types.proto` and `api.proto`, proto3.

This is the **schema**: which fields exist and their types. Which fields the game actually fills in, and with what values, still needs real captures (Phase 0, `tools/capture.py`). The HOTFIX build on Brad's PC (2026-06-12) predates telemetry and has no definitions.

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

## Differences from the spec (§2.4, §2.5, §4)

**Not in the LIVE schema at all:**
- Vehicle hull `health`.
- `shields{level, faces[]}`.
- `master_mode{mode, spooled}` (NAV/SCM, quantum spool).

So the fleet board's hull and shield bars, master mode and `hull_threshold` events can't be built from LIVE today. What *is* available: the `shld` and `hit` warning lights, shield generator/emitter power, fuel, landed/gear state, and `ACTOR_DOWNED`/`ACTOR_DEAD` events. These may arrive in a later patch (community docs mention them, possibly from PTU). The agent re-extracts the schema whenever the exe changes, so the normalizer should treat them as optional.

**In the schema although the spec says "not reported":**
- Decoupled mode (`ifcs_coupled`), G-safe and proximity assist, as `{enabled, active}` flags.
- Doors (`open_state`, `lock_state`).

Captures will show whether the game actually fills these in.

**Renamed vs. the spec's guesses:**
- countermeasures `remaining` is actually `amount`.
- weapons `powered` / "in active group" are `is_powered` / `contained_in_preset`.
- boost `reserve` is `reserves`.
- Annunciators are a 6-state enum, not booleans.
