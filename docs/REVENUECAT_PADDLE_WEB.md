# Laro Pro — RevenueCat + Paddle (web)

Laro keeps **RevenueCat** as the subscription hub (entitlement **Laro Pro**, offering `default`, webhooks to Laro backend). **Paddle Billing** is the recommended **merchant of record** for web checkout via RevenueCat Web (tax, compliance, customer emails, Paddle customer portal).

The web app uses **`@revenuecat/purchases-js`** with the **Web Billing public key** (`rcb_…`). You do not embed Paddle.js directly — RevenueCat launches Paddle checkout when the RC project is linked to Paddle.

## Why RC + Paddle (vs RC Billing + Stripe)

| | RC Billing (Stripe) | Paddle via RC |
|---|---------------------|----------------|
| Merchant of record | You | Paddle |
| VAT / global tax | Your responsibility | Paddle |
| Customer portal | RevenueCat / Stripe | Paddle (via RC `managementURL`) |
| Laro backend webhook | RevenueCat → `/subscriptions/webhook/revenuecat` | Same |

## RevenueCat dashboard

1. **Paddle**
   - Activate **Paddle Billing** (not Classic) in Paddle.
   - Create subscription **products/prices** (weekly + monthly, GBP).
   - Create a **Paddle API key** with permissions needed for RC import (see [RC Paddle docs](https://www.revenuecat.com/docs/web/integrations/paddle)).

2. **RevenueCat project** ([Laro](https://app.revenuecat.com/projects/7e4715d3))
   - **Web** → add **Paddle** configuration → paste Paddle API key.
   - **Import products** from Paddle into the project (map to **Laro Pro** entitlement).
   - **Offering `default`**: packages `$rc_weekly` / `$rc_monthly` attach **Paddle** web products (web-only; Play products detached if using web-only policy).
   - Copy the **Web Billing public API key** (`rcb_…`) for the Paddle-backed web app.

3. **Webhooks (unchanged)**
   - RevenueCat → Integrations → Webhooks → `POST https://laro.food/api/v1/subscriptions/webhook/revenuecat`
   - Authorization: `REVENUECAT_WEBHOOK_AUTH` on the server.

## Laro deployment env

```bash
# Frontend (docker-entrypoint injects into built JS)
REACT_APP_REVENUECAT_WEB_API_KEY=rcb_…

# Backend
REVENUECAT_WEBHOOK_AUTH=Bearer …
LARO_BILLING_PROVIDER=revenuecat
LARO_RC_WEB_BILLING_ENGINE=paddle   # documentation / UI hint only
```

Optional: set `LARO_BILLING_PROVIDER=lemonsqueezy` only if using the direct Lemon Squeezy integration instead of RC.

## Web app behaviour

- Settings → **Laro Pro** → **Unlock Laro Pro** → RevenueCat paywall → Paddle checkout.
- **Manage billing** uses `CustomerInfo.managementURL` (Paddle portal when Paddle is the engine).
- Pro gating on Laro API uses Postgres (`subscription_*`) updated by the **RevenueCat webhook**, not Paddle webhooks directly.

## Sandbox

Use Paddle sandbox + RC sandbox/test keys; use a separate offering or products if needed. Point webhooks at staging with the same auth pattern.

## References

- [RevenueCat — Paddle Billing](https://www.revenuecat.com/docs/web/integrations/paddle)
- [RevenueCat Web overview](https://www.revenuecat.com/docs/web/overview)
- [Paddle × RevenueCat](https://www.paddle.com/revenuecat-integration)
