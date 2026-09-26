// ANTIGRAVITY — Reusable UI Primitives
// Skeleton, Section headers, Market rows, Badges, Empty/Error states

import React, { useEffect, useRef } from 'react'
import {
  View, Text, TouchableOpacity, StyleSheet,
  Animated, ViewStyle, TextStyle,
} from 'react-native'
import { Colors, Spacing, Radius, FontSize, FontWeight, MonoStyle } from '@/constants/theme'

// ── Shimmer Skeleton ─────────────────────────────────────────────────────────

export function SkeletonBox({ width, height, style, rounded }: {
  width?: number | string; height?: number; style?: ViewStyle; rounded?: boolean
}) {
  const opacity = useRef(new Animated.Value(0.3)).current

  useEffect(() => {
    const anim = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 0.7, duration: 800, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.3, duration: 800, useNativeDriver: true }),
      ])
    )
    anim.start()
    return () => anim.stop()
  }, [])

  return (
    <Animated.View
      style={[{
        width: width ?? '100%',
        height: height ?? 16,
        backgroundColor: Colors.bgElevated,
        borderRadius: rounded ? Radius.full : Radius.sm,
        opacity,
      }, style]}
    />
  )
}

export function SkeletonText({ lines = 1, style }: { lines?: number; style?: ViewStyle }) {
  return (
    <View style={style}>
      {Array.from({ length: lines }).map((_, i) => (
        <SkeletonBox
          key={i}
          height={13}
          width={i === lines - 1 && lines > 1 ? '65%' : '100%'}
          style={{ marginBottom: i < lines - 1 ? 8 : 0 }}
        />
      ))}
    </View>
  )
}

export function SkeletonCard({ height = 100, style }: { height?: number; style?: ViewStyle }) {
  return (
    <View style={[{
      backgroundColor: Colors.bgCard,
      borderRadius: Radius.lg,
      borderWidth: 1,
      borderColor: Colors.border,
      padding: Spacing.lg,
      marginBottom: Spacing.md,
      height,
      overflow: 'hidden',
    }, style]}>
      <SkeletonBox height={14} width="55%" style={{ marginBottom: 10 }} />
      <SkeletonBox height={11} width="80%" style={{ marginBottom: 6 }} />
      <SkeletonBox height={11} width="65%" />
    </View>
  )
}

export function SkeletonMarketRow() {
  return (
    <View style={s.marketRowSkeleton}>
      <View style={{ flex: 1 }}>
        <SkeletonBox height={12} width={80} style={{ marginBottom: 6 }} />
        <SkeletonBox height={11} width={50} />
      </View>
      <SkeletonBox height={20} width={60} rounded />
    </View>
  )
}

export function SkeletonNewsItem() {
  return (
    <View style={s.newsItemSkeleton}>
      <SkeletonBox height={10} width={60} style={{ marginBottom: 8 }} />
      <SkeletonText lines={2} style={{ marginBottom: 8 }} />
      <SkeletonBox height={10} width={100} />
    </View>
  )
}

// ── Section Header ───────────────────────────────────────────────────────────

export function SectionHeader({
  title, subtitle, action, onAction,
}: {
  title: string; subtitle?: string; action?: string; onAction?: () => void
}) {
  return (
    <View style={s.sectionHeader}>
      <View style={{ flex: 1 }}>
        <Text style={s.sectionTitle}>{title}</Text>
        {subtitle && <Text style={s.sectionSubtitle}>{subtitle}</Text>}
      </View>
      {action && onAction && (
        <TouchableOpacity onPress={onAction} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
          <Text style={s.sectionAction}>{action}</Text>
        </TouchableOpacity>
      )}
    </View>
  )
}

// ── Change Badge ─────────────────────────────────────────────────────────────

