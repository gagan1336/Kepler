import { View, Text, TouchableOpacity, StyleSheet, Linking } from 'react-native'
import { LinearGradient } from 'expo-linear-gradient'
import { DigestItem } from '@/lib/api'
import { Colors, FontSize, Radius, Spacing } from '@/constants/theme'

interface Props {
  item: DigestItem
}

const SENTIMENT_CFG = {
  POSITIVE: { color: Colors.green, bg: Colors.greenDim, label: '▲ Positive' },
  NEGATIVE: { color: Colors.red, bg: Colors.redDim, label: '▼ Negative' },
  NEUTRAL:  { color: Colors.yellow, bg: Colors.yellowDim, label: '◆ Neutral' },
}

export function DigestCard({ item }: Props) {
  const cfg = SENTIMENT_CFG[item.sentiment] ?? SENTIMENT_CFG.NEUTRAL

  return (
    <TouchableOpacity
      style={[styles.card, { borderColor: `${cfg.color}22` }]}
      activeOpacity={0.85}
      onPress={() => item.url && Linking.openURL(item.url)}
    >
      <LinearGradient
        colors={['rgba(255,255,255,0.02)', 'transparent']}
        style={StyleSheet.absoluteFill}
      />

      {/* Category + Sentiment */}
      <View style={styles.row}>
        <View style={[styles.pill, { backgroundColor: 'rgba(255,255,255,0.05)' }]}>
          <Text style={styles.pillText}>{item.category}</Text>
        </View>
        <View style={[styles.pill, { backgroundColor: cfg.bg }]}>
          <Text style={[styles.pillText, { color: cfg.color }]}>{cfg.label}</Text>
        </View>
      </View>

      {/* Headline */}
      <Text style={styles.headline} numberOfLines={3}>{item.headline}</Text>

      {/* Summary */}
      {item.summary ? (
        <Text style={styles.summary} numberOfLines={4}>{item.summary}</Text>
      ) : null}

      {/* Source */}
      <View style={styles.footer}>
        <Text style={styles.source}>{item.source}</Text>
        {item.url ? <Text style={styles.readMore}>Read →</Text> : null}
      </View>
    </TouchableOpacity>
  )
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.lg,
    borderWidth: 1,
    padding: Spacing.lg,
    marginBottom: Spacing.md,
    overflow: 'hidden',
  },
  row: {
    flexDirection: 'row',
    gap: Spacing.sm,
    marginBottom: Spacing.md,
    flexWrap: 'wrap',
  },
  pill: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: 3,
    borderRadius: Radius.full,
  },
  pillText: {
    fontSize: FontSize.xs,
    fontFamily: 'Inter_600SemiBold',
    color: Colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  headline: {
    fontSize: FontSize.base,
    fontFamily: 'Inter_700Bold',
    color: Colors.textPrimary,
    lineHeight: 22,
    marginBottom: Spacing.sm,
  },
  summary: {
    fontSize: FontSize.sm,
    fontFamily: 'Inter_400Regular',
    color: Colors.textSecondary,
    lineHeight: 20,
    marginBottom: Spacing.md,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: Spacing.xs,
  },
  source: {
    fontSize: FontSize.xs,
    fontFamily: 'Inter_400Regular',
    color: Colors.textMuted,
  },
  readMore: {
    fontSize: FontSize.xs,
    fontFamily: 'Inter_600SemiBold',
    color: Colors.accent,
  },
})
