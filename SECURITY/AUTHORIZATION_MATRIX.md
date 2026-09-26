# ANTIGRAVITY — Authorization Matrix

> Last updated: 2026-09-26

## Role Definitions

| Role | Description | How Assigned |
|---|---|---|
| anonymous | Unauthenticated request | No JWT |
| authenticated | Valid Supabase JWT | Any plan, is_active=True |
| free | Free-tier user | user.plan == "free" |
| pro | Pro-tier user | user.plan == "pro" |
| elite | Elite-tier user | user.plan == "elite" |
| admin | Admin user | user.email == settings.admin_email |

## Role Hierarchy

`
admin
  ↳ elite (admin can do everything elite can)
    ↳ pro
      ↳ free/authenticated
        ↳ anonymous
`

## Plan Check Implementation

All plan checks are server-side via equire_plan() in uth.py:

`python
plan_levels = {"free": 0, "pro": 1, "elite": 2}
# Raises 403 if user's plan level < required level
`

Plan is loaded from the DATABASE (not client), so it cannot be spoofed.

## Endpoint Authorization Matrix

| Endpoint | Anonymous | Free | Pro | Elite | Admin |
|---|---|---|---|---|---|
| GET /health | ✅ | ✅ | ✅ | ✅ | ✅ |
| GET /digest/today | 3 items | 3 items | ✅ | ✅ | ✅ |
| GET /digest/history | ❌ | ❌ | ✅ | ✅ | ✅ |
| GET /breakout/today | 5 items | 5 items | ✅ | ✅ | ✅ |
| GET /deepdive/list | ❌ | ❌ | ✅ | ✅ | ✅ |
| GET /deepdive/{id} | ❌ | ❌ | ❌ | ✅ | ✅ |
| GET /screener/quality | ❌ | ❌ | ✅ | ✅ | ✅ |
| GET /ml/radar | ❌ | ❌ | ✅ | ✅ | ✅ |
| POST /ml/retrain | ❌ | ❌ | ❌ | ❌ | ✅ |
| POST /signals/upload | ❌ | ❌ | ❌ | ❌ | ✅ |
| DELETE /signals/{id} | ❌ | ❌ | ❌ | ❌ | ✅ |
| POST /admin/* | ❌ | ❌ | ❌ | ❌ | ✅ |

## Fields Users CANNOT Modify

The following fields are NEVER accepted from client requests:

| Field | Reason |
|---|---|
| user.plan | Must be set only via verified payment webhooks |
| user.is_active | Must be set only server-side |
| user.supabase_id | Set from verified JWT, never from client body |
| user.role | No role field; plan is the authorization mechanism |
| subscription.status | Set only by webhook handlers with HMAC verification |
| crypto_payment.status | Set only by webhook handler with HMAC verification |

## BOLA (Broken Object Level Authorization) Tests

| Object Type | Ownership Check | Verified? |
|---|---|---|
| CryptoPayment | CryptoPayment.user_id == current_user.id | ✅ YES |
| Subscription | Subscription.user_id == current_user.id | ✅ YES |
| ContentLog | ContentLog.user_id = current_user.id | ✅ YES (write only, no read) |
| StockSignal | No user ownership — shared content | N/A |
| DeepDive | No user ownership — shared content | N/A |
| DailyDigest | No user ownership — shared content | N/A |

## Known Authorization Gaps

1. **/admin/deepdive** — requires equire_plan("elite") but NOT _is_admin(). Any Elite user can create deep dives. Consider whether this is intentional.
2. **/admin/trigger/*** — same issue. Any Elite user can trigger news pipeline, breakout scan, Telegram publish.
3. **/api/v1/swing/picks** — PUBLIC endpoint. Returns AI-generated thesis data. Consider AUTH requirement.
4. **/api/v1/swing/hermes-status** — PUBLIC endpoint. Returns internal ML weight data.
