// KEPLER -- AdMob Unit IDs
// App ID is real. Unit IDs below are Google test IDs.
// To go live: create ad units in AdMob console → replace PROD strings → set IS_TEST = false

const IS_TEST = true   // ← flip to false + fill PROD IDs before release

// Your AdMob App ID (Android)
export const ADMOB_APP_ID = 'ca-app-pub-2843056453636534~7776390491'

export const AdUnits = {
  // ── Rewarded (unlock Screener / DeepDive full read) ──────────────────────
  REWARDED: IS_TEST
    ? 'ca-app-pub-3940256099942544/5224354917'           // Google test rewarded
    : 'ca-app-pub-2843056453636534/XXXXXXXXXX',           // TODO: replace with your unit ID

  // ── Interstitial (between screener runs) ─────────────────────────────────
  INTERSTITIAL: IS_TEST
    ? 'ca-app-pub-3940256099942544/1033173712'           // Google test interstitial
    : 'ca-app-pub-2843056453636534/XXXXXXXXXX',           // TODO: replace with your unit ID

  // ── Rewarded Interstitial (mid-session, no forced watch) ─────────────────
  REWARDED_INTERSTITIAL: IS_TEST
    ? 'ca-app-pub-3940256099942544/5354046379'           // Google test rewarded interstitial
    : 'ca-app-pub-2843056453636534/XXXXXXXXXX',           // TODO: replace with your unit ID
}
