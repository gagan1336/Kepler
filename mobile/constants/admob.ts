// KEPLER -- AdMob Unit IDs
// Using Google's official test IDs during development.
// Replace with your real AdMob IDs before publishing.

const IS_TEST = true   // flip to false and fill PROD IDs before release

export const AdUnits = {
  // ── Banner ─────────────────────────────────────────────────────────────────
  BANNER: IS_TEST
    ? 'ca-app-pub-3940256099942544/6300978111'            // Android test
    : 'ca-app-pub-XXXXXXXXXXXXXXXX/XXXXXXXXXX',            // TODO: replace

  // ── Rewarded (for unlocking Kepler/Swing/DeepDives) ───────────────────────
  REWARDED: IS_TEST
    ? 'ca-app-pub-3940256099942544/5224354917'            // Android test
    : 'ca-app-pub-XXXXXXXXXXXXXXXX/XXXXXXXXXX',            // TODO: replace

  // ── Interstitial (between screener loads) ─────────────────────────────────
  INTERSTITIAL: IS_TEST
    ? 'ca-app-pub-3940256099942544/1033173712'            // Android test
    : 'ca-app-pub-XXXXXXXXXXXXXXXX/XXXXXXXXXX',            // TODO: replace
}
