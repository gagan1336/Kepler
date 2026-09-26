# ANTIGRAVITY — API Inventory
> Last updated: 2026-09-26 | Total endpoints: 55+

## Auth Required Legend
- PUBLIC = No auth required
- AUTH = Any valid Supabase JWT
- PRO = Pro or Elite plan
- ELITE = Elite plan only
- ADMIN = Admin email check (_is_admin())

## Core Endpoints

| METHOD | PATH | AUTH | RATE LIMIT | SENSITIVE? | ADMIN? | NOTES |
|--------|------|------|-----------|------------|--------|-------|
| GET | /health | PUBLIC | None | No | No | Safe public |
| GET | /auth/me | AUTH | None | Yes (user profile) | No | Creates local user on 1st call |
| GET | /public/stats | PUBLIC | 30/min | No | No | Aggregated counts only |
| GET | /public/sample | PUBLIC | 30/min | No | No | Sample content |

## Digest Endpoints
| METHOD | PATH | AUTH | RATE LIMIT | SENSITIVE? | NOTES |
|--------|------|------|-----------|------------|-------|
| GET | /digest/today | Optional | None | Partial | Free=3 items only |
| GET | /digest/history | PRO | None | No | 90 max |
| GET | /digest/correlations | AUTH | None | Partial | Free gets teaser |

## Content Endpoints
| METHOD | PATH | AUTH | RATE LIMIT | SENSITIVE? | NOTES |
|--------|------|------|-----------|------------|-------|
| GET | /breakout/today | Optional | None | Partial | Free=5 items |
| GET | /breakout/stats | PRO | None | No | Backtesting |
| GET | /sector/latest | Optional | None | No | Public |
| GET | /sector/history | PRO | None | No | 52 max |
| GET | /ipo/hub | PUBLIC | 20/min | No | 30-min cached |
| GET | /ipo/latest | PUBLIC | None | No | |
| GET | /ipo/{ipo_id} | PRO | None | No | |
| POST | /ipo/create | ELITE | None | No | Admin trigger |
| GET | /deepdive/list | PRO | None | No | Metadata only |
| GET | /deepdive/{dive_id} | ELITE | None | Yes (premium content) | Full content |
| POST | /deepdive/generate | ELITE | None | No | AI trigger |

## Market Data Endpoints
| METHOD | PATH | AUTH | RATE LIMIT | SENSITIVE? | NOTES |
|--------|------|------|-----------|------------|-------|
| GET | /markets/global | PUBLIC | 60/min | No | 5-min cached |
| GET | /news/live | Optional | 60/min | No | Public |
| GET | /news/live/categories | PUBLIC | None | No | |
| POST | /news/live/refresh | PRO | 5/min | No | Force refresh |
| GET | /news/market-updates | Optional | 30/min | No | |
| GET | /news/market-updates/types | PUBLIC | None | No | |
| GET | /picks/curated | PUBLIC | 10/min | No | DISCLAIMER: Not SEBI advice |
| GET | /sectors/live | PUBLIC | 30/min | No | |
| GET | /new-listings | Optional | 20/min | No | |

## Stock Endpoints
| METHOD | PATH | AUTH | RATE LIMIT | SENSITIVE? | NOTES |
|--------|------|------|-----------|------------|-------|
| GET | /stock/search | Optional | 30/min | No | Max q=30 chars |
| GET | /stock/{symbol} | AUTH | 20/min | No | Symbol validated |
| GET | /stock/{symbol}/live | AUTH | 60/min | No | |
| GET | /screener/presets | Optional | 30/min | No | |
| GET | /screener/preset/{name} | AUTH | 15/min | No | |
| POST | /screener/custom | PRO | 10/min | No | Max 50 results |
| GET | /screener/quality | PRO | 10/min | No | |
| GET | /screener/value | PRO | 10/min | No | |
| GET | /screener/dividend | PRO | 10/min | No | |
| GET | /screener/swing | Optional | 30/min | No | |
| GET | /screener/swing/{preset} | PRO | 10/min | No | |
| GET | /screener/fundamentals/{sym} | AUTH | 20/min | No | 24h cached |
| GET | /screener/cache-stats | ELITE | None | No | Internal cache info |

