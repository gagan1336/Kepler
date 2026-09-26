# ANTIGRAVITY — Incident Response Plan

> Last updated: 2026-09-26

## Severity Levels

| Level | Description | Response Time |
|---|---|---|
| P0 - CRITICAL | Active breach, credential leak, payment fraud | Immediate (<1 hour) |
| P1 - HIGH | Unauthorized access, data exposure, service outage | <4 hours |
| P2 - MEDIUM | Unusual access patterns, rate limit abuse, failed auth spike | <24 hours |
| P3 - LOW | Single account issue, minor misconfiguration | <72 hours |

---

## Incident: API Key / Secret Leaked

### Indicators
- Secret found in public GitHub repository
- Secret found in logs
- Unusual API usage spike (Gemini, Razorpay, etc.)
- Third-party notification

### Response Steps
1. **Immediate (P0):** Revoke the leaked key on the provider's dashboard
2. Generate a replacement key
3. Update ackend/.env and all deployment environment variables
4. Restart backend service
5. Review provider logs for unauthorized usage during exposure window
6. Check git history: git log --all -p -- .env to confirm what was exposed
7. Document what was exposed and for how long
8. If financial impact (Gemini, Razorpay): contact provider support

### Specific Key Procedures
- **GEMINI_API_KEY**: See SECURITY/SECRET_ROTATION.md Section 1
- **RAZORPAY_KEY_SECRET**: See SECURITY/SECRET_ROTATION.md Section 4
- **SUPABASE_JWT_SECRET**: See SECURITY/SECRET_ROTATION.md Section 2

---

## Incident: Supabase JWT Secret Compromised

### Indicators
- Forged JWTs observed
- Unusual account activity for users who didn't log in
- Secret found in logs or public repository

### Response Steps
1. **IMMEDIATELY** go to Supabase Dashboard → Settings → API → Reset JWT Secret
2. This invalidates ALL active sessions — all users will be logged out
3. Update SUPABASE_JWT_SECRET in backend .env and deployment
4. Restart backend
5. Review auth logs in Supabase for suspicious sessions before rotation
6. Post status update informing users they must re-login
7. Review what data the forged tokens may have accessed

---

## Incident: User Account Compromised

### Indicators
- User reports unauthorized access
- Unusual activity from user account
- Login from unusual geographic location

### Response Steps
1. Go to Supabase Dashboard → Authentication → Users → Find user
2. Click "Ban User" to immediately revoke all sessions
3. Change users.is_active = False in the database
4. Email the user at their registered address
5. Review ContentLog for unauthorized views
6. Review Subscription for unauthorized plan changes
7. Re-enable account after user verifies identity and changes password
8. Document the incident

---

## Incident: Database Compromised / Unauthorized Access

### Indicators
- Unusual database queries in logs
- Data appearing on external sites
- Database credential leak

### Response Steps
1. **Immediately** revoke database credentials on hosting provider
2. Rotate DATABASE_URL (see SECRET_ROTATION.md)
3. **Preserve logs** before making changes — logs are evidence
4. Assess what data was accessed (users table = PII, subscriptions = financial)
5. If user PII was accessed: prepare for breach notification (DPDP/GDPR obligations)
6. Restore from known-good backup if data was modified
7. Audit all database queries in the exposure window
8. Change all related passwords (Supabase, Railway/Render/hosting)

---

## Incident: Payment Fraud / Webhook Bypass

### Indicators
- Users upgraded to paid plans without corresponding Razorpay payment
- Unusual plan upgrades
- Webhook signature verification failures

### Response Steps
1. Check /payment/verify-subscription logs for signature mismatches
2. Check /webhooks/razorpay logs for invalid signatures
3. Review subscriptions table for anomalous activations
4. For each suspicious upgrade: verify on Razorpay dashboard
5. Downgrade fraudulent accounts: set users.plan = "free", mark subscription as raudulent
6. Block suspicious IPs
7. Review HMAC verification code to ensure it wasn't bypassed

---

## Incident: AI Cost Abuse (Gemini)

### Indicators
- Sudden spike in Gemini API costs
- Excessive calls to AI endpoints
- Rate limit violations on AI endpoints

### Response Steps
1. Check rate limiting logs for who is hitting AI endpoints
2. Temporarily disable AI endpoints if costs are critical: set endpoint to return 503
3. Identify the abusive account(s) and suspend them
4. Contact Google to dispute fraudulent charges if applicable
5. Implement stricter per-user daily quotas
6. Consider requiring CAPTCHA for AI endpoints

---

## Incident: Mobile App Compromise (APK Extraction)

### Indicators
- Backend receiving requests with valid JWTs but from non-app clients
- Unusual usage patterns suggesting automation
- Bulk data extraction attempts

### Response Steps
1. Verify that no server secrets were in the APK (check mobile bundle)
2. If Supabase anon key was extracted: this is acceptable (anon key is public-safe with RLS)
3. Implement additional request validation (User-Agent, Expo-specific headers)
4. Rate limit aggressive clients
5. For true automation abuse: implement CAPTCHA challenge

---

## Contact Escalation

| Scenario | Contact |
|---|---|
| Gemini API abuse | Google Cloud Console → Billing |
| Razorpay fraud | support@razorpay.com |
| Supabase breach | security@supabase.io |
| Railway compromise | support@railway.app |
| Telegram bot token leak | @BotFather on Telegram |
