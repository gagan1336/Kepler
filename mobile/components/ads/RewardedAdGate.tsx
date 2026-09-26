// RewardedAdGate — stub for Expo Go development
// Real rewarded ads load in the production native build
import React, { useState } from 'react'
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { Colors, FontSize, Radius, Spacing } from '@/constants/theme'

interface Props {
  children: React.ReactNode
  feature: string
  onUnlocked?: () => void
}

export function RewardedAdGate({ children, feature, onUnlocked }: Props) {
  const [unlocked, setUnlocked] = useState(false)

  const unlock = () => {
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
      {/* In Expo Go: tap to unlock instantly for testing */}
      <TouchableOpacity style={styles.btn} onPress={unlock} activeOpacity={0.8}>
        <Ionicons name="play-circle" size={18} color={Colors.bg} />
        <Text style={styles.btnText}>Watch Ad to Unlock</Text>
      </TouchableOpacity>
      <Text style={styles.note}>Tap to unlock (Expo Go preview)</Text>
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
    fontFamily: 'Inter_900Black',
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
