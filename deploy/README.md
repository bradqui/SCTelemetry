# Running a hub

The hub is one Docker container: the fleet page, sign-in, and the place your members' agents send their telemetry. You need a server with Docker, a domain name, and a reverse proxy that does https.

## 1. Start it

```bash
git clone https://github.com/bradqui/SCTelemetry.git
cd SCTelemetry/deploy
cp .env.example .env
nano .env                       # HUB_URL and HUB_ORG_NAME at least
docker compose up -d --build
docker compose logs hub
```

The log shows a **setup link** the first time:

```
WARNING fleet_hub.app: No admin yet. Open this link to create the admin account:
WARNING fleet_hub.app:     https://fleet.example.org/join/AbC...
```

Open it once your proxy is up (step 2), or paste it into your agent: `fleet_agent link <setup link>` creates your admin account and links your PC in one go. The link works once. If you lose it, restart the container while there's still no admin, and a new one is logged.

The hub listens on `127.0.0.1:8100` only. `curl -s http://127.0.0.1:8100/api/health` should answer.

## 2. https in front

Point a DNS name at the server, then proxy it to `127.0.0.1:8100` with WebSockets allowed. Pick one:

**Caddy** (gets certificates by itself):

```
fleet.example.org {
    reverse_proxy 127.0.0.1:8100
}
```

**nginx**:

```nginx
server {
    server_name fleet.example.org;
    listen 443 ssl;   # plus your certificate lines (certbot adds them)
    location / {
        proxy_pass http://127.0.0.1:8100;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_read_timeout 120s;
    }
}
```

**Apache** 2.4.47+ (`a2enmod proxy proxy_http headers`), in the https site:

```apache
ProxyPreserveHost On
RequestHeader set X-Forwarded-Proto "https"
ProxyPass        /  http://127.0.0.1:8100/ upgrade=websocket
ProxyPassReverse /  http://127.0.0.1:8100/
```

Redirect plain http to https. **Cloudflare's proxy** (orange cloud) works: set SSL/TLS to **Full (strict)**, keep WebSockets on, and turn **Bot Fight Mode off** (it blocks agents). Get the certificate first with the record DNS-only (gray) if your server issues its own.

## 3. Bring your org in

On the fleet page, **your name → Admin → Invites**: pick how many uses and how long it lasts, create, and send the link.

- **Players** run `fleet_agent link <invite link>` on their gaming PC. That creates their account (named after their in-game handle unless they pick another) and links the PC. `fleet_agent open`, or **Fleet** in the cockpit view, opens the fleet page signed in.
- **Watchers without the game** open the link in a browser and join there.
- **Another device**: **Your account → Sign in on another device** shows a short code to type on it.
- **Another PC**: `fleet_agent link https://fleet.example.org` on it, then confirm the code on the page.

Admins can suspend or remove members (removing deletes their PCs and history), make other admins, and change the org name (**Admin → Members / Settings**).

### Optional: Discord

Fill in the `DISCORD_*` settings in `.env` (the comments there say where to find them) and restart. Then:

- invite pages offer **Join with Discord**, and members can connect Discord under **Your account**, then sign in with it anywhere;
- members who connected Discord are suspended if they lose the member role, and restored if they get it back;
- **Admin → Settings** can let holders of the role join without an invite.

Nothing requires Discord: without it, everything above works with invites and codes.

### Optional: a bot or other integration

**Admin → Integrations** makes API keys for bots and scripts: read the fleet, follow events live, create invites. See [docs/HUB_API.md](../docs/HUB_API.md).

## Updating

```bash
cd SCTelemetry && git pull && cd deploy && docker compose up -d --build
```

The database upgrades itself on start. Agents reconnect by themselves.

## Your data

One SQLite file in the `hub-data` volume (`hub.sqlite3`): members, sign-in sessions, linked PCs, invites, API keys and the event log (30 days by default). Every token, code and key is stored as a hash. Live telemetry is held in memory only. Whoever runs the hub can see everything members share, so run it for people who trust you.

Back up while running:

```bash
docker compose exec hub python -c "import sqlite3; s=sqlite3.connect('/data/hub.sqlite3'); s.backup(sqlite3.connect('/data/backup.sqlite3'))"
docker cp fleet-hub:/data/backup.sqlite3 ./hub-backup.sqlite3
```

## Trying it on your PC

```bash
HUB_DEV_LOGIN=1 uv run python -m fleet_hub
```

Open `http://127.0.0.1:8100`, sign in with any name (the first one becomes admin), and create an invite under **Admin → Invites**. Then, in another terminal (`FLEET_TELEMETRY_HOME` keeps this test apart from your real agent settings):

```bash
export FLEET_TELEMETRY_HOME=/tmp/fleet-test
uv run python -m fleet_agent link <invite link> --name "Test Pilot"
uv run python -m fleet_agent run --replay --uplink     # recordings, sent to your test hub
```

Test sign-in is refused on an https hub.
