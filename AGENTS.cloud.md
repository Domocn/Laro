# AGENTS.md

## Cursor Cloud specific instructions

### Authoritative repo vs public artefact

- **`Domocn/laro-priv`** is the authoritative source (production `laro.food`, Play Store, this tree).
- **`Domocn/Laro`** is a **generated** self-host artefact (`create-public-repo.sh`). It deliberately strips
  `docker-compose.production.yml`, the production `Caddyfile`, `DEPLOY.md`, backups/systemd, etc.
- **Never deploy `laro.food` / the OVH VPS from the public repo.** Production uses
  `docker-compose.simple.yml` + `docker-compose.production.yml` on `/opt/laro` (see `DEPLOY.md`).
  Public compose alone publishes Flower/Postgres/Redis on `0.0.0.0`.

This Cloud Agent workspace may still be attached to public `Domocn/Laro`. Develop against the
private clone at **`~/laro-priv`** (refreshed by the update script via the deploy key
`~/.ssh/laro_ovh`). Push with that same SSH key (write deploy key on `laro-priv`).

### Services (local dev)

| Service | Command | Port |
|---|---|---|
| Postgres | `sudo pg_ctlcluster 16 main start` (DB `laro_priv`, user `laro`/`laro`) | 5432 |
| Backend | `cd ~/laro-priv/backend && set -a && source .env && set +a && ./venv/bin/uvicorn server:app --host 0.0.0.0 --port 8001` | 8001 |
| Frontend | `cd ~/laro-priv/frontend && PORT=3000 BROWSER=none HOST=0.0.0.0 REACT_APP_BACKEND_URL=http://localhost:8001 npm start` | 3000 |

- Use a **dedicated DB** (`laro_priv`). Do not reuse a DB initialized by the public-repo schema —
  column sets differ and inserts fail (e.g. missing `nutrition` / `dietary_tags`).
- `config.py` does **not** auto-load `.env` at import; export/`source` `.env` before uvicorn.
  Copy from `.env.example` → `~/laro-priv/.env` and `backend/.env` for local use (gitignored).
- Registration **auto-verifies** when `is_email_configured()` is false (`EMAIL_ENABLED` + Resend or SMTP).
  When email is configured, verification mail is required before login.
- Frontend reads `localStorage.laro_server_url` or `REACT_APP_BACKEND_URL` (CRA/craco).
- **Localhost port gotcha:** `normalizeServerUrl` in `frontend/src/lib/api.js`
  treats any URL whose **hostname** matches the page (e.g. both `localhost`)
  as same-origin and returns `''`, so the SPA calls relative `api/` on `:3000`
  and 404s even when `REACT_APP_BACKEND_URL=http://localhost:8001`. Workaround
  for UI testing: open the app via `http://127.0.0.1:3000` and point the API at
  `http://localhost:8001` (or the reverse) so hostnames differ; or exercise the
  API with curl. Production same-host Caddy proxy is unaffected.
- Redis/Ollama optional; production overlay disables Ollama on the VPS.

### Production (OVH)

- Host: `/opt/laro`, user `agentdeploy` (docker group, no sudo). SSH key: `~/.ssh/laro_ovh`.
- Compose: `docker compose -f docker-compose.simple.yml -f docker-compose.production.yml …`
  **Never** `docker compose up` / `docker compose -f docker-compose.yml` alone — that
  starts the non-production `docker-compose.yml` stack, tears down `laro-*` services, and can 502
  `laro.food`. Build frontend with the same two-file compose (or
  `docker build -t ghcr.io/domocn/laro-frontend:latest ./frontend` then
  `up -d --force-recreate frontend`).
- **Auto-deploy:** `deploy/laro-deploy.sh` (cron every 10 min as `agentdeploy`, or
  `laro-deploy.timer`). Production overlay uses GHCR `:main` tags. Manual:
  `LARO_FORCE_DEPLOY=1 /opt/laro/deploy/laro-deploy.sh`. Logs: `/opt/laro/logs/deploy.log`.
- **Instagram/TikTok reels:** need Netscape cookies at
  `/opt/laro/secrets/yt-dlp-cookies.txt` (`YT_DLP_COOKIES_FILE`). Vision model via
  `OLLAMA_VISION_MODEL` (already `gemma4` on prod). See `secrets/README.md`.
