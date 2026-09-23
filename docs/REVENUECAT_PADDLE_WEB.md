# Legacy: RevenueCat + Paddle / Web Billing

**New Laro Pro web subscriptions use Lemon Squeezy.** See [`LEMON_SQUEEZY_BILLING.md`](./LEMON_SQUEEZY_BILLING.md).

This document is kept for **grandfathered** subscribers and admin tooling.

- Keep `REVENUECAT_WEBHOOK_AUTH` and `POST /api/v1/subscriptions/webhook/revenuecat` until legacy subs expire.
- Do **not** set `REACT_APP_REVENUECAT_WEB_API_KEY` on new deployments (web checkout no longer uses `purchases-js`).

Historical RC + Paddle setup: [RevenueCat Paddle docs](https://www.revenuecat.com/docs/web/integrations/paddle).
