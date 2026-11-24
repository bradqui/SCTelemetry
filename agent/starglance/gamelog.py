"""Follow the game's Game.log for what the telemetry stream doesn't carry.

Game.log is the game's own debug log, written fresh on every launch. It isn't an
API: CIG adds, rewords and removes lines between patches (docs/FIELDS.md has the
history from four years of logs). So every parser here is optional, an
unrecognised line is ignored, and nothing breaks if a line type disappears.

What we read (party channel chatter deliberately left out):

- location: armistice zones, jurisdiction, monitored space (and comm arrays
  down), restricted areas, private property, the server (shard)
- the ship you're aboard, seated or on foot: boarding a ship joins its comms
  channel, "<Manufacturer Model> : <owner handle>" (leaving is logged only
  sometimes)
- quantum travel (within a star system): route plotted with destination,
  arrival, obstruction, party calibration
- jump drive (through a jump point to another star system), older format only
  so far, and the star system it names
- contracts: accepted, shared, completed, failed, abandoned; objectives; rewards
- combat: ships destroyed (yours, by you, near you); player deaths and the jump
  drive in the older formats, in case they come back
- personal: injuries (body part, severity, tier), incapacitation, medical bed
- hangar requests, blueprints received

Only lines a parser recognises are kept anywhere (captures included).
"""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from starglance_shared import Aboard, Event, Injury, Location, Mission, Route, Session

from .normalize import model_name

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- parsing


@dataclass(frozen=True)
class LogEvent:
    kind: str
    data: dict = field(default_factory=dict)


_TS = re.compile(r"^<\d{4}-\d\d-\d\dT[^>]*>\s?")
_NOTIFICATION = re.compile(r'<UpdateNotificationItem> Notification "(.*)" \[\d+\], Action: Next')
_ROUTE = re.compile(r"Player has selected point (\S+) as their destination")
_HANDLE = re.compile(r"<Legacy login response>.*?Handle\[([^\]]+)\]")
_SHARD = re.compile(r"<Join PU>.*?shard\[([^\]]+)\]|<Update Shard Id> New Shard Id: ([\w-]+)")
_END_MISSION = re.compile(r"<EndMission>.*?CompletionType\[(\w+)\]")
_VEHICLE = re.compile(
    r"<Vehicle Destroyed> Vehicle '([^']+)'.*?class '([^']+)'.*?destroyed: reason \[(\w+)\]"
    r" level \[(\d+)\] -> \[(\d+)\].*?killer '([^']*)'"
)
_ACTOR_DEATH = re.compile(
    r"<Actor Death> CActor::Kill: '([^']+)'.*?killed by '([^']+)'.*?using '([^']*)'"
    r".*?damage type '([^']*)'"
)
_JUMP_DRIVE = re.compile(r"<Jump Drive State Changed> Now (\w+) \|[^|]*\|[^|]*\| (\w+) \|")
_INJURY = re.compile(r"^(Minor|Moderate|Severe) Injury Detected - (.+?) - Tier (\d)")
_TAGS = re.compile(r"<EM\d>(.*?)</EM\d>")
_CHANNEL = re.compile(r"^You have (joined|left the) channel '(.+) : ([^']+)'")

_INTERESTING = (
    "<UpdateNotificationItem>",
    "Quantum Target",
    "Quantum Drive Arrived",
    "<Legacy login response>",
    "<Join PU>",
    "<Update Shard Id>",
    "<EndMission>",
    "<Vehicle Destroyed>",
    "<Actor Death>",
    "<Jump Drive State Changed>",
)


