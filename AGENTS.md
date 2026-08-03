# AGENTS.md

## Cursor Cloud specific instructions

Laro is a self-hosted recipe manager. This repo is a single product split into two runnable
services plus a database:

- Backend: FastAPI app in `backend/` (ASGI app is `server:app`), serves REST `/api/*` + WebSockets on port 8001.
- Frontend: React + Vite SPA at the repo root, dev server on port 3000 (`npm run dev`).
- Database: PostgreSQL (database `laro`, role `laro`/`laro`). Schema is auto-created by the backend on startup.
- Optional: Redis (multi-instance WebSocket sync) and an LLM (Ollama/OpenAI/etc.) for AI features. Both are optional — the backend degrades gracefully to single-instance mode without Redis, and non-AI features work without an LLM.

The update script (run on VM startup) refreshes only code dependencies: `npm install` at the root
and a Python venv at `backend/venv` with `backend/requirements.txt`. System packages
(PostgreSQL, `python3-venv`, `build-essential`) are already provisioned in the environment and are
NOT reinstalled by the update script.

### Starting the services (not done by the update script)

1. Start PostgreSQL (it is not auto-started): `sudo pg_ctlcluster 16 main start`.
   If the `laro` role/database are missing, recreate them:
   `sudo -u postgres psql -c "CREATE ROLE laro LOGIN PASSWORD 'laro';"` then
   `sudo -u postgres psql -c "CREATE DATABASE laro OWNER laro;"`
2. Backend: `backend/.env` already holds `DATABASE_URL`, `JWT_SECRET`, etc. IMPORTANT: `config.py`
   reads plain `os.getenv` and does NOT auto-load `.env` at startup, so you must export it first:
   `cd backend && set -a && source .env && set +a && ./venv/bin/uvicorn server:app --host 0.0.0.0 --port 8001`
   (`backend/.env` is git-ignored; recreate it from `backend/.env.example` if absent.)
3. Frontend: `npm run dev` from the repo root (Vite serves on http://localhost:3000).

Note: the README's manual command `uvicorn main:app --port 8000` is WRONG — there is no `main.py`.
The real app is `server:app` on port 8001 (matches the Dockerfile).

### Wiring the dev frontend to the backend (non-obvious, required)

`vite.config.ts` defines NO dev proxy for `/api`. The axios client (`src/lib/api.tsx`) reads the
backend base URL from the browser `localStorage` key `mise_server_url`. For the dev frontend to
reach the backend you must set it in the browser (DevTools console), then reload:

```
localStorage.setItem('mise_server_url','http://localhost:8001'); location.reload();
```

Gotcha: the in-app "Server Config" page (`src/pages/ServerConfig.tsx`) saves to a DIFFERENT key,
`laro_server_url` (a leftover from the Mise -> Laro rename), which the axios client does NOT read.
So using that page alone will not connect the SPA — set `mise_server_url` directly.

The first registered user becomes admin. Email validation rejects reserved TLDs like `.test`
(use e.g. `@example.com`).

### Testing / linting / building

- Backend tests: from `backend/` run `./venv/bin/python -m pytest`. 83 pass; 8 fail because the
  async tests use `@pytest.mark.asyncio` but `pytest-asyncio` is not declared in
  `requirements.txt` (pre-existing repo gap, not an environment issue).
- Type check (frontend): `npx tsc --noEmit`. The only error is a reference to a missing
  `tsconfig.node.json` (see known bugs below); source files themselves type-check clean.
- `npm run lint` is currently NOT runnable as written: it invokes `bun` (not installed) and
  references `scripts/check-css-variables.js` / `scripts/check-css-classes.js` which do not exist,
  and `eslint` is not in `package.json` (no eslint/stylelint config present). This is a repo-level
  tooling gap, not an environment gap.
- There is no frontend build step required for development (`npm run dev` is enough); `npm run build`
  is the production build.

### Known pre-existing frontend code bugs (NOT environment issues)

These currently prevent the SPA from rendering past the loading screen and are code defects, not
setup problems (do not "fix" them as part of environment setup):

- `src/lib/debug.tsx` is missing symbols used elsewhere: `DebugLogger.debug(...)` (called in
  `src/context/AuthContext.tsx` on every load, throwing before `setLoading(false)`), plus
  `debug.ws`, `logWsEvent`, and `debugStats` (used in `src/hooks/useLiveRefresh.tsx`).
- `tsconfig.json` references `./tsconfig.node.json`, which does not exist.

To exercise the full UI end-to-end you must first address these code bugs; the backend API,
database, and both dev servers are otherwise fully functional.