- Follow **`DEPLOY.md`**. Do not bring up experimental/cheap stacks that bind 80/443.
- Public site: `https://laro.food`. Bare IP HTTP: `http://51.38.68.224` (Caddyfile site block).
- **Meal-plan / AI failures:** full server detail is in `docker logs laro-backend`
  (`Meal plan generation failed`, `Failed to parse meal plan JSON`, LLM preview).
  Clients should surface API `detail` via `getAiQuotaErrorMessage` (web) /
  `ApiErrorDetail` (Android) — not only generic codes like E-MP004.
- **Email:** backend reads `EMAIL_ENABLED`, `RESEND_API_KEY`, `SMTP_*`, and
  `OAUTH_REDIRECT_BASE_URL` from compose → `/opt/laro/.env`. Prefer Resend;
  set `SMTP_FROM_EMAIL=noreply@laro.food` and verify the domain in Resend DNS
  before flipping `EMAIL_ENABLED=true`. Cloudflare may 403 non-browser curls to
  `https://laro.food` — smoke-test auth via origin `127.0.0.1:8001` on the VPS.
- **Verify / reset links** must be path-based (`/verify-email?token=…`), not
  `/#/verify-email?…`. Resend click-tracking strips hash fragments. Caddy +
  `index.html` bounce path URLs into HashRouter.
- **App version** (Settings “Laro v…”): from `VERSION` / `backend/VERSION` /
  `APP_VERSION`. VPS builds must use
  `docker build --build-arg APP_VERSION=$(cat VERSION) …` and set `APP_VERSION`
  in `/opt/laro/.env`, or Settings shows `0.0.0-dev`.
- **Android password managers:** login/register use Compose `ContentType` +
  `AutofillHelpers.commit()`. Register must commit on
  `needsEmailVerification` (not only `loginSuccess`). Web↔app credential
  sharing still needs Digital Asset Links
  (`/.well-known/assetlinks.json`) with the Play App Signing SHA-256 — not
  wired yet.
- **Android edge-to-edge (SDK 35+):** `MainActivity` calls `enableEdgeToEdge()` with
  transparent `SystemBarStyle` scrims (before `super.onCreate`). Do **not** set
  `Window.statusBarColor` / theme `statusBarColor` / `navigationBarColor` (deprecated
  on API 35+). Prefer transparent system bars + Compose inset paddings
  (`statusBarsPadding` / `navigationBarsPadding` / `imePadding`). Root `LaroNavHost`
  Scaffold uses `contentWindowInsets = WindowInsets(0)` and pads the bottom nav with
  `navigationBarsPadding()`; bottom-tab screens also zero content insets and pad the
  header with `statusBarsPadding()`. Theme uses `windowLayoutInDisplayCutoutMode=always`.
  R8: release `isMinifyEnabled` + `isShrinkResources`; `android.enableR8.fullMode=true` +
  `android.r8.optimizedResourceShrinking=true` (AGP **8.13.2**). AGP 9.0 deferred
  (would auto-enable optimized resource shrinking; validate Compose/KSP/Hilt first).
- **Play `LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES`:** Not in app source or themes
  (we set cutout mode `always`). Origin: `androidx.activity.EdgeToEdgeApi28.adjustLayoutInDisplayCutoutMode`
  (bytecode `iconst_1` = SHORT_EDGES for API 28–29). API 30+ uses `EdgeToEdgeApi30` →
  ALWAYS (`iconst_3`). Still present in `activity`/`activity-compose` **1.12.4 and 1.13.0**.
  No Accompanist. Cannot clear the Play warning without androidx fixing that class or
  dropping `enableEdgeToEdge()` (not recommended). Ignore until library updates.
- **Android R8 + Gson (release-only crashes):** Debug skips minify, so reflective
  faults (Gson DTOs marked abstract; anonymous `TypeToken` losing generic
  signatures) only show in release / Play. Prefer
  `TypeToken.getParameterized(...)` over `object : TypeToken<…>() {}` (see
  `Converters.kt`, fixed in `v4.2.1` / `dde0af8`). Keep DTO classes from being
  shrunk abstract (`proguard-rules.pro`). When fixing a Crashlytics crash,
  match the **exact stack** (e.g. `Converters.<init>` vs Health Connect paths)
  — nearby “Settings crash fixed” commits may harden a different code path.
  Verify release dex: no anonymous TypeToken subclasses at the crash site;
  `javap`/dexdump on the release APK beats “it compiles.” After minify:
  `android/scripts/check-r8-typetoken.sh` (needs
  `./gradlew :app:minifyReleaseWithR8`). Unit: `./gradlew :app:testDebugUnitTest
  --tests com.laro.app.data.db.ConvertersTest`.
