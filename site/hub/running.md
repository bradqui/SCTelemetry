# Setting up a hub

The hub is one Docker container: the fleet page, sign-in, and the place your members' agents send their telemetry. Each org runs its own; there's no central service.

You need:

- a server with Docker (a small VPS is plenty);
- a domain name pointing at it;
- a reverse proxy that does https (Caddy, nginx, Apache, or Cloudflare in front).

About ten minutes, start to finish.

## 1. Start it

```bash
git clone https://github.com/bradqui/starglance.git
cd starglance/deploy
cp .env.example .env
nano .env                       # HUB_URL and HUB_ORG_NAME at least
docker compose pull             # the released hub image (ghcr.io/bradqui/starglance-hub)
docker compose up -d
docker compose logs hub
```

The first time, the log shows a **setup link**:

```
WARNING starglance_hub.app: No admin yet. Open this link to create the admin account:
WARNING starglance_hub.app:     https://fleet.example.org/join/AbC...
```

Open it once https is up (step 2), or paste it into your own Starglance: `starglance link <setup link>` makes your admin account and links your PC in one go. It works once; if you lose it, restart the container while there's still no admin and a new one is logged.

The hub listens on `127.0.0.1:8100` only. `curl -s http://127.0.0.1:8100/api/health` should answer.

## 2. Put https in front

Point your DNS name at the server, then proxy it to `127.0.0.1:8100` with WebSockets allowed.

::: code-group

```txt [Caddy]
fleet.example.org {
    reverse_proxy 127.0.0.1:8100
}
```

```nginx [nginx]
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

```apache [Apache 2.4.47+]
# a2enmod proxy proxy_http headers; in the https site:
ProxyPreserveHost On
RequestHeader set X-Forwarded-Proto "https"
ProxyPass        /  http://127.0.0.1:8100/ upgrade=websocket
ProxyPassReverse /  http://127.0.0.1:8100/
```

:::

Caddy gets its certificate by itself. Redirect plain http to https.

**Cloudflare's proxy** (orange cloud) works: set SSL/TLS to **Full (strict)**, keep WebSockets on, and turn **Bot Fight Mode off** (it blocks agents). Get the certificate first with the record DNS-only (grey) if your server issues its own.

## 3. Bring your org in

On the fleet page, **your name → Admin → Invites**: pick how many uses and how long it lasts, create it, and send the link. See [Admin](/hub/admin).

## Settings

The ones in `.env` you'll most likely touch:

| Setting | What it is |
|---|---|
| `HUB_URL` | The hub's public address, like `https://fleet.example.org` |
| `HUB_ORG_NAME` | Your org's name on the page (you can change it later under Admin → Settings) |
| `HUB_EVENT_RETENTION_DAYS` | How long fleet events are kept (30 days by default) |
| `HUB_REPORT_RETENTION_DAYS` | How long problem reports are kept (30 days by default) |
| `DISCORD_*` | Optional defaults for Discord sign-in; easier to set up on the page ([Admin](/hub/admin#discord)) |
| `HUB_VERSION` | Stay on one version, e.g. `0.7.0` |
| `HUB_HOST_NAME`, `HUB_HOST_URL` | Only if you run this hub for another org: "Hosted by" on the page, and their admins can ask you to close it ([Admin](/hub/admin#hosted-orgs)) |

The comments in `.env.example` explain each one.

## Updating

```bash
cd starglance && git pull && cd deploy && docker compose pull && docker compose up -d
```

The database upgrades itself on start, and agents reconnect by themselves. Hub and agents are released together with the same version: after you update the hub, members whose Starglance is behind see an **Update** button, and ones older than the hub supports are told to update.

## Your data

One SQLite file in the `hub-data` volume (`hub.sqlite3`): members, sign-in sessions, linked PCs, invites, API keys, the event log and problem reports. Every token, code and key is stored as a hash. Live telemetry is held in memory only.

Back up while running: **Admin → Settings → Download everything** saves a consistent copy (a zip with `hub.sqlite3`). For a scheduled backup on the server:

```bash
docker compose exec -u hub hub python -c "import sqlite3; s=sqlite3.connect('/data/hub.sqlite3'); s.backup(sqlite3.connect('/data/backup.sqlite3'))"
docker compose cp hub:/data/backup.sqlite3 ./hub-backup.sqlite3
```

::: warning You can see what members share
Whoever runs the hub can see everything members share with the fleet. Run it for people who trust you, and tell them who has access.
:::

## Troubleshooting

**`unable to open database file`, restarting over and over.** The hub runs as its own user (uid 10001), which couldn't write to `/data`. Since 0.5.0 the image fixes this on start; update with `docker compose pull && docker compose up -d`. On an older image, or a read-only mount: `sudo chown -R 10001:10001 <your data folder>`.

**Everyone gets "too many attempts" at once.** Hubs before 0.5.0 couldn't see visitors' real addresses behind Docker's network, so everyone shared one limit. Update the hub.

**Agents can't connect through Cloudflare.** Turn Bot Fight Mode off, and check that WebSockets are on.

More: the full guide in [deploy/README.md](https://github.com/bradqui/starglance/blob/main/deploy/README.md).
