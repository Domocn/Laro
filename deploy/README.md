# Cheap single-VPS deployment (e.g. OVH)

Runs **all of Laro** (web UI + API + database) on one small VPS at a single
address — by default the bare IP you were given (e.g. `http://51.38.68.224`).
No Netlify frontend and no Railway backend are required.

Architecture: **two containers** — the app (FastAPI backend that also serves the
built frontend) and Postgres — behind Caddy. No Ollama, Redis, Celery worker,
Flower or analytics stack (none are required), which is what makes it cheap.

## Why this is cheaper
- **One app process** serves both the API and the web UI (`SERVE_FRONTEND=true`).
- **Postgres on the same box** — no managed-database fee.
- **No self-hosted LLM** — use the on-device AI in the Android app, or a
  pay-per-use cloud key.
- Flat-rate VPS (~€4–5/mo) beats usage-billed PaaS for an always-on API.

## Prerequisites
- A VPS with a public IP (yours: `51.38.68.224`, hostname
  `vps-51feb6de.vps.ovh.net`).
- Ports **80** (and optionally **443**) open inbound.

## One-time setup on the VPS

SSH in as `ubuntu`, then:

```bash
# 1) Install Docker + compose plugin
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker

# 2) Get the code (use the branch that has this deploy pack once merged, or main)
git clone https://github.com/Domocn/Laro.git
cd Laro

# 3) Configure — IP mode (default): leave LARO_SITE_ADDRESS blank
cp deploy/env.example deploy/.env
nano deploy/.env
# Required: POSTGRES_PASSWORD, JWT_SECRET (openssl rand -base64 48)
# Leave LARO_SITE_ADDRESS= empty so the site is http://51.38.68.224

# 4) Launch
docker compose -f deploy/docker-compose.cheap.yml --env-file deploy/.env up -d --build
```

Open **`http://51.38.68.224`**. The first registered user becomes admin. Schema
is created automatically on first boot.

### Optional: HTTPS with a domain later
Set `LARO_SITE_ADDRESS=vps-51feb6de.vps.ovh.net` (or your own domain whose A/AAAA
points at `51.38.68.224`), then recreate Caddy:

```bash
docker compose -f deploy/docker-compose.cheap.yml --env-file deploy/.env up -d caddy
```

Let's Encrypt cannot issue certificates for a bare IP — TLS needs a DNS name.

## Point clients at this VPS
- **Web (this box):** open `http://51.38.68.224` — UI and API are same-origin.
- **Android app:** server URL = `http://51.38.68.224` (or `https://…` after TLS).
- You can stop the Netlify frontend and Railway backend once this is live.

## Operations

```bash
docker compose -f deploy/docker-compose.cheap.yml logs -f app

git pull && docker compose -f deploy/docker-compose.cheap.yml --env-file deploy/.env up -d --build

docker compose -f deploy/docker-compose.cheap.yml exec postgres \
  pg_dump -U laro laro > backup-$(date +%F).sql
```

## Moving off Railway
The old cloud relay URL was hardcoded to `web-production-b3fb4.up.railway.app`.
It's now configurable via `CLOUD_RELAY_URL`. If this VPS is your new "cloud"
relay (after you have HTTPS on a domain):

```
CLOUD_RELAY_URL=wss://vps-51feb6de.vps.ovh.net/api/v1/remote/relay
```

## Notes
- Combined SPA+API on one port was verified in development. Caddy on a bare IP
  (HTTP `:80`) is the default for this OVH box; cert issuance only applies when
  `LARO_SITE_ADDRESS` is a public domain.