- **ADHD / neurospicy a11y:** Web presets in `AccessibilityContext` + CSS classes;
  `confirmDestructive` gates deletes; `iconLabels` shows nav text; Cook Mode
  honors `timerNotifications` + haptics. Android `applyNeuroPreset()` applies
  full bundles (not single toggles) and best-effort syncs to `/preferences`.
  Focus/simplified calm the Android home (hide stats / getting-started).
- **RevenueCat (Play):** public SDK key via `android/local.properties`
  `REVENUECAT_API_KEY=goog_…` or env/Cursor secret `REVENUECAT_API_KEY`
  (Gradle `localOrGradleProperty`). Release CI is wired:
  `auto-release-on-merge.yml` and `bump-version.yml` pass
  `REVENUECAT_API_KEY: ${{ secrets.REVENUECAT_API_KEY }}` into
  `./gradlew bundleRelease` (keep the GitHub Actions secret in sync).
  Backend webhook needs `REVENUECAT_WEBHOOK_AUTH` in `/opt/laro/.env`
  (exact Authorization header; already set on the VPS — not required as a
  Cursor secret). Webhook URL:
  `https://laro.food/api/v1/subscriptions/webhook/revenuecat`.
  GET returns a health JSON; events must POST with that Authorization.
  Cloudflare Bot Fight previously challenged POSTs (“Just a moment…” HTML).
  Path must be allowed through (Bot Fight off or a skip/config rule). Verified
  public POST returns `{"status":"ok",...}` JSON when CF allows it. See
  `android/REVENUECAT_SETUP_GUIDE.md` Step 3.
  **Admin ↔ RevenueCat:** set `REVENUECAT_SECRET_API_KEY=sk_…` (project Secret
  API key — not `goog_`) so Admin → Subscriptions grant/revoke also grant/revoke
  promotional entitlement `Laro Pro` (`REVENUECAT_ENTITLEMENT_ID`). UI can Check /
  Sync RC per user. Paid Play subs (`source=revenuecat`) are not revoked in RC
  when admin clears Laro DB. Laro Postgres remains the gating source of truth;
  RC is the billing + client entitlement mirror.
  Full local `assembleDebug` also needs
  `android/app/google-services.json` (Firebase).
  **Web Settings → Laro Pro:** backend `/subscriptions/status` (owner forever +
  webhook sync). **Preferred checkout: Lemon Squeezy** — set `LEMONSQUEEZY_API_KEY`,
  `LEMONSQUEEZY_STORE_ID`, variant IDs, and `LEMONSQUEEZY_WEBHOOK_SECRET`; webhook
  POST `/api/v1/subscriptions/webhook/lemonsqueezy`. Frontend calls
  `/subscriptions/checkout` (auth) and redirects to the LS checkout URL with
  `custom[user_id]` for account binding. Legacy RevenueCat Web Billing still works
  if `REACT_APP_REVENUECAT_WEB_API_KEY=rcb_…` and LS is not configured.
  **Owner forever:** `LARO_OWNER_EMAILS` (default `cowandom79@gmail.com`) and
  `role=super_admin` are always Pro on the backend; Android Pro is RevenueCat
  **or** `GET /subscriptions/status` / auth `is_pro` (not RC entitlement alone).
  **Pro offering UI:** Settings → Laro Pro (`SubscriptionSection` + RevenueCat paywall)
  is the only subscribe CTA in the web app. Do not add secondary “pay on the website”
  banners or Play fallbacks. Android should hide in-app purchase and rely on the same
  account sync (optional: open Settings in the web app for checkout).
  **Account seamlessness:** login + `/auth/me` (+ OAuth callbacks) always attach
  `is_pro` / `is_owner` / `is_lifetime` via `user_subscription_fields`. Web Settings
  Laro Pro falls back to those auth flags if `/subscriptions/status` fails, so owner
  never flashes Free. Android ORs RC entitlement with backend Pro from auth/status.
  **Security (private data):** JWTs require a live `sessions` row (logout/password
  reset revoke access). Recipe reads enforce author/household/admin via
  `utils/authorization.py`. Password-reset/deletion tokens are never returned in API
  JSON unless `ALLOW_INSECURE_TOKEN_RESPONSE=true` (local only). RevenueCat webhooks
  fail closed without `REVENUECAT_WEBHOOK_AUTH`. `JWT_SECRET` is required in compose;
  `DEBUG_MODE` defaults false. After deploy, users may need to **log in again** once.
  Client i18n keys avoid `*Password:"…"` shapes that secret scanners flag as hardcoded
  credentials (labels use `pwd*` / `*Pwd*` keys). SPA edge headers (Caddy): enforcing
  CSP (inline + OpenPanel + Google Fonts allowlisted), Permissions-Policy, COOP
  `same-origin-allow-popups`, HSTS preload.
  AI-bot `Disallow` rules in live `robots.txt` are **Cloudflare-managed** — change in
  the CF dashboard, not the repo. CAA / DNSSEC are DNS-provider settings (not app code).
  Household email invite and friend-code add are **pending consent** (`household_invites` /
  `friend_requests`); accept/decline on web Household/Friends pages. Recipe uploads need
  HMAC `?exp=&sig=` (`utils/upload_tokens.py`). Public share links default/cap at 30/90 days.
  Bare IP `http://51.38.68.224` redirects only — no cleartext API proxy.

