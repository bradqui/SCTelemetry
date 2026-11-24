"""Raw game frames (``MessageToDict`` output) -> our ``Snapshot`` (spec §4).

Written against real LIVE captures (docs/FIELDS.md, fixtures/). Every field is
treated as optional and unknown shapes never raise: CIG can change the stream
in any patch. Quirks handled here:

- ``crew_role`` flickers PILOT -> UNSPECIFIED -> PILOT on sitting down: keep the
  last known role for the same seat.
- ``locomotion`` flickers ON_FOOT <-> EVA around airlocks: a new value must hold
  for ``LOCOMOTION_HOLD_MS`` before it's reported.
- ``hydrogen_fuel`` reads 0 whenever the engines are off, and for a moment after
  the vehicle appears: reported as None (unknown) then, not as empty.
- altitude is FLT_MAX in space -> None.
- heading is a compass bearing over the planet below. With no planet (altitude
  FLT_MAX) the game keeps sending the last value, frozen, however hard you turn:
  reported as None there.
- ``quantum_fuel`` is always 0 -> None until a non-zero value is ever seen.
- no master mode field: NAV when the quantum drive light is lit, SCM when it's
  off, None when the ship is unpowered.
- no quantum travel field. During a jump the flight instruments freeze: ``speed``
  repeats the exact same value (0, 0.05, 21.7, whatever it was) and G reads
  exactly 0, while the heading still drifts. A ship stopped in space also has a
  frozen speed and zero G, but its heading is frozen too. So: quantum when speed
  is bit-identical with G == 0 for ``QUANTUM_FREEZE_MS`` and the heading moved.
  Once in a jump, it lasts until G reads anything but 0: mid-jump the speed can
  step (e.g. to exactly 0) and the heading can hold still for 15 s or more.
  Far from any planet the heading never moves (see above), so a jump there
  can't be told from a stop by the instruments alone. Game.log fills the gap:
  when a quantum route is plotted (``route_active``, set by the pipeline) and the
  quantum drive is lit (NAV), frozen instruments count without the heading.
  Every jump in a 44-minute session (including multi-leg routes) fell inside a
  plotted route with NAV on; both dead stops in deep space were outside one.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from fleet_shared import (
    Countermeasure,
    Environment,
    Flight,
    Gun,
    Shields,
    Ship,
    Snapshot,
    Status,
    Vitals,
    Weapons,
)

log = logging.getLogger(__name__)

LOCOMOTION_HOLD_MS = 400
QUANTUM_FREEZE_MS = 1000
"""How long the instruments must stay frozen before it counts as a quantum jump."""
FUEL_SETTLE_MS = 2000
FLT_MAX_ISH = 1e30

_ENTITY_ID = re.compile(r"_\d{6,}$")

MANUFACTURERS = {
    "AEGS": "Aegis Dynamics",
    "ANVL": "Anvil Aerospace",
    "AOPOA": "Aopoa",
    "ARGO": "Argo Astronautics",
    "BANU": "Banu",
    "CNOU": "Consolidated Outland",
    "CRUS": "Crusader Industries",
    "DRAK": "Drake Interplanetary",
    "ESPR": "Esperia",
    "GAMA": "Gatac Manufacture",
    "GRIN": "Greycat Industrial",
    "KRIG": "Kruger Intergalactic",
    "MISC": "MISC",
    "MRAI": "Mirai",
    "ORIG": "Origin Jumpworks",
    "RSI": "Roberts Space Industries",
    "TMBL": "Tumbril",
    "VNCL": "Vanduul",
    "XIAN": "Aopoa",
    "XNAA": "Aopoa",
}

POWER_KEYS = {
    "powerplants": "powerplants",
    "engines": "engines",
    "weapons": "weapons",
    "coolers": "coolers",
    "life_support": "life_support",
    "gravity_generators": "gravity_generators",
    "sensors": "sensors",
    "shield_generators": "shield_generators",
    "shield_emitters": "shield_emitters",
}
LIGHT_KEYS = ("pwr", "wpn", "thr", "shld", "cool", "qdrv", "radr", "prox", "hit", "misl")


# ---------------------------------------------------------------- small helpers


def _get(d: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(d, dict):
            return None
        d = d.get(key)
    return d


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f or abs(f) > FLT_MAX_ISH:  # NaN or FLT_MAX
        return None
    return f


def _int(value: Any) -> int | None:
    try:
        return int(value) if not isinstance(value, bool) else None
    except (TypeError, ValueError):
        return None


def _bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _frac(gauge: Any) -> float | None:
    cur, mx = _num(_get(gauge, "current")), _num(_get(gauge, "max"))
    if cur is None or not mx:
        return None
    return max(0.0, min(1.0, cur / mx))


def _enum(value: Any, prefix: str) -> str | None:
    """``ACTOR_LOCOMOTION_STATE_ON_FOOT`` -> ``on_foot``; UNSPECIFIED -> None."""
    if not isinstance(value, str) or not value:
        return None
    name = value[len(prefix) :] if value.startswith(prefix) else value
    name = name.lower()
    return None if name in ("unspecified", "") else name


LEVELS = {"off", "nominal", "minor", "minor_flashing", "major", "major_flashing"}
DEPLOYMENTS = {"retracted", "deploying", "deployed", "retracting"}
VEHICLE_TYPES = {"spaceship", "ground", "gravlev", "boat"}
LOCOMOTIONS = {"on_foot", "eva", "seated"}


def _choice(value: str | None, allowed: set[str]) -> str | None:
    """A value the schema knows, or None (a new game enum value must not break the snapshot)."""
    return value if value in allowed else None


def strip_entity_id(name: str) -> str:
    return _ENTITY_ID.sub("", name)


def seat_role(seat: str | None, crew_role: str | None) -> str | None:
    s = (seat or "").lower()
    if "copilot" in s or "co_pilot" in s:
        return "copilot"
    if "pilot" in s:
        return "pilot"
    if "gunner" in s or "turret" in s:
        return "gunner"
    if crew_role in ("pilot", "gunner", "crew"):
        return crew_role
    return "crew" if seat else None


def model_name(class_name: str) -> str:
    """E.g. ``RSI_Constellation_Mk5_Centaurus`` -> "Constellation Mk5 Centaurus"."""
    prefix, _, rest = class_name.partition("_")
    words = (rest or prefix).split("_")
    return " ".join(w[:1].upper() + w[1:] for w in words if w)


def manufacturer_for(class_name: str, given: Any) -> str | None:
    if isinstance(given, str) and given:
        return given
    return MANUFACTURERS.get(class_name.partition("_")[0].upper())


# ---------------------------------------------------------------- normalizer


class Normalizer:
    """Stateful: some quirks need the previous frames. One per game session."""

    def __init__(self) -> None:
        self._locomotion: str | None = None
        self._locomotion_candidate: tuple[str, int] | None = None
        self._seat: str | None = None
        self._role: str | None = None
        self._vehicle_since: int | None = None
        self._vehicle_id: str | None = None
        self._master_mode: str | None = None
        self._qt_fuel_seen = False
        self.route_active = False
        """A quantum route is plotted (from Game.log); see the module docstring."""
        self._qt_reset()
        self._warned: set[str] = set()

    def feed(self, raw: dict, t: int) -> Snapshot:
        try:
            return self._feed(raw if isinstance(raw, dict) else {}, t)
        except Exception:  # never let a weird frame kill the agent
            log.exception("Couldn't normalize a frame; sending status only")
            return Snapshot(t=t, status=Status(locomotion="unknown"))

    # -- sections

    def _feed(self, raw: dict, t: int) -> Snapshot:
        self._check_shape(raw)
        status = self._status(raw.get("actor") or {}, t)
        vehicle_state = _get(raw, "vehicle", "state")
        ship = self._ship(vehicle_state, t) if isinstance(vehicle_state, dict) else None
        if ship is None:
            self._vehicle_since = None
            self._vehicle_id = None
            self._master_mode = None
            self._qt_reset()
        weapons = self._weapons(raw.get("weapons")) if ship is not None else None
        return Snapshot(
            t=t,
            status=status,
            ship=ship,
            weapons=weapons,
            vitals=self._vitals(raw.get("actor") or {}),
            uec=_int(_get(raw, "actor", "state", "uec_balance")),
        )

    def _status(self, actor: dict, t: int) -> Status:
        raw_loco = (
            _choice(
                _enum(_get(actor, "state", "locomotion"), "ACTOR_LOCOMOTION_STATE_"), LOCOMOTIONS
            )
            or "unknown"
        )
        locomotion = self._debounce_locomotion(raw_loco, t)

        seat_name = _get(actor, "state", "seat_name")
        seat = strip_entity_id(seat_name) if isinstance(seat_name, str) and seat_name else None
        crew = _enum(_get(actor, "state", "crew_role"), "ACTOR_CREW_ROLE_")

        if seat != self._seat:
            self._seat = seat
            self._role = None
        role = seat_role(seat, crew) if seat else None
        if seat and crew is None and self._role:
            role = self._role  # the UNSPECIFIED flicker
        if role:
            self._role = role
        return Status(in_game=True, locomotion=locomotion, seat=seat, role=role)

    def _debounce_locomotion(self, value: str, t: int) -> str:
        if self._locomotion is None:
            self._locomotion = value
        elif value != self._locomotion:
            cand = self._locomotion_candidate
            if cand is None or cand[0] != value:
                self._locomotion_candidate = (value, t)
            elif t - cand[1] >= LOCOMOTION_HOLD_MS:
                self._locomotion = value
                self._locomotion_candidate = None
        else:
            self._locomotion_candidate = None
        return self._locomotion  # type: ignore[return-value]

    def _ship(self, vs: dict, t: int) -> Ship | None:
        raw_name = vs.get("name")
        class_name = vs.get("class_name") or (strip_entity_id(raw_name) if raw_name else None)
        if not class_name:
            return None
        ship_id = raw_name or class_name
        if ship_id != self._vehicle_id:
            self._vehicle_id = ship_id
            self._vehicle_since = t
            self._master_mode = None
            self._qt_reset()

        power = {
            ours: v
            for theirs, ours in POWER_KEYS.items()
            if (v := _bool(_get(vs, "power", theirs))) is not None
        }
        lights = {
            k: lvl
            for k in LIGHT_KEYS
            if (lvl := _choice(_enum(_get(vs, "annunciators", k), "ANNUNCIATOR_STATE_"), LEVELS))
        }
        powered = power.get("powerplants")

        flight = vs.get("flight") or {}
        inst = flight.get("instruments") or {}
        settings = flight.get("settings") or {}
        fstate = flight.get("state") or {}

        h2 = _num(inst.get("hydrogen_fuel"))
        settling = self._vehicle_since is not None and t - self._vehicle_since < FUEL_SETTLE_MS
        if h2 == 0 and (settling or power.get("engines") is False):
            h2 = None  # the gauge reads 0 whenever the engines are off
        qt = _num(inst.get("quantum_fuel"))
        if qt:
            self._qt_fuel_seen = True
        if not self._qt_fuel_seen:
            qt = None

        speed = _num(inst.get("speed"))
        alt = _num(inst.get("altitude"))
        raw_alt = inst.get("altitude")
        deep_space = isinstance(raw_alt, (int, float)) and abs(raw_alt) > FLT_MAX_ISH
        nav = powered is not False and lights.get("qdrv") not in (None, "off")
        quantum = self._quantum(
            inst.get("speed"), _get(inst, "g_meter", "current"), inst.get("heading"), t, nav
        )

        shields_powered = power.get("shield_generators")
        if shields_powered is not None and power.get("shield_emitters") is not None:
            shields_powered = shields_powered and power["shield_emitters"]

        return Ship(
            id=ship_id,
            cls=class_name,
            model=model_name(class_name),
            manufacturer=manufacturer_for(class_name, vs.get("manufacturer")),
            type=_choice(_enum(vs.get("type"), "VEHICLE_TYPE_"), VEHICLE_TYPES) or "unknown",  # type: ignore[arg-type]
            hull=_frac(vs.get("health")) if isinstance(vs.get("health"), dict) else None,
            master_mode=self._infer_mode(lights.get("qdrv"), powered),
            powered=powered,
            shields=Shields(
                powered=shields_powered,
                level=_num(_get(vs, "shields", "level")),
            ),
            power=power,
            lights=lights,  # type: ignore[arg-type]
            gear=_choice(  # type: ignore[arg-type]
                _enum(fstate.get("gear"), "VEHICLE_COMPONENT_DEPLOYMENT_STATE_"), DEPLOYMENTS
            ),
            landed=_bool(fstate.get("is_landed")),
            flight=Flight(
                speed=speed,
                alt=alt,
                radar_alt=_num(inst.get("radar_altitude")),
                vsi=_num(inst.get("vertical_speed_indicator")),
                heading=None if deep_space else _num(inst.get("heading")),
                g=_num(_get(inst, "g_meter", "current")),
                g_max=_num(_get(inst, "g_meter", "max")),
                atmo_density=_num(inst.get("atmospheric_density")),
                h2_fuel=h2,
                qt_fuel=qt,
                boost_reserve=_num(_get(inst, "boost", "reserves")),
                boost_engaged=_bool(_get(inst, "boost", "engaged")),
                cruise=_bool(_get(settings, "ifcs_cruise_mode", "active")),
                g_safe=_bool(_get(settings, "ifcs_g_safe", "active")),
                coupled=_bool(_get(settings, "ifcs_coupled", "active")),
                prox_assist=_bool(_get(settings, "ifcs_proximity_assist", "active")),
                quantum=quantum,
            ),
        )

    def _qt_reset(self) -> None:
        self._qt_last: tuple[Any, Any] | None = None  # raw (speed, heading) last frame
        self._qt_since: int | None = None  # when the speed froze
        self._qt_turned = False  # heading moved while frozen
        self._qt_on = False

    def _quantum(self, speed: Any, g: Any, heading: Any, t: int, nav: bool = False) -> bool | None:
        """Raw values on purpose: "frozen" means bit-identical, not merely close."""
        if not isinstance(speed, (int, float)) or isinstance(speed, bool):
            self._qt_reset()
            return None
        last, self._qt_last = self._qt_last, (speed, heading)
        if self._qt_on and g == 0:
            return True
        if last is None or speed != last[0] or g != 0:
            self._qt_since, self._qt_turned, self._qt_on = None, False, False
            return False
        if self._qt_since is None:
            self._qt_since = t
        if heading != last[1]:
            self._qt_turned = True
        moving = self._qt_turned or (self.route_active and nav)
        self._qt_on = moving and t - self._qt_since >= QUANTUM_FREEZE_MS
        return self._qt_on

    def _infer_mode(self, qdrv: str | None, powered: bool | None) -> str | None:
        if powered is False or qdrv is None:
            self._master_mode = None
        elif qdrv == "off":
            self._master_mode = "SCM"
        else:
            self._master_mode = "NAV"
        return self._master_mode

    def _weapons(self, w: Any) -> Weapons | None:
        if not isinstance(w, dict):
            return None
        guns = [
            Gun(
                name=strip_entity_id(str(g.get("name", ""))),
                powered=bool(g.get("is_powered")),
                ready=bool(g.get("ready_to_fire")),
            )
            for g in w.get("weapons") or []
            if isinstance(g, dict)
        ]
        cms = [
            Countermeasure(
                type=_choice(_enum(c.get("type"), "COUNTERMEASURE_TYPE_"), {"decoy", "noise"})  # type: ignore[arg-type]
                or "unknown",
                count=_int(c.get("amount")) or 0,
            )
            for c in w.get("countermeasures") or []
            if isinstance(c, dict)
        ]
        return Weapons(
            gimbals_locked=_bool(_get(w, "settings", "gimbals_locked")),
            guns=guns,
            countermeasures=cms,
        )

    def _vitals(self, actor: dict) -> Vitals | None:
        v = actor.get("vitals")
        env = actor.get("environment") or {}
        if not isinstance(v, dict):
            return None
        return Vitals(
            health=_frac(v.get("health")),
            oxygen=_frac(v.get("oxygen")),
            hunger=_frac(v.get("hunger")),
            thirst=_frac(v.get("thirst")),
            body_temp=_num(_get(v, "body_temperature", "current")),
            heart_rate=_num(v.get("heart_rate")),
            gravity=_num(v.get("gravity")),
            pressure=_num(v.get("pressure")),
            intoxication=_int(v.get("intoxication_level")),
            environment=Environment(
                temperature=_num(env.get("external_temperature")),
                breathable=_bool(env.get("breathable_atmosphere")),
                radiation=_num(env.get("ambient_radiation_rate")),
            ),
        )

    def _check_shape(self, raw: dict) -> None:
        """Log (once per session) top-level sections we don't know, to spot game changes."""
        known = {"actor", "vehicle", "weapons", "events", "turret", "force_feedback"}
        for key in raw:
            if key not in known and key not in self._warned:
                self._warned.add(key)
                log.warning("New telemetry section from the game: %r (not shown yet)", key)


def raw_game_events(raw: dict) -> list[str]:
    """Game event types in a frame, e.g. ``['actor_downed']``."""
    events = _get(raw, "events", "events")
    if not isinstance(events, list):
        return []
    out = []
    for e in events:
        kind = _enum(_get(e, "type"), "GAME_EVENT_TYPE_")
        if kind:
            out.append(kind)
    return out
