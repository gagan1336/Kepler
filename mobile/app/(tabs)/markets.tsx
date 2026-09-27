// KEPLER -- Market Pulse Screen
// Sub-tabs: Overview | Breakouts | Sectors

import { useState, useCallback, useEffect, useRef } from 'react'
import {
  View, Text, ScrollView, StyleSheet, RefreshControl,
  TouchableOpacity, FlatList, TextInput,
} from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import {
  apiGlobalMarkets, apiBreakouts, apiSectorsLive,
  apiScreenerQuality, apiScreenerValue, apiScreenerDividend, apiScreenerPreset,
  apiScreenerSwing, apiStockSearch,
  GlobalMarketsResult, GlobalMarketTicker, BreakoutStock, SectorLive, ScreenerStock,
  clearAllCache,
} from '@/lib/api'
import {
  SectionHeader, MarketRow, StockRow, SentimentBadge,
  SkeletonMarketRow, SkeletonCard, ErrorState, EmptyState, TabSelector, Divider,
  AIProcessing,
} from '@/components/ui'
import { Colors, Spacing, Radius, FontSize, FontWeight, MonoStyle } from '@/constants/theme'

type Tab = 'overview' | 'breakouts' | 'sectors' | 'screener'

// ── Helpers ───────────────────────────────────────────────────────────────────

function pctColor(v: number) {
  return v > 0 ? Colors.positive : v < 0 ? Colors.negative : Colors.textMuted
}
function sign(v: number) { return v >= 0 ? '+' : '' }

// ── Group Label ───────────────────────────────────────────────────────────────

const GROUP_LABELS: Record<string, { label: string; icon: string }> = {
  gift_nifty:  { label: 'INDIA',       icon: '🇮🇳' },
  us:          { label: 'US MARKETS',  icon: '🇺🇸' },
  asia:        { label: 'ASIA',        icon: '🌏' },
  europe:      { label: 'EUROPE',      icon: '🇪🇺' },
  commodities: { label: 'COMMODITIES', icon: '⚡' },
  forex:       { label: 'FOREX',       icon: '💱' },
  crypto:      { label: 'CRYPTO',      icon: '₿' },
}

// ── Overview Tab ─────────────────────────────────────────────────────────────

function OverviewTab({ markets, loading }: { markets: GlobalMarketsResult | null; loading: boolean }) {
  if (loading) {
    return (
      <View>
        {[1, 2, 3, 4, 5, 6, 7, 8].map(i => <SkeletonMarketRow key={i} />)}
      </View>
    )
  }

  if (!markets) {
    return <ErrorState title="MARKET DATA UNAVAILABLE" />
  }

  const groups = ['gift_nifty', 'us', 'asia', 'commodities', 'forex', 'crypto']

  return (
    <View>
      {groups.map(groupKey => {
        const tickers: GlobalMarketTicker[] = (markets.groups as any)[groupKey] ?? []
        if (!tickers.length) return null
        const meta = GROUP_LABELS[groupKey]

        return (
          <View key={groupKey} style={s.groupBlock}>
            <View style={s.groupLabel}>
              <Text style={s.groupIcon}>{meta?.icon}</Text>
              <Text style={s.groupLabelText}>{meta?.label ?? groupKey.toUpperCase()}</Text>
            </View>
            <View style={s.groupCard}>
              {tickers.map((t, i) => (
                <MarketRow
                  key={t.symbol}
                  name={t.name}
                  value={t.current_price}
                  change={t.change_pct}
                  unit={t.unit}
                />
              ))}
            </View>
          </View>
        )
      })}
    </View>
  )
}

// ── Breakout Row ──────────────────────────────────────────────────────────────