### Home Assistant

Two pieces:

1. **Custom component** (sensors/calendar/services against an existing Laro API such as `laro.food`):
   `custom_components/laro/` (mirrored under `homeassistant-integration/custom_components/laro/`).
   Copy into HA `config/custom_components/laro`, restart, then Settings → Devices → Add Integration → Laro.
   URL = Laro base (no `/api`), token = Settings → API Tokens in Laro (`laro_…`).
   Coordinator prefers `GET /api/homeassistant/all`.
2. **Supervisor add-on** (runs full Laro inside HA OS): source tree
   `laro-home-assistant-addon/`. Public store repo: `Domocn/laro-home-assistant-addon`
   (if that GitHub path is not renamed yet, set `HA_ADDON_REPO_URL` when syncing).
   Install URL: `https://github.com/Domocn/laro-home-assistant-addon`.
   Sync workflow source-of-truth copy: `docs/github-workflows/sync-ha-addon.yaml`
   (copy into `.github/workflows/` with a `workflow`-scoped PAT). Manual sync:
   `scripts/sync-ha-addon-repo.sh` when you have push access to the public add-on repo.
   Secret: `ADDON_REPO_TOKEN`.

HA unit tests: `backend/venv/bin/python -m pytest backend/tests/test_ha_addon_functionality.py`.
Addon mode env: `LARO_HA_ADDON=true`. JWT must persist in
`/data/jwt_secret` across addon restarts (`rootfs/run.sh`).

### Mobile (Compose) polish

- Play shell is root `android/` (`com.laro.app`). Capacitor was tried and reverted; do not cut over.
- Offline recipe push runs via `OfflineSyncWorker` (WorkManager) on launch / every 15m when online.
- Widgets (`MealPlanWidget`, `ShoppingListWidget`) must use
  `WidgetDatabaseEntryPoint` (same Room/SQLCipher as the app) — never a second
  plain `Room.databaseBuilder`.
- Cook Mode: keep-awake + timers + TTS (speaker button; auto-read in focus mode).
- **Health Connect** (v4.0.7+): Sync calories/macros when a meal is **marked
  cooked**. Surfaces:
  - Cook Mode → **Finish** sheet → “Sync to Health Connect” toggle
  - Settings → **Health Connect** (and Preferences → Cooking Preferences, top)
  Toggle requests `WRITE_NUTRITION`. Needs Health Connect app / system support
  (API 28+). Off by default until enabled.