def parse_line(line: str) -> LogEvent | None:
    """One (joined) log line -> what it means, or None."""
    if not any(k in line for k in _INTERESTING):
        return None  # fast path: almost every line
    if m := _NOTIFICATION.search(line):
        return parse_notification(m.group(1))
    if "Quantum Target" in line and (m := _ROUTE.search(line)):
        return LogEvent("route", {"destination": destination_name(m.group(1))})
    if "<Quantum Drive Arrived - Arrived at Final Destination>" in line:
        return LogEvent("arrived")
    if m := _HANDLE.search(line):
        return LogEvent("handle", {"handle": m.group(1)})
    if m := _SHARD.search(line):
        return LogEvent("shard", {"shard": m.group(1) or m.group(2)})
    if m := _END_MISSION.search(line):
        return LogEvent("end_mission", {"how": m.group(1)})
    if m := _VEHICLE.search(line):
        vid, cls, reason, before, after, killer = m.groups()
        return LogEvent(
            "vehicle_destroyed",
            {
                "vehicle": vid,
                "cls": cls,
                "reason": reason,
                "level": int(after),
                "was": int(before),
                "killer": killer,
            },
        )
    if m := _ACTOR_DEATH.search(line):
        victim, killer, weapon, damage = m.groups()
        return LogEvent(
            "actor_death",
            {"victim": victim, "killer": killer, "weapon": weapon, "damage": damage},
        )
    if m := _JUMP_DRIVE.search(line):
        return LogEvent("jump_drive", {"state": m.group(1), "system": m.group(2)})
    return None


def parse_notification(text: str) -> LogEvent | None:
    """The text of an on-screen notification (the game appends ": " to most)."""
    t = " ".join(text.replace("\xa0", " ").split())  # joined lines, odd spaces
    if m := _CHANNEL.match(t):  # before the ":" split: the channel name has one
        joined, name, owner = m.groups()
        return LogEvent(
            "channel_join" if joined == "joined" else "channel_left",
            {"ship": channel_ship(name), "owner": owner.strip()},
        )
    head, _, rest = t.partition(":")
    rest = rest.strip().rstrip(":").strip()
    head = head.strip()

    if head == "Entering Armistice Zone - Combat Prohibited" or head.startswith(
        "Entering Armistice"
    ):
        return LogEvent("armistice", {"on": True})
    if head.startswith("Leaving Armistice"):
        return LogEvent("armistice", {"on": False})
    if m := re.match(r"Entered (.+?) Jurisdiction$", head):
        return LogEvent("jurisdiction", {"name": m.group(1)})
    if head == "Entered Monitored Space":
        return LogEvent("monitored", {"on": True})
    if head in ("Exited Monitored Space", "Left Monitored Space", "Leaving Monitored Space"):
        return LogEvent("monitored", {"on": False})
    if head == "Monitored Space Down":
        return LogEvent("comms", {"up": False})
    if head == "Monitored Space Restored":
        return LogEvent("comms", {"up": True})
    if head.startswith("Leaving Restricted Area"):
        return LogEvent("restricted", {"on": False})
    if head.startswith("Restricted Area") and "relocated" in head:
        # "Restricted Area For your safety, you've been relocated.": already moved out.
        return LogEvent("restricted", {"on": False})
    if head.startswith("Restricted Area") or head.startswith("Entering Restricted Area"):
        return LogEvent("restricted", {"on": True, "note": rest or None})
    if head.startswith("Entering Private Property"):
        return LogEvent("private", {"on": True})
    if head.startswith("Leaving Private Property"):
        return LogEvent("private", {"on": False})
    if head == "Quantum Travel" and "obstructed" in rest:
        return LogEvent("blocked")
    if m := re.match(r"Quantum Travel Calibration (Started|Complete) By (.+)$", head):
        return LogEvent("qt_calibration", {"by": m.group(2), "done": m.group(1) == "Complete"})
    for word, kind in (
        ("Accepted", "contract_accepted"),
        ("Complete", "contract_complete"),
        ("Failed", "contract_failed"),
        ("Shared", "contract_shared"),
    ):
        if head == f"Contract {word}":
            title, tags = contract_title(t.partition(":")[2])
            return LogEvent(kind, {"title": title, "tags": tags})
    for word, kind in (
        ("New Objective", "objective_new"),
        ("Objective Complete", "objective_complete"),
        ("Objective Withdrawn", "objective_withdrawn"),
        ("Objective Failed", "objective_failed"),
    ):
        if head == word:
            return LogEvent(kind, {"text": rest})
    if m := re.match(r"Awarded ([\d,]+) aUEC$", head):
        return LogEvent("reward", {"auec": int(m.group(1).replace(",", ""))})
    if m := _INJURY.match(head):
        return LogEvent(
            "injury",
            {"severity": m.group(1).lower(), "part": m.group(2).strip(), "tier": int(m.group(3))},
        )
    if head == "Incapacitated":
        return LogEvent("incapacitated")
    if head == "Medical Bed" and "restored your health" in rest:
        return LogEvent("healed")
    if head == "Hangar Request Completed":
        return LogEvent("hangar_ready")
    if head.startswith("Joined hangar queue"):
        return LogEvent("hangar_queue")
    if head == "Received Blueprint":
        return LogEvent("blueprint", {"name": rest})
    return None


