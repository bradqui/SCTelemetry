"""Derive events by diffing consecutive snapshots (spec §4, "agent-side derived events").

The game's own seat events are unreliable (ENTER_SEAT arrived 3 of 6 times in
the first capture), so seat events come from state changes. The game's other
events (spawn, downed, dead, respawn) are passed through.

Warning lights: a light that stays minor/major for ``WARNING_ON_HOLD_MS`` is
``warning_on`` (shields flash MAJOR for a moment every time they come up);
``warning_off`` only once it has stayed calm for ``WARNING_OFF_HOLD_MS``.
Otherwise a ``hit`` light flashing through a fight would be dozens of events.
The thruster light in NAV is the quantum drive locking the thrusters, not a
fault (see ``expected_light``).
"""

from __future__ import annotations

from fleet_shared import Event, Snapshot, expected_light

WARNING_OFF_HOLD_MS = 5000
WARNING_ON_HOLD_MS = 600
HULL_THRESHOLDS = (0.75, 0.50, 0.25)
FUEL_THRESHOLDS = (0.25, 0.10)
ACTIVE_LEVELS = {"minor", "minor_flashing", "major", "major_flashing"}
PASSTHROUGH = {
    "actor_spawn": "spawn",
    "actor_downed": "downed",
    "actor_dead": "dead",
    "actor_respawn": "respawn",
}


class EventDeriver:
    def __init__(self) -> None:
        self.prev: Snapshot | None = None
        self.last_ship_id: str | None = None
        self.warnings_on: set[str] = set()
        self.calm_since: dict[str, int] = {}
        self.lit_since: dict[str, int] = {}

    def feed(self, snap: Snapshot, game_events: list[str] | None = None) -> list[Event]:
        out: list[Event] = []
        t = snap.t

        def emit(kind: str, **data) -> None:
            out.append(Event(t=t, kind=kind, data=data))  # type: ignore[arg-type]

        prev = self.prev
        st, pst = snap.status, prev.status if prev else None
        ship, pship = snap.ship, prev.ship if prev else None

        # -- seats (from state). The first snapshot only sets the starting state.
        seat, pseat = st.seat if st else None, pst.seat if pst else None
        if prev is not None and seat != pseat:
            if pseat:
                emit("seat_leave", seat=pseat, role=pst.role if pst else None)
            if seat:
                emit("seat_enter", seat=seat, role=st.role if st else None)

        # -- ships
        if ship and ship.id != self.last_ship_id:
            if self.last_ship_id is not None:
                emit("ship_change", ship=ship.id, model=ship.model, previous=self.last_ship_id)
            self.last_ship_id = ship.id

        same_ship = ship is not None and pship is not None and ship.id == pship.id
        if same_ship:
            assert ship and pship
            if ship.master_mode and pship.master_mode and ship.master_mode != pship.master_mode:
                emit("mode_change", mode=ship.master_mode, previous=pship.master_mode)
            if pship.flight.quantum is not True and ship.flight.quantum is True:
                emit("quantum_start", ship=ship.id)
            if pship.flight.quantum is True and ship.flight.quantum is False:
                emit("quantum_end", ship=ship.id)
            if pship.landed is True and ship.landed is False:
                emit("takeoff", ship=ship.id)
            if pship.landed is False and ship.landed is True:
                emit("landed", ship=ship.id)
            for level in _crossed_down(pship.hull, ship.hull, HULL_THRESHOLDS):
                emit("hull_threshold", ship=ship.id, below=level, hull=ship.hull)
            for level in _crossed_down(pship.flight.h2_fuel, ship.flight.h2_fuel, FUEL_THRESHOLDS):
                emit("fuel_threshold", ship=ship.id, below=level, fuel=ship.flight.h2_fuel)

        # -- warning lights, with a hold before "off"
        if ship is None:
            self.warnings_on.clear()
            self.calm_since.clear()
            self.lit_since.clear()
        else:
            active = {
                k
                for k, lvl in ship.lights.items()
                if lvl in ACTIVE_LEVELS and not expected_light(k, ship.master_mode)
            }
            for light in list(self.lit_since):
                if light not in active:
                    del self.lit_since[light]
            for light in sorted(active - self.warnings_on):
                # A ship we just sat in arrives with its lights already set: not news.
                if not same_ship:
                    self.warnings_on.add(light)
                    continue
                since = self.lit_since.setdefault(light, t)
                if t - since >= WARNING_ON_HOLD_MS:
                    emit("warning_on", light=light, level=ship.lights[light])
                    self.warnings_on.add(light)
            for light in sorted(self.warnings_on):
                if light in active:
                    self.calm_since.pop(light, None)
                    continue
                since = self.calm_since.setdefault(light, t)
                if t - since >= WARNING_OFF_HOLD_MS:
                    emit("warning_off", light=light)
                    self.warnings_on.discard(light)
                    self.calm_since.pop(light, None)

        # -- game's own events
        for kind in game_events or []:
            if kind in PASSTHROUGH:
                emit(PASSTHROUGH[kind])

        self.prev = snap
        return out


def _crossed_down(before: float | None, after: float | None, levels) -> list[float]:
    if before is None or after is None:
        return []
    return [lvl for lvl in levels if before >= lvl > after]
