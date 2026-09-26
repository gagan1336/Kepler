import { useState, useCallback } from 'react'
import {
  View, Text, FlatList, StyleSheet, TouchableOpacity,
  ActivityIndicator, ScrollView, TextInput,
} from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import {
  apiScreenerQuality, apiScreenerValue, apiScreenerDividend,
  apiScreenerSwing, apiStockSearch, ScreenerStock,
} from '@/lib/api'
import { RewardedAdGate } from '@/components/ads/RewardedAdGate'
import { Colors, FontSize, Radius, Spacing } from '@/constants/theme'

type ScreenTab = 'quality' | 'value' | 'dividend' | 'swing' | 'search'

const LOADERS: Record<ScreenTab, (() => Promise<any[]>) | null> = {
  quality:  apiScreenerQuality,
  value:    apiScreenerValue,
  dividend: apiScreenerDividend,
  swing:    apiScreenerSwing,
  search:   null,
}

const TAB_CFG = [
  { id: 'quality',  label: '💎 Quality',   desc: 'High ROCE, low debt, consistent growth' },
  { id: 'value',    label: '🏷️ Value',     desc: 'Undervalued stocks with strong fundamentals' },
  { id: 'dividend', label: '💰 Dividend',  desc: 'High yield, stable payout history' },
  { id: 'swing',    label: '📈 Swing',     desc: 'Technical setups for short-term trades' },
  { id: 'search',   label: '🔍 Search',    desc: 'Search any stock by name or symbol' },
]

function fmt(v: any, suffix = '') { return v == null ? '—' : `${Number(v).toFixed(1)}${suffix}` }
function fmtCr(v: number | null | undefined) {
  if (v == null) return '—'
  if (v >= 100000) return `₹${(v / 100000).toFixed(1)}L Cr`
  if (v >= 1000) return `₹${(v / 1000).toFixed(1)}K Cr`
  return `₹${Math.round(v)} Cr`
}
function scoreColor(s?: number) {
  if (s == null) return Colors.textMuted
  if (s >= 75) return '#10b981'
  if (s >= 55) return '#3b82f6'
  if (s >= 35) return '#f59e0b'
  return '#ef4444'
}
function chgColor(v?: number | null) { return (v ?? 0) >= 0 ? '#10b981' : '#ef4444' }

function StockRow({ stock }: { stock: ScreenerStock }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <TouchableOpacity style={styles.stockRow} onPress={() => setExpanded(e => !e)} activeOpacity={0.8}>
      <View style={styles.stockMain}>
        <View style={{ flex: 1 }}>
          <Text style={styles.symbol}>{stock.symbol}</Text>
          <Text style={styles.stockName} numberOfLines={1}>{stock.name}</Text>
        </View>
        <View style={styles.stockRight}>
          {stock.price != null && <Text style={styles.price}>₹{stock.price.toFixed(1)}</Text>}
          {stock.change_pct != null && (
            <Text style={[styles.chg, { color: chgColor(stock.change_pct) }]}>
              {stock.change_pct >= 0 ? '+' : ''}{stock.change_pct.toFixed(2)}%
            </Text>
          )}
        </View>
        {stock.score != null && (
          <View style={[styles.scoreBadge, { borderColor: scoreColor(stock.score) + '60' }]}>
            <Text style={[styles.scoreVal, { color: scoreColor(stock.score) }]}>{Math.round(stock.score)}</Text>
          </View>
        )}
        <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={14} color={Colors.textMuted} />
      </View>

      {expanded && (
        <View style={styles.details}>
          <View style={styles.detailGrid}>
            {[
              { l: 'Mkt Cap', v: fmtCr(stock.market_cap_cr) },
              { l: 'Sector', v: stock.sector ?? '—' },
              { l: 'P/E', v: fmt(stock.pe_ratio) },
              { l: 'P/B', v: fmt(stock.pb_ratio) },
              { l: 'ROE', v: fmt(stock.roe, '%') },
              { l: 'ROCE', v: fmt(stock.roce, '%') },
              { l: 'D/E', v: fmt(stock.debt_equity) },
              { l: 'Rev CAGR 3Y', v: fmt(stock.revenue_growth_3y, '%') },
              { l: 'PAT CAGR 3Y', v: fmt(stock.profit_growth_3y, '%') },
              { l: 'Div Yield', v: fmt(stock.dividend_yield, '%') },
            ].map(({ l, v }) => (
              <View key={l} style={styles.detailCell}>
                <Text style={styles.detailLabel}>{l}</Text>
                <Text style={styles.detailValue}>{v}</Text>
              </View>
            ))}
          </View>
        </View>
      )}
    </TouchableOpacity>
  )
}

