# SC Fleet Telemetry

Live Star Citizen ship and crew status for our org: shown on each member's second monitor or VR overlay, on phones as a PWA, and in Discord through ButlerBot.

**Status:** greenfield, Phase 0 (spike) not started.

The full build spec is in [docs/SC_FLEET_TELEMETRY_SPEC.md](docs/SC_FLEET_TELEMETRY_SPEC.md).

## How it fits together

- **Agent** (Windows, per member): reads the game's local telemetry gRPC stream on `127.0.0.1:50051`, normalizes it, serves a local cockpit view, and pushes the shared fields outbound to the hub.
- **Hub** (FastAPI, Docker, on the ButlerBot server): ingests agent data, serves the fleet PWA, and publishes events to Redis.
- **Web** (PWA): fleet board and member detail; the same bundle is the agent's local view.
- **Cog** (`telemetry`, Red-DiscordBot): `!fleet`, `!ready`, ops, and alerts in ButlerBot.

No world position, no remote control of anyone's game, and nothing that touches memory or Easy Anti-Cheat.

## Planned layout

```
agent/     Windows agent
hub/       FastAPI service
web/       PWA source
cog/       Red cog: telemetry/
shared/    Pydantic wire-schema models
tools/     capture.py, replay.py
fixtures/  scrubbed captured frames (JSONL)
docs/      spec and ops notes
```
