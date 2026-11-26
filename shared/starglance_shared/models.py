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

RELEASES_URL = "https://github.com/bradqui/starglance/releases/latest"
"""Where agents are downloaded (the hub's update notices point here)."""


def version_tuple(version: str | None) -> tuple[int, ...] | None:
    """ "0.2.0" -> (0, 2, 0); None for anything else (a development build: never refused)."""
    if not version:
        return None
    core = version.strip().lstrip("v").split("+")[0].split("-")[0]
    parts = core.split(".")
    if not all(p.isdigit() for p in parts):
        return None
    return tuple(int(p) for p in parts)


_SYSTEMS = (
    ("iPhone", "iPhone"),
    ("iPad", "iPad"),
    ("Android", "Android"),
    ("CrOS", "ChromeOS"),
    ("Windows", "Windows"),
    ("Macintosh", "Mac"),
    ("Linux", "Linux"),
)
_BROWSERS = (
    ("Edg", "Edge"),
    ("OPR/", "Opera"),
    ("Firefox/", "Firefox"),
    ("FxiOS", "Firefox"),
    ("CriOS", "Chrome"),
    ("Chrome/", "Chrome"),
    ("Safari/", "Safari"),
)


def device_label(user_agent: str) -> str | None:
    """A rough name for a device from its User-Agent: "Safari on iPhone", "Edge on Windows"."""
    if not user_agent:
        return None
    system = next((name for key, name in _SYSTEMS if key in user_agent), None)
    browser = next((name for key, name in _BROWSERS if key in user_agent), None)
    if browser and system:
        return f"{browser} on {system}"
    return browser or system or "A browser"


SHARE_CATEGORIES = ("status", "ship", "weapons", "vitals", "uec", "location", "mission", "combat")
"""What a member can share with the fleet. All on by default; each can be switched off.

location: zone, jurisdiction, server, star system, planet or moon, landing area, quantum
destination (no coordinates).
mission: current contracts and objectives. combat: kills, ships lost, session counts."""

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
    handle: str | None = None
    """Your in-game handle (Game.log login line): how other members' ship channels name you."""


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


class Injury(_Model):
    part: str
    """E.g. "Head", "Left arm", "Torso"."""
    severity: str
    """minor | moderate | severe."""
    tier: int
    """Medical treatment tier required (1 is the most capable bed)."""


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
    injuries: list[Injury] = Field(default_factory=list)
    """From Game.log; cleared by a medical bed or respawning."""


# ---------------------------------------------------------------- messages


class Route(_Model):
    """A plotted quantum route (within a star system), from Game.log."""

    destination: str | None = None
    state: Literal["plotted", "en_route", "arrived", "blocked"]
    since: int
    """ms since epoch the state began."""


class LastArrived(_Model):
    """Where your last quantum jump ended, and when. Not where you are: you may have moved
    on since, and the log doesn't say. Forgotten on a new route, a server change, death,
    or after a while (gamelog.LAST_ARRIVED_MS)."""

    destination: str
    since: int


class Aboard(_Model):
    """The ship you're aboard, seated or not, from its comms channel: boarding a ship
    joins "<Manufacturer Model> : <owner handle>". Leaving isn't always logged, so this
    also ends on another ship's channel, a server change, death or a new game."""

    ship: str
    """E.g. "RSI Constellation Taurus" (the game's name, not the class)."""
    owner: str
    """The owner's in-game handle."""
    since: int


class Location(_Model):
    """Where you are in game terms, from Game.log notices. No coordinates."""

    armistice: bool | None = None
    jurisdiction: str | None = None
    monitored: bool | None = None
    """In monitored space (crimes are reported)."""
    comms: bool | None = None
    """False while the local comm array is down ("Monitored Space Down")."""
    restricted: bool | None = None
    private: bool | None = None
    """On private property."""
    shard: str | None = None
    """The server, e.g. pub_use1b_13165946_150: the same shard means the same universe."""
    system: str | None = None
    """Star system, when the game names it (jump drive lines)."""
    route: Route | None = None
    last_arrived: LastArrived | None = None
    landing: str | None = None
    """The landing area you're in: a city, station, outpost or gateway ("Lorville"), by
    the name the game shows (read from the player's own game files)."""
    body: str | None = None
    """The planet or moon you're at ("Daymar"), from the ground the game has loaded, a
    jump that just ended there, or where a route was plotted from."""
    aboard: Aboard | None = None


class Objective(_Model):
    """One of a contract's objectives ("Deliver 0/168 SCU of Ammonia to ..."). The log
    gives its text when it's set; it doesn't report delivery progress along the way."""

    id: str | None = None
    """The game's id for it (from the notice), so a repeat or a change finds the same one."""
    text: str
    state: Literal["active", "complete", "failed", "withdrawn"] = "active"


class Mission(_Model):
    """A contract (or loose objective) from Game.log notices."""

    id: str | None = None
    """The game's mission id, when the log gave one: objectives and endings find their
    contract by it (several can be active at once)."""
    title: str | None = None
    tags: list[str] = Field(default_factory=list)
    """E.g. ["150 Rep", "BP"] from the contract name."""
    state: Literal["active", "complete", "failed", "abandoned"]
    since: int
    objectives: list[Objective] = Field(default_factory=list)
    """Every objective, in the order the game set them (hauling contracts have several)."""
    shared: bool = False


