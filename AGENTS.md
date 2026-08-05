# AGENTS.md

## Cursor Cloud specific instructions

### Authoritative repo vs this public artefact

- **`Domocn/laro-priv`** (clone at `~/laro-priv`) is the authoritative source for production
  `laro.food`, Play Store Android, and day-to-day development.
- **`Domocn/Laro`** (`/workspace`) is a **generated** self-host artefact from
  `create-public-repo.sh`. Prefer developing against `~/laro-priv`.
- Never deploy production from this public repo alone.

The update script refreshes deps for both trees when the deploy key
`~/.ssh/laro_ovh` is present, and writes `android/local.properties` from
`REVENUECAT_API_KEY` when that Cursor secret is injected.

### Services (local / Cloud Agent)

| Service | Command | Port |
|---|---|---|
| Postgres | `sudo pg_ctlcluster 16 main start` | 5432 |
| Backend (priv) | `cd ~/laro-priv/backend && set -a && source .env && set +a && ./venv/bin/uvicorn server:app --host 0.0.0.0 --port 8001` | 8001 |
| Frontend (priv) | `cd ~/laro-priv/frontend && PORT=3000 BROWSER=none HOST=0.0.0.0 REACT_APP_BACKEND_URL=http://localhost:8001 npm start` | 3000 |

Public-tree equivalents use `/workspace` + `backend/` and CRA at the repo root
(`npm start` / craco), not Vite. README's `uvicorn main:app --port 8000` is wrong —
use `server:app` on **8001**.

- Prefer DB `laro_priv` for the private clone; do not reuse a DB initialized from
  the public schema (column sets differ).
- `config.py` does **not** auto-load `.env`; `source` it before uvicorn.
- Registration auto-verifies when email is not configured (`EMAIL_ENABLED` + Resend/SMTP).
- Frontend API base: `localStorage.laro_server_url` or `REACT_APP_BACKEND_URL`.
- **Localhost port gotcha:** `normalizeServerUrl` collapses any same-hostname
  URL to same-origin mode (ignores port). Serving the SPA on
  `http://localhost:3000` with API `http://localhost:8001` yields relative
  `api/` → `:3000` 404s. Use mixed hostnames (`127.0.0.1` vs `localhost`) for
  UI, or call the API directly. Production same-host proxy is fine.
- Redis / Ollama optional for core auth + recipe CRUD.

### Secrets useful in Cloud Agents

- `RESEND_API_KEY` — optional local/prod email (keep `EMAIL_ENABLED=false` for
  local hello-world so registration auto-verifies).
- `REVENUECAT_API_KEY` — Play public SDK key (`goog_…`). Written to
  `~/laro-priv/android/local.properties` by the update script; Gradle also reads
  the env var. Release CI on `laro-priv` already injects
  `secrets.REVENUECAT_API_KEY` into `bundleRelease` (keep the GitHub secret).

### Lint / test / build

- Backend: `cd ~/laro-priv/backend && ./venv/bin/python -m pytest`
  (some async tests need `pytest-asyncio` if not declared).
- Frontend: `npm start` / `npm run build` under `~/laro-priv/frontend` (or `/workspace`).
- Android: `./gradlew :app:generateDebugBuildConfig` verifies `BuildConfig.REVENUECAT_API_KEY`;
  full `assembleDebug` needs `android/app/google-services.json`.

See `~/laro-priv/AGENTS.md` and `DEPLOY.md` for production OVH notes.
