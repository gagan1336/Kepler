import { View, Text, StyleSheet } from 'react-native'
import { BreakoutStock } from '@/lib/api'
import { Colors, FontSize, Radius, Spacing } from '@/constants/theme'

interface Props {
  stock: BreakoutStock
}

function Metric({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={[styles.metricValue, color ? { color } : undefined]}>{value}</Text>
    </View>
  )
}

export function BreakoutCard({ stock }: Props) {
  const d = stock.technical_data
  const rsiColor =
    d?.rsi != null
      ? d.rsi >= 70 ? Colors.red : d.rsi <= 30 ? Colors.green : Colors.yellow
      : undefined

  return (
    <View style={styles.card}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.symbol}>{stock.symbol}</Text>
          {stock.company_name ? (
            <Text style={styles.name} numberOfLines={1}>{stock.company_name}</Text>
          ) : null}
        </View>
        <View style={styles.badge}>
          <Text style={styles.badgeText}>📈 Breakout</Text>
        </View>
      </View>

      {/* Setup description */}
      {stock.setup_description ? (
        <Text style={styles.desc} numberOfLines={3}>{stock.setup_description}</Text>
      ) : null}

      {/* Technical metrics */}
      {d && (
        <View style={styles.metricsRow}>
          {d.rsi != null && (
            <Metric label="RSI" value={d.rsi.toFixed(1)} color={rsiColor} />
          )}
          {d.price != null && (
            <Metric label="Price" value={`₹${d.price.toLocaleString('en-IN')}`} />
          )}
          {d.vol_ratio != null && (
            <Metric
              label="Vol"
              value={`${d.vol_ratio.toFixed(1)}x`}
              color={d.vol_ratio >= 2 ? Colors.green : Colors.textSecondary}
            />
          )}
          {d.ema20 != null && (
            <Metric label="EMA20" value={`₹${d.ema20.toFixed(0)}`} />
          )}
        </View>
      )}
    </View>
  )
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.lg,
    borderWidth: 1,
    borderColor: 'rgba(61,220,132,0.15)',
    padding: Spacing.lg,
    marginBottom: Spacing.md,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: Spacing.sm,
  },
  symbol: {
    fontSize: FontSize.lg,
    fontFamily: 'Inter_900Black',
    color: Colors.textPrimary,
    letterSpacing: 1,
  },
  name: {
    fontSize: FontSize.sm,
    fontFamily: 'Inter_400Regular',
    color: Colors.textSecondary,
    marginTop: 2,
    maxWidth: 180,
  },
  badge: {
    backgroundColor: Colors.greenDim,
    borderRadius: Radius.full,
    paddingHorizontal: Spacing.md,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: 'rgba(61,220,132,0.25)',
  },
  badgeText: {
    fontSize: FontSize.xs,
    fontFamily: 'Inter_700Bold',
    color: Colors.green,
  },
  desc: {
    fontSize: FontSize.sm,
    fontFamily: 'Inter_400Regular',
    color: Colors.textSecondary,
    lineHeight: 20,
    marginBottom: Spacing.md,
  },
  metricsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
    marginTop: Spacing.sm,
  },
  metric: {
    backgroundColor: 'rgba(255,255,255,0.03)',
    borderRadius: Radius.sm,
    padding: Spacing.sm,
    minWidth: 72,
    alignItems: 'center',
  },
  metricLabel: {
    fontSize: FontSize.xs,
    fontFamily: 'Inter_400Regular',
    color: Colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 2,
  },
  metricValue: {
    fontSize: FontSize.sm,
    fontFamily: 'Inter_700Bold',
    color: Colors.textPrimary,
  },
})
