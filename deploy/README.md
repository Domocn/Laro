# Cheap single-VPS deployment (e.g. OVH)

Runs all of Laro on one small VPS as **two containers** — the app (FastAPI
backend serving the built frontend) and Postgres — behind Caddy for automatic
HTTPS. No Ollama, Redis, Celery worker, Flower or analytics stack (none are
required), which is what makes it cheap compared to the multi-service
`docker-compose.yml` or a usage-billed PaaS.

## Why this is cheaper
- **One app process** serves both the API and the web UI (`SERVE_FRONTEND=true`),
  so there's no separate nginx/frontend container.
- **Postgres runs on the same box** — no managed-database fee.
- **No self-hosted LLM** (Ollama is the biggest RAM cost). Use the on-device AI in
  the Android app, or a pay-per-use cloud key.
- A flat-rate VPS (~€4–5/mo) is typically far cheaper than usage-billed hosting
  for an always-on API.

## Prerequisites
- A VPS with a public IP (e.g. OVH `vps-51feb6de.vps.ovh.net`, `51.38.68.224`).
- A DNS name pointing at it. The OVH hostname already resolves, or point your own
  domain's A/AAAA records at the VPS IP.

## One-time setup on the VPS

SSH in as `ubuntu`, then:

```bash
# 1) Install Docker + compose plugin
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker

# 2) Get the code
git clone https://github.com/Domocn/Laro.git
cd Laro

# 3) Configure
cp deploy/env.example deploy/.env
nano deploy/.env          # set LARO_DOMAIN, POSTGRES_PASSWORD, JWT_SECRET (openssl rand -base64 48)

# 4) Launch (builds the combined image, starts postgres + app + caddy)
docker compose -f deploy/docker-compose.cheap.yml --env-file deploy/.env up -d --build
```

Open `https://<LARO_DOMAIN>` — Caddy fetches a Let's Encrypt certificate
automatically. The first registered user becomes admin. The database schema is
created automatically on first boot.

## Operations

```bash
# logs
docker compose -f deploy/docker-compose.cheap.yml logs -f app

# update to latest code
git pull && docker compose -f deploy/docker-compose.cheap.yml up -d --build

# backup the database
docker compose -f deploy/docker-compose.cheap.yml exec postgres \
  pg_dump -U laro laro > backup-$(date +%F).sql
```

## Frontend hosting

You can either serve the UI from this one container (default here) or keep the
existing Netlify frontend and point it at `https://<LARO_DOMAIN>` (set the server
URL in the app, and restrict `CORS_ORIGINS` to the Netlify origin).

## Moving off Railway
The old cloud relay URL was hardcoded to `web-production-b3fb4.up.railway.app`.
It's now configurable via `CLOUD_RELAY_URL` (`backend/config.py`). If this VPS is
your new "cloud" relay, set in `deploy/.env`:

```
CLOUD_RELAY_URL=wss://<LARO_DOMAIN>/api/v1/remote/relay
```

## Notes / limitations
- The combined image build and the app's ability to serve the SPA + API on one
  port were verified in development. Caddy's Let's Encrypt issuance needs a real
  public domain, so it can only be verified on the VPS itself.
- `usesCleartextTraffic`/HTTP is only for local testing; always use the HTTPS
  Caddy endpoint in production (the web app calls the API over HTTPS).
