// KEPLER -- AdMob Unit IDs
// Real production IDs — IS_TEST = false

const IS_TEST = false

// Your AdMob App ID (Android)
export const ADMOB_APP_ID = 'ca-app-pub-2843056453636534~7776390491'

export const AdUnits = {
  // ── Rewarded (unlock Screener / DeepDive full read) ──────────────────────
  REWARDED: IS_TEST
    ? 'ca-app-pub-3940256099942544/5224354917'           // Google test rewarded
    : 'ca-app-pub-2843056453636534/4926865872',           // ✅ Production

  // ── Interstitial (between screener runs) ─────────────────────────────────
  INTERSTITIAL: IS_TEST
    ? 'ca-app-pub-3940256099942544/1033173712'           // Google test interstitial
    : 'ca-app-pub-2843056453636534/7687568617',           // ✅ Production

  // ── Rewarded Interstitial (mid-session) ──────────────────────────────────
  REWARDED_INTERSTITIAL: IS_TEST
    ? 'ca-app-pub-3940256099942544/5354046379'           // Google test rewarded interstitial
    : 'ca-app-pub-2843056453636534/1847995131',           // ✅ Production
}
