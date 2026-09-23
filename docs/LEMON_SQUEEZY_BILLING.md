# Laro Pro — Lemon Squeezy (primary billing)

All **new** Laro Pro subscriptions on the web use **Lemon Squeezy** (merchant of record). Laro’s backend is the source of truth for Pro access (`subscription_status`, webhooks).

**RevenueCat webhooks** remain enabled only for **grandfathered** subscribers who paid via Play / old RC Web Billing.

## Lemon Squeezy setup

1. Create a [Lemon Squeezy](https://app.lemonsqueezy.com) store and **subscription** products:
   - **Laro Pro Weekly** (GBP)
   - **Laro Pro Monthly** (GBP)
   - Optional: 2-week trial with card on file (configured on the product/offer in LS).

2. Note **Store ID** and each product **Variant ID** from the LS dashboard.

3. **Webhook** in Lemon Squeezy → Settings → Webhooks:
   - URL: `https://laro.food/api/v1/subscriptions/webhook/lemonsqueezy`
   - Signing secret → `LEMONSQUEEZY_WEBHOOK_SECRET` on the server
   - Events: `subscription_created`, `subscription_updated`, `subscription_cancelled`, `subscription_expired`, `subscription_payment_success`, `subscription_payment_failed`, `subscription_resumed`, etc.

## Laro server env

```bash
LARO_BILLING_PROVIDER=lemonsqueezy   # default in code

LEMONSQUEEZY_API_KEY=
LEMONSQUEEZY_STORE_ID=
LEMONSQUEEZY_VARIANT_ID_WEEKLY=
LEMONSQUEEZY_VARIANT_ID_MONTHLY=
LEMONSQUEEZY_WEBHOOK_SECRET=
LEMONSQUEEZY_CHECKOUT_REDIRECT_URL=https://laro.food/settings?pro=success
```

Checkout URLs are created server-side with `custom[user_id]` so Pro binds to the logged-in Laro account.

## Web app flow

1. User opens **Settings → Laro Pro → Unlock Laro Pro** (weekly/monthly if both variants configured).
2. `POST /api/v1/subscriptions/checkout` returns a Lemon Squeezy checkout URL.
3. After payment, LS webhook updates the user row; UI refresh shows **Pro**.
4. **Manage billing** → `GET /api/v1/subscriptions/customer-portal` (Paddle-style portal hosted by Lemon Squeezy).

## Android

Do not sell new subs in-app. Deep-link or instruct users to **laro.food → Settings → Laro Pro**. Pro syncs via the same Laro account.

## Legacy RevenueCat

Keep `REVENUECAT_WEBHOOK_AUTH` and `/subscriptions/webhook/revenuecat` until all legacy RC/Play subs have migrated or expired. Do not set `REACT_APP_REVENUECAT_WEB_API_KEY` for new deployments.

**Migration runbook:** [`MIGRATE_REVENUECAT_TO_LEMON_SQUEEZY.md`](./MIGRATE_REVENUECAT_TO_LEMON_SQUEEZY.md)
