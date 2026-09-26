import { View, Text, StyleSheet, ScrollView } from 'react-native'
import { DeepDiveSafe } from '@/lib/api'
import { Colors, FontSize, Radius, Spacing } from '@/constants/theme'

interface Props {
  item: DeepDiveSafe
  expanded?: boolean
}

const RISK_CFG = {
  LOW:    { color: Colors.green, label: 'Low Risk' },
  MEDIUM: { color: Colors.yellow, label: 'Medium Risk' },
  HIGH:   { color: Colors.red, label: 'High Risk' },
}

export function DeepDiveCard({ item, expanded = false }: Props) {
  const risk = item.risk_rating ? RISK_CFG[item.risk_rating] : null

  return (
    <View style={styles.card}>
      {/* Header */}
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          {item.symbol ? (
            <Text style={styles.symbol}>{item.symbol}</Text>
          ) : null}
          <Text style={styles.title} numberOfLines={expanded ? undefined : 2}>
            {item.title}
          </Text>
        </View>
        {risk && (
          <View style={[styles.riskBadge, { backgroundColor: `${risk.color}18`, borderColor: `${risk.color}33` }]}>
            <Text style={[styles.riskText, { color: risk.color }]}>{risk.label}</Text>
          </View>
        )}
      </View>

      {/* Tags */}
      {item.tags && item.tags.length > 0 && (
        <View style={styles.tagsRow}>
          {item.tags.slice(0, 4).map(tag => (
            <View key={tag} style={styles.tag}>
              <Text style={styles.tagText}>{tag}</Text>
            </View>
          ))}
          {item.sector ? (
            <View style={[styles.tag, { backgroundColor: Colors.accentDim, borderColor: Colors.accentBorder }]}>
              <Text style={[styles.tagText, { color: Colors.accent }]}>{item.sector}</Text>
            </View>
          ) : null}
        </View>
      )}

      {/* Summary / teaser */}
      {item.summary ? (
        <Text style={styles.summary} numberOfLines={expanded ? undefined : 3}>
          {item.summary}
        </Text>
      ) : null}

      {/* Metrics snapshot */}
      {item.metrics_snapshot && expanded && (
        <View style={styles.metricsGrid}>
          {Object.entries(item.metrics_snapshot).slice(0, 6).map(([k, v]) => (
            <View key={k} style={styles.metricBox}>
              <Text style={styles.metricLabel}>{k.toUpperCase().replace(/_/g, ' ')}</Text>
              <Text style={styles.metricValue}>{String(v)}</Text>
            </View>
          ))}
        </View>
      )}

      {/* Sections (full content) */}
      {expanded && item.sections && item.sections.map((s, i) => (
        <View key={i} style={styles.section}>
          <Text style={styles.sectionHeading}>{s.heading}</Text>
          <Text style={styles.sectionBody}>{s.body}</Text>
        </View>
      ))}

      {/* Disclaimer — always visible */}
      <Text style={styles.disclaimer}>
        Educational analysis only. This is not investment advice or a recommendation to buy or sell.
      </Text>
    </View>
  )
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.lg,
    marginBottom: Spacing.md,
  },
  header: {
    flexDirection: 'row',
    gap: Spacing.md,
    marginBottom: Spacing.md,
    alignItems: 'flex-start',
  },
  symbol: {
    fontSize: FontSize.xs,
    fontFamily: 'Inter_700Bold',
    color: Colors.textMuted,
    letterSpacing: 2,
    textTransform: 'uppercase',
    marginBottom: 3,
  },
  title: {
    fontSize: FontSize.base,
    fontFamily: 'Inter_700Bold',
    color: Colors.textPrimary,
    lineHeight: 22,
  },
  riskBadge: {
    borderRadius: Radius.sm,
    borderWidth: 1,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
    alignSelf: 'flex-start',
    flexShrink: 0,
  },
  riskText: {
    fontSize: FontSize.xs,
    fontFamily: 'Inter_700Bold',
  },
  tagsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.xs,
    marginBottom: Spacing.md,
  },
  tag: {
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderRadius: Radius.full,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 3,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  tagText: {
    fontSize: FontSize.xs,
    fontFamily: 'Inter_600SemiBold',
    color: Colors.textSecondary,
  },
  summary: {
    fontSize: FontSize.sm,
    fontFamily: 'Inter_400Regular',
    color: Colors.textSecondary,
    lineHeight: 21,
    marginBottom: Spacing.md,
  },
  metricsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
    marginBottom: Spacing.lg,
  },
  metricBox: {
    backgroundColor: 'rgba(255,255,255,0.03)',
    borderRadius: Radius.sm,
    padding: Spacing.md,
    minWidth: '30%',
    flex: 1,
  },
  metricLabel: {
    fontSize: 9,
    fontFamily: 'Inter_600SemiBold',
    color: Colors.textMuted,
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  metricValue: {
    fontSize: FontSize.sm,
    fontFamily: 'Inter_700Bold',
    color: Colors.textPrimary,
  },
  section: {
    marginBottom: Spacing.lg,
  },
  sectionHeading: {
    fontSize: FontSize.base,
    fontFamily: 'Inter_700Bold',
    color: Colors.accent,
    marginBottom: Spacing.sm,
  },
  sectionBody: {
    fontSize: FontSize.sm,
    fontFamily: 'Inter_400Regular',
    color: Colors.textSecondary,
    lineHeight: 22,
  },
  disclaimer: {
    fontSize: FontSize.xs,
    fontFamily: 'Inter_400Regular',
    color: Colors.textMuted,
    textAlign: 'center',
    marginTop: Spacing.md,
    paddingTop: Spacing.md,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
    fontStyle: 'italic',
  },
})
