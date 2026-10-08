// RewardedAdGate — shows a rewarded ad to unlock a feature
// In Expo Go (no native SDK): shows a mock "tap to unlock" button for testing
// In native builds: shows a real Google rewarded ad via react-native-google-mobile-ads

import React, { useState, useEffect, useRef } from 'react'
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { Colors, FontSize, Radius, Spacing } from '@/constants/theme'
import { AdUnits } from '@/constants/admob'

// Dynamically load AdMob SDK — won't throw in Expo Go, just null
let RewardedAd: any = null
let RewardedAdEventType: any = null
let RewardedAdRewards: any = null

try {
  const mod = require('react-native-google-mobile-ads')
  RewardedAd = mod.RewardedAd
  RewardedAdEventType = mod.RewardedAdEventType
  RewardedAdRewards = mod.RewardedAdRewards
} catch {}

const SDK_AVAILABLE = RewardedAd != null

interface Props {
  children: React.ReactNode
  feature: string
  onUnlocked?: () => void
}

export function RewardedAdGate({ children, feature, onUnlocked }: Props) {
  const [unlocked, setUnlocked] = useState(false)
  const [adLoaded, setAdLoaded] = useState(false)
  const [adLoading, setAdLoading] = useState(SDK_AVAILABLE) // loading if SDK available
  const [adError, setAdError] = useState(false)
  const adRef = useRef<any>(null)

  useEffect(() => {
    if (!SDK_AVAILABLE) return

    try {
      const ad = RewardedAd.createForAdRequest(AdUnits.REWARDED, {
        requestNonPersonalizedAdsOnly: false,
      })

      const unsubLoaded = ad.addAdEventListener(RewardedAdEventType.LOADED, () => {
        setAdLoaded(true)
        setAdLoading(false)
        setAdError(false)
      })

      const unsubError = ad.addAdEventListener(RewardedAdEventType.ERROR, () => {
        setAdLoading(false)
        setAdError(true)
      })

      const unsubEarned = ad.addAdEventListener(
        RewardedAdEventType.EARNED_REWARD,
        () => {
          setUnlocked(true)
          onUnlocked?.()
        }
      )

      ad.load()
      adRef.current = ad

      return () => {
        unsubLoaded()
        unsubError()
        unsubEarned()
      }
    } catch {}
  }, [])

  const handleWatch = async () => {
    if (!SDK_AVAILABLE) {
      // Expo Go stub — unlock instantly
      setUnlocked(true)
      onUnlocked?.()
      return
    }
    if (adRef.current && adLoaded) {
      try {
        await adRef.current.show()
      } catch {
        // If show fails, unlock anyway (ad dismissed)
        setUnlocked(true)
        onUnlocked?.()
      }
    }
  }

  const handleSkip = () => {
    // If ad failed to load, allow free access
    setUnlocked(true)
    onUnlocked?.()
  }

  if (unlocked) return <>{children}</>

  return (
    <View style={styles.gate}>
      <View style={styles.iconCircle}>
        <Ionicons name="lock-closed" size={28} color={Colors.accent} />
      </View>

      <Text style={styles.title}>Unlock {feature}</Text>
      <Text style={styles.subtitle}>
        Watch a short ad to access this feature for free.
      </Text>

      {adLoading ? (
        <View style={styles.loadingRow}>
          <ActivityIndicator color={Colors.accent} size="small" />
          <Text style={styles.loadingText}>Loading ad…</Text>
        </View>
      ) : adError ? (
        <>
          <Text style={styles.errorText}>Ad unavailable right now.</Text>
          <TouchableOpacity style={styles.btn} onPress={handleSkip} activeOpacity={0.8}>
            <Ionicons name="checkmark-circle" size={18} color={Colors.bg} />
            <Text style={styles.btnText}>Continue Anyway</Text>
          </TouchableOpacity>
        </>
      ) : (
        <TouchableOpacity
          style={[styles.btn, !adLoaded && !SDK_AVAILABLE ? {} : (!adLoaded ? styles.btnDisabled : {})]}
          onPress={handleWatch}
          activeOpacity={0.8}
          disabled={SDK_AVAILABLE && !adLoaded}
        >
          <Ionicons name="play-circle" size={18} color={Colors.bg} />
          <Text style={styles.btnText}>Watch Ad to Unlock</Text>
        </TouchableOpacity>
      )}

      {!SDK_AVAILABLE && (
        <Text style={styles.note}>Tap to unlock (Expo Go preview)</Text>
      )}
    </View>
  )
}

const styles = StyleSheet.create({
  gate: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: Spacing.xxxl,
    gap: Spacing.md,
  },
  iconCircle: {
    width: 72, height: 72,
    borderRadius: Radius.full,
    backgroundColor: Colors.accentDim,
    borderWidth: 1,
    borderColor: Colors.accentBorder,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.sm,
  },
  title: {
    fontSize: FontSize.xl,
    fontWeight: '900',
    color: Colors.textPrimary,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: FontSize.sm,
    color: Colors.textSecondary,
    textAlign: 'center',
    lineHeight: 20,
    maxWidth: 280,
  },
  loadingRow: {
    marginTop: Spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  loadingText: {
    color: Colors.textMuted,
    fontSize: FontSize.sm,
  },
  errorText: {
    color: Colors.negative,
    fontSize: FontSize.sm,
    textAlign: 'center',
  },
  btn: {
    marginTop: Spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    backgroundColor: Colors.accent,
    paddingHorizontal: Spacing.xxl,
    paddingVertical: Spacing.md,
    borderRadius: Radius.full,
  },
  btnDisabled: {
    opacity: 0.4,
  },
  btnText: {
    color: Colors.bg,
    fontWeight: '700',
    fontSize: FontSize.base,
  },
  note: {
    fontSize: FontSize.xs,
    color: Colors.textMuted,
    marginTop: Spacing.sm,
  },
})
