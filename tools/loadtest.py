"""Will my server handle my org? What a hub needs for a given number of players in game.

Starts its own hub (a temporary database, test sign-in on, 127.0.0.1 only) as a child
process, so a real hub and its data are never touched, and it can't be pointed at anyone
else's. Then, step by step, adds players whose agents send what a real one does in flight
(a full snapshot, then what changed ten times a second, a full one every 30 s, an event
now and then) and viewers with the fleet page open (each watching one member), and
measures the hub process: CPU, memory, and how long an update takes to reach a viewer. At
the end: what your org needs at its busiest, and how many players one hub handles.

Also for anyone changing the hub: run it before and after to see what a change costs.

On your server, inside the released hub image (it has Python and the hub already):

    curl -fsSLO https://raw.githubusercontent.com/bradqui/starglance/main/tools/loadtest.py
    docker run --rm --entrypoint python \\
      -v "$PWD/loadtest.py:/loadtest.py:ro" \\
      ghcr.io/bradqui/starglance-hub:latest /loadtest.py

From a checkout:  uv run python tools/loadtest.py
Options: --steps 10,25,50,100  --viewers 0.25 (per player)  --seconds 20  --players 25

CPU and memory come from /proc on Linux, or psutil where it's installed (uv run --with
psutil ...); without either only the delays are measured. The
players and viewers run in this process: if its own CPU nears 100% of a core, the hub is
waiting on the test, not the other way round, and the script says so.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import aiohttp

RATE_HZ = 10  # what agents send (uplink.RATE_HZ)
FULL_EVERY_S = 30.0
EVENT_EVERY_S = 30.0  # roughly: route plotted, zone entered, warnings...
WARMUP_S = 5.0


def now_ms() -> int:
    return int(time.time() * 1000)


# ---------------------------------------------------------------- a player in flight


def snapshot(i: int, t: int) -> dict:
    """A full snapshot shaped like a real one in flight (about 2 KB)."""
    lights = dict.fromkeys(
        ("pwr", "wpn", "thr", "shld", "cool", "qdrv", "radr", "prox", "hit", "misl"), "nominal"
    )
    return {
        "type": "snapshot",
        "v": 1,
        "t": t,
        "status": {
            "in_game": True,
            "locomotion": "seated",
            "seat": "Seat_Pilot",
            "role": "pilot",
            "handle": f"Pilot{i:03}",
        },
        "ship": {
            "id": f"TEST_ship_{900000000000 + i}",
            "class": "ORIG_m80",
            "model": "M80",
            "manufacturer": "Origin Jumpworks",
            "type": "spaceship",
            "hull": None,
            "master_mode": "SCM",
            "powered": True,
            "shields": {"powered": True, "level": None, "faces": None},
            "power": dict.fromkeys(
                (
                    "powerplants",
                    "engines",
                    "weapons",
                    "coolers",
                    "life_support",
                    "gravity_generators",
                    "sensors",
                    "shield_generators",
                    "shield_emitters",
                ),
                True,
            ),
            "lights": lights,
            "gear": "retracted",
            "landed": False,
            "flight": {
                "speed": 180.0,
                "alt": 1200.0,
                "radar_alt": 1180.0,
                "vsi": 0.0,
                "heading": 90.0,
                "g": 1.0,
                "g_max": 4.0,
                "atmo_density": 0.8,
                "h2_fuel": 0.9,
                "qt_fuel": None,
                "boost_reserve": 1.0,
                "boost_engaged": False,
                "cruise": False,
                "g_safe": True,
                "coupled": True,
                "prox_assist": False,
                "quantum": False,
            },
        },
        "weapons": {
            "gimbals_locked": True,
            "guns": [{"name": "Cannon_S4", "powered": True, "ready": True}] * 4,
            "countermeasures": [{"type": "decoy", "count": 48}, {"type": "noise", "count": 5}],
        },
        "vitals": {
            "health": 1.0,
            "oxygen": 1.0,
            "hunger": 0.9,
            "thirst": 0.9,
            "body_temp": 36.5,
            "heart_rate": 70.0,
            "gravity": 1.0,
            "pressure": 1.0,
            "intoxication": 0,
            "environment": {"temperature": 21.0, "breathable": True, "radiation": 0.0},
            "injuries": [],
        },
        "uec": 1_000_000 + i,
        "location": {
            "system": "Stanton",
            "jurisdiction": "UEE",
            "shard": "test_shard_1",
            "armistice": False,
        },
        "missions": [
            {
                "id": None,
                "title": "Haul cargo",
                "tags": [],
                "state": "active",
                "since": t,
                "objectives": [
                    {"id": None, "text": f"Deliver 0/48 SCU of Cargo {k}", "state": "active"}
                    for k in range(3)
                ],
                "shared": False,
            },
        ],
        "session": {
            "kills": 0,
            "ships_lost": 0,
            "deaths": 0,
            "incaps": 0,
            "contracts": 0,
            "failed": 0,
            "earned": 0,
            "quantum_trips": 0,
            "system_jumps": 0,
        },
    }


@dataclass
class Stats:
    sent: int = 0
    received: int = 0
    received_bytes: int = 0
    delays: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def reset(self) -> None:
        self.sent = self.received = self.received_bytes = 0
        self.delays.clear()


async def player(
    http: aiohttp.ClientSession, ws_base: str, token: str, i: int, stats: Stats, stop: asyncio.Event
) -> None:
    async with http.ws_connect(
        f"{ws_base}/ws/agent", headers={"Authorization": f"Bearer {token}"}
    ) as ws:
        welcome = json.loads((await ws.receive()).data)
        await ws.send_str(
            json.dumps(
                {
                    "type": "hello",
                    "v": 1,
                    "agent_version": welcome["latest_agent"],
                    "channel": "LIVE",
                }
            )
        )
        rng = random.Random(i)
        await asyncio.sleep(rng.random() / RATE_HZ)  # not all in step
        full_at = event_at = 0.0
        speed, alt, heading = (
            150.0 + rng.random() * 100,
            1000.0 + rng.random() * 500,
            rng.random() * 360,
        )

        async def drain() -> None:  # the hub's replies (errors, if any)
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT and '"error"' in msg.data:
                    stats.errors.append(msg.data[:200])

        reader = asyncio.create_task(drain())
        try:
            while not stop.is_set():
                t, mono = now_ms(), time.monotonic()
                if mono >= full_at:
                    await ws.send_str(json.dumps(snapshot(i, t), separators=(",", ":")))
                    full_at = mono + FULL_EVERY_S
                else:
                    speed += rng.uniform(-8, 8)
                    alt += rng.uniform(-15, 15)
                    heading = (heading + rng.uniform(-3, 3)) % 360
                    patch = {
                        "t": t,
                        "ship": {
                            "flight": {
                                "speed": round(speed, 3),
                                "alt": round(alt, 2),
                                "radar_alt": round(alt - 20, 2),
                                "vsi": round(rng.uniform(-20, 20), 3),
                                "heading": round(heading, 3),
                                "g": round(rng.uniform(0.5, 3), 3),
                            }
                        },
                        "vitals": {"heart_rate": round(rng.uniform(60, 110), 2)},
                    }
                    await ws.send_str(
                        json.dumps(
                            {"type": "delta", "v": 1, "t": t, "patch": patch}, separators=(",", ":")
                        )
                    )
                if mono >= event_at:
                    if event_at:
                        await ws.send_str(
                            json.dumps(
                                {
                                    "type": "event",
                                    "v": 1,
                                    "t": t,
                                    "kind": "quantum_route",
                                    "data": {"destination": "Somewhere"},
                                }
                            )
                        )
                    event_at = mono + rng.uniform(0.5, 1.5) * EVENT_EVERY_S
                stats.sent += 1
                await asyncio.sleep(max(0.0, 1 / RATE_HZ - (time.monotonic() - mono)))
        finally:
            reader.cancel()


async def viewer(
    http: aiohttp.ClientSession, ws_base: str, token: str, i: int, stats: Stats, stop: asyncio.Event
) -> None:
    """The fleet page: the roster live, and one member open."""
    async with http.ws_connect(
        f"{ws_base}/ws/view", headers={"Authorization": f"Bearer {token}"}
    ) as ws:
        focused = False
        while not stop.is_set():
            try:
                msg = await asyncio.wait_for(ws.receive(), 1.0)
            except TimeoutError:
                continue
            if msg.type != aiohttp.WSMsgType.TEXT:
                break
            stats.received += 1
            stats.received_bytes += len(msg.data)
            data = json.loads(msg.data)
            kind = data.get("type")
            if kind == "roster" and not focused and data.get("members"):
                members = sorted(data["members"])
                await ws.send_str(
                    json.dumps({"type": "focus", "member": members[i % len(members)]})
                )
                focused = True
            elif kind == "member_delta" and isinstance(data.get("patch", {}).get("t"), int):
                stats.delays.append(now_ms() - data["patch"]["t"])


# ---------------------------------------------------------------- the hub under test


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Proc:
    """CPU seconds and memory of a process: /proc on Linux, else psutil if it's there."""

    def __init__(self, pid: int, children: bool = True) -> None:
        self.pid = pid
        self.children = children
        self.ok = Path(f"/proc/{pid}/stat").exists()
        self.tick = os.sysconf("SC_CLK_TCK") if self.ok else 100
        self.ps = None
        if not self.ok:
            try:
                import psutil

                self.ps = psutil.Process(pid)
            except Exception:
                pass

    def _tree(self) -> list:
        """The process and its children (a venv's python.exe on Windows is a launcher)."""
        return [self.ps, *(self.ps.children(recursive=True) if self.children else [])]

    def cpu(self) -> float | None:
        if self.ps is not None:
            return sum(t.user + t.system for t in (p.cpu_times() for p in self._tree()))
        if not self.ok:
            return None
        fields = Path(f"/proc/{self.pid}/stat").read_text().rsplit(")", 1)[1].split()
        return (int(fields[11]) + int(fields[12])) / self.tick  # utime + stime

    def rss_mb(self) -> float | None:
        if self.ps is not None:
            return sum(p.memory_info().rss for p in self._tree()) / 1024 / 1024
        if not self.ok:
            return None
        for line in Path(f"/proc/{self.pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
        return None


def mem_available_gb() -> float | None:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1024 / 1024
    except OSError:
        pass
    return None


async def start_hub(data: Path) -> tuple[subprocess.Popen, str]:
    port = free_port()
    url = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "HUB_DATA_DIR": str(data),
        "HUB_BIND": "127.0.0.1",
        "HUB_PORT": str(port),
        "HUB_URL": url,
        "HUB_ORG_NAME": "Load test",
        "HUB_DEV_LOGIN": "1",
    }
    # Its log to a file: a pipe nobody reads fills up and stalls the hub mid-test.
    log = data / "hub.log"
    with log.open("wb") as out:
        hub = subprocess.Popen(
            [sys.executable, "-m", "starglance_hub"], env=env, stdout=out, stderr=subprocess.STDOUT
        )
    async with aiohttp.ClientSession() as http:
        for _ in range(100):
            if hub.poll() is not None:
                raise SystemExit(
                    f"The hub didn't start:\n{log.read_text(errors='replace')[-2000:]}"
                )
            try:
                async with http.get(f"{url}/api/health") as r:
                    if r.status == 200:
                        return hub, url
            except aiohttp.ClientError:
                pass
            await asyncio.sleep(0.2)
    hub.kill()
    raise SystemExit("The hub didn't answer in 20 s.")


