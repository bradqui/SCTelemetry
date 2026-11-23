"""Our own compact telemetry schema (spec §4), built from what the game really sends.

The agent turns raw game frames into these models. The hub, web UI and cog
only ever see these, never the game's protobuf JSON, so CIG's schema changes
stay inside the agent's normalizer.

Every value the game might not send is optional. ``None`` means "not known
right now"; it is never a stand-in for zero.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1

SHARE_CATEGORIES = ("status", "ship", "weapons", "vitals", "uec")
"""What a member can switch off. Everything is shared by default (spec §11.6)."""

Level = Literal["off", "nominal", "minor", "minor_flashing", "major", "major_flashing"]
"""Warning light state, from the game's annunciator enum."""

Locomotion = Literal["on_foot", "eva", "seated", "unknown"]
SeatRole = Literal["pilot", "copilot", "gunner", "crew"]
MasterMode = Literal["NAV", "SCM"]
Deployment = Literal["retracted", "deploying", "deployed", "retracting"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


# ---------------------------------------------------------------- snapshot parts


class Status(_Model):
    in_game: bool = True
    locomotion: Locomotion = "unknown"
    seat: str | None = None
    """Seat name without the entity id, e.g. ``RSI_Constellation_Mk5_CoPilot_SeatDashboard``."""
    role: SeatRole | None = None
    """From the seat name, falling back to the game's crew role (it calls co-pilots PILOT)."""


class Shields(_Model):
    powered: bool | None = None
    level: float | None = None
    """0–1. Not sent by the game yet (LIVE 2026-11); kept so the UI can show it if it appears."""
    faces: list[float] | None = None


class Flight(_Model):
    speed: float | None = None
    """m/s."""
    alt: float | None = None
    """m above sea level; None in space (the game sends FLT_MAX there)."""
    radar_alt: float | None = None
    vsi: float | None = None
    heading: float | None = None
    g: float | None = None
    g_max: float | None = None
    atmo_density: float | None = None
    h2_fuel: float | None = None
    """0–1."""
    qt_fuel: float | None = None
    """0–1. The game always sends 0 so far; None until a non-zero value is seen."""
    boost_reserve: float | None = None
    boost_engaged: bool | None = None
    cruise: bool | None = None
    g_safe: bool | None = None
    coupled: bool | None = None
    prox_assist: bool | None = None
    quantum: bool | None = None
    """In quantum travel. Inferred: the game freezes speed and G during a jump
    while the heading still moves (see the agent's normalizer)."""


class Ship(_Model):
    id: str
    """Unique per ship instance: ``<class>_<entity id>``."""
    cls: str = Field(alias="class")
    model: str
    """Readable name, e.g. "Constellation Mk5 Centaurus"."""
    manufacturer: str | None = None
    type: Literal["spaceship", "ground", "gravlev", "boat", "unknown"] = "unknown"
    hull: float | None = None
    """0–1. Not sent by the game yet (LIVE 2026-11)."""
    master_mode: MasterMode | None = None
    """Inferred: NAV when the quantum drive light is on, SCM when it's off (and powered)."""
    powered: bool | None = None
    shields: Shields = Field(default_factory=Shields)
    power: dict[str, bool] = Field(default_factory=dict)
    lights: dict[str, Level] = Field(default_factory=dict)
    """All 10 warning lights: pwr wpn thr shld cool qdrv radr prox hit misl."""
    gear: Deployment | None = None
    landed: bool | None = None
    flight: Flight = Field(default_factory=Flight)


class Gun(_Model):
    name: str
    powered: bool
    ready: bool


class Countermeasure(_Model):
    type: Literal["decoy", "noise", "unknown"]
    count: int


class Weapons(_Model):
    gimbals_locked: bool | None = None
    guns: list[Gun] = Field(default_factory=list)
    countermeasures: list[Countermeasure] = Field(default_factory=list)

    @property
    def ready(self) -> int:
        return sum(g.ready for g in self.guns)


class Environment(_Model):
    temperature: float | None = None
    """°C outside the suit."""
    breathable: bool | None = None
    radiation: float | None = None


class Vitals(_Model):
    health: float | None = None
    """0–1."""
    oxygen: float | None = None
    hunger: float | None = None
    """0–1 where 1 is fully fed."""
    thirst: float | None = None
    body_temp: float | None = None
    heart_rate: float | None = None
    gravity: float | None = None
    pressure: float | None = None
    intoxication: int | None = None
    environment: Environment = Field(default_factory=Environment)


# ---------------------------------------------------------------- messages


class Route(_Model):
    """A plotted quantum route, from the game's Game.log (local view only for now)."""

    destination: str | None = None
    state: Literal["plotted", "en_route", "arrived", "blocked"]
    since: int
    """ms since epoch the state began."""


class Snapshot(_Model):
    type: Literal["snapshot"] = "snapshot"
    v: int = SCHEMA_VERSION
    t: int
    """ms since epoch."""
    status: Status | None = None
    ship: Ship | None = None
    weapons: Weapons | None = None
    vitals: Vitals | None = None
    uec: int | None = None
    route: Route | None = None
    """Never shared off this PC (see apply_sharing)."""


EventKind = Literal[
    "game_start",
    "game_exit",
    "seat_enter",
    "seat_leave",
    "ship_change",
    "mode_change",
    "quantum_start",
    "quantum_end",
    "quantum_route",
    "quantum_arrived",
    "quantum_blocked",
    "takeoff",
    "landed",
    "warning_on",
    "warning_off",
    "hull_threshold",
    "fuel_threshold",
    "spawn",
    "downed",
    "dead",
    "respawn",
]


class Event(_Model):
    type: Literal["event"] = "event"
    v: int = SCHEMA_VERSION
    t: int
    kind: EventKind
    data: dict = Field(default_factory=dict)


class Hello(_Model):
    type: Literal["hello"] = "hello"
    v: int = SCHEMA_VERSION
    agent_version: str
    channel: str | None = None
    game_build: str | None = None
    share: list[str] = Field(default_factory=lambda: list(SHARE_CATEGORIES))


class Heartbeat(_Model):
    type: Literal["heartbeat"] = "heartbeat"
    v: int = SCHEMA_VERSION
    t: int
    in_game: bool


# ---------------------------------------------------------------- privacy


def apply_sharing(snapshot: Snapshot, share: set[str] | list[str]) -> Snapshot:
    """A copy without the categories the member switched off (spec §3: privacy at the agent)."""
    share = set(share)
    return snapshot.model_copy(
        update={
            "status": snapshot.status if "status" in share else None,
            "ship": snapshot.ship if "ship" in share else None,
            "weapons": snapshot.weapons if "weapons" in share else None,
            "vitals": snapshot.vitals if "vitals" in share else None,
            "uec": snapshot.uec if "uec" in share else None,
            # Where you're heading is location: local only until the org decides otherwise.
            "route": None,
        }
    )