- **Google Health API** (v4.3.0+): Cloud nutrition write (Fitbit / Google Health)
  via backend OAuth — complementary to on-device Health Connect.
  - Link: web **Settings → Security → Google Health**, or Android **Security**.
  - On mark-cooked / cook-session complete, if linked + `sync_on_cook`, backend
    POSTs anonymous `nutrition-log` to `health.googleapis.com`.
  - Env: `GOOGLE_HEALTH_CLIENT_ID` / `GOOGLE_HEALTH_CLIENT_SECRET` (else
    `GOOGLE_CLIENT_*`). Redirects: `{OAUTH_REDIRECT_BASE_URL}/oauth/callback/google-health`
    and `laro://oauth/callback/google-health`. Scope:
    `googlehealth.nutrition.writeonly` (**Restricted** — add test users in Cloud
    Console until Google verification completes).
  - Undo a log: `DELETE /api/google-health/logs/{log_id}` (batchDelete on Google).
  Tokens are Fernet-encrypted at rest (key from `JWT_SECRET` or
  `GOOGLE_HEALTH_TOKEN_KEY`).
- **Meal packs from URL**: Meal Planner import accepts Huel-style product /
  collection URLs (shakes, RTD, pouches) via `POST /ai/import-meal-plan-url`
  (`import_mode=meal_packs`). PDF/paste remains for printable weekly plans.
  RTD/packs are **always** saved as **Recipes** (category `Meal Pack`) — never
  meal-plan-only. Macros come from the page or user entry. Same path via
  `POST /ai/import-url`, Recipes page `POST /import/url`, and web filter chip
  **Meal Pack**.
- **Recipe / meal-plan PDFs**: `POST /ai/import-recipe-pdf` splits one document
  into separate recipes (no overlapping titles), skips library duplicates, and
  tags each `needs-review`. Web: Quick Add → PDF, Import modal, Recipes
  “Needs review” filter. Android: Recipes FAB → Import PDF; Meal Plan → PDF.
  Weekly plans: `POST /ai/import-meal-plan-pdf` (web + Android).
- Web/PWA/HA share `frontend/`; SW API offline cache patterns are `/api/recipes`
  etc. (not `/api/v1/...`).

### Settings / preferences

Full inventory: `docs/SETTINGS_AND_PREFERENCES.md`. Web routes: `/#/settings`,
`/#/settings/preferences`, `/#/settings/security`. Settings last tab is labeled
**App** (id still `admin`) and holds notifications/reminders. Prefer
`useUserPreferences()` when reading cooking prefs in new UI. Accent stays
localStorage-only; a11y dual-writes local + `/preferences`.

### Mobile (Compose) polish

- Play shell is root `android/` (`com.laro.app`). Offline recipe push runs via
  `OfflineSyncWorker` (WorkManager) on launch / every 15m when online.
- **Recipe list after login:** Logout clears Room. `AuthRepository` must call
  `recipeRepository.refreshRecipes()` after login / OAuth / session restore
  (not only when Home/Recipes ViewModels open — onboarding can skip those).
  Never wipe synced Room rows when the server returned rows that all failed to
  parse. Share the activity-scoped `AuthViewModel` into `LoginScreen` so login
  work is not cancelled when the Login back-stack entry is popped.
- **WebSocket:** Caddy must proxy both `/ws` and `/ws/*` to the backend.
  Android builds `wss://laro.food/ws` (no token in URL; auth as first message).
- Widgets (`MealPlanWidget`, `ShoppingListWidget`) must use
  `WidgetDatabaseEntryPoint` (same Room/SQLCipher as the app) — never a second
  plain `Room.databaseBuilder`.
- Cook Mode: keep-awake + timers + TTS (speaker button; auto-read in focus mode).
- Web/PWA/HA share `frontend/`; SW API offline cache patterns are `/api/recipes`
  etc. (not `/api/v1/...`).

### Lint / test

- Backend: `cd backend && ./venv/bin/python -m pytest` (many pass; some async tests still need
  `pytest-asyncio` if not declared).
- Frontend: CRA/`craco` — `npm start` / `npm run build` under `frontend/`.
- Android: `cd android && ./gradlew assembleDebug`.
- HA: `backend/venv/bin/python -m pytest backend/tests/test_ha_addon_functionality.py`

### Gap-fix notes (durable)

- **`users.friends`** is a TEXT JSON array column (added in DB init/migrations). Without it,
  `POST /friends/add` 500s. Fresh DBs get it from `SCHEMA`; existing DBs get the `IF NOT EXISTS` ALTER.
  Friend add creates a **pending** `friend_requests` row; mutual friendship only after accept
  (or reciprocal pending request → auto-accept).
