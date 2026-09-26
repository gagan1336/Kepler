# ANTIGRAVITY — Supabase RLS Audit

> Last audited: 2026-09-26  
> Framework: Supabase Row Level Security (RLS)

## Overview

The ANTIGRAVITY backend uses SQLAlchemy + PostgreSQL as its primary database, NOT the Supabase PostgREST API directly. This means:

- **Primary data access is through the FastAPI backend**, which enforces authentication and authorization at the application layer
- **Supabase is used for Authentication only** (JWT issuing, Google OAuth)
- Direct Supabase PostgREST API access to the database is NOT used by the mobile app

**This significantly reduces RLS risk** — the mobile app authenticates with Supabase, gets a JWT, and then calls the FastAPI backend which makes its own PostgreSQL queries.

## Database Access Architecture

`
Mobile App
    │
    ├── Supabase Auth (JWT only)
    │       └── Issues JWT tokens
    │
    └── FastAPI Backend (all data access)
            └── PostgreSQL via SQLAlchemy
                    └── Application-layer auth/authz
`

## Tables Accessed Via FastAPI Backend

| Table | Purpose | RLS Needed? | Notes |
|---|---|---|---|
| users | User accounts | N/A (backend-only) | Backend enforces ownership |
| subscriptions | Subscription records | N/A (backend-only) | user_id FK enforced |
| daily_digests | Daily digest content | N/A (backend-only) | No user-specific data |
| breakout_watchlist | Breakout alerts | N/A (backend-only) | No user-specific data |
| sector_reports | Sector reports | N/A (backend-only) | No user-specific data |
| content_log | View tracking | N/A (backend-only) | user_id logged |
| ipo_briefs | IPO information | N/A (backend-only) | No user-specific data |
| deep_dives | Research reports | N/A (backend-only) | Plan-gated at API layer |
| market_updates | Market news | N/A (backend-only) | No user-specific data |
| stock_signals | Chart signals | N/A (backend-only) | Plan-gated at API layer |
| crypto_payments | Crypto payment records | N/A (backend-only) | user_id ownership checked |

## Supabase Auth Tables (Supabase-managed)

Supabase manages its own auth schema (uth.*). These tables are managed by Supabase and have built-in RLS.

| Table | RLS | Status |
|---|---|---|
| auth.users | Yes (Supabase-managed) | ✅ Managed by Supabase |
| auth.sessions | Yes (Supabase-managed) | ✅ Managed by Supabase |
| auth.identities | Yes (Supabase-managed) | ✅ Managed by Supabase |

## Recommendations

### If You Ever Expose Tables via Supabase PostgREST

If you ever add a Supabase client to the mobile app that directly queries the database (NOT recommended), you MUST:

1. Enable RLS on every exposed table
2. Create policies that scope reads to uth.uid():
   `sql
   -- Example for users table
   CREATE POLICY "Users can read own data" ON users
     FOR SELECT USING (auth.uid()::text = supabase_id);
   `
3. Never expose admin or aggregate data without admin role checks
4. Test cross-user access is blocked

### Current Security Model: PASS

Since the backend handles all database access and enforces:
- JWT verification on every request
- User ownership checks (e.g., user_id == current_user.id)
- Plan-level gates (equire_plan())

The current architecture is acceptable for pre-launch. RLS at the Supabase layer is an additional defense-in-depth measure to add before scale.

## Action Items

- [ ] Verify no Supabase client is used in mobile app for direct database access (confirmed: mobile uses only Auth)
- [ ] If adding Supabase Realtime, enable RLS before enabling Realtime on any table
- [ ] Add supabase_service_role_key to **NEVER** list — it must never appear anywhere