function BreakoutRow({ item, index }: { item: BreakoutStock; index: number }) {
  const td = item.technical_data ?? {}
  return (
    <View style={s.breakoutRow}>
      <Text style={s.breakoutNum}>{String(index + 1).padStart(2, '0')}</Text>
      <View style={s.breakoutMid}>
        <View style={s.breakoutSymWrap}>
          <Text style={s.breakoutSym}>{item.symbol?.replace('.NS', '') ?? '—'}</Text>
        </View>
        <Text style={s.breakoutName} numberOfLines={1}>{item.company_name ?? '—'}</Text>
      </View>
      <View style={s.breakoutRight}>
        {td.price != null && (
          <Text style={[s.breakoutPrice, MonoStyle]}>
            ₹{td.price.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
          </Text>
        )}
        <View style={s.breakoutMetrics}>
          {td.rsi != null && <Text style={s.breakoutMeta}>RSI {td.rsi.toFixed(0)}</Text>}
          {td.vol_ratio != null && <Text style={s.breakoutMeta}>Vol {td.vol_ratio.toFixed(1)}x</Text>}
        </View>
      </View>
    </View>
  )
}

// ── Breakouts Tab ─────────────────────────────────────────────────────────────

function BreakoutsTab({ stocks, loading }: { stocks: BreakoutStock[]; loading: boolean }) {
  if (loading) {
    return (
      <View>
        {[1, 2, 3, 4, 5].map(i => <SkeletonCard key={i} height={70} />)}
      </View>
    )
  }

  if (!stocks.length) {
    return (
      <EmptyState
        icon="⚡"
        title="NO BREAKOUTS TODAY"
        subtitle="The scanner runs daily after market hours. Check back tomorrow morning."
      />
    )
  }

  return (
    <View style={s.groupCard}>
      <View style={s.breakoutHeader}>
        <Text style={s.breakoutHeaderText}>
          {stocks.length} SETUPS IDENTIFIED
        </Text>
      </View>
      {stocks.map((item, i) => (
        <BreakoutRow key={item.id} item={item} index={i} />
      ))}
      <Text style={s.breakoutDisclaimer}>
        Technical breakout patterns identified by scanner. Not investment advice.
      </Text>
    </View>
  )
}

// ── Sector Row ────────────────────────────────────────────────────────────────

function SectorRow({ item }: { item: SectorLive }) {
  const [expanded, setExpanded] = useState(false)
  const color = pctColor(item.day_pct)
  const barWidth = Math.min(Math.abs(item.day_pct) / 4, 1)

  return (
    <TouchableOpacity
      style={s.sectorRow}
      onPress={() => setExpanded(e => !e)}
      activeOpacity={0.8}
    >
      {/* Main row */}
      <View style={s.sectorMain}>
        <View style={{ flex: 1 }}>
          <Text style={s.sectorName}>{item.name}</Text>
          {/* Bar */}
          <View style={s.sectorBarTrack}>
            <View style={[s.sectorBar, {
              width: `${barWidth * 100}%`,
              backgroundColor: color,
              alignSelf: item.day_pct >= 0 ? 'flex-start' : 'flex-end',
            }]} />
          </View>
        </View>
        <View style={s.sectorRight}>
          <Text style={[s.sectorPct, { color }, MonoStyle]}>
            {sign(item.day_pct)}{item.day_pct.toFixed(2)}%
          </Text>
          <SentimentBadge sentiment={item.sentiment} />
        </View>
      </View>

      {/* Performance row */}
      <View style={s.sectorPerf}>
        {[
          { l: '1W', v: item.week_pct },
          { l: '1M', v: item.month_pct },
          { l: 'YTD', v: item.ytd_pct },
          { l: 'RS', v: item.rs_nifty },
        ].map(({ l, v }) => (
          <View key={l} style={s.perfCell}>
            <Text style={[s.perfVal, { color: pctColor(v) }, MonoStyle]}>
              {sign(v)}{v.toFixed(1)}%
            </Text>
            <Text style={s.perfLabel}>{l}</Text>
          </View>
        ))}
      </View>

      {/* Expanded movers */}
      {expanded && item.top_movers?.length > 0 && (
        <View style={s.moversSection}>
          <Text style={s.moversLabel}>TOP MOVERS</Text>
          {item.top_movers.slice(0, 5).map(m => (
            <View key={m.symbol} style={s.moverRow}>
              <Text style={s.moverSym}>{m.symbol?.replace('.NS', '')}</Text>
              <Text style={s.moverName} numberOfLines={1}>{m.name}</Text>
              <Text style={[s.moverChg, { color: pctColor(m.change_pct) }, MonoStyle]}>
                {sign(m.change_pct)}{m.change_pct.toFixed(2)}%
              </Text>
            </View>
          ))}
        </View>
      )}
    </TouchableOpacity>
  )
}

// ── Sectors Tab ───────────────────────────────────────────────────────────────

function SectorsTab({ sectors, loading }: { sectors: SectorLive[]; loading: boolean }) {
  if (loading) {
    return (
      <View>
        {[1, 2, 3, 4].map(i => <SkeletonCard key={i} height={100} />)}
      </View>
    )
  }

  if (!sectors.length) {
    return (
      <EmptyState
        icon="🏭"
        title="SECTOR DATA UNAVAILABLE"
        subtitle="Sector data is loading in the background. Pull to refresh."
      />
    )
  }

  const sorted = [...sectors].sort((a, b) => b.day_pct - a.day_pct)

  return (
    <View style={s.groupCard}>
      {sorted.map(item => (
        <SectorRow key={item.symbol} item={item} />
      ))}
    </View>
  )
}

// ── Screener (inline compact) ────────────────────────────────────────────────

const SCREEN_PRESETS = [
  { key: 'quality',        label: 'Quality',   color: '#7C6CFF', fetch: () => apiScreenerQuality() },
  { key: 'value',          label: 'Value',     color: '#22C55E', fetch: () => apiScreenerValue() },
  { key: 'dividend',       label: 'Dividend',  color: '#F59E0B', fetch: () => apiScreenerDividend() },
  { key: 'momentum',       label: 'Momentum',  color: '#F43F5E', fetch: () => apiScreenerPreset('momentum') },
] as const

function ScreenerTab() {
  const [active, setActive] = useState<string | null>(null)
  const [stocks, setStocks] = useState<ScreenerStock[]>([])
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState<ScreenerStock[]>([])
  const [searching, setSearching] = useState(false)
  const searchRef = useRef<any>(null)

  const loadPreset = useCallback(async (key: string) => {
    const preset = SCREEN_PRESETS.find(p => p.key === key)
    if (!preset) return
    setActive(key); setStocks([]); setLoading(true)
    try { const r = await preset.fetch(); setStocks(Array.isArray(r) ? r : []) }
    catch {} finally { setLoading(false) }
  }, [])

  const doSearch = useCallback((text: string) => {
    setQuery(text)
    clearTimeout(searchRef.current)
    if (!text.trim()) { setSearchResults([]); return }
    setSearching(true)
    searchRef.current = setTimeout(async () => {
      try { const r = await apiStockSearch(text.trim()); setSearchResults(r) }
      catch { setSearchResults([]) } finally { setSearching(false) }
    }, 400)
  }, [])

  const activePreset = SCREEN_PRESETS.find(p => p.key === active)
  const isSearch = query.trim().length > 0

  return (
    <View>
      {/* Search */}
      <View style={s.screenerSearch}>
        <TextInput
          style={s.screenerInput}
          placeholder="Search stocks..."
          placeholderTextColor={Colors.textMuted}
          value={query}
          onChangeText={doSearch}
          autoCorrect={false}
          autoCapitalize="characters"
        />
      </View>

      {isSearch ? (
        searching ? <AIProcessing label="Searching" /> :
        searchResults.length > 0 ? (
          <View style={s.groupCard}>
            {searchResults.map(st => (
              <ScreenStockRow key={st.symbol} stock={st} />
            ))}
          </View>
        ) : (
          <EmptyState icon="◎" title="NO RESULTS" subtitle={`No match for "${query}"`} />
        )
      ) : (
        <>
          {/* Preset chips */}
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: Spacing.lg }}>
            <View style={{ flexDirection: 'row', gap: Spacing.sm }}>
              {SCREEN_PRESETS.map(p => (
                <TouchableOpacity
                  key={p.key}
                  style={[
                    s.screenerChip,
                    active === p.key && { backgroundColor: p.color + '15', borderColor: p.color + '40' }
                  ]}
                  onPress={() => loadPreset(p.key)}
                >
                  <Text style={[s.screenerChipText, active === p.key && { color: p.color }]}>
                    {p.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </ScrollView>

          {!active && (
            <EmptyState icon="◆" title="SELECT A SCREENER" subtitle="Choose a preset above to scan 2,600+ NSE stocks" />
          )}

          {loading && <AIProcessing label={`Scanning ${activePreset?.label}`} />}

          {!loading && stocks.length > 0 && (
            <View style={s.groupCard}>
              <View style={{ padding: Spacing.md, borderBottomWidth: 1, borderBottomColor: Colors.border }}>
                <Text style={{ fontSize: FontSize.xxs, fontWeight: FontWeight.bold, color: Colors.accent, letterSpacing: 1.2 }}>
                  {stocks.length} STOCKS
                </Text>
              </View>
              {stocks.map(st => (
                <ScreenStockRow key={st.symbol} stock={st} />
              ))}
            </View>
          )}
        </>
      )}
      <Text style={s.disclaimer}>Not SEBI registered. Educational only.</Text>
    </View>
  )
}

function ScreenStockRow({ stock }: { stock: ScreenerStock }) {
  const change = stock.today_change_pct ?? stock.change_pct
  const color = (change ?? 0) > 0 ? Colors.positive : (change ?? 0) < 0 ? Colors.negative : Colors.textMuted
  return (
    <View style={s.screenRow}>
      <View style={s.screenSymBox}>
        <Text style={s.screenSym}>{stock.symbol?.replace('.NS', '')}</Text>
      </View>
      <View style={{ flex: 1 }}>
        <Text style={s.screenName} numberOfLines={1}>{stock.company_name}</Text>
        <Text style={s.screenSector} numberOfLines={1}>{stock.sector}</Text>
      </View>
      <View style={{ alignItems: 'flex-end' }}>
        {stock.current_price != null && (
          <Text style={[s.screenPrice, MonoStyle]}>₹{stock.current_price.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</Text>
        )}
        {change != null && (
          <Text style={[s.screenChange, { color }, MonoStyle]}>{change >= 0 ? '+' : ''}{change.toFixed(2)}%</Text>
        )}
      </View>
    </View>
  )
}

const TABS = [
  { key: 'overview' as Tab,  label: 'Overview' },
  { key: 'breakouts' as Tab, label: 'Breakouts' },
  { key: 'sectors' as Tab,   label: 'Sectors' },
  { key: 'screener' as Tab,  label: 'Screener' },
]

export default function MarketsScreen() {
  const [tab, setTab] = useState<Tab>('overview')
  const [markets, setMarkets] = useState<GlobalMarketsResult | null>(null)
  const [breakouts, setBreakouts] = useState<BreakoutStock[]>([])
  const [sectors, setSectors] = useState<SectorLive[]>([])
  const [loading, setLoading] = useState({ overview: true, breakouts: true, sectors: true })
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(async () => {
    // Fire all in parallel
    const [m, b, s] = await Promise.allSettled([
      apiGlobalMarkets(),
      apiBreakouts(),
      apiSectorsLive(),
    ])

    if (m.status === 'fulfilled') setMarkets(m.value)
    setLoading(p => ({ ...p, overview: false }))

    if (b.status === 'fulfilled') {
      const res = b.value as any
      setBreakouts(Array.isArray(res) ? res : (res?.stocks ?? []))
    }
    setLoading(p => ({ ...p, breakouts: false }))

    if (s.status === 'fulfilled') setSectors(s.value)
    setLoading(p => ({ ...p, sectors: false }))

    setRefreshing(false)
  }, [])

  useEffect(() => { load() }, [load])

  const onRefresh = useCallback(() => {
    setRefreshing(true)
    clearAllCache()
    setLoading({ overview: true, breakouts: true, sectors: true })
    load()
  }, [load])

  return (
    <SafeAreaView style={s.safe} edges={['top']}>
      {/* ── Fixed Header ──────────────────────────────────────── */}
      <View style={s.header}>
        <Text style={s.headerTitle}>MARKETS</Text>
        {markets && (
          <View style={[s.impactBadge, {
            backgroundColor: markets.impact_score === 'BULLISH' ? Colors.positiveDim
              : markets.impact_score === 'BEARISH' ? Colors.negativeDim : Colors.bgElevated,
            borderColor: markets.impact_score === 'BULLISH' ? Colors.positiveBorder
              : markets.impact_score === 'BEARISH' ? Colors.negativeBorder : Colors.border,
          }]}>
            <Text style={[s.impactText, {
              color: markets.impact_score === 'BULLISH' ? Colors.positive
                : markets.impact_score === 'BEARISH' ? Colors.negative : Colors.textMuted,
            }]}>
              GLOBAL {markets.impact_score}
            </Text>
          </View>
        )}
      </View>

      {/* ── Tab Selector ──────────────────────────────────────── */}
      <View style={s.tabWrap}>
        <TabSelector tabs={TABS} active={tab} onSelect={setTab} />
      </View>

      {/* ── Content ───────────────────────────────────────────── */}
      <ScrollView
        style={s.scroll}
        contentContainerStyle={s.content}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.accent} />
        }
      >
        {tab === 'overview' && (
          <OverviewTab markets={markets} loading={loading.overview} />
        )}
        {tab === 'breakouts' && (
          <BreakoutsTab stocks={breakouts} loading={loading.breakouts} />
        )}
        {tab === 'sectors' && (
          <SectorsTab sectors={sectors} loading={loading.sectors} />
        )}
        {tab === 'screener' && <ScreenerTab />}

        {tab !== 'screener' && (
          <Text style={s.disclaimer}>
            Market data may be delayed up to 15 minutes. Not SEBI registered. Educational only.
          </Text>
        )}
      </ScrollView>
    </SafeAreaView>
  )
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.bg },
  scroll: { flex: 1 },
  content: { padding: Spacing.xl, paddingBottom: 40 },

  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: Spacing.xl, paddingTop: Spacing.xl, paddingBottom: Spacing.lg,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  headerTitle: {
    fontSize: FontSize.h1, fontWeight: FontWeight.black,
    color: Colors.textPrimary, letterSpacing: -0.5,
  },
  impactBadge: {
    paddingHorizontal: Spacing.md, paddingVertical: 5,
    borderRadius: Radius.full, borderWidth: 1,
  },
  impactText: { fontSize: FontSize.xxs, fontWeight: FontWeight.bold, letterSpacing: 0.8 },

  tabWrap: { paddingHorizontal: Spacing.xl, paddingVertical: Spacing.md },

  // Group blocks
  groupBlock: { marginBottom: Spacing.xl },
  groupLabel: {
    flexDirection: 'row', alignItems: 'center', gap: Spacing.sm,
    marginBottom: Spacing.sm,
  },
  groupIcon: { fontSize: 12 },
  groupLabelText: {
    fontSize: FontSize.xxs, fontWeight: FontWeight.bold,
    color: Colors.textMuted, letterSpacing: 1.5,
  },
  groupCard: {
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.lg, borderWidth: 1, borderColor: Colors.border,
    paddingHorizontal: Spacing.lg, overflow: 'hidden',
  },

  // Breakout
  breakoutHeader: {
    paddingVertical: Spacing.md,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  breakoutHeaderText: {
    fontSize: FontSize.xxs, fontWeight: FontWeight.bold,
    color: Colors.accent, letterSpacing: 1.5,
  },
  breakoutRow: {
    flexDirection: 'row', alignItems: 'center',
    paddingVertical: Spacing.md,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  breakoutNum: {
    fontSize: FontSize.xxs, color: Colors.accent, fontWeight: FontWeight.bold,
    width: 24, letterSpacing: 0.5,
  },
  breakoutMid: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  breakoutSymWrap: {
    paddingHorizontal: Spacing.sm, paddingVertical: 3,
    backgroundColor: Colors.bgElevated, borderRadius: Radius.xs,
  },
  breakoutSym: {
    fontSize: FontSize.xxs, fontWeight: FontWeight.black,
    color: Colors.textPrimary, letterSpacing: 0.5,
  },
  breakoutName: {
    fontSize: FontSize.xs, color: Colors.textSecondary, flex: 1,
  },
  breakoutRight: { alignItems: 'flex-end' },
  breakoutPrice: {
    fontSize: FontSize.sm, fontWeight: FontWeight.semibold,
    color: Colors.textPrimary, marginBottom: 2,
  },
  breakoutMetrics: { flexDirection: 'row', gap: Spacing.sm },
  breakoutMeta: {
    fontSize: FontSize.xxs, color: Colors.textMuted,
    backgroundColor: Colors.bgElevated, paddingHorizontal: 5,
    paddingVertical: 2, borderRadius: Radius.xs,
  },
  breakoutDisclaimer: {
    fontSize: FontSize.xxs, color: Colors.textDisabled,
    paddingVertical: Spacing.md, textAlign: 'center',
  },

  // Sector
  sectorRow: {
    paddingVertical: Spacing.md,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  sectorMain: { flexDirection: 'row', alignItems: 'center', gap: Spacing.md },
  sectorName: {
    fontSize: FontSize.sm, fontWeight: FontWeight.semibold,
    color: Colors.textPrimary, marginBottom: 5,
  },
  sectorBarTrack: {
    height: 2, backgroundColor: Colors.bgElevated, borderRadius: 1,
    overflow: 'hidden',
  },
  sectorBar: { height: 2, borderRadius: 1, minWidth: 4 },
  sectorRight: { alignItems: 'flex-end', gap: 4, minWidth: 80 },
  sectorPct: {
    fontSize: FontSize.base, fontWeight: FontWeight.bold,
  },
  sectorPerf: {
    flexDirection: 'row', marginTop: Spacing.sm, gap: Spacing.xl,
  },
  perfCell: { alignItems: 'center', gap: 2 },
  perfVal: { fontSize: FontSize.xxs, fontWeight: FontWeight.semibold },
  perfLabel: { fontSize: FontSize.xxs, color: Colors.textMuted },

  moversSection: {
    marginTop: Spacing.md, paddingTop: Spacing.md,
    borderTopWidth: 1, borderTopColor: Colors.border,
  },
  moversLabel: {
    fontSize: FontSize.xxs, color: Colors.textMuted, fontWeight: FontWeight.bold,
    letterSpacing: 1, marginBottom: Spacing.sm,
  },
  moverRow: {
    flexDirection: 'row', alignItems: 'center',
    paddingVertical: 5, gap: Spacing.sm,
  },
  moverSym: {
    fontSize: FontSize.xs, fontWeight: FontWeight.bold,
    color: Colors.textPrimary, width: 70,
  },
  moverName: { flex: 1, fontSize: FontSize.xs, color: Colors.textSecondary },
  moverChg: { fontSize: FontSize.xs, fontWeight: FontWeight.semibold },

  disclaimer: {
    fontSize: FontSize.xxs, color: Colors.textDisabled,
    textAlign: 'center', marginTop: Spacing.xl, lineHeight: 16,
  },

  // Screener inline
  screenerSearch: { marginBottom: Spacing.lg },
  screenerInput: {
    backgroundColor: Colors.bgCard, borderRadius: Radius.md,
    borderWidth: 1, borderColor: Colors.border,
    paddingHorizontal: Spacing.md, paddingVertical: Spacing.md,
    fontSize: FontSize.sm, color: Colors.textPrimary,
  },
  screenerChip: {
    paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm,
    backgroundColor: Colors.bgCard, borderRadius: Radius.full,
    borderWidth: 1, borderColor: Colors.border,
  },
  screenerChipText: {
    fontSize: FontSize.xs, color: Colors.textMuted, fontWeight: FontWeight.semibold,
  },
  screenRow: {
    flexDirection: 'row', alignItems: 'center',
    padding: Spacing.md,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  screenSymBox: {
    width: 50, height: 32, borderRadius: Radius.sm,
    backgroundColor: Colors.bgElevated, borderWidth: 1, borderColor: Colors.border,
    alignItems: 'center', justifyContent: 'center', marginRight: Spacing.md,
  },
  screenSym: { fontSize: FontSize.xxs, fontWeight: FontWeight.black, color: Colors.accent, letterSpacing: 0.5 },
  screenName: { fontSize: FontSize.sm, fontWeight: FontWeight.semibold, color: Colors.textPrimary, marginBottom: 2 },
  screenSector: { fontSize: FontSize.xxs, color: Colors.textMuted },
  screenPrice: { fontSize: FontSize.sm, fontWeight: FontWeight.bold, color: Colors.textPrimary, marginBottom: 2 },
  screenChange: { fontSize: FontSize.xxs, fontWeight: FontWeight.semibold },
})
