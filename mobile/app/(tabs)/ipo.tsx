// ANTIGRAVITY — IPO Intelligence Screen
// Tabs: Open | Upcoming | All. Live GMP, subscription, composite score.

import { useState, useCallback, useEffect } from 'react'
import {
  View, Text, ScrollView, StyleSheet, RefreshControl,
  TouchableOpacity, Linking,
} from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { apiIPOHub, IpoBrief, IpoHubResult, clearAllCache } from '@/lib/api'
import {
  SectionHeader, SkeletonCard, EmptyState, ErrorState, TabSelector, Divider,
} from '@/components/ui'
import { Colors, Spacing, Radius, FontSize, FontWeight, MonoStyle } from '@/constants/theme'

type Tab = 'open' | 'upcoming' | 'all'

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDays(n: number | null, label: string) {
  if (n == null) return null
  if (n === 0) return `${label} Today`
  if (n < 0) return null
  return `${label} in ${n}d`
}

function subColor(total: number) {
  if (total >= 50) return Colors.positive
  if (total >= 10) return Colors.warning
  if (total > 0)   return Colors.textSecondary
  return Colors.textMuted
}

const GRADE_COLOR: Record<string, string> = {
  'A+': Colors.positive, A: Colors.positive,
  'B+': '#22D3EE', B: '#22D3EE',
  'C+': Colors.warning,  C: Colors.warning,
  D: Colors.negative,
}

// ── Stats Bar ─────────────────────────────────────────────────────────────────

function StatsBar({ stats, gmpCount }: { stats: IpoHubResult['stats']; gmpCount: number }) {
  const items = [
    { label: 'TOTAL',     value: stats.total },
    { label: 'OPEN',      value: stats.open,      color: Colors.positive },
    { label: 'UPCOMING',  value: stats.upcoming },
    { label: 'ALLOTMENT', value: stats.allotment },
    { label: 'GMP DATA',  value: gmpCount,         color: Colors.accent },
  ]

  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.statsScroll}>
      <View style={s.statsBar}>
        {items.map(it => (
          <View key={it.label} style={s.statCell}>
            <Text style={[s.statVal, it.color ? { color: it.color } : {}, MonoStyle]}>
              {it.value}
            </Text>
            <Text style={s.statLabel}>{it.label}</Text>
          </View>
        ))}
      </View>
    </ScrollView>
  )
}

// ── IPO Card ─────────────────────────────────────────────────────────────────