async def join_players(url: str, n: int, have: int) -> list[str]:
    """Players n...: the admin's invite, each from its own (made-up, local) address."""
    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as admin:
        async with admin.get(f"{url}/auth/dev", params={"name": "Admin"}) as r:
            r.raise_for_status()
        async with admin.post(
            f"{url}/api/admin/invites", json={"uses": None, "days": 1}, headers={"Origin": url}
        ) as r:
            if r.status != 201:
                raise SystemExit(f"Couldn't make an invite: {r.status} {await r.text()}")
            code = (await r.json())["url"].rsplit("/join/", 1)[1]
    tokens = []
    async with aiohttp.ClientSession() as http:
        for i in range(have, n):
            # Each from its own address: the hub limits joins per address.
            fwd = f"10.{(i >> 16) & 255}.{(i >> 8) & 255}.{i & 255}"
            async with http.post(
                f"{url}/api/agent/join",
                json={"invite": code, "name": f"Pilot{i:03}", "machine": "Load PC"},
                headers={"X-Forwarded-For": fwd},
            ) as r:
                if r.status != 200:
                    raise SystemExit(f"Player {i} couldn't join: {r.status} {await r.text()}")
                tokens.append((await r.json())["token"])
    return tokens


# ---------------------------------------------------------------- the run


