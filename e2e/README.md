# Laro Playwright E2E

Smoke tests for the **web frontend** (`frontend/`) against a running API + dev server.

## Prerequisites

- Postgres with `laro_priv` (see `AGENTS.md`)
- Backend on port **8001**
- Frontend dev server on port **3000** with `REACT_APP_BACKEND_URL=http://127.0.0.1:8001`

## Run locally

```bash
# Terminal 1 — backend (LARO_E2E=1 avoids 429s during global setup + 10 smoke tests)
cd backend && set -a && source .env && set +a && export LARO_E2E=1 && ./venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001

# Terminal 2 — frontend
cd frontend && PORT=3000 BROWSER=none HOST=0.0.0.0 REACT_APP_BACKEND_URL=http://127.0.0.1:8001 yarn start

# Terminal 3 — e2e
cd e2e && npm install && npx playwright install chromium && npm test
```

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `PLAYWRIGHT_BASE_URL` | `http://localhost:3000` | Use **localhost** (not 127.0.0.1) so the API can stay on `http://127.0.0.1:8001` without `api.js` same-hostname → relative `/api` on :3000 |
| `LARO_E2E` | (backend env) | Set to `1` on the API when running Playwright locally |
| `E2E_FORCE_AUTH` | — | Set to `1` to re-run UI login and refresh `.auth/user.json` |
| `PLAYWRIGHT_API_URL` | `http://127.0.0.1:8001` | Register/login in global setup |
| `E2E_EMAIL` / `E2E_PASSWORD` | auto-register | Reuse account on shared envs |

## Against production

Not recommended from CI. For manual runs only, set `PLAYWRIGHT_BASE_URL=https://laro.food` and valid `E2E_*` credentials.