- **Reminders** are live: `services/reminders.py` sweeps meal / shopping / weekly-plan.
  - In-process loop via `REMINDERS_INPROCESS=true` (default) on the API.
  - Celery Beat service `beat` in `docker-compose.simple.yml` (deduped by `reminder_dispatch_log`).
  - Delivery: FCM (Android), Web Push (needs `VAPID_*` env), email if `EMAIL_ENABLED`.
  - Meal: minutes-before from web Settings; dinner clock 18:00 (web) or mobile `reminder_time` HH:MM.
  - Shopping: Saturday ~10:00 UTC; weekly plan: Sunday ~16:00 UTC if next week &lt; 3 meals.
  - Manual sweep: `POST /api/notifications/reminders/run` (admin, or any user when `DEBUG_MODE`).
- **UK Open Prices (cost estimates):** GBP catalog from Open Food Facts Open Prices is synced into
  Postgres (`uk_open_prices`) every **12h** via Celery Beat (`sync_uk_open_prices_task`). Lookups
  read the local table (offline at request time); first use seeds if empty. Export for Android:
  `GET /api/costs/uk-catalog`. Manual refresh: `POST /api/costs/uk-catalog/sync`. Toggle with
  `OPEN_PRICES_ENABLED`. Android Room table `uk_open_prices` refreshes in `OfflineSyncWorker`
  and falls back to local matching when the API is unreachable.
- **Hands-free cook voice:** In Cook Mode tap **Hands-free** (web) or the
  **Hands-free** chip (Android), allow the mic once, leave the phone nearby with
  the screen on, and say **“Next”** / **“Back”** / **“Repeat”**. Preference is
  remembered (`localStorage.laro_cook_hands_free` / Android `laro_cook` prefs).
  Mic pauses while TTS reads a step so it doesn’t hear itself. Google Home
  speakers still cannot receive Laro voice commands — use the phone mic.
- **Google Cast (Chromecast) cook mode:** Custom CAF receiver at
  `/cast/receiver.html` (namespace `urn:x-cast:food.laro.cook`). Cook Mode Cast
  button + hands-free keep the phone as the mic while the TV/Hub shows steps.
  Requires `REACT_APP_CAST_APP_ID` from
  [Cast Developer Console](https://cast.google.com/publish) with receiver URL
  `https://laro.food/cast/receiver.html` (or your host). Injected at container
  start like other `REACT_APP_*` keys; optional override
  `localStorage.laro_cast_app_id`. Media Session also maps headset / system
  “next track” to the next cook step.
  - **Works:** Chromecast with screen, Google TV, Nest Hub / Nest Hub Max.
  - **Does not work:** speaker-only Google Home / Nest Mini / Nest Audio.
- Web **Friends** UI: `/#/friends` (user menu). Open PRs against `laro-priv` via the GitHub UI —
  cloud `gh` / ManagePullRequest tokens cannot see the private repo.
- **Referrals:** Friend codes (`friend_code`) double as referral codes. Signup with
  `referral_code` (web: `/register?ref=CODE`, Android register field) grants **14 days** Pro
  (`referral_trial_end` + `subscription_status=trial`). Backend `is_premium_user` honors the
  referral trial. Referrer earns **points** (50 on signup, 150 when friend subscribes) redeemable
  in the **Reward store** on Friends (`GET/POST /rewards/*`) for Pro days, AI uses, recipe/friend/
  cookbook/household slots, and weekly share boosts. Free-tier gates: recipes 15, friends 3,
  shares/week 5, cookbooks 3, household members 2 (+ redeemable bonuses).
- **Support tickets:** `/#/support` (user menu **Help & support**). API under `/support/tickets`
  (+ `/support/admin/tickets` for staff). Admin Dashboard → Tickets. Android: Report a Bug
  creates a ticket; **My Tickets** under Settings → Data.
- **Cloud AI (laro.food):** set `IS_CLOUD=true` with Ollama Cloud (`OLLAMA_URL=https://ollama.com`,
  `OLLAMA_API_KEY`, `OLLAMA_MODEL`). Settings then shows managed **Laro AI** (no local Ollama /
  BYO keys / Embedded picker). Receipt / photo OCR uses `OLLAMA_VISION_MODEL` (default
  `gemma4` when a cloud API key is set) — text models like `gpt-oss` cannot see images.
  Vision calls must send the Bearer key via `/api/chat` (`call_ollama_vision` in
  `backend/dependencies.py`). Pro = unlimited quota; free = `FREE_AI_USES`.