export function ChangeBadge({ value, compact }: { value: number; compact?: boolean }) {
  const isPos = value > 0
  const isNeg = value < 0
  const color = isPos ? Colors.positive : isNeg ? Colors.negative : Colors.textMuted
  const bg    = isPos ? Colors.positiveDim : isNeg ? Colors.negativeDim : 'transparent'
  const prefix = isPos ? '+' : ''

  if (compact) {
    return (
      <Text style={[s.changeBadgeText, { color }, MonoStyle]}>
        {prefix}{value.toFixed(2)}%
      </Text>
    )
  }

  return (
    <View style={[s.changeBadge, { backgroundColor: bg }]}>
      <Text style={[s.changeBadgeText, { color }, MonoStyle]}>
        {prefix}{value.toFixed(2)}%
      </Text>
    </View>
  )
}

// ── Market Row — compact single-line ─────────────────────────────────────────

export function MarketRow({
  name, value, change, unit = '', onPress,
}: {
  name: string; value: number; change: number; unit?: string; onPress?: () => void
}) {
  const color = change > 0 ? Colors.positive : change < 0 ? Colors.negative : Colors.textMuted
  const formatted = unit === 'pts'
    ? value.toLocaleString('en-IN', { maximumFractionDigits: 0 })
    : value.toFixed(2)

  const Row = onPress ? TouchableOpacity : View

  return (
    <Row
      style={s.marketRow}
      onPress={onPress}
      activeOpacity={0.7}
    >
      <Text style={s.marketRowName} numberOfLines={1}>{name}</Text>
      <View style={s.marketRowRight}>
        <Text style={[s.marketRowValue, MonoStyle]}>{unit !== 'pts' ? unit : ''}{formatted}</Text>
        <ChangeBadge value={change} compact />
      </View>
    </Row>
  )
}

// ── Stock Row — for screener / watchlist ─────────────────────────────────────

