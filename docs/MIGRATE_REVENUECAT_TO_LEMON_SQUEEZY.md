# Billing: Lemon Squeezy only (Google Play pay removed)

Laro Pro is sold **only** on the web through **Lemon Squeezy** (`laro.food → Settings → Unlock Laro Pro`). The Android app does **not** use Google Play billing or RevenueCat purchases — sign in and subscribe on the web; Pro syncs to the app via your Laro account.

## Production setup

1. Create LS products and webhook (see [`LEMON_SQUEEZY_BILLING.md`](./LEMON_SQUEEZY_BILLING.md)).
2. Set `LARO_BILLING_PROVIDER=lemonsqueezy` and all `LEMONSQUEEZY_*` on the server.
3. Deploy frontend **without** `REACT_APP_REVENUECAT_WEB_API_KEY`.
4. **Android:** remove/hide any in-app paywall; deep-link or instruct users to `https://laro.food/settings`.
5. Verify checkout → webhook → `/subscriptions/status` shows Pro.

## Retiring RevenueCat / Play (optional cleanup)

Legacy `POST /api/v1/subscriptions/webhook/revenuecat` and `REVENUECAT_*` env vars are **no longer required** for new sales. After `GET /admin/subscriptions/billing-overview` shows no active `source=revenuecat` subs you care about:

1. Unset `REVENUECAT_WEBHOOK_AUTH` on production.
2. Remove RevenueCat SDK / Play billing products from the Android app release.
3. Archive or read-only the RevenueCat project.

## Checklist

- [ ] LS webhook receiving events (200 OK)
- [ ] Production `LEMONSQUEEZY_*` set
- [ ] Android build has no Google Play subscription SKUs / RC paywall
- [ ] Web + Android QA: same account gets Pro after web checkout