function IPOCard({ ipo }: { ipo: IpoBrief }) {
  const [expanded, setExpanded] = useState(false)
  const isOpen    = ipo.status === 'OPEN'
  const isUpcoming = ipo.status === 'UPCOMING'
  const isSME     = ipo.issue_type === 'SME'

  const sub = ipo.subscription
  const gmp = ipo.gmp
  const score = ipo.score_data

  const statusColor = isOpen ? Colors.positive : isUpcoming ? Colors.accent : Colors.textMuted
  const gradeColor = score?.grade ? (GRADE_COLOR[score.grade] ?? Colors.textMuted) : Colors.textMuted

  return (
    <TouchableOpacity
      style={[s.ipoCard, isOpen && { borderColor: Colors.positiveBorder }]}
      onPress={() => setExpanded(e => !e)}
      activeOpacity={0.88}
    >
      {/* Header */}
      <View style={s.ipoHeader}>
        <View style={{ flex: 1 }}>
          <View style={s.ipoTopRow}>
            <Text style={s.ipoName} numberOfLines={1}>{ipo.company_name}</Text>
            <View style={[s.statusPill, { backgroundColor: statusColor + '15', borderColor: statusColor + '30' }]}>
              <Text style={[s.statusText, { color: statusColor }]}>{ipo.status}</Text>
            </View>
          </View>
          <View style={s.ipoSubRow}>
            <View style={[s.smePill, { backgroundColor: isSME ? Colors.accentDim : Colors.bgElevated }]}>
              <Text style={[s.smeText, { color: isSME ? Colors.accent : Colors.textMuted }]}>
                {ipo.issue_type}
              </Text>
            </View>
            <Text style={s.ipoExchange}>{ipo.exchange}</Text>
            {ipo.industry && <Text style={s.ipoIndustry} numberOfLines={1}>{ipo.industry}</Text>}
          </View>
        </View>
      </View>

      {/* Key data row */}
      <View style={s.ipoDataRow}>
        {/* Price band */}
        <View style={s.dataCell}>
          <Text style={s.dataCellLabel}>PRICE BAND</Text>
          <Text style={[s.dataCellValue, MonoStyle]}>
            {ipo.price_band ?? (ipo.price_band_max ? `₹${ipo.price_band_max}` : '—')}
          </Text>
        </View>

        {/* GMP */}
        <View style={s.dataCell}>
          <Text style={s.dataCellLabel}>GMP</Text>
          {gmp && gmp.gmp_price !== 0 ? (
            <Text style={[s.dataCellValue, {
              color: gmp.gmp_price > 0 ? Colors.positive : Colors.negative,
            }, MonoStyle]}>
              {gmp.gmp_price > 0 ? '+' : ''}₹{gmp.gmp_price}
              {gmp.premium_pct != null ? ` (${gmp.premium_pct > 0 ? '+' : ''}${gmp.premium_pct.toFixed(1)}%)` : ''}
            </Text>
          ) : <Text style={[s.dataCellValue, { color: Colors.textMuted }]}>—</Text>}
        </View>

        {/* Subscription */}
        <View style={s.dataCell}>
          <Text style={s.dataCellLabel}>SUBS</Text>
          {sub && sub.total > 0 ? (
            <Text style={[s.dataCellValue, { color: subColor(sub.total) }, MonoStyle]}>
              {sub.total.toFixed(1)}×
            </Text>
          ) : <Text style={[s.dataCellValue, { color: Colors.textMuted }]}>—</Text>}
        </View>

        {/* Score */}
        {score && (
          <View style={s.dataCell}>
            <Text style={s.dataCellLabel}>GRADE</Text>
            <Text style={[s.dataCellValue, { color: gradeColor }, MonoStyle]}>
              {score.grade}
              <Text style={{ fontSize: FontSize.xxs, color: Colors.textMuted }}>
                {' '}{score.composite_score.toFixed(0)}/100
              </Text>
            </Text>
          </View>
        )}
      </View>

      {/* Dates */}
      <View style={s.ipoDates}>
        {ipo.open_date && (
          <Text style={s.dateChip}>
            Open: {ipo.open_date}
            {ipo.days_to_open != null && ipo.days_to_open >= 0
              ? ` · ${formatDays(ipo.days_to_open, 'Opens')}` : ''}
          </Text>
        )}
        {ipo.close_date && (
          <Text style={s.dateChip}>Close: {ipo.close_date}</Text>
        )}
        {ipo.listing_date && (
          <Text style={s.dateChip}>List: {ipo.listing_date}</Text>
        )}
      </View>

      {/* Expanded detail */}
      {expanded && (
        <View style={s.ipoExpanded}>
          <Divider style={{ marginBottom: Spacing.lg }} />

          {/* Full subscription breakdown */}
          {sub && sub.total > 0 && (
            <View style={s.subTable}>
              <Text style={s.subTableTitle}>SUBSCRIPTION</Text>
              <View style={s.subRow}>
                {[
                  { l: 'QIB',   v: sub.qib },
                  { l: 'NII',   v: sub.nii },
                  { l: 'RII',   v: sub.rii },
                  { l: 'TOTAL', v: sub.total, bold: true },
                ].map(cell => (
                  <View key={cell.l} style={s.subCell}>
                    <Text style={s.subLabel}>{cell.l}</Text>
                    <Text style={[s.subVal, { color: subColor(cell.v) }, cell.bold && { fontWeight: FontWeight.black }, MonoStyle]}>
                      {cell.v.toFixed(1)}×
                    </Text>
                  </View>
                ))}
              </View>
            </View>
          )}

          {/* Est listing */}
          {gmp?.est_listing && (
            <View style={s.estListing}>
              <Text style={s.estLabel}>EST. LISTING PRICE</Text>
              <Text style={[s.estValue, { color: Colors.positive }, MonoStyle]}>₹{gmp.est_listing}</Text>
            </View>
          )}

          {/* Score breakdown */}
          {score && (
            <View style={s.scoreSection}>
              <Text style={s.subTableTitle}>SCORE BREAKDOWN</Text>
              {[
                { l: 'GMP Signal',  v: score.gmp_score,   max: 20 },
                { l: 'Subscription',v: score.sub_score,   max: 25 },
                { l: 'Issue Quality',v: score.qual_score, max: 15 },
                { l: 'Valuation',   v: score.val_score,   max: 15 },
                { l: 'Market Timing',v: score.time_score, max: 15 },
                { l: 'Fundamentals',v: score.fund_score,  max: 10 },
              ].map(row => (
                <View key={row.l} style={s.scoreRow}>
                  <Text style={s.scoreLabel}>{row.l}</Text>
                  <View style={s.scoreBarTrack}>
                    <View style={[s.scoreBarFill, {
                      width: `${(row.v / row.max) * 100}%`,
                      backgroundColor: row.v / row.max > 0.6 ? Colors.positive : row.v / row.max > 0.3 ? Colors.warning : Colors.negative,
                    }]} />
                  </View>
                  <Text style={[s.scoreVal, MonoStyle]}>{row.v}/{row.max}</Text>
                </View>
              ))}
            </View>
          )}

          {/* RHP Link */}
          {ipo.rhp_url && (
            <TouchableOpacity
              style={s.rhpBtn}
              onPress={() => Linking.openURL(ipo.rhp_url).catch(() => {})}
            >
              <Text style={s.rhpText}>VIEW RHP / DOCUMENTS →</Text>
            </TouchableOpacity>
          )}

          <Text style={s.ipoDisclaimer}>
            GMP is unofficial grey market data. Not SEBI registered. Educational only.
          </Text>
        </View>
      )}
    </TouchableOpacity>
  )
}