export function StockRow({
  symbol, name, price, change, metric, metricLabel, onPress,
}: {
  symbol: string; name: string; price?: number | null; change?: number | null;
  metric?: string; metricLabel?: string; onPress?: () => void
}) {
  const color = (change ?? 0) > 0 ? Colors.positive : (change ?? 0) < 0 ? Colors.negative : Colors.textMuted

  return (
    <TouchableOpacity style={s.stockRow} onPress={onPress} activeOpacity={0.7}>
      <View style={s.stockSymbolBox}>
        <Text style={s.stockSymbol} numberOfLines={1}>{symbol.replace('.NS', '')}</Text>
      </View>
      <View style={s.stockMid}>
        <Text style={s.stockName} numberOfLines={1}>{name}</Text>
        {metricLabel && metric && (
          <Text style={s.stockMetric}>{metricLabel}: {metric}</Text>
        )}
      </View>
      <View style={s.stockRight}>
        {price != null && (
          <Text style={[s.stockPrice, MonoStyle]}>₹{price.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</Text>
        )}
        {change != null && (
          <Text style={[s.stockChange, { color }, MonoStyle]}>
            {change >= 0 ? '+' : ''}{change.toFixed(2)}%
          </Text>
        )}
      </View>
    </TouchableOpacity>
  )
}

// ── Sentiment Badge ───────────────────────────────────────────────────────────

const SENTIMENT_COLORS: Record<string, { color: string; bg: string }> = {
  POSITIVE: { color: Colors.positive, bg: Colors.positiveDim },
  NEGATIVE: { color: Colors.negative, bg: Colors.negativeDim },
  NEUTRAL:  { color: Colors.textMuted, bg: Colors.bgElevated },
  BULLISH:  { color: Colors.positive, bg: Colors.positiveDim },
  BEARISH:  { color: Colors.negative, bg: Colors.negativeDim },
  MIXED:    { color: Colors.warning, bg: Colors.warningDim },
}

export function SentimentBadge({ sentiment }: { sentiment: string }) {
  const cfg = SENTIMENT_COLORS[sentiment?.toUpperCase()] ?? SENTIMENT_COLORS.NEUTRAL
  return (
    <View style={[s.sentBadge, { backgroundColor: cfg.bg }]}>
      <Text style={[s.sentText, { color: cfg.color }]}>{sentiment}</Text>
    </View>
  )
}

// ── Category Pill ─────────────────────────────────────────────────────────────

export function CategoryPill({ label }: { label: string }) {
  return (
    <View style={s.categoryPill}>
      <Text style={s.categoryPillText}>{label.toUpperCase()}</Text>
    </View>
  )
}

// ── Empty State ───────────────────────────────────────────────────────────────

export function EmptyState({
  icon, title, subtitle, action, onAction,
}: {
  icon?: string; title: string; subtitle?: string; action?: string; onAction?: () => void
}) {
  return (
    <View style={s.emptyState}>
      {icon && <Text style={s.emptyIcon}>{icon}</Text>}
      <Text style={s.emptyTitle}>{title}</Text>
      {subtitle && <Text style={s.emptySubtitle}>{subtitle}</Text>}
      {action && onAction && (
        <TouchableOpacity style={s.emptyAction} onPress={onAction}>
          <Text style={s.emptyActionText}>{action}</Text>
        </TouchableOpacity>
      )}
    </View>
  )
}

// ── Error State ───────────────────────────────────────────────────────────────

export function ErrorState({
  title, subtitle, onRetry,
}: {
  title?: string; subtitle?: string; onRetry?: () => void
}) {
  return (
    <View style={s.errorState}>
      <Text style={s.errorTitle}>{title ?? 'DATA UNAVAILABLE'}</Text>
      <Text style={s.errorSubtitle}>
        {subtitle ?? "We couldn't load this right now."}
      </Text>
      {onRetry && (
        <TouchableOpacity style={s.retryBtn} onPress={onRetry}>
          <Text style={s.retryText}>TRY AGAIN</Text>
        </TouchableOpacity>
      )}
    </View>
  )
}

// ── AI Processing Indicator ───────────────────────────────────────────────────

export function AIProcessing({ label }: { label?: string }) {
  const dot1 = useRef(new Animated.Value(0)).current
  const dot2 = useRef(new Animated.Value(0)).current
  const dot3 = useRef(new Animated.Value(0)).current

  useEffect(() => {
    const animate = (dot: Animated.Value, delay: number) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(delay),
          Animated.timing(dot, { toValue: 1, duration: 400, useNativeDriver: true }),
          Animated.timing(dot, { toValue: 0, duration: 400, useNativeDriver: true }),
          Animated.delay(800 - delay),
        ])
      )

    const a1 = animate(dot1, 0)
    const a2 = animate(dot2, 200)
    const a3 = animate(dot3, 400)
    a1.start(); a2.start(); a3.start()
    return () => { a1.stop(); a2.stop(); a3.stop() }
  }, [])

  const dotStyle = (dot: Animated.Value) => ({
    width: 5, height: 5, borderRadius: 3,
    backgroundColor: Colors.accent,
    marginHorizontal: 2,
    opacity: dot,
  })

  return (
    <View style={s.aiProcessing}>
      <Text style={s.aiLabel}>{label ?? 'Synthesizing signals'}</Text>
      <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 8 }}>
        <Animated.View style={dotStyle(dot1)} />
        <Animated.View style={dotStyle(dot2)} />
        <Animated.View style={dotStyle(dot3)} />
      </View>
    </View>
  )
}

// ── Divider ───────────────────────────────────────────────────────────────────

export function Divider({ style }: { style?: ViewStyle }) {
  return <View style={[s.divider, style]} />
}

// ── Premium Button ────────────────────────────────────────────────────────────

export function PremiumButton({
  label, onPress, variant = 'primary', size = 'md', disabled, loading,
}: {
  label: string; onPress: () => void;
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean; loading?: boolean;
}) {
  const isP = variant === 'primary'
  const isS = variant === 'secondary'
  const pad = size === 'sm' ? 10 : size === 'lg' ? 18 : 14

  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={disabled || loading}
      activeOpacity={0.8}
      style={[
        s.premBtn,
        { paddingVertical: pad },
        isP && { backgroundColor: Colors.accent },
        isS && { backgroundColor: Colors.bgElevated, borderWidth: 1, borderColor: Colors.border },
        !isP && !isS && { backgroundColor: 'transparent' },
        (disabled || loading) && { opacity: 0.5 },
      ]}
    >
      <Text style={[
        s.premBtnText,
        { fontSize: size === 'sm' ? FontSize.xs : FontSize.sm },
        isP && { color: Colors.white },
        !isP && { color: isS ? Colors.textPrimary : Colors.accent },
      ]}>
        {loading ? '···' : label}
      </Text>
    </TouchableOpacity>
  )
}