def contract_title(raw: str) -> tuple[str, list[str]]:
    """' Retake <EM4>[150 Rep] [BP]*</EM4>: ' -> ('Retake', ['150 Rep', 'BP'])."""
    tags: list[str] = []
    for chunk in _TAGS.findall(raw):
        tags += [x.strip(" *") for x in re.findall(r"\[([^\]]+)\]", chunk)]
    title = _TAGS.sub("", raw).strip().rstrip(":").strip()
    return title, tags


_PREFIXES = ("OOC_", "ObjectContainer_", "MISSION_QT_", "Mission_QT_")
_BODY_CODE = re.compile(r"^[A-Za-z]+_\d+[a-z]?_")  # Stanton_1b_ (system + planet code)


def destination_name(raw: str) -> str:
    """OOC_Stanton_1b_Aberdeen -> Aberdeen; MISSION_QT_Bounty_Beacon_9279... -> Bounty Beacon."""
    name = re.sub(r"_\d{6,}$", "", raw)
    for prefix in _PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix) :]
            break
    name = _BODY_CODE.sub("", name)
    name = name.replace("_", " ").strip()
    return name or raw


_AI = re.compile(r"_(?:PU_)?AI_(CRIM|CIV|SEC|UEE|LAW|PIR|NT|[A-Z]+)(?:_.*)?$")
_AI_KIND = {
    "CRIM": "hostile",
    "PIR": "hostile",
    "NT": "hostile",
    "CIV": "civilian",
    "SEC": "security",
    "UEE": "security",
    "LAW": "security",
}


def ship_name(cls: str) -> tuple[str, str | None]:
    """'ANVL_Hurricane_PU_AI_CRIM' -> ('Hurricane', 'hostile')."""
    m = _AI.search(cls)
    base = cls[: m.start()] if m else cls
    return model_name(re.sub(r"_\d{6,}$", "", base)), (
        _AI_KIND.get(m.group(1), "npc") if m else None
    )


def channel_ship(name: str) -> str:
    """A ship channel's name: 'RSI Constellation Taurus' as is; an untranslated one
    ('@vehicle_NameRSI_Perseus') -> 'RSI Perseus'."""
    name = name.strip()
    if name.startswith("@vehicle_Name"):
        name = name[len("@vehicle_Name") :].replace("_", " ")
    return name


def who(name: str) -> str:
    """Killer names: NPC classes become a plain description, players stay as they are.

    Player handles can contain _ and -, so only known NPC shapes count as NPCs.
    """
    if not name or name.lower() in ("unknown", "none"):
        return "unknown"
    if "PDC" in name or "Turret" in name:
        return "a defence turret"
    if name.startswith(("PU_", "AIModule", "NPC_")) or "-Human-" in name:
        return "an NPC"
    return name


# ---------------------------------------------------------------- state from the log

