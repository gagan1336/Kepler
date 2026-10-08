// InterstitialService — singleton to preload and show interstitial ads
// Works only in native builds (not Expo Go). Silently no-ops in Expo Go.

import { AdUnits } from '@/constants/admob'

let InterstitialAd: any = null
let AdEventType: any = null
let loaded = false
let currentAd: any = null

// Dynamically require the SDK — won't throw in Expo Go, just returns null
try {
  const mod = require('react-native-google-mobile-ads')
  InterstitialAd = mod.InterstitialAd
  AdEventType = mod.AdEventType
} catch {}

function createAndLoad() {
  if (!InterstitialAd) return
  try {
    const ad = InterstitialAd.createForAdRequest(AdUnits.INTERSTITIAL, {
      requestNonPersonalizedAdsOnly: false,
    })
    ad.addAdEventListener(AdEventType.LOADED, () => {
      loaded = true
      currentAd = ad
    })
    ad.addAdEventListener(AdEventType.ERROR, () => {
      loaded = false
      // Retry after 30s on error
      setTimeout(createAndLoad, 30_000)
    })
    ad.addAdEventListener(AdEventType.CLOSED, () => {
      loaded = false
      currentAd = null
      // Preload next ad immediately after close
      setTimeout(createAndLoad, 1000)
    })
    ad.load()
  } catch {}
}

/** Call once at app start to preload the first interstitial */
export function preloadInterstitial() {
  createAndLoad()
}

/**
 * Show an interstitial if one is ready.
 * Returns true if ad was shown, false if not ready (e.g. Expo Go or not loaded yet).
 */
export async function showInterstitial(): Promise<boolean> {
  if (!loaded || !currentAd) return false
  try {
    await currentAd.show()
    return true
  } catch {
    return false
  }
}

/** Whether an interstitial is ready to show */
export function isInterstitialReady(): boolean {
  return loaded && currentAd != null
}
