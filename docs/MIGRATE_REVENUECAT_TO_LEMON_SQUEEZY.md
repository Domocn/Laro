# Migrate RevenueCat web billing → Lemon Squeezy

Laro’s **new** Pro sales run on **Lemon Squeezy**. **RevenueCat** stays only as a **read-only legacy pipe** until existing Play / RC Web subscribers churn off.

There is no automatic “port subscription” from RC to LS — payment methods and contracts live in Google Play, Paddle/Stripe (old RC Web), or RC. Migration is **operational**: ship LS, stop new RC web sales, honor remaining time, then retire RC webhooks.

## Phase 1 — Ship Lemon Squeezy (production)

1. Create LS products (weekly + monthly) and webhook (see [`LEMON_SQUEEZY_BILLING.md`](./LEMON_SQUEEZY_BILLING.md)).
2. Set backend env on `laro.food`:
   - `LARO_BILLING_PROVIDER=lemonsqueezy`
   - All `LEMONSQUEEZY_*` variables
3. Deploy **frontend without** `REACT_APP_REVENUECAT_WEB_API_KEY` (web app no longer loads `purchases-js`).
4. Verify: test user → Settings → **Unlock Laro Pro** → LS checkout → webhook → Pro in `/subscriptions/status`.

## Phase 2 — Stop new RevenueCat web revenue

In [RevenueCat](https://app.revenuecat.com/projects/7e4715d3):

- Offering `default`: web packages should be **LS only in app code**; in RC you may **detach** RC Billing / Play products from packages (already done for Play on web-only policy) or leave products but **do not** expose new web checkout.
- Do not publish new Web Purchase Links / paywalls for RC Billing.
- Optional: pause or archive unused RC Billing (Stripe) products after LS is live.

**Android:** remove or hide in-app RC paywall; open `https://laro.food/settings` for Pro (same Laro user id).

## Phase 3 — Grandfather existing RC / Play subs

Keep until `subscription_expires` passes for everyone with `subscription_source = revenuecat`:

| Component | Action |
|-----------|--------|
| `POST /api/v1/subscriptions/webhook/revenuecat` | **Keep** + `REVENUECAT_WEBHOOK_AUTH` |
| Laro Postgres | Source of truth (`subscription_status`, `subscription_expires`) |
| Settings UI | Legacy manage hint for `source=revenuecat` |
| `REVENUECAT_SECRET_API_KEY` | Optional: admin “Sync RC” / promotional grants only |

Active legacy subs **keep Pro** until RC sends `EXPIRATION` or expiry date passes. No forced downgrade on deploy.

**Admin visibility:** `GET /api/v1/admin/subscriptions/billing-overview` (super_admin) — counts by `subscription_source`.

## Phase 4 — Communicate (recommended)

Email or in-app notice for `source=revenuecat` users with future `subscription_expires`:

- New billing is on **laro.food → Settings → Laro Pro** (Lemon Squeezy).
- When their current period ends, resubscribe on the web (or cancel).
- Play-billed users still manage via **Google Play → Subscriptions** until they cancel there.

## Phase 5 — Retire RevenueCat (later)

When **billing-overview** shows **zero** active `revenuecat` subs (or you accept cutting off stragglers):

1. Remove `REVENUECAT_WEBHOOK_AUTH` from production (webhook returns 503).
2. Remove `goog_` / Play SDK from Android if unused.
3. Archive RC project or leave read-only for history.
4. Remove `REVENUECAT_SECRET_API_KEY` if admin no longer syncs to RC.

## Rollback

If LS fails, temporarily set `LARO_BILLING_PROVIDER=disabled` and restore `REACT_APP_REVENUECAT_WEB_API_KEY` + prior frontend build — only if RC web products still exist on the offering.

## Checklist

- [ ] LS webhook receiving events (200 OK in LS dashboard)
- [ ] Production LS env vars set
- [ ] Frontend deployed without `rcb_` key
- [ ] RC webhook still authorized for legacy
- [ ] Android not selling new RC packages
- [ ] billing-overview reviewed for remaining `revenuecat` count