ARRIVED_SHOWN_MS = 120_000
"""How long "arrived at X" stays up."""
ENDED_SHOWN_MS = 120_000
"""How long a finished, failed or abandoned contract stays up."""
MAX_MISSIONS = 4


class RouteTracker:
    """Quantum route state from log events plus the telemetry's quantum flag."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.destination: str | None = None
        self.state: str | None = None  # plotted | en_route | arrived | blocked
        self.since = 0

    def on_log(self, ev: LogEvent, t: int) -> list[Event]:
        if ev.kind == "route":
            self.destination, self.state, self.since = ev.data["destination"], "plotted", t
            return [Event(t=t, kind="quantum_route", data={"destination": self.destination})]
        if ev.kind == "arrived":
            self.state, self.since = "arrived", t
            return [Event(t=t, kind="quantum_arrived", data={"destination": self.destination})]
        if ev.kind == "blocked":
            self.state, self.since = "blocked", t
            return [Event(t=t, kind="quantum_blocked", data={"destination": self.destination})]
        return []

    @property
    def active(self) -> bool:
        """A route is plotted and not yet arrived: a jump may be under way."""
        return self.state in ("plotted", "en_route")

    def route(self, t: int, quantum: bool | None) -> Route | None:
        if self.state is None:
            return None
        if quantum and self.state in ("plotted", "blocked"):
            self.state, self.since = "en_route", t
        if self.state == "arrived" and t - self.since > ARRIVED_SHOWN_MS:
            self.reset()
            return None
        return Route(destination=self.destination, state=self.state, since=self.since)  # type: ignore[arg-type]


class LogState:
    """Everything we know from Game.log, for the snapshot, plus the events it implies."""

    def __init__(self) -> None:
        self.handle: str | None = None
        self.route = RouteTracker()
        self.reset_session()

    def reset_session(self) -> None:
        """A new game launch (new Game.log)."""
        self.route.reset()
        self.loc: dict = {}
        self.aboard: Aboard | None = None
        self.missions: list[Mission] = []
        self.injuries: dict[str, Injury] = {}
        self.session = Session()

    # -- feed

    def on_log(self, ev: LogEvent, t: int, my_ship: str | None = None) -> list[Event]:
        k, d = ev.kind, ev.data

        def event(kind: str, **data) -> list[Event]:
            return [Event(t=t, kind=kind, data=data)]  # type: ignore[arg-type]

        if k in ("route", "arrived", "blocked"):
            if k == "arrived":
                self.session.quantum_trips += 1
            return self.route.on_log(ev, t)
        if k == "handle":
            self.handle = d["handle"]
            return []
        if k == "shard":
            before = self.loc.get("shard")
            changed = before != d["shard"]
            self.loc["shard"] = d["shard"]
            if changed and before is not None:
                self.aboard = None  # moved to another server: the ship didn't come along
            return event("shard_join", shard=d["shard"]) if changed else []

        # -- the ship you're aboard
        if k == "channel_join":
            a = self.aboard
            if a and (a.ship, a.owner) == (d["ship"], d["owner"]):
                return []
            self.aboard = Aboard(ship=d["ship"], owner=d["owner"], since=t)
            return event("boarded", ship=d["ship"], owner=d["owner"])
        if k == "channel_left":
            a = self.aboard
            if not a or (a.ship, a.owner) != (d["ship"], d["owner"]):
                return []
            self.aboard = None
            return event("disembarked", ship=d["ship"], owner=d["owner"])

        # -- location
        if k in ("armistice", "monitored", "restricted", "private"):
            if self.loc.get(k) == d["on"]:
                return []  # the game repeats some of these
            self.loc[k] = d["on"]
            return event(
                f"{k}_{'enter' if d['on'] else 'leave'}",
                **({"note": d["note"]} if d.get("note") else {}),
            )
        if k == "jurisdiction":
            if self.loc.get("jurisdiction") == d["name"]:
                return []
            self.loc["jurisdiction"] = d["name"]
            return event("jurisdiction", name=d["name"])
        if k == "comms":
            self.loc["comms"] = d["up"]
            return event("comms_restored" if d["up"] else "comms_down")

        # -- contracts
        if k == "contract_accepted":
            self.missions = [m for m in self.missions if m.title != d["title"]]
            self.missions.insert(
                0, Mission(title=d["title"], tags=d["tags"], state="active", since=t)
            )
            del self.missions[MAX_MISSIONS:]
            return event(k, title=d["title"])
        if k in ("contract_complete", "contract_failed", "contract_shared"):
            m = self._mission(d["title"])
            if k == "contract_shared":
                m.shared = True
            else:
                m.state, m.since = ("complete" if k == "contract_complete" else "failed"), t
                if k == "contract_complete":
                    self.session.contracts += 1
                else:
                    self.session.failed += 1
            return event(k, title=d["title"])
        if k == "end_mission":
            if d["how"].lower().startswith("abandon"):
                active = [m for m in self.missions if m.state == "active"]
                if len(active) == 1:  # the line has an id, not a title: only sure with one
                    active[0].state, active[0].since = "abandoned", t
                    return event("contract_abandoned", title=active[0].title)
            return []
        if k.startswith("objective_"):
            m = next((m for m in self.missions if m.state == "active"), None)
            if m is None:
                m = Mission(title=None, state="active", since=t)
                self.missions.insert(0, m)
            if k == "objective_new":
                m.objective, m.objective_done = d["text"], False
            elif m.objective == d["text"] or m.objective is None:
                m.objective = d["text"]
                m.objective_done = k == "objective_complete"
            return event(k, text=d["text"], title=m.title)
        if k == "reward":
            self.session.earned += d["auec"]
            return event("reward", auec=d["auec"])

        # -- combat
        if k == "vehicle_destroyed":
            if d["level"] < 2 or d["was"] >= 2:
                return []  # only count the final explosion, once
            name, kind = ship_name(d["cls"])
            killer = d["killer"]
            if my_ship and d["vehicle"] == my_ship:
                self.session.ships_lost += 1
                return event("ship_lost", ship=name, by=who(killer), reason=d["reason"])
            if self.handle and killer == self.handle:
                self.session.kills += 1
                return event("kill", target=name, npc=kind, reason=d["reason"])
            return event(
                "vehicle_destroyed", target=name, npc=kind, by=who(killer), reason=d["reason"]
            )
        if k == "actor_death":
            if self.handle and d["victim"] == self.handle:
                self.session.deaths += 1
                self.aboard = None
                return event("death", by=who(d["killer"]), damage=d["damage"])
            if self.handle and d["killer"] == self.handle:
                self.session.kills += 1
                return event("kill", target=who(d["victim"]), npc=None, reason=d["damage"])
            return []
        if k == "jump_drive":
            # Jump drive = through a jump point to another star system (not quantum travel).
            # States: Idle, Tuning, EntryChecks, RequestingJump, WaitingForOpen, Entering,
            # Transiting, Exiting. The system named is where the drive is now.
            moved = self.loc.get("system") not in (None, d["system"])
            self.loc["system"] = d["system"]
            state = d["state"]
            if state == "Entering":
                return event("jump_start", system=d["system"])
            if state == "Exiting" or moved:
                self.session.system_jumps += 1
                return event("jump_end", system=d["system"])
            return []

        # -- personal
        if k == "injury":
            self.injuries[d["part"]] = Injury(
                part=d["part"], severity=d["severity"], tier=d["tier"]
            )
            return event("injury", **d)
        if k == "healed":
            self.injuries.clear()
            return event("healed")
        if k == "incapacitated":
            self.session.incaps += 1
            return event("incapacitated")

        # -- other
        if k == "qt_calibration":
            return event("qt_calibration", by=d["by"], done=d["done"])
        if k in ("hangar_ready", "hangar_queue"):
            return event(k)
        if k == "blueprint":
            return event("blueprint", name=d["name"])
        return []

    def _mission(self, title: str) -> Mission:
        for m in self.missions:
            if m.title == title:
                return m
        m = Mission(title=title, state="active", since=0)
        self.missions.insert(0, m)
        del self.missions[MAX_MISSIONS:]
        return m

    def respawned(self) -> None:
        self.injuries.clear()
        self.aboard = None

    # -- read

    def location(self, t: int, quantum: bool | None) -> Location | None:
        route = self.route.route(t, quantum)
        if not self.loc and route is None and self.aboard is None:
            return None
        return Location(
            armistice=self.loc.get("armistice"),
            jurisdiction=self.loc.get("jurisdiction"),
            monitored=self.loc.get("monitored"),
            comms=self.loc.get("comms"),
            restricted=self.loc.get("restricted"),
            private=self.loc.get("private"),
            shard=self.loc.get("shard"),
            system=self.loc.get("system"),
            route=route,
            aboard=self.aboard.model_copy() if self.aboard else None,
        )

    def mission_list(self, t: int) -> list[Mission]:
        self.missions = [
            m for m in self.missions if m.state == "active" or t - m.since <= ENDED_SHOWN_MS
        ]
        return [m.model_copy() for m in self.missions]


# ---------------------------------------------------------------- following the file


class LineJoiner:
    """Some notifications span lines (the text holds a newline). Joins them back up."""

    MAX_LINES = 6

    def __init__(self) -> None:
        self._parts: list[str] = []

    def feed(self, line: str) -> str | None:
        line = line.rstrip("\r\n")
        if self._parts:
            self._parts.append(_TS.sub("", line))
            if self._closed(self._parts[-1]) or len(self._parts) >= self.MAX_LINES:
                joined, self._parts = " ".join(self._parts), []
                return joined
            return None
        if '<UpdateNotificationItem> Notification "' in line and not self._closed(line):
            self._parts = [line]
            return None
        return line

    @staticmethod
    def _closed(text: str) -> bool:
        return re.search(r'" \[\d+\], Action: \w+', text) is not None


class GameLogTail:
    """Follows Game.log in a thread and hands recognised lines to ``on_line(line, quiet)``.

    On start it reads the existing file quietly (``quiet=True``), so what happened
    before the agent started is known without replaying it as news. A new game
    launch replaces the file: when it shrinks, we start again from the top and
    call ``on_new_session``.
    """

    POLL_S = 0.5

    def __init__(
        self,
        path: Path,
        on_line: Callable[[str, bool], None],
        on_new_session: Callable[[], None] | None = None,
    ) -> None:
        self.path = path
        self.on_line = on_line
        self.on_new_session = on_new_session
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="game-log", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=3)

    def _run(self) -> None:
        pos = 0
        quiet = True  # the first read is history
        buf = b""
        joiner = LineJoiner()
        while not self._stop.is_set():
            try:
                size = self.path.stat().st_size
                if size < pos:  # the game restarted and began a new log
                    pos, buf, joiner = 0, b"", LineJoiner()
                    quiet = False
                    if self.on_new_session:
                        self.on_new_session()
                if size > pos:
                    with open(self.path, "rb") as fh:
                        fh.seek(pos)
                        chunk = fh.read(size - pos)
                    pos += len(chunk)
                    *lines, buf = (buf + chunk).split(b"\n")
                    for raw in lines:
                        line = joiner.feed(raw.decode("utf-8", errors="replace"))
                        if line is not None and parse_line(line):
                            self.on_line(line, quiet)
                quiet = False
            except FileNotFoundError:
                pos, buf = 0, b""
                quiet = False  # whatever appears next is a new session
            except OSError as exc:
                log.debug("Game.log not readable yet: %s", exc)
            self._stop.wait(self.POLL_S)