## Subscription/Payment Endpoints
| METHOD | PATH | AUTH | RATE LIMIT | SENSITIVE? | NOTES |
|--------|------|------|-----------|------------|-------|
| GET | /subscription/status | AUTH | None | Yes (billing info) | User-scoped |
| POST | /subscription/create | AUTH | None | Yes | HMAC verified |
| POST | /subscription/cancel | AUTH | None | Yes | |
| GET | /dashboard/stats | AUTH | None | Yes | User-specific |
| POST | /payment/verify-subscription | AUTH | None | CRITICAL | HMAC signature verified |
| POST | /webhooks/razorpay | PUBLIC | None | CRITICAL | Signature verified |
| POST | /crypto/create-payment | AUTH | None | Yes | |
| GET | /crypto/payment-status/{id} | AUTH | None | Yes | User_id ownership check ✅ |
| POST | /crypto/webhook | PUBLIC | None | CRITICAL | HMAC sha512 verified |

## Signals Endpoints
| METHOD | PATH | AUTH | RATE LIMIT | SENSITIVE? | NOTES |
|--------|------|------|-----------|------------|-------|
| POST | /signals/upload | ADMIN | None | Yes | File upload, validated |
| GET | /signals | AUTH | None | Partial | Plan-gated images |
| DELETE | /signals/{id} | ADMIN | None | No | Admin only |

## Admin Endpoints (require _is_admin() check)
| METHOD | PATH | AUTH | SENSITIVE? | NOTES |
|--------|------|------|------------|-------|
| POST | /admin/regenerate-correlations | AUTH+ADMIN | No | Admin only |
| POST | /admin/deepdive | ELITE+? | No | Missing _is_admin() check — any Elite can call |
| POST | /admin/trigger/news-pipeline | ELITE | No | Any Elite can call |
| POST | /admin/trigger/breakout-scan | ELITE | No | Any Elite can call |
| POST | /admin/trigger/telegram | ELITE | No | Any Elite can call |

## ML Endpoints
| METHOD | PATH | AUTH | RATE LIMIT | SENSITIVE? | NOTES |
|--------|------|------|-----------|------------|-------|
| GET | /ml/model-info | PUBLIC | None | Partial | Exposes model metadata |
| GET | /ml/radar | PRO | 6/min | No | |
| GET | /ml/score/{symbol} | PRO | 30/min | No | |
| POST | /ml/retrain | ADMIN | None | No | FIXED: was broken |

## Swing Trading Endpoints (v1)
| METHOD | PATH | AUTH | RATE LIMIT | NOTES |
|--------|------|------|-----------|-------|
| GET | /api/v1/swing/strategies | PUBLIC | 30/min | No auth required |
| GET | /api/v1/swing/backtest/{key} | PUBLIC | 20/min | No auth required |
| GET | /api/v1/swing/leaderboard | PUBLIC | 30/min | No auth required |
| POST | /api/v1/swing/backtest/run | ADMIN | 2/hour | FIXED: was broken |
| GET | /api/v1/picks/probability/{sym} | PUBLIC | 30/min | No auth — exposing analytics |
| GET | /api/v1/swing/best-strategy-stocks | AUTH | 10/min | |
| GET | /api/v1/picks | AUTH | 10/min | |
| GET | /api/v1/swing/presets | PUBLIC | 30/min | |
| GET | /api/v1/swing/preset/{name} | AUTH | 10/min | |
| GET | /api/v1/swing/picks | PUBLIC | 30/min | No auth required |
| POST | /api/v1/swing/scan/trigger | PRO | 2/hour | |
| GET | /api/v1/swing/paper-trades | AUTH | 20/min | |
| GET | /api/v1/swing/hermes-status | PUBLIC | 20/min | Exposes internal weights |
| GET | /notifications/register | AUTH | 10/min | |

## Security Observations

### ⚠️ MEDIUM RISK — Endpoints Needing Review
1. **/ml/model-info** — PUBLIC, exposes model training metadata, AUC scores. Consider AUTH requirement.
2. **/api/v1/picks/probability/{symbol}** — PUBLIC. Exposes technical analysis. Consider AUTH requirement.
3. **/api/v1/swing/picks** — PUBLIC. Returns AI-generated thesis. Consider AUTH requirement.
4. **/api/v1/swing/hermes-status** — PUBLIC. Exposes internal weights file. Restrict to ADMIN.
5. **/admin/deepdive** — Listed as admin endpoint but only checks equire_plan("elite"), not _is_admin(). Any Elite user can create deep dives.
6. **/admin/trigger/*** — Same as above. Any Elite user can trigger pipelines.

### Duplicate Routes (API9 — Improper Inventory)
- /screener/swing/{name} and /api/v1/swing/preset/{name} — same functionality, two paths
- /picks/curated and /api/v1/picks — overlapping pick functionality
