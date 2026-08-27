# Feastival Pocket

Unofficial **offline** companion for [Big Feastival](https://bigfeastival.com/) 2026 (Fri 28–Sun 30 August, Alex James’ farm, Kingham, OX7 6UJ).

Not affiliated with PWR Events. Times and trader lists were copied from the public timetable and festival map on 27 August 2026. Always trust the official site and on-site signage if they disagree.

## Why this exists

Phone signal on the farm is unreliable. This app is a static PWA: after the first load, the service worker serves the timetable, line-up, site directory, street-food list, travel notes and your starred plan with no network.

## Run locally

```bash
cd apps/feastival-offline
npm install
npm run dev
```

Preview the production build (includes the service worker):

```bash
npm run build
npm run preview
```

Open the preview URL once while online, then toggle the browser to offline and keep using the app.

## Deploy on Vercel

1. Import this GitHub repo (or a fork).
2. Set **Root Directory** to `apps/feastival-offline`.
3. Framework preset: Vite. Build command `npm run build`, output `dist`.
4. Deploy. Add to Home Screen on iOS/Android for the standalone app.

`vercel.json` already rewrites unknown paths to `index.html`.

## Data

`scripts/build-data.py` compiles the billed grid into `src/data/events.json`. Rebuild with `python3 scripts/build-data.py` after edits.