// ── Main Screen ───────────────────────────────────────────────────────────────

const TABS = [
  { key: 'open' as Tab,     label: 'Open' },
  { key: 'upcoming' as Tab, label: 'Upcoming' },
  { key: 'all' as Tab,      label: 'All' },
]

export default function IPOScreen() {
  const [tab, setTab]     = useState<Tab>('open')
  const [hub, setHub]     = useState<IpoHubResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(async () => {
    setError(false)
    try {
      const result = await apiIPOHub()
      setHub(result)
    } catch {
      setError(true)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const onRefresh = useCallback(() => {
    setRefreshing(true)
    clearAllCache()
    load()
  }, [load])

  const filteredIPOs = hub?.ipos.filter(ipo => {
    if (tab === 'open')     return ipo.status === 'OPEN'
    if (tab === 'upcoming') return ipo.status === 'UPCOMING'
    return true
  }) ?? []

  return (
    <SafeAreaView style={s.safe} edges={['top']}>
      {/* Header */}
      <View style={s.header}>
        <Text style={s.headerTitle}>IPO INTELLIGENCE</Text>
        {hub && <Text style={s.headerSub}>{hub.stats.total} issues tracked · {hub.gmp_count} with GMP</Text>}
      </View>

      {/* Stats */}
      {hub && !loading && (
        <StatsBar stats={hub.stats} gmpCount={hub.gmp_count} />
      )}

      {/* Tabs */}
      <View style={s.tabWrap}>
        <TabSelector tabs={TABS} active={tab} onSelect={setTab} />
      </View>

      {/* Content */}
      <ScrollView
        style={s.scroll}
        contentContainerStyle={s.content}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.accent} />
        }
      >
        {loading ? (
          [1, 2, 3].map(i => <SkeletonCard key={i} height={140} />)
        ) : error ? (
          <ErrorState
            title="IPO DATA UNAVAILABLE"
            subtitle="Could not load IPO data. Pull to retry."
            onRetry={load}
          />
        ) : filteredIPOs.length === 0 ? (
          <EmptyState
            icon="🚀"
            title={`NO ${tab.toUpperCase()} IPOS`}
            subtitle={
              tab === 'open' ? 'No IPOs are currently open for subscription.'
              : tab === 'upcoming' ? 'No upcoming IPOs in the next few days.'
              : 'No IPO data available.'
            }
          />
        ) : (
          filteredIPOs.map(ipo => <IPOCard key={ipo.id} ipo={ipo} />)
        )}

        <Text style={s.disclaimer}>
          GMP is unofficial grey market data and may not reflect actual listing price.{'\n'}
          Not SEBI registered. For educational purposes only.
        </Text>
      </ScrollView>
    </SafeAreaView>
  )
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.bg },
  scroll: { flex: 1 },
  content: { padding: Spacing.xl, paddingBottom: 40 },

  header: {
    paddingHorizontal: Spacing.xl, paddingTop: Spacing.xl, paddingBottom: Spacing.md,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  headerTitle: {
    fontSize: FontSize.h1, fontWeight: FontWeight.black,
    color: Colors.textPrimary, letterSpacing: -0.5,
  },
  headerSub: { fontSize: FontSize.xs, color: Colors.textMuted, marginTop: 2 },

  // Stats
  statsScroll: { borderBottomWidth: 1, borderBottomColor: Colors.border },
  statsBar: { flexDirection: 'row', paddingHorizontal: Spacing.xl, paddingVertical: Spacing.md, gap: Spacing.xl },
  statCell: { alignItems: 'center', gap: 3, minWidth: 50 },
  statVal: { fontSize: FontSize.h3, fontWeight: FontWeight.bold, color: Colors.textPrimary },
  statLabel: { fontSize: FontSize.xxs, color: Colors.textMuted, fontWeight: FontWeight.bold, letterSpacing: 0.8 },

  tabWrap: { paddingHorizontal: Spacing.xl, paddingVertical: Spacing.md },

  // IPO Card
  ipoCard: {
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.xl, borderWidth: 1, borderColor: Colors.border,
    padding: Spacing.xl, marginBottom: Spacing.sm,
  },
  ipoHeader: { marginBottom: Spacing.md },
  ipoTopRow: { flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.sm, marginBottom: Spacing.xs },
  ipoName: {
    flex: 1, fontSize: FontSize.base, fontWeight: FontWeight.bold,
    color: Colors.textPrimary, letterSpacing: -0.2,
  },
  statusPill: {
    paddingHorizontal: Spacing.sm, paddingVertical: 4,
    borderRadius: Radius.full, borderWidth: 1,
  },
  statusText: { fontSize: FontSize.xxs, fontWeight: FontWeight.black, letterSpacing: 0.5 },
  ipoSubRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, flexWrap: 'wrap' },
  smePill: {
    paddingHorizontal: Spacing.sm, paddingVertical: 3, borderRadius: Radius.xs,
  },
  smeText: { fontSize: FontSize.xxs, fontWeight: FontWeight.bold, letterSpacing: 0.5 },
  ipoExchange: { fontSize: FontSize.xxs, color: Colors.textMuted },
  ipoIndustry: { fontSize: FontSize.xxs, color: Colors.textMuted, flex: 1 },

  // Data row
  ipoDataRow: {
    flexDirection: 'row', gap: Spacing.lg, marginBottom: Spacing.md,
    paddingTop: Spacing.md, borderTopWidth: 1, borderTopColor: Colors.border,
  },
  dataCell: { flex: 1, gap: 4 },
  dataCellLabel: {
    fontSize: FontSize.xxs, color: Colors.textMuted,
    fontWeight: FontWeight.bold, letterSpacing: 0.8,
  },
  dataCellValue: {
    fontSize: FontSize.sm, fontWeight: FontWeight.bold, color: Colors.textPrimary,
  },

  // Dates
  ipoDates: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.xs },
  dateChip: { fontSize: FontSize.xxs, color: Colors.textMuted },

  // Expanded
  ipoExpanded: { marginTop: Spacing.md },
  subTable: { marginBottom: Spacing.lg },
  subTableTitle: {
    fontSize: FontSize.xxs, fontWeight: FontWeight.bold,
    color: Colors.textMuted, letterSpacing: 1.2, marginBottom: Spacing.sm,
  },
  subRow: { flexDirection: 'row', gap: Spacing.xl },
  subCell: { alignItems: 'center', gap: 3 },
  subLabel: { fontSize: FontSize.xxs, color: Colors.textMuted },
  subVal: { fontSize: FontSize.sm, fontWeight: FontWeight.bold },

  estListing: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: Colors.positiveDim, borderRadius: Radius.md,
    padding: Spacing.md, marginBottom: Spacing.lg,
    borderWidth: 1, borderColor: Colors.positiveBorder,
  },
  estLabel: { fontSize: FontSize.xxs, color: Colors.textSecondary, fontWeight: FontWeight.bold },
  estValue: { fontSize: FontSize.base, fontWeight: FontWeight.black },

  // Score
  scoreSection: { marginBottom: Spacing.lg },
  scoreRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.md, marginBottom: Spacing.sm },
  scoreLabel: { fontSize: FontSize.xxs, color: Colors.textMuted, width: 90 },
  scoreBarTrack: {
    flex: 1, height: 4, backgroundColor: Colors.bgElevated,
    borderRadius: 2, overflow: 'hidden',
  },
  scoreBarFill: { height: 4, borderRadius: 2 },
  scoreVal: { fontSize: FontSize.xxs, color: Colors.textSecondary, width: 32, textAlign: 'right' },

  rhpBtn: {
    paddingVertical: Spacing.md, alignItems: 'center',
    borderWidth: 1, borderColor: Colors.border, borderRadius: Radius.md,
    marginBottom: Spacing.md,
  },
  rhpText: { fontSize: FontSize.xxs, fontWeight: FontWeight.bold, color: Colors.accent, letterSpacing: 1 },

  ipoDisclaimer: {
    fontSize: FontSize.xxs, color: Colors.textDisabled, textAlign: 'center', lineHeight: 16,
  },

  disclaimer: {
    fontSize: FontSize.xxs, color: Colors.textDisabled,
    textAlign: 'center', marginTop: Spacing.xl, lineHeight: 16,
  },
})