// ── Tab Selector (for sub-tabs in screens) ────────────────────────────────────

export function TabSelector<T extends string>({
  tabs, active, onSelect,
}: {
  tabs: { key: T; label: string }[];
  active: T;
  onSelect: (t: T) => void;
}) {
  return (
    <View style={s.tabSelector}>
      {tabs.map(t => (
        <TouchableOpacity
          key={t.key}
          onPress={() => onSelect(t.key)}
          style={[s.tabBtn, active === t.key && s.tabBtnActive]}
          activeOpacity={0.7}
        >
          <Text style={[s.tabBtnText, active === t.key && s.tabBtnTextActive]}>
            {t.label}
          </Text>
        </TouchableOpacity>
      ))}
    </View>
  )
}

// ── Styles ────────────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  // Market Row
  marketRow: {
    flexDirection: 'row', alignItems: 'center',
    paddingVertical: Spacing.md,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  marketRowName: {
    flex: 1, fontSize: FontSize.sm, fontWeight: FontWeight.medium,
    color: Colors.textSecondary, letterSpacing: 0.2,
  },
  marketRowRight: { alignItems: 'flex-end', gap: 3 },
  marketRowValue: {
    fontSize: FontSize.sm, fontWeight: FontWeight.semibold,
    color: Colors.textPrimary,
  },

  // Market Row Skeleton
  marketRowSkeleton: {
    flexDirection: 'row', alignItems: 'center',
    paddingVertical: Spacing.md,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },

  // News Item Skeleton
  newsItemSkeleton: {
    paddingVertical: Spacing.lg,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },

  // Section Header
  sectionHeader: {
    flexDirection: 'row', alignItems: 'center',
    marginBottom: Spacing.md, marginTop: Spacing.xl,
  },
  sectionTitle: {
    fontSize: FontSize.xxs, fontWeight: FontWeight.bold,
    color: Colors.textMuted, letterSpacing: 1.2,
  },
  sectionSubtitle: {
    fontSize: FontSize.xs, color: Colors.textMuted, marginTop: 2,
  },
  sectionAction: {
    fontSize: FontSize.xs, color: Colors.accent,
    fontWeight: FontWeight.semibold, letterSpacing: 0.5,
  },

  // Change Badge
  changeBadge: {
    paddingHorizontal: Spacing.sm, paddingVertical: 3,
    borderRadius: Radius.xs,
  },
  changeBadgeText: {
    fontSize: FontSize.xs, fontWeight: FontWeight.semibold,
  },

  // Stock Row
  stockRow: {
    flexDirection: 'row', alignItems: 'center',
    paddingVertical: Spacing.md,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  stockSymbolBox: {
    width: 52, height: 36, borderRadius: Radius.sm,
    backgroundColor: Colors.bgElevated, borderWidth: 1,
    borderColor: Colors.border, alignItems: 'center', justifyContent: 'center',
    marginRight: Spacing.md,
  },
  stockSymbol: {
    fontSize: FontSize.xxs, fontWeight: FontWeight.bold,
    color: Colors.accent, letterSpacing: 0.5,
  },
  stockMid: { flex: 1 },
  stockName: {
    fontSize: FontSize.sm, fontWeight: FontWeight.medium,
    color: Colors.textPrimary, marginBottom: 2,
  },
  stockMetric: { fontSize: FontSize.xs, color: Colors.textMuted },
  stockRight: { alignItems: 'flex-end' },
  stockPrice: {
    fontSize: FontSize.sm, fontWeight: FontWeight.semibold,
    color: Colors.textPrimary, marginBottom: 2,
  },
  stockChange: { fontSize: FontSize.xs, fontWeight: FontWeight.medium },

  // Sentiment Badge
  sentBadge: {
    paddingHorizontal: Spacing.sm, paddingVertical: 2,
    borderRadius: Radius.xs, alignSelf: 'flex-start',
  },
  sentText: {
    fontSize: FontSize.xxs, fontWeight: FontWeight.bold, letterSpacing: 0.5,
  },

  // Category Pill
  categoryPill: {
    paddingHorizontal: Spacing.sm, paddingVertical: 2,
    backgroundColor: Colors.bgElevated,
    borderRadius: Radius.xs, borderWidth: 1, borderColor: Colors.border,
    alignSelf: 'flex-start',
  },
  categoryPillText: {
    fontSize: FontSize.xxs, fontWeight: FontWeight.bold,
    color: Colors.textMuted, letterSpacing: 1,
  },

  // Empty State
  emptyState: {
    alignItems: 'center', paddingVertical: Spacing.section,
    paddingHorizontal: Spacing.xxxl,
  },
  emptyIcon: { fontSize: 32, marginBottom: Spacing.lg },
  emptyTitle: {
    fontSize: FontSize.sm, fontWeight: FontWeight.bold,
    color: Colors.textMuted, letterSpacing: 0.8,
    textAlign: 'center', marginBottom: Spacing.sm,
  },
  emptySubtitle: {
    fontSize: FontSize.xs, color: Colors.textDisabled,
    textAlign: 'center', lineHeight: 18,
  },
  emptyAction: {
    marginTop: Spacing.lg, paddingHorizontal: Spacing.xl,
    paddingVertical: Spacing.sm, borderRadius: Radius.md,
    backgroundColor: Colors.bgElevated, borderWidth: 1, borderColor: Colors.border,
  },
  emptyActionText: {
    fontSize: FontSize.xs, fontWeight: FontWeight.bold,
    color: Colors.textSecondary, letterSpacing: 0.5,
  },

  // Error State
  errorState: {
    alignItems: 'center', paddingVertical: Spacing.section,
    paddingHorizontal: Spacing.xxxl,
  },
  errorTitle: {
    fontSize: FontSize.xs, fontWeight: FontWeight.bold,
    color: Colors.textMuted, letterSpacing: 1.2,
    textAlign: 'center', marginBottom: Spacing.sm,
  },
  errorSubtitle: {
    fontSize: FontSize.xs, color: Colors.textDisabled,
    textAlign: 'center', lineHeight: 18, marginBottom: Spacing.xl,
  },
  retryBtn: {
    paddingHorizontal: Spacing.xl, paddingVertical: Spacing.sm,
    borderRadius: Radius.md, borderWidth: 1, borderColor: Colors.border,
    backgroundColor: Colors.bgElevated,
  },
  retryText: {
    fontSize: FontSize.xs, fontWeight: FontWeight.bold,
    color: Colors.textSecondary, letterSpacing: 1,
  },

  // AI Processing
  aiProcessing: { alignItems: 'center', paddingVertical: Spacing.xl },
  aiLabel: {
    fontSize: FontSize.xs, color: Colors.textMuted,
    letterSpacing: 0.5, fontWeight: FontWeight.medium,
  },

  // Divider
  divider: { height: 1, backgroundColor: Colors.border, marginVertical: Spacing.lg },

  // Premium Button
  premBtn: {
    alignItems: 'center', borderRadius: Radius.md,
    paddingHorizontal: Spacing.xl,
  },
  premBtnText: { fontWeight: FontWeight.bold, letterSpacing: 0.5 },

  // Tab Selector
  tabSelector: {
    flexDirection: 'row',
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.lg, padding: 3,
    borderWidth: 1, borderColor: Colors.border,
  },
  tabBtn: {
    flex: 1, paddingVertical: Spacing.sm,
    alignItems: 'center', borderRadius: Radius.md,
  },
  tabBtnActive: { backgroundColor: Colors.bgElevated },
  tabBtnText: {
    fontSize: FontSize.xs, fontWeight: FontWeight.semibold,
    color: Colors.textMuted, letterSpacing: 0.3,
  },
  tabBtnTextActive: { color: Colors.textPrimary },
})
