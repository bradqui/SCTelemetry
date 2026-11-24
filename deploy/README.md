# Deploying the hub

The hub runs as one Docker container behind the Virtualmin-managed Apache site. Both of its ports listen on `127.0.0.1` only:

| Port | What | Reached by |
|---|---|---|
| 8100 | The site: fleet page, sign-in, agent connections | Apache (`https://fleet.fridaynightclub.xyz`) |
| 8101 | Bot-only API | ButlerBot, directly (it uses host networking). Never add it to Apache. |

## 1. Discord application

1. At discord.com/developers, create a **New Application** (e.g. "Fleet Telemetry"). It doesn't need a bot user.
2. Under **OAuth2**, add the redirect `https://fleet.fridaynightclub.xyz/auth/callback`.
3. Note the **Client ID** and **Client Secret**. The secret goes only in `.env` on the server.
4. In Discord, switch on Developer Mode (Settings → Advanced). Right-click the server → **Copy Server ID**, and the org member role → **Copy Role ID**.

## 2. DNS and the site

1. In Cloudflare, add an `A` record for `fleet` pointing at the server, **DNS only (gray cloud)** to start.
2. In Virtualmin, create the sub-server `fleet.fridaynightclub.xyz` with SSL. Once DNS resolves, request a Let's Encrypt certificate.
3. Add to the **SSL (443)** site's directives (Server Configuration → Edit Directives):

   ```apache
   ProxyPreserveHost On
   RequestHeader set X-Forwarded-Proto "https"
   ProxyPass        /  http://127.0.0.1:8100/ upgrade=websocket
   ProxyPassReverse /  http://127.0.0.1:8100/
   ```

4. Redirect plain http to https for the site (Virtualmin: Website Redirects, or the site's SSL settings).

Later, to put Cloudflare's proxy in front (orange cloud): SSL/TLS mode **Full (strict)**, WebSockets on, **Bot Fight Mode off** (it blocks agents), Rocket Loader off.

## 3. Get the code onto the server

The repo is private, so the server needs read access. Either:

- a **deploy key**: `ssh-keygen -t ed25519 -f ~/.ssh/sctelemetry_deploy -N ""`, add the `.pub` file in GitHub (repo → Settings → Deploy keys, read-only), then
  `GIT_SSH_COMMAND="ssh -i ~/.ssh/sctelemetry_deploy" git clone git@github.com:bradqui/SCTelemetry.git`
- or `gh auth login` on the server and `gh repo clone bradqui/SCTelemetry`.

## 4. Configure and start

```bash
cd SCTelemetry/deploy
cp .env.example .env
nano .env                         # Discord IDs, secret, HUB_INTERNAL_SECRET
docker compose up -d --build
docker compose logs -f hub        # "Hub 0.1.0 on 0.0.0.0:8100 (public: https://...)"
curl -s http://127.0.0.1:8100/api/health
```

The startup log lists any setting that's missing.

Then open `https://fleet.fridaynightclub.xyz`, sign in with Discord, and link a PC:

```powershell
uv run python -m fleet_agent link        # opens the browser; confirm the code
uv run python -m fleet_agent run         # now also sends to the fleet
```

## Updating

```bash
cd SCTelemetry && git pull && cd deploy && docker compose up -d --build
```

Agents reconnect by themselves.

## Data

Everything lives in the `hub-data` volume as one SQLite file (`hub.sqlite3`): members, sign-in sessions, linked PCs (token hashes only), and the event log, which is kept for 30 days. Live telemetry is held in memory only.

To back it up while running:

```bash
docker compose exec hub python -c "import sqlite3; s=sqlite3.connect('/data/hub.sqlite3'); s.backup(sqlite3.connect('/data/backup.sqlite3'))"
docker cp fleet-hub:/data/backup.sqlite3 ./hub-backup.sqlite3
```

## Trying it without Discord

On any PC with the repo:

```bash
HUB_DEV_LOGIN=1 HUB_INTERNAL_SECRET=dev uv run python -m fleet_hub
uv run python -m fleet_agent link --hub http://127.0.0.1:8100
uv run python -m fleet_agent run --replay --uplink --hub http://127.0.0.1:8100
```

Open `http://127.0.0.1:8100` and sign in with any name. Test sign-in is refused on an https hub.
