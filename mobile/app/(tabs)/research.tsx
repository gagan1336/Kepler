// ANTIGRAVITY — Screener Screen (Research Tab)
// Preset screeners + Search. Connects to existing 2,600+ stock backend.

import { useState, useCallback, useEffect, useRef } from 'react'
import {
  View, Text, ScrollView, StyleSheet, RefreshControl,
  TouchableOpacity, TextInput, FlatList, ActivityIndicator, Keyboard,
} from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import {
  apiScreenerQuality, apiScreenerValue, apiScreenerDividend,
  apiScreenerPreset, apiScreenerSwing, apiStockSearch,
  ScreenerStock, clearAllCache,
} from '@/lib/api'
import {
  SectionHeader, StockRow, SkeletonCard, EmptyState, ErrorState,
  AIProcessing, Divider,
} from '@/components/ui'
import { Colors, Spacing, Radius, FontSize, FontWeight, MonoStyle } from '@/constants/theme'

// ── Preset Definitions ────────────────────────────────────────────────────────

const PRESETS = [
  {
    key: 'quality',
    label: 'Quality',
    desc: 'Strong fundamentals, high ROE, low debt',
    icon: '◆',
    color: '#7C6CFF',
    fetch: () => apiScreenerQuality(),
    metric: (s: ScreenerStock) => s.roe != null ? `ROE ${s.roe.toFixed(1)}%` : undefined,
  },
  {
    key: 'value',
    label: 'Value',
    desc: 'Low PE/PB relative to sector peers',
    icon: '◇',
    color: '#22C55E',
    fetch: () => apiScreenerValue(),
    metric: (s: ScreenerStock) => s.pe_ratio != null ? `PE ${s.pe_ratio.toFixed(1)}x` : undefined,
  },
  {
    key: 'dividend',
    label: 'Dividend',
    desc: 'Consistent dividend payers with yield',
    icon: '○',
    color: '#F59E0B',
    fetch: () => apiScreenerDividend(),
    metric: (s: ScreenerStock) => s.dividend_yield != null ? `Yield ${(s.dividend_yield * 100).toFixed(2)}%` : undefined,
  },
  {
    key: 'momentum',
    label: 'Momentum',
    desc: 'Strong price momentum stocks',
    icon: '△',
    color: '#F43F5E',
    fetch: () => apiScreenerPreset('momentum'),
    metric: (s: ScreenerStock) => s.change_pct != null ? `52W ${s.change_pct > 0 ? '+' : ''}${s.change_pct.toFixed(1)}%` : undefined,
  },
  {
    key: 'swing_breakout',
    label: 'Swing',
    desc: 'Technical swing setups',
    icon: '⊿',
    color: '#14B8A6',
    fetch: () => apiScreenerSwing('breakout').then(r => r.stocks),
    metric: (s: ScreenerStock) => s.today_change_pct != null ? `${s.today_change_pct > 0 ? '+' : ''}${s.today_change_pct.toFixed(2)}%` : undefined,
  },
  {
    key: 'lowdebt',
    label: 'Low Debt',
    desc: 'Financially conservative companies',
    icon: '□',
    color: '#6366F1',
    fetch: () => apiScreenerPreset('lowdebt'),
    metric: (s: ScreenerStock) => s.debt_to_equity != null ? `D/E ${s.debt_to_equity.toFixed(2)}` : undefined,
  },
] as const

type PresetKey = typeof PRESETS[number]['key'] | 'search'

// ── Stock Detail Row ──────────────────────────────────────────────────────────

function StockDetailRow({ stock, metric }: { stock: ScreenerStock; metric?: string }) {
  const change = stock.today_change_pct ?? stock.change_pct
  const changeColor = (change ?? 0) > 0 ? Colors.positive : (change ?? 0) < 0 ? Colors.negative : Colors.textMuted

  return (
    <View style={s.stockRow}>
      <View style={s.stockSymBox}>
        <Text style={s.stockSym} numberOfLines={1}>{stock.symbol?.replace('.NS', '')}</Text>
      </View>
      <View style={s.stockMid}>
        <Text style={s.stockName} numberOfLines={1}>{stock.company_name}</Text>
        <Text style={s.stockSector} numberOfLines={1}>{stock.sector}</Text>
      </View>
      <View style={s.stockRight}>
        {stock.current_price != null && (
          <Text style={[s.stockPrice, MonoStyle]}>
            ₹{stock.current_price.toLocaleString('en-IN', { maximumFractionDigits: 2, minimumFractionDigits: 2 })}
          </Text>
        )}
        <View style={s.stockBottom}>
          {change != null && (
            <Text style={[s.stockChange, { color: changeColor }, MonoStyle]}>
              {change >= 0 ? '+' : ''}{change.toFixed(2)}%
            </Text>
          )}
          {metric && <Text style={s.stockMetric}>{metric}</Text>}
        </View>
      </View>
    </View>
  )
}