@dataclass
class Row:
    players: int
    viewers: int
    cpu: float | None  # % of one core
    rss: float | None  # MB
    p50: float | None
    p95: float | None
    recv_s: float
    kb_s: float
    me: float | None  # this script's own CPU, % of one core


def pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return s[min(len(s) - 1, int(q * len(s)))]


def fmt(v: float | None, spec: str = ".0f", unit: str = "") -> str:
    return "n/a" if v is None else f"{v:{spec}}{unit}"


async def run(args: argparse.Namespace) -> None:
    steps = sorted({int(s) for s in args.steps.split(",")})
    with tempfile.TemporaryDirectory(
        prefix="starglance-loadtest-", ignore_cleanup_errors=True
    ) as tmp:
        hub, url = await start_hub(Path(tmp))
        proc = Proc(hub.pid)
        me = Proc(os.getpid(), children=False)  # the hub is our child: not ours to count
        ws_base = url.replace("http://", "ws://")
        stats, stop = Stats(), asyncio.Event()
        tasks: list[asyncio.Task] = []
        tokens: list[str] = []
        rows: list[Row] = []
        print(
            f"Hub {url} (pid {hub.pid}), {os.cpu_count()} CPUs, "
            f"{fmt(mem_available_gb(), '.1f', ' GB')} available\n"
        )
        print(
            f"{'players':>7} {'viewers':>7} {'hub CPU':>9} {'hub RAM':>8} {'delay p50':>9} "
            f"{'p95':>6} {'to viewers':>14} {'test CPU':>8}"
        )
        timeout = aiohttp.ClientTimeout(total=None)
        connector = aiohttp.TCPConnector(limit=0)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as http:
            try:
                for n in [0, *steps]:
                    if n > len(tokens):
                        tokens += await join_players(url, n, len(tokens))
                    have_players = sum(1 for t in tasks if t.get_name().startswith("p"))
                    for i in range(have_players, n):
                        tasks.append(
                            asyncio.create_task(
                                player(http, ws_base, tokens[i], i, stats, stop), name=f"p{i}"
                            )
                        )
                    want_viewers = 0 if n == 0 else max(1, math.ceil(n * args.viewers))
                    have_viewers = sum(1 for t in tasks if t.get_name().startswith("v"))
                    for j in range(have_viewers, want_viewers):
                        tasks.append(
                            asyncio.create_task(
                                viewer(http, ws_base, tokens[j % len(tokens)], j, stats, stop),
                                name=f"v{j}",
                            )
                        )
                    await asyncio.sleep(WARMUP_S)
                    for t in tasks:
                        if t.done() and t.exception():
                            raise SystemExit(f"A test connection failed: {t.exception()!r}")
                    stats.reset()
                    c0, m0, w0 = proc.cpu(), me.cpu(), time.monotonic()
                    await asyncio.sleep(args.seconds)
                    c1, m1, wall = proc.cpu(), me.cpu(), time.monotonic() - w0
                    row = Row(
                        players=n,
                        viewers=want_viewers,
                        cpu=None if c0 is None else (c1 - c0) / wall * 100,
                        rss=proc.rss_mb(),
                        p50=pct(stats.delays, 0.5),
                        p95=pct(stats.delays, 0.95),
                        recv_s=stats.received / wall,
                        kb_s=stats.received_bytes / wall / 1024,
                        me=None if m0 is None else (m1 - m0) / wall * 100,
                    )
                    rows.append(row)
                    print(
                        f"{n:>7} {want_viewers:>7} {fmt(row.cpu, '.1f', '%'):>9} "
                        f"{fmt(row.rss, '.0f', ' MB'):>8} "
                        f"{fmt(row.p50, '.0f', ' ms'):>9} {fmt(row.p95, '.0f', ' ms'):>6} "
                        f"{row.recv_s:>6.0f}/s {row.kb_s:>5.0f} KB/s {fmt(row.me, '.0f', '%'):>8}"
                    )
                    if row.me is not None and row.me > 85:
                        print(
                            "        (the test itself is near a full core: bigger steps "
                            "would measure the test, not the hub)"
                        )
                    if stats.errors:
                        print(f"        hub said: {stats.errors[0]}")
            finally:
                stop.set()
                await asyncio.gather(*tasks, return_exceptions=True)
                hub.terminate()
                try:
                    hub.wait(10)
                except subprocess.TimeoutExpired:
                    hub.kill()
        summary(rows, args.players, args.viewers)


