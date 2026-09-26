# ANTIGRAVITY — Threat Model

> Last updated: 2026-09-26
> Framework: OWASP API Security Top 10, OWASP MASVS

---

## 1. Assets

| Asset | Sensitivity | Location |
|---|---|---|
| User email addresses | HIGH | PostgreSQL users.email |
| Supabase JWTs (access tokens) | CRITICAL | Mobile: SecureStore / Backend: memory |
| Supabase JWT Secret | CRITICAL | Backend .env -> SUPABASE_JWT_SECRET |
| Gemini API Key | CRITICAL | Backend .env -> GEMINI_API_KEY |
| Razorpay Key Secret | CRITICAL | Backend .env -> RAZORPAY_KEY_SECRET |
| Razorpay Webhook Secret | CRITICAL | Backend .env -> RAZORPAY_WEBHOOK_SECRET |
| NOWPayments API Key + IPN Secret | CRITICAL | Backend .env |
| Telegram Bot Token | CRITICAL | Backend .env -> TELEGRAM_BOT_TOKEN |
| Google OAuth Client Secret | CRITICAL | Backend .env |
| Database URL with credentials | CRITICAL | Backend .env -> DATABASE_URL |
| User subscription/plan status | HIGH | PostgreSQL subscriptions, users.plan |
| Deep Dive research content (Elite) | HIGH | PostgreSQL deep_dives |
| Admin email | HIGH | Previously hardcoded in main.py (NOW in ADMIN_EMAIL env var) |
| Push notification tokens | MEDIUM | push_tokens.json (disk) |

---

## 2. Attacker Profiles

### 2.1 Anonymous Internet Attacker
- **Goal:** Access premium content without paying; DoS
- **Attack surface:** All public endpoints
- **Impact:** Content scraping; resource exhaustion
- **Mitigation:** Rate limiting (slowapi); CORS; no secrets in responses

### 2.2 Malicious Authenticated User
- **Goal:** Access Pro/Elite content on a Free account; escalate plan
- **Attack surface:** Every authenticated endpoint
- **Key vectors:** BOLA; mass assignment; payment replay
- **Impact:** Unauthorized premium content access; payment fraud
- **Mitigation:** Server-side plan enforcement; resource ownership DB checks

### 2.3 Automated Bot / Credential Stuffer
- **Goal:** Enumerate accounts; brute-force; scrape data
- **Mitigation:** Supabase Auth has built-in protection; rate limiting

### 2.4 Reverse Engineer (APK Analyst)
- **Goal:** Extract API keys, Supabase keys from APK
- **Attack surface:** Compiled APK; EXPO_PUBLIC_* variables
- **Impact:** Unauthorized API usage
- **Mitigation:** Only anon key + API URL in mobile bundle; backend enforces all auth/authz
- **Status:** ACCEPTABLE - only safe-to-expose values in mobile bundle

### 2.5 Attacker with Leaked Source Code
- **Goal:** Identify vulnerabilities; map all endpoints
- **FIXED:** Admin email was hardcoded (gagansolanki293@gmail.com) — moved to env var

### 2.6 AI Cost Abuser
- **Goal:** Hammer Gemini endpoints to run up costs
- **Attack surface:** /deepdive/generate, /admin/trigger/*
- **Impact:** Massive Gemini API bill
- **Mitigation:** Plan gating; rate limiting
- **CURRENT GAP:** No per-user daily AI quota tracking

---

## 3. OWASP API Security Top 10 Mapping

| Risk | Status | Notes |
|---|---|---|
| API1 BOLA | PARTIAL | CryptoPayment has user_id check; shared content endpoints are safe |
| API2 Broken Auth | PASS | Supabase JWT verification via JWKS + HS256 fallback |
| API3 Mass Assignment | PASS | Plan/role fields not user-settable via API body |
| API4 Resource Consumption | PARTIAL | Rate limiting present; no AI daily quota per user |
| API5 Broken Function Auth | FIXED | ml/retrain and backtest/run had broken is_admin checks (now fixed) |
| API6 Business Flow | PASS | Payment HMAC signatures verified |
| API7 SSRF | PASS | No user URL input; external requests use fixed URLs |
| API8 Security Misconfiguration | PARTIAL | Docs disabled in prod; security headers now added |
| API9 Improper Inventory | PARTIAL | Duplicate routes exist (/screener/swing + /api/v1/swing/preset) |
| API10 Unsafe Consumption | PARTIAL | External data validated; AI outputs not sanitized |

---

## 4. Vulnerabilities Found and Status

| ID | Severity | Description | Status |
|---|---|---|---|
| CRIT-001 | CRITICAL | Gemini API key in .env (rotate immediately) | ROTATE NOW |
| CRIT-002 | CRITICAL | Supabase JWT secret in .env (rotate immediately) | ROTATE NOW |
| CRIT-003 | HIGH | Admin email hardcoded in source code | FIXED in main.py |
| CRIT-004 | HIGH | ml/retrain used broken is_admin check (always False) | FIXED in main.py |
| CRIT-005 | HIGH | swing/backtest/run used broken is_admin check | FIXED in main.py |
| CRIT-006 | MEDIUM | frontend/.env.local committed to git history | Anon key only - low risk |
| CRIT-007 | HIGH | No per-user AI quota tracking | OPEN - future work |
| CRIT-008 | MEDIUM | push_tokens.json stored on disk unencrypted | OPEN - future work |
| CRIT-009 | MEDIUM | Internal exception details in error messages | PARTIALLY FIXED |
| NEW-001 | MEDIUM | update_type query param passed to ORM without allowlist | FIXED in main.py |
| NEW-002 | MEDIUM | Signal upload accepted arbitrary signal_type/plan strings | FIXED in main.py |
| NEW-003 | MEDIUM | CORS allowed all methods/headers with wildcard | FIXED in main.py |
| NEW-004 | LOW | No security response headers | FIXED in main.py |
| NEW-005 | LOW | Backend URL logged unconditionally in mobile (even production) | FIXED in api.ts |
| NEW-006 | MEDIUM | /admin/deepdive and /admin/trigger/* accessible by any Elite user | OPEN - by design? |
| NEW-007 | MEDIUM | /api/v1/swing/hermes-status PUBLIC - exposes internal ML weights | OPEN |
| NEW-008 | MEDIUM | /ml/model-info PUBLIC - exposes model training metadata | OPEN |

---

## 5. Trust Boundaries

```
[Internet] ─── [Rate Limiter] ─── [FastAPI] ─── [PostgreSQL]
                                      |
                               [Supabase Auth]
                                      |
                               [External APIs]
                                 (Gemini, Razorpay, Telegram, News)
```

- **Never trust:** Incoming JWT payload (always verify signature)
- **Never trust:** User-supplied file extensions (use content-type validation)
- **Never trust:** User-supplied strings in ORM filter comparisons (use allowlists)
- **Never expose:** Full stack traces to API clients in production
- **Never put:** Server secrets in mobile app bundle
