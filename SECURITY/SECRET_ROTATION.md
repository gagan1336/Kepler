# ANTIGRAVITY — Secret Rotation Procedures

> **CRITICAL:** Treat each credential as potentially compromised. Rotate immediately if exposed.  
> Status: Review each credential below after any security incident.

---

## How to Rotate Each Credential

### 1. Gemini API Key
**Current Key Location:** ackend/.env → GEMINI_API_KEY

**Steps:**
1. Go to https://aistudio.google.com/app/apikey
2. Click "Create API Key"
3. Copy the new key
4. Update ackend/.env: GEMINI_API_KEY=<new_key>
5. On Railway/Render/deployment: update the environment variable
6. Restart the backend service
7. Delete the old key from Google AI Studio
8. Verify backend starts and AI features work

**⚠️ MUST ROTATE — current key AIzaSyAVsduo2aX3jY0kS2a_7x3ZnfbDDJqA6Ns is in source code**

---

### 2. Supabase JWT Secret
**Current Key Location:** ackend/.env → SUPABASE_JWT_SECRET

**Steps:**
1. Go to Supabase Dashboard → Project → Settings → API
2. Scroll to "JWT Settings"
3. Click "Generate a new secret"
4. Copy the new JWT secret
5. **IMPORTANT:** This invalidates ALL currently active sessions (users will be logged out)
6. Update ackend/.env: SUPABASE_JWT_SECRET=<new_secret>
7. Update deployment environment variables
8. Restart backend
9. Inform users that re-login is required

**⚠️ MUST ROTATE — current secret is in source code**

**Impact:** All users will need to log in again after rotation.

---

### 3. Supabase Anon Key
**Current Key Location:** ackend/.env → SUPABASE_ANON_KEY, mobile/.env.local → EXPO_PUBLIC_SUPABASE_ANON_KEY

**Note:** The anon key is designed to be public (used in client apps). It is safe to expose. However, if RLS is misconfigured, rotation may be needed.

**Steps:**
1. Go to Supabase Dashboard → Project → Settings → API
2. Scroll to "Project API keys"
3. Click "Rotate anon key" (note: this is a rare operation)
4. Update all client-side code and mobile app builds
5. Submit new app build to Play Store

---

### 4. Razorpay Key Secret
**Current Key Location:** ackend/.env → RAZORPAY_KEY_SECRET

**Steps:**
1. Go to https://dashboard.razorpay.com/app/keys
2. Generate new API keys
3. Update ackend/.env
4. Update deployment environment variables  
5. Restart backend
6. The public Key ID (RAZORPAY_KEY_ID) may also need updating in mobile app

---

### 5. Razorpay Webhook Secret
**Current Key Location:** ackend/.env → RAZORPAY_WEBHOOK_SECRET

**Steps:**
1. Go to Razorpay Dashboard → Webhooks
2. Edit the webhook → Regenerate secret
3. Update ackend/.env
4. Restart backend immediately (webhook verification will fail until updated)

---

### 6. NOWPayments API Key
**Current Key Location:** ackend/.env → NOWPAYMENTS_API_KEY

**Steps:**
1. Log in to https://nowpayments.io
2. Go to Store Settings → API Keys
3. Create a new key
4. Update ackend/.env
5. Restart backend

---

### 7. NOWPayments IPN Secret
**Current Key Location:** ackend/.env → NOWPAYMENTS_IPN_SECRET

**Steps:**
1. Log in to NOWPayments → IPN Settings
2. Change the IPN secret
3. Update ackend/.env
4. Restart backend immediately

---

### 8. Telegram Bot Token
**Current Key Location:** ackend/.env → TELEGRAM_BOT_TOKEN

**Steps:**
1. Open Telegram → Message @BotFather
2. Send /revoke → select your bot
3. BotFather issues a new token
4. Update ackend/.env
5. Restart backend and scheduler

---

### 9. Resend API Key
**Current Key Location:** ackend/.env → RESEND_API_KEY

**Steps:**
1. Go to https://resend.com/api-keys
2. Create a new API key with the same permissions
3. Update ackend/.env
4. Restart backend
5. Delete the old key

---

### 10. Google OAuth Client Secret
**Current Key Location:** ackend/.env → GOOGLE_CLIENT_SECRET

**Steps:**
1. Go to https://console.cloud.google.com/apis/credentials
2. Click on your OAuth 2.0 client
3. Click "Reset Secret"
4. Update ackend/.env
5. Restart backend

---

### 11. Database Password / DATABASE_URL
**Current Key Location:** ackend/.env → DATABASE_URL

**Steps:**
1. Go to your hosting provider (Railway/Render/Supabase)
2. Reset the database password
3. Update DATABASE_URL in ackend/.env with the new password
4. Update deployment environment variables
5. Restart backend (connection pool will be re-established)

**⚠️ High impact — all database connections will drop during restart**

---

## Post-Rotation Checklist

After rotating any credential:
- [ ] Update ackend/.env locally
- [ ] Update deployment environment variables (Railway/Render/etc.)
- [ ] Restart the backend service
- [ ] Test the affected functionality works
- [ ] Check logs for errors
- [ ] Revoke/delete the old credential
- [ ] Document the rotation date in this file

---

## Rotation Schedule

| Credential | Last Rotated | Recommended Frequency | Next Due |
|---|---|---|---|
| GEMINI_API_KEY | NEVER (was in source code) | **IMMEDIATELY** | NOW |
| SUPABASE_JWT_SECRET | NEVER (was in source code) | **IMMEDIATELY** | NOW |
| RAZORPAY_KEY_SECRET | Unknown | Annually | 2027-01-01 |
| TELEGRAM_BOT_TOKEN | Unknown | Annually | 2027-01-01 |
| DATABASE PASSWORD | Unknown | Quarterly | 2027-01-01 |
| RESEND_API_KEY | Unknown | Annually | 2027-01-01 |