def summary(rows: list[Row], players: int, ratio: float) -> None:
    measured = [r for r in rows if r.cpu is not None and r.rss is not None and r.players]
    if not measured:
        print("\nCPU and memory need Linux, or psutil: run it on your server for the summary.")
        return
    idle = rows[0]

    def at(n: float, key: str) -> float:
        """A measure at n players, between the steps around it (or scaled from the last)."""
        pts = [(r.players, getattr(r, key)) for r in measured]
        lo = max((p for p in pts if p[0] <= n), default=pts[0])
        hi = min((p for p in pts if p[0] >= n), default=pts[-1])
        if hi[0] == lo[0]:
            return lo[1] * (n / lo[0] if key == "cpu" else 1)
        return lo[1] + (n - lo[0]) / (hi[0] - lo[0]) * (hi[1] - lo[1])

    viewers = max(1, math.ceil(players * ratio))
    print(f"\nIdle hub: {fmt(idle.rss, '.0f', ' MB')}, {fmt(idle.cpu, '.1f', '%')} of a core.")
    print(
        f"Your org at its busiest ({players} players in game, {viewers} with the fleet page "
        f"open): about {at(players, 'rss'):.0f} MB and {at(players, 'cpu'):.0f}% of one core."
    )
    # A hub works on one core: past about 80% of it, updates start to queue.
    over = [(a, b) for a, b in zip(measured, measured[1:], strict=False) if b.cpu >= 80 > a.cpu]
    if over:
        a, b = over[0]
        most = a.players + (80 - a.cpu) / (b.cpu - a.cpu) * (b.players - a.players)
        print(f"One hub handles about {most:.0f} players in game at once (80% of its core).")
    elif measured[0].cpu >= 80:
        print(f"Even {measured[0].players} players take most of a core on this machine.")
    else:
        print(
            f"One hub handled {measured[-1].players} players in game at once within 80% of "
            "its core; try bigger --steps to find its limit."
        )


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--steps",
        default="10,25,50,100",
        help="players in game at each step (default 10,25,50,100)",
    )
    ap.add_argument(
        "--viewers", type=float, default=0.25, help="fleet pages open per player (default 0.25)"
    )
    ap.add_argument(
        "--seconds", type=float, default=20, help="measuring time per step (default 20)"
    )
    ap.add_argument(
        "--players",
        type=int,
        default=25,
        help="your org's players in game at its busiest, for the summary (default 25)",
    )
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