export default function ScreenerScreen() {
  const [tab, setTab] = useState<ScreenTab>('quality')
  const [stocks, setStocks] = useState<ScreenerStock[]>([])
  const [loading, setLoading] = useState(false)
  const [loaded, setLoaded] = useState<string>('')
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)

  const runScreener = useCallback(async (t: ScreenTab) => {
    const loader = LOADERS[t]
    if (!loader) return
    if (loaded === t) return // already loaded
    setLoading(true)
    try {
      const data = await loader()
      setStocks(data)
      setLoaded(t)
    } catch (e: any) {
      console.log('Screener error', e)
      setStocks([])
    } finally {
      setLoading(false)
    }
  }, [loaded])

  const onTabChange = (t: ScreenTab) => {
    setTab(t)
    setStocks([])
    setLoaded('')
    if (t !== 'search') runScreener(t)
  }

  const doSearch = async () => {
    if (!query.trim()) return
    setSearching(true)
    try {
      const results = await apiStockSearch(query.trim())
      setStocks(results)
    } catch {
      setStocks([])
    } finally {
      setSearching(false)
    }
  }

  const currentTab = TAB_CFG.find(t => t.id === tab)!

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Stock Screener</Text>
        {loaded === tab && stocks.length > 0 && (
          <Text style={styles.resultCount}>{stocks.length} stocks</Text>
        )}
      </View>

      {/* Tab scroll */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.tabScroll} contentContainerStyle={styles.tabRow}>
        {TAB_CFG.map(t => (
          <TouchableOpacity
            key={t.id}
            style={[styles.tabBtn, tab === t.id && styles.tabBtnActive]}
            onPress={() => onTabChange(t.id as ScreenTab)}
          >
            <Text style={[styles.tabText, tab === t.id && styles.tabTextActive]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Description */}
      <View style={styles.descBar}>
        <Text style={styles.descText}>{currentTab.desc}</Text>
        {tab !== 'search' && loaded !== tab && !loading && (
          <TouchableOpacity onPress={() => runScreener(tab)} style={styles.runBtn}>
            <Ionicons name="play" size={12} color={Colors.bg} />
            <Text style={styles.runBtnText}>Run Screen</Text>
          </TouchableOpacity>
        )}
      </View>

      <RewardedAdGate feature="Stock Screener" onUnlocked={() => { if (tab !== 'search') runScreener(tab) }}>
        <>
          {/* Search input */}
          {tab === 'search' && (
            <View style={styles.searchBar}>
              <TextInput
                style={styles.searchInput}
                placeholder="Search by symbol or company name…"
                placeholderTextColor={Colors.textMuted}
                value={query}
                onChangeText={setQuery}
                onSubmitEditing={doSearch}
                returnKeyType="search"
              />
              <TouchableOpacity style={styles.searchBtn} onPress={doSearch}>
                {searching
                  ? <ActivityIndicator size="small" color={Colors.bg} />
                  : <Ionicons name="search" size={18} color={Colors.bg} />
                }
              </TouchableOpacity>
            </View>
          )}

          {/* Loading */}
          {(loading || searching) && (
            <View style={styles.center}>
              <ActivityIndicator color={Colors.accent} size="large" />
              <Text style={styles.loadingText}>Running screener… this may take a moment</Text>
            </View>
          )}

          {/* Results */}
          {!loading && !searching && (
            <FlatList
              data={stocks}
              keyExtractor={(item, i) => item.symbol ?? String(i)}
              renderItem={({ item }) => <StockRow stock={item} />}
              contentContainerStyle={styles.list}
              ItemSeparatorComponent={() => <View style={styles.separator} />}
              ListEmptyComponent={
                loaded === tab || (tab === 'search' && query) ? (
                  <View style={styles.center}>
                    <Text style={{ fontSize: 36 }}>📭</Text>
                    <Text style={styles.emptyTitle}>No results found</Text>
                  </View>
                ) : (
                  <View style={styles.center}>
                    <Text style={{ fontSize: 48 }}>⚡</Text>
                    <Text style={styles.emptyTitle}>Tap "Run Screen" to start</Text>
                    <Text style={styles.emptySub}>Screens 2,600+ NSE-listed stocks using Kepler AI</Text>
                  </View>
                )
              }
            />
          )}
        </>
      </RewardedAdGate>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.bg },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: Spacing.xl, paddingVertical: Spacing.lg,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  headerTitle: { fontSize: FontSize.xl, fontWeight: '900', color: Colors.textPrimary },
  resultCount: { fontSize: FontSize.sm, color: Colors.textMuted },
  tabScroll: { maxHeight: 50, borderBottomWidth: 1, borderBottomColor: Colors.border },
  tabRow: { flexDirection: 'row', paddingHorizontal: Spacing.lg, paddingVertical: Spacing.sm, gap: Spacing.sm },
  tabBtn: {
    paddingHorizontal: Spacing.lg, paddingVertical: 6,
    borderRadius: Radius.full, borderWidth: 1, borderColor: Colors.border,
  },
  tabBtnActive: { borderColor: Colors.accentBorder, backgroundColor: Colors.accentDim },
  tabText: { fontSize: FontSize.sm, color: Colors.textMuted, fontWeight: '600' },
  tabTextActive: { color: Colors.accent },
  descBar: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: Spacing.xl, paddingVertical: Spacing.md,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  descText: { flex: 1, fontSize: FontSize.sm, color: Colors.textSecondary },
  runBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: Colors.accent, paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm, borderRadius: Radius.full,
  },
  runBtnText: { fontSize: FontSize.xs, fontWeight: '700', color: Colors.bg },
  searchBar: {
    flexDirection: 'row', margin: Spacing.lg,
    backgroundColor: Colors.bgCard, borderRadius: Radius.lg,
    borderWidth: 1, borderColor: Colors.border, overflow: 'hidden',
  },
  searchInput: {
    flex: 1, paddingHorizontal: Spacing.lg, paddingVertical: Spacing.md,
    fontSize: FontSize.base, color: Colors.textPrimary,
  },
  searchBtn: {
    backgroundColor: Colors.accent, paddingHorizontal: Spacing.lg, alignItems: 'center', justifyContent: 'center',
  },
  list: { paddingHorizontal: Spacing.lg, paddingBottom: Spacing.xxxl },
  stockRow: {
    paddingVertical: Spacing.md,
  },
  stockMain: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  symbol: { fontSize: FontSize.base, fontWeight: '800', color: Colors.textPrimary },
  stockName: { fontSize: FontSize.xs, color: Colors.textSecondary, marginTop: 2 },
  stockRight: { alignItems: 'flex-end' },
  price: { fontSize: FontSize.sm, fontWeight: '700', color: Colors.textPrimary },
  chg: { fontSize: FontSize.xs, fontWeight: '600' },
  scoreBadge: {
    width: 40, height: 40, borderRadius: 20, borderWidth: 2,
    alignItems: 'center', justifyContent: 'center',
  },
  scoreVal: { fontSize: FontSize.sm, fontWeight: '900' },
  details: { marginTop: Spacing.sm },
  detailGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 4 },
  detailCell: {
    width: '30%', backgroundColor: Colors.bgCard, borderRadius: Radius.sm,
    padding: Spacing.sm, borderWidth: 1, borderColor: Colors.border,
  },
  detailLabel: { fontSize: FontSize.xs, color: Colors.textMuted },
  detailValue: { fontSize: FontSize.sm, fontWeight: '700', color: Colors.textPrimary, marginTop: 2 },
  separator: { height: 1, backgroundColor: Colors.border },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: Spacing.md, padding: Spacing.xxxl },
  loadingText: { color: Colors.textSecondary, fontSize: FontSize.sm, textAlign: 'center' },
  emptyTitle: { fontSize: FontSize.lg, fontWeight: '700', color: Colors.textPrimary, textAlign: 'center' },
  emptySub: { fontSize: FontSize.sm, color: Colors.textMuted, textAlign: 'center' },
})
