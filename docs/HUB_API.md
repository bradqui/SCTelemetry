# Hub integration API

For anything that isn't the fleet page or an agent: a Discord bot, a stream overlay, a script that posts to a channel. Read the fleet, follow events as they happen, and hand out invites.

The API is versioned (`/api/v1/`). Within v1, fields and event kinds may be **added** but nothing is removed or renamed, so ignore what you don't know.

## Keys

An admin creates a key on the fleet page: **your name → Admin → Integrations**. The key is shown once; store it like a password. Send it on every request:

```
Authorization: Bearer ftk_...
```

| Scope | Allows |
|---|---|
| `read` | the roster, one member's live state, events (history and live stream) |
| `invites` | creating member invites (never admin invites) |

Deleting the key on the same page cuts it off immediately.

Base address: the hub's public address (e.g. `https://fleet.example.org`). A bot on the same machine as the hub can use `http://127.0.0.1:8100` and skip the proxy.

Errors are JSON with an HTTP status: `{"error": "unknown API key"}` (401), `{"error": "this key lacks the 'invites' scope"}` (403), and so on.

## Endpoints

### `GET /api/health`

No key needed. `{"ok": true, "version": "0.1.0"}`.

### `GET /api/v1/fleet` (read)

Everyone with a linked PC, as the fleet page's roster shows them:

```jsonc
{
  "t": 1795496765924,               // ms since epoch
  "org": "Example Org",
  "members": [
    {
      "id": "m_3f2a9c1d4b5e6f70",   // stable member id
      "name": "Ace",
      "avatar": null,               // image URL when they connected Discord
      "presence": "live",           // live | idle (agent on, not in game) | stale | offline
      "last_seen": null,            // ms; only when stale or offline
      "channel": "LIVE",
      "locomotion": "seated",       // on_foot | eva | seated | unknown
      "role": "pilot",              // pilot | copilot | gunner | crew | null
      "handle": "Wren_SC",          // in-game handle (from Game.log), or null
      "ship": {                     // null when not in a ship (or not shared)
        "id": "ORIG_m80_123456789", // same id = same ship: crewmates share it
        "model": "M80",
        "manufacturer": "Origin Jumpworks",
        "master_mode": "SCM",       // SCM | NAV | null
        "quantum": false,           // in quantum travel
        "powered": true,
        "landed": false,
        "gear": "retracted",
        "hull": null,               // 0-1; the game doesn't send it yet
        "shields": {"powered": true, "level": null},
        "speed": 212,               // m/s, rounded (frozen during quantum: use "quantum")
        "alt": 4812,                // m; null in space
        "agl": 85,                  // m over the ground, near a surface; else null
        "vsi": 18,                  // vertical speed, m/s
        "heading": 274,             // degrees; null away from planets
        "g": 2.4,
        "h2_fuel": 0.91,            // 0-1
        "alarm": "major",           // major | minor | null: the worst warning light
        "lights": ["hit"],          // which lights: pwr wpn thr shld cool qdrv radr prox hit misl
        "fleet_alarm": "major",     // major | null: what the fleet should hear (getting hit, a
        "fleet_lights": ["hit"],    //   radar warning); on 1 s before it counts, off 3 s to clear
        "alerts": {"hit": "major", "thr": "minor"}  // every lit light, held the same way:
                                    //   major (a warning) or minor (a caution); pick your own
      },
      "location": {                 // null when not shared
        "armistice": false,
        "restricted": false,
        "private": false,
        "monitored": true,
        "comms": true,
        "jurisdiction": "Hurston Dynamics",
        "system": null,
        "shard": "pub_use1b_13165946_150",   // same shard = same server instance
        "route": {"destination": "Bounty Beacon", "state": "en_route"},
        "aboard": {                 // the ship they're aboard, seated or on foot; else null
          "ship": "RSI Constellation Taurus",   // the game's name for it
          "owner": "Kestrel_SC",    // owner's in-game handle
          "since": 1795540000000,
          "owner_id": "m_123",      // the member who owns it, when they're in the fleet
          "ship_id": "RSI_Constellation_Taurus_987"  // the owner's ship, when they're flying it
        }
      },
      "vitals": {"health": 1.0, "oxygen": 1.0, "hunger": 0.64, "thirst": 0.81,   // 0-1
                 "body_temp": 36.6, "heart_rate": 84,
                 "injury": null, "injuries": 0},   // injury: the worst of minor | moderate | severe
      "mission": {"title": "Combat Gauntlet - Scenario #1", "objective": "Defeat Hostile Ships"},
      "session": {"kills": 3, "ships_lost": 0, "deaths": 0, "incaps": 0, "contracts": 1,
                  "failed": 0, "earned": 0, "quantum_trips": 2, "system_jumps": 0}
    }
  ]
}
```