class Session(_Model):
    """Counts for this game session, from Game.log."""

    kills: int = 0
    """Ships (or, in older builds, players) destroyed by you."""
    ships_lost: int = 0
    deaths: int = 0
    incaps: int = 0
    contracts: int = 0
    """Contracts completed."""
    failed: int = 0
    earned: int = 0
    """aUEC awarded (shared only with "uec")."""
    quantum_trips: int = 0
    """Quantum routes completed (within a system)."""
    system_jumps: int = 0
    """Jump point transits to another star system."""


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
    location: Location | None = None
    missions: list[Mission] | None = None
    """Active contracts first, then ones that just ended."""
    session: Session | None = None


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
    "place_enter",
    "qt_calibration",
    "jump_start",
    "jump_end",
    "shard_join",
    "armistice_enter",
    "armistice_leave",
    "jurisdiction",
    "monitored_enter",
    "monitored_leave",
    "comms_down",
    "comms_restored",
    "restricted_enter",
    "restricted_leave",
    "private_enter",
    "private_leave",
    "contract_accepted",
    "contract_shared",
    "contract_complete",
    "contract_failed",
    "contract_abandoned",
    "objective_new",
    "objective_complete",
    "objective_withdrawn",
    "objective_failed",
    "reward",
    "kill",
    "vehicle_destroyed",
    "ship_lost",
    "death",
    "injury",
    "healed",
    "incapacitated",
    "hangar_ready",
    "hangar_queue",
    "boarded",
    "disembarked",
    "blueprint",
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


class Delta(_Model):
    """What changed in the snapshot since the last one sent (see ``starglance_shared.patch``).

    Agent -> hub only, between full snapshots. ``patch`` is a merge patch of the
    snapshot's JSON (by alias, e.g. ``ship.class``)."""

    type: Literal["delta"] = "delta"
    v: int = SCHEMA_VERSION
    t: int
    patch: dict


class Heartbeat(_Model):
    type: Literal["heartbeat"] = "heartbeat"
    v: int = SCHEMA_VERSION
    t: int
    in_game: bool


def expected_light(light: str, master_mode: str | None) -> bool:
    """A lit warning light that isn't a fault: in NAV the quantum drive locks the
    thrusters (THR reads MAJOR through every jump). Alarms and warning events skip it;
    the lights themselves still show what the game shows."""
    return light == "thr" and master_mode == "NAV"


FLEET_ALARM_HOLD_MS = 1000
"""A light must stay on this long before the fleet hears about it (shields blip MAJOR for
a moment every time they come up)."""
FLEET_ALARM_OFF_MS = 3000
"""...and off this long before it clears (the hit light flickers between hits)."""


def fleet_alarm_lights(lights: dict) -> dict[str, str]:
    """The warning lights worth telling the whole fleet about: light -> "major".

    The cockpit shows every light, as the game's panel does. The fleet only hears that
    someone needs help now: getting hit, or a radar warning (on for exactly the stretches
    hostiles were about, in every recording so far). No cautions: they last (thruster
    damage stays minor for minutes after a fight) and aren't a call for help. Those, and
    shields coming back after NAV, weapons not ready while landed and proximity, stay on
    that member's card and dashboard.
    """
    out: dict[str, str] = {}
    hit = lights.get("hit")
    if isinstance(hit, str) and hit.startswith(("major", "minor")):
        out["hit"] = "major"
    if lights.get("radr") in ("major", "major_flashing"):
        out["radr"] = "major"
    return out


def alert_lights(lights: dict, master_mode: str | None = None) -> dict[str, str]:
    """Every lit warning light, as the headers' alerts: light -> "major" (a warning) or
    "minor" (a caution). Each viewer picks which go in its headers (the page's alert
    settings); the hub holds them like fleet alarms first (FLEET_ALARM_HOLD_MS/_OFF_MS).
    The hit light counts as a warning whatever it shows; THR in NAV isn't a fault
    (expected_light)."""
    out: dict[str, str] = {}
    for light, value in lights.items():
        if not isinstance(value, str) or expected_light(light, master_mode):
            continue
        if value.startswith("major") or (light == "hit" and value.startswith("minor")):
            out[light] = "major"
        elif value.startswith("minor"):
            out[light] = "minor"
    return out


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
            "location": snapshot.location if "location" in share else None,
            "missions": snapshot.missions if "mission" in share else None,
            "session": _session_shared(snapshot.session, share),
        }
    )


def _session_shared(session: Session | None, share: set[str]) -> Session | None:
    if session is None or "combat" not in share:
        return None
    return session if "uec" in share else session.model_copy(update={"earned": 0})


EVENT_CATEGORY: dict[str, str] = {
    **dict.fromkeys(
        [
            "quantum_route",
            "quantum_arrived",
            "quantum_blocked",
            "place_enter",
            "qt_calibration",
            "jump_start",
            "jump_end",
            "shard_join",
            "armistice_enter",
            "armistice_leave",
            "jurisdiction",
            "monitored_enter",
            "monitored_leave",
            "comms_down",
            "comms_restored",
            "restricted_enter",
            "restricted_leave",
            "private_enter",
            "private_leave",
            "boarded",
            "disembarked",
        ],
        "location",
    ),
    **dict.fromkeys(
        [
            "contract_accepted",
            "contract_shared",
            "contract_complete",
            "contract_failed",
            "contract_abandoned",
            "objective_new",
            "objective_complete",
            "objective_withdrawn",
            "objective_failed",
        ],
        "mission",
    ),
    **dict.fromkeys(["kill", "vehicle_destroyed", "ship_lost", "death"], "combat"),
    **dict.fromkeys(["injury", "healed", "incapacitated"], "vitals"),
    "reward": "uec",
}
"""Events about a share category; the rest follow "status"."""


def event_shared(event: Event, share: set[str] | list[str]) -> bool:
    """Whether a member's sharing settings allow this event to leave their PC."""
    return EVENT_CATEGORY.get(event.kind, "status") in set(share)