// ── Preset Card ───────────────────────────────────────────────────────────────

function PresetCard({
  preset, active, onPress,
}: {
  preset: typeof PRESETS[number]; active: boolean; onPress: () => void
}) {
  return (
    <TouchableOpacity
      style={[s.presetCard, active && { borderColor: preset.color, backgroundColor: preset.color + '08' }]}
      onPress={onPress}
      activeOpacity={0.8}
    >
      <Text style={[s.presetIcon, { color: preset.color }]}>{preset.icon}</Text>
      <Text style={[s.presetLabel, active && { color: preset.color }]}>{preset.label}</Text>
      <Text style={s.presetDesc} numberOfLines={2}>{preset.desc}</Text>
    </TouchableOpacity>
  )
}

// ── Cap Formatter ─────────────────────────────────────────────────────────────

function formatCap(cr?: number | null) {
  if (cr == null) return '—'
  if (cr >= 100000) return `₹${(cr / 100000).toFixed(1)}L Cr`
  if (cr >= 1000)   return `₹${(cr / 1000).toFixed(1)}K Cr`
  return `₹${cr.toFixed(0)} Cr`
}

// ── Stock Card (expanded) ─────────────────────────────────────────────────────

function StockExpandedRow({ stock, metricFn }: { stock: ScreenerStock; metricFn?: (s: ScreenerStock) => string | undefined }) {
  const change = stock.today_change_pct ?? stock.change_pct
  const changeColor = (change ?? 0) > 0 ? Colors.positive : (change ?? 0) < 0 ? Colors.negative : Colors.textMuted
  const metric = metricFn ? metricFn(stock) : undefined

  const metrics = [
    stock.pe_ratio != null       && { l: 'PE',  v: stock.pe_ratio.toFixed(1) },
    stock.pb_ratio != null       && { l: 'PB',  v: stock.pb_ratio.toFixed(2) },
    stock.roe != null            && { l: 'ROE', v: `${stock.roe.toFixed(1)}%` },
    stock.market_cap_cr != null  && { l: 'CAP', v: formatCap(stock.market_cap_cr) },
  ].filter(Boolean) as { l: string; v: string }[]

  return (
    <View style={s.expandedRow}>
      <View style={s.expandedTop}>
        <View style={s.stockSymBox}>
          <Text style={s.stockSym} numberOfLines={1}>{stock.symbol?.replace('.NS', '')}</Text>
        </View>
        <View style={s.stockMid}>
          <Text style={s.stockName} numberOfLines={1}>{stock.company_name}</Text>
          <Text style={s.stockSector} numberOfLines={1}>{stock.sector}</Text>
        </View>
        <View style={s.stockRight}>
          {stock.current_price != null && (
            <Text style={[s.stockPrice, MonoStyle]}>
              ₹{stock.current_price.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
            </Text>
          )}
          {change != null && (
            <Text style={[s.stockChange, { color: changeColor }, MonoStyle]}>
              {change >= 0 ? '+' : ''}{change.toFixed(2)}%
            </Text>
          )}
        </View>
      </View>
      {metrics.length > 0 && (
        <View style={s.metricsRow}>
          {metrics.slice(0, 4).map(m => (
            <View key={m.l} style={s.metricCell}>
              <Text style={s.metricLabel}>{m.l}</Text>
              <Text style={[s.metricValue, MonoStyle]}>{m.v}</Text>
            </View>
          ))}
        </View>
      )}
    </View>
  )
}

// ── Main Screen ───────────────────────────────────────────────────────────────

export default function ScreenerScreen() {
  const [activePreset, setActivePreset] = useState<PresetKey | null>(null)
  const [stocks, setStocks]   = useState<ScreenerStock[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(false)
  const [query, setQuery]     = useState('')
  const [searchStocks, setSearchStocks] = useState<ScreenerStock[]>([])
  const [searching, setSearching]       = useState(false)
  const [refreshing, setRefreshing]     = useState(false)
  const searchTimeout = useRef<any>(null)

  const loadPreset = useCallback(async (key: PresetKey) => {
    if (key === 'search') return
    const preset = PRESETS.find(p => p.key === key)
    if (!preset) return
    setActivePreset(key)
    setStocks([])
    setLoading(true)
    setError(false)
    try {
      const result = await preset.fetch()
      setStocks(Array.isArray(result) ? result : [])
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  const handleSearch = useCallback((text: string) => {
    setQuery(text)
    clearTimeout(searchTimeout.current)
    if (!text.trim()) { setSearchStocks([]); return }
    setSearching(true)
    searchTimeout.current = setTimeout(async () => {
      try {
        const res = await apiStockSearch(text.trim())
        setSearchStocks(res)
      } catch { setSearchStocks([]) }
      finally { setSearching(false) }
    }, 400)
  }, [])

  const activePresetDef = PRESETS.find(p => p.key === activePreset)
  const isSearchMode = query.trim().length > 0

  return (
    <SafeAreaView style={s.safe} edges={['top']}>
      {/* Header */}
      <View style={s.header}>
        <Text style={s.headerTitle}>SCREENER</Text>
        <Text style={s.headerSub}>2,600+ NSE stocks</Text>
      </View>

      {/* Search */}
      <View style={s.searchWrap}>
        <View style={s.searchBar}>
          <Text style={s.searchIcon}>⊕</Text>
          <TextInput
            style={s.searchInput}
            placeholder="Search stocks, symbols..."
            placeholderTextColor={Colors.textMuted}
            value={query}
            onChangeText={handleSearch}
            autoCorrect={false}
            autoCapitalize="characters"
            returnKeyType="search"
          />
          {query.length > 0 && (
            <TouchableOpacity onPress={() => { setQuery(''); setSearchStocks([]) }}>
              <Text style={s.searchClear}>✕</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>

      {/* Search Results */}
      {isSearchMode ? (
        <ScrollView style={s.scroll} contentContainerStyle={s.content}>
          {searching ? (
            <AIProcessing label="Searching stocks" />
          ) : searchStocks.length > 0 ? (
            <View style={s.card}>
              <Text style={s.cardHeader}>{searchStocks.length} RESULTS</Text>
              {searchStocks.map((st, i) => (
                <StockDetailRow key={st.symbol} stock={st} />
              ))}
            </View>
          ) : (
            <EmptyState icon="◎" title="NO RESULTS" subtitle={`No stocks found for "${query}"`} />
          )}
        </ScrollView>
      ) : (
        <ScrollView
          style={s.scroll}
          contentContainerStyle={s.content}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => { clearAllCache(); if (activePreset) loadPreset(activePreset) }}
              tintColor={Colors.accent}
            />
          }
        >
          {/* Preset Grid */}
          {!activePreset && (
            <>
              <Text style={s.pickLabel}>WHAT ARE YOU LOOKING FOR?</Text>
              <View style={s.presetGrid}>
                {PRESETS.map(p => (
                  <View key={p.key} style={s.presetGridItem}>
                    <PresetCard
                      preset={p}
                      active={false}
                      onPress={() => loadPreset(p.key)}
                    />
                  </View>
                ))}
              </View>

              <Text style={s.disclaimer}>
                Screener scans 2,600+ NSE stocks via real-time fundamental data.{'\n'}
                First load may take 30–60 seconds. Not SEBI registered. Educational only.
              </Text>
            </>
          )}

          {/* Active Preset Results */}
          {activePreset && (
            <>
              {/* Preset selector chips */}
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.chipScroll}>
                <View style={s.chips}>
                  <TouchableOpacity style={s.backChip} onPress={() => { setActivePreset(null); setStocks([]) }}>
                    <Text style={s.backChipText}>← All</Text>
                  </TouchableOpacity>
                  {PRESETS.map(p => (
                    <TouchableOpacity
                      key={p.key}
                      style={[s.chip, activePreset === p.key && { backgroundColor: p.color + '15', borderColor: p.color + '40' }]}
                      onPress={() => loadPreset(p.key)}
                    >
                      <Text style={[s.chipText, activePreset === p.key && { color: p.color }]}>{p.label}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </ScrollView>

              {loading ? (
                <View style={{ paddingTop: Spacing.xl }}>
                  <AIProcessing label={`Scanning ${activePresetDef?.label} stocks`} />
                  <Text style={s.loadingNote}>
                    Analyzing 2,600+ stocks — this may take a moment
                  </Text>
                </View>
              ) : error ? (
                <ErrorState onRetry={() => activePreset && loadPreset(activePreset)} />
              ) : stocks.length > 0 ? (
                <View style={s.card}>
                  <View style={s.resultHeader}>
                    <Text style={s.cardHeader}>{stocks.length} STOCKS</Text>
                    {activePresetDef && (
                      <Text style={[s.cardHeaderSub, { color: activePresetDef.color }]}>
                        {activePresetDef.icon} {activePresetDef.label}
                      </Text>
                    )}
                  </View>
                  {stocks.map((st, i) => (
                    <StockExpandedRow
                      key={st.symbol}
                      stock={st}
                      metricFn={activePresetDef?.metric}
                    />
                  ))}
                </View>
              ) : (
                <EmptyState
                  icon="◎"
                  title="NO STOCKS FOUND"
                  subtitle="The screener found no stocks matching this filter right now."
                />
              )}

              <Text style={s.disclaimer}>
                Data from public market sources. Not SEBI registered. Educational only.
              </Text>
            </>
          )}
        </ScrollView>
      )}
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

  // Search
  searchWrap: { padding: Spacing.xl, paddingBottom: Spacing.md },
  searchBar: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: Colors.bgCard, borderRadius: Radius.md,
    borderWidth: 1, borderColor: Colors.border,
    paddingHorizontal: Spacing.md, paddingVertical: Spacing.md, gap: Spacing.sm,
  },
  searchIcon: { fontSize: 16, color: Colors.textMuted },
  searchInput: {
    flex: 1, fontSize: FontSize.sm, color: Colors.textPrimary,
    padding: 0, height: 20,
  },
  searchClear: { fontSize: 14, color: Colors.textMuted, padding: 4 },

  // Preset grid
  pickLabel: {
    fontSize: FontSize.xxs, fontWeight: FontWeight.bold,
    color: Colors.textMuted, letterSpacing: 1.5, marginBottom: Spacing.lg,
  },
  presetGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm },
  presetGridItem: { width: '48%' },
  presetCard: {
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.lg, borderWidth: 1, borderColor: Colors.border,
    padding: Spacing.lg, gap: 6,
  },
  presetIcon: { fontSize: 20 },
  presetLabel: {
    fontSize: FontSize.sm, fontWeight: FontWeight.bold,
    color: Colors.textPrimary, letterSpacing: 0.3,
  },
  presetDesc: { fontSize: FontSize.xs, color: Colors.textMuted, lineHeight: 16 },

  // Chips
  chipScroll: { marginBottom: Spacing.lg },
  chips: { flexDirection: 'row', gap: Spacing.sm, paddingRight: Spacing.xl },
  backChip: {
    paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm,
    backgroundColor: Colors.bgElevated, borderRadius: Radius.full,
    borderWidth: 1, borderColor: Colors.border,
  },
  backChipText: { fontSize: FontSize.xs, color: Colors.textSecondary, fontWeight: FontWeight.semibold },
  chip: {
    paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm,
    backgroundColor: Colors.bgCard, borderRadius: Radius.full,
    borderWidth: 1, borderColor: Colors.border,
  },
  chipText: { fontSize: FontSize.xs, color: Colors.textMuted, fontWeight: FontWeight.semibold },

  // Cards
  card: {
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.lg, borderWidth: 1, borderColor: Colors.border,
    overflow: 'hidden',
  },
  cardHeader: {
    fontSize: FontSize.xxs, fontWeight: FontWeight.bold,
    color: Colors.accent, letterSpacing: 1.5,
  },
  cardHeaderSub: { fontSize: FontSize.xs, fontWeight: FontWeight.semibold },
  resultHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    padding: Spacing.lg, borderBottomWidth: 1, borderBottomColor: Colors.border,
  },

  // Stock rows
  stockRow: {
    flexDirection: 'row', alignItems: 'center',
    padding: Spacing.md,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  expandedRow: {
    padding: Spacing.md,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  expandedTop: { flexDirection: 'row', alignItems: 'center', marginBottom: Spacing.sm },
  stockSymBox: {
    width: 52, height: 34, borderRadius: Radius.sm,
    backgroundColor: Colors.bgElevated, borderWidth: 1, borderColor: Colors.border,
    alignItems: 'center', justifyContent: 'center', marginRight: Spacing.md,
  },
  stockSym: {
    fontSize: FontSize.xxs, fontWeight: FontWeight.black,
    color: Colors.accent, letterSpacing: 0.5,
  },
  stockMid: { flex: 1 },
  stockName: {
    fontSize: FontSize.sm, fontWeight: FontWeight.semibold,
    color: Colors.textPrimary, marginBottom: 2,
  },
  stockSector: { fontSize: FontSize.xxs, color: Colors.textMuted },
  stockRight: { alignItems: 'flex-end' },
  stockPrice: {
    fontSize: FontSize.sm, fontWeight: FontWeight.bold,
    color: Colors.textPrimary, marginBottom: 2,
  },
  stockBottom: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  stockChange: { fontSize: FontSize.xxs, fontWeight: FontWeight.semibold },
  stockMetric: { fontSize: FontSize.xxs, color: Colors.textMuted },

  // Metrics row
  metricsRow: {
    flexDirection: 'row', gap: Spacing.xl, paddingLeft: 52 + Spacing.md,
  },
  metricCell: { gap: 2 },
  metricLabel: { fontSize: FontSize.xxs, color: Colors.textMuted, letterSpacing: 0.5 },
  metricValue: { fontSize: FontSize.xs, fontWeight: FontWeight.semibold, color: Colors.textSecondary },

  // Loading
  loadingNote: {
    fontSize: FontSize.xxs, color: Colors.textDisabled,
    textAlign: 'center', marginTop: Spacing.md,
  },

  disclaimer: {
    fontSize: FontSize.xxs, color: Colors.textDisabled,
    textAlign: 'center', marginTop: Spacing.xl, lineHeight: 16,
  },
})