Anything a member chose not to share is `null` (or `0` for `session.earned`).

### `GET /api/v1/members/{id}` (read)

One member: `{"summary": {...as above...}, "snapshot": {...}}`. The snapshot is the full live state the agent sends (schema in `shared/starglance_shared/models.py`, field notes in `docs/FIELDS.md`): weapons, every warning light, power, vitals, contracts. `snapshot` is `null` while they're not in game.

### `GET /api/v1/events?since=<ms>&limit=<n>` (read)

Events after `since` (default: all kept, 30 days), oldest first, at most `limit` (default 100, max 500):

```json
[{"member": "m_3f2a9c1d4b5e6f70", "t": 1795496700000, "kind": "kill", "data": {"target": "C8 Pisces", "npc": "hostile", "reason": "Combat"}}]
```

Poll with the last `t` you saw as `since`, or use the stream.

### `GET /api/v1/events/stream` (read, WebSocket)

Every event as it happens:

```json
{"type": "event", "member": "m_3f2a9c1d4b5e6f70", "t": 1795496700000, "kind": "warning_on", "data": {"light": "hit", "level": "major_flashing"}}
```

Nothing is sent to the hub. The hub pings every 25 s; reconnect if the socket closes (hub restarts, deploys), and use `/api/v1/events?since=` to catch up on what you missed.

Useful kinds for alerts:

| Kind | `data` |
|---|---|
| `warning_on` / `warning_off` | `light` (pwr, wpn, thr, shld, cool, qdrv, radr, prox, hit, misl), `level` |
| `hull_threshold` / `fuel_threshold` | `ship`, `below` (the threshold crossed), `hull` / `fuel` |
| `kill` | `target` (ship model), `npc` (hostile, civilian, security, npc; null for a player), `reason` |
| `ship_lost` | `ship`, `by`, `reason` |
| `vehicle_destroyed` (near them, by someone else) | `target`, `npc`, `by`, `reason` |
| `injury` | `part`, `severity` (minor, moderate, severe), `tier` |
| `incapacitated`, `healed` | |
| `quantum_route`, `quantum_arrived`, `quantum_blocked` | `destination` |
| `contract_accepted`, `contract_complete`, `contract_failed`, `contract_abandoned` | `title` |
| `jurisdiction` | `name` |
| `boarded`, `disembarked` | `ship`, `owner` (in-game handle). Leaving isn't always logged by the game |
| `armistice_enter` / `armistice_leave`, `restricted_enter` / `restricted_leave` | |
| `game_start`, `game_exit`, `seat_enter`, `seat_leave`, `ship_change`, `takeoff`, `landed` | (seat events: `seat`, `role`) |

The full list is `EventKind` in `shared/starglance_shared/models.py`. A member's events only arrive if they share that category.

### `POST /api/v1/invites` (invites)

```json
{"uses": 1, "days": 7, "note": "for Ace"}
```

`uses`: 1, 5, 25 or `null` (unlimited). `days`: 1, 7, 30 or `null` (never expires). Returns `201` with `{"url": "https://fleet.example.org/join/...", "expires_at": ..., "max_uses": 1, ...}`. Keys can only make member invites.

## Example: a Discord bot

A Red-DiscordBot cog (or any discord.py bot) needs only `aiohttp`, which Red already ships. The hub address and key belong in the bot's own config, not in code.

```python
import asyncio
import aiohttp


class Hub:
    def __init__(self, base: str, key: str):
        self.base = base.rstrip("/")
        self.http = aiohttp.ClientSession(headers={"Authorization": f"Bearer {key}"})

    async def fleet(self) -> dict:
        async with self.http.get(f"{self.base}/api/v1/fleet") as r:
            r.raise_for_status()
            return await r.json()

    async def invite(self, note: str) -> str:
        async with self.http.post(
            f"{self.base}/api/v1/invites", json={"uses": 1, "days": 7, "note": note}
        ) as r:
            r.raise_for_status()
            return (await r.json())["url"]

    async def follow(self, on_event):
        """Call on_event(event) for every fleet event, reconnecting forever."""
        ws_url = self.base.replace("http", "ws", 1) + "/api/v1/events/stream"
        while True:
            try:
                async with self.http.ws_connect(ws_url, heartbeat=30) as ws:
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await on_event(msg.json())
            except aiohttp.ClientError:
                pass
            await asyncio.sleep(5)
```

A `!fleet` command formats `fleet()["members"]` (online ones: `presence != "offline"`); an alerts task runs `follow()` and posts, say, `warning_on` with `level` starting `major`, or `incapacitated`, to a channel; `!invite @someone` DMs them `invite(...)`. Map Discord users to members by name, or have members tell the bot their member id (shown in the URL when you open them on the fleet page: `#m=<id>`).
