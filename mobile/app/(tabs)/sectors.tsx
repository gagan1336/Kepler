import { useState, useCallback, useEffect } from 'react'
import {
  View, Text, FlatList, StyleSheet, TouchableOpacity,
  RefreshControl, ActivityIndicator, ScrollView,
} from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import { apiSectorsLive, apiSectorReports, SectorLive, SectorReport } from '@/lib/api'
import { Colors, FontSize, Radius, Spacing } from '@/constants/theme'

type Tab = 'live' | 'reports'
type SortKey = '1D' | '1W' | '1M' | 'RS'

const SENTIMENT_CFG: Record<string, { color: string; bg: string }> = {
  BULLISH: { color: '#10b981', bg: 'rgba(16,185,129,0.12)' },
  BEARISH: { color: '#ef4444', bg: 'rgba(239,68,68,0.12)' },
  MIXED:   { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)' },
}

function pctColor(v: number) { return v > 0 ? '#10b981' : v < 0 ? '#ef4444' : '#64748b' }
function sign(v: number) { return v >= 0 ? '+' : '' }

function HeatBar({ value, max = 3 }: { value: number; max?: number }) {
  const clamp = Math.max(-max, Math.min(max, value))
  const pct = ((clamp + max) / (2 * max)) * 100
  return (
    <View style={heat.track}>
      <View style={heat.midLine} />
      <View style={[heat.bar, {
        left: pct > 50 ? '50%' : `${pct}%`,
        right: pct > 50 ? `${100 - pct}%` : '50%',
        backgroundColor: pct > 50 ? '#10b981' : '#ef4444',
      }]} />
    </View>
  )
}

function SectorCard({ item }: { item: SectorLive }) {
  const [expanded, setExpanded] = useState(false)
  const cfg = SENTIMENT_CFG[item.sentiment] ?? SENTIMENT_CFG.MIXED

  return (
    <TouchableOpacity style={styles.card} onPress={() => setExpanded(e => !e)} activeOpacity={0.85}>
      <View style={styles.sectorHeader}>
        <View style={{ flex: 1 }}>
          <Text style={styles.sectorName}>{item.name}</Text>
          <View style={[styles.sentBadge, { backgroundColor: cfg.bg, borderColor: cfg.color + '40' }]}>
            <Text style={[styles.sentText, { color: cfg.color }]}>{item.sentiment}</Text>
          </View>
        </View>
        <View style={styles.pctCol}>
          <Text style={[styles.pct1D, { color: pctColor(item.day_pct) }]}>
            {sign(item.day_pct)}{item.day_pct.toFixed(2)}%
          </Text>
          <Text style={styles.pct1DLabel}>1D</Text>
        </View>
        <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={16} color={Colors.textMuted} style={{ marginLeft: 8 }} />
      </View>

      {/* Performance bars */}
      <View style={styles.perfRow}>
        {[
          { label: '1W', v: item.week_pct },
          { label: '1M', v: item.month_pct },
          { label: 'YTD', v: item.ytd_pct },
          { label: 'RS', v: item.rs_nifty },
        ].map(({ label, v }) => (
          <View key={label} style={styles.perfCell}>
            <Text style={[styles.perfVal, { color: pctColor(v) }]}>{sign(v)}{v.toFixed(1)}%</Text>
            <Text style={styles.perfLabel}>{label}</Text>
          </View>
        ))}
      </View>

      <HeatBar value={item.day_pct} />

      {expanded && (
        <>
          {/* Top movers */}
          {item.top_movers?.length > 0 && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Top Movers</Text>
              {item.top_movers.slice(0, 4).map(m => (
                <View key={m.symbol} style={styles.moverRow}>
                  <Text style={styles.moverSymbol}>{m.symbol}</Text>
                  <Text style={styles.moverName} numberOfLines={1}>{m.name}</Text>
                  <Text style={[styles.moverChg, { color: pctColor(m.change_pct) }]}>
                    {sign(m.change_pct)}{m.change_pct.toFixed(2)}%
                  </Text>
                </View>
              ))}
            </View>
          )}

          {/* News */}
          {item.news?.length > 0 && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Sector News</Text>
              {item.news.slice(0, 3).map((n, i) => (
                <View key={i} style={styles.newsItem}>
                  <View style={[styles.impDot, {
                    backgroundColor: n.impact === 'HIGH' ? '#ef4444' : n.impact === 'MEDIUM' ? '#f59e0b' : '#64748b'
                  }]} />
                  <Text style={styles.newsTitle} numberOfLines={2}>{n.title}</Text>
                </View>
              ))}
            </View>
          )}
        </>
      )}
    </TouchableOpacity>
  )
}

function SectorReportCard({ item }: { item: SectorReport }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <TouchableOpacity style={styles.card} onPress={() => setExpanded(e => !e)} activeOpacity={0.85}>
      <View style={styles.reportHeader}>
        <Text style={styles.reportSector}>{item.sector_name ?? 'Sector Report'}</Text>
        <Text style={styles.reportDate}>{new Date(item.date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}</Text>
        <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={14} color={Colors.textMuted} />
      </View>
      {item.content && (
        <Text style={styles.reportContent} numberOfLines={expanded ? undefined : 3}>
          {item.content}
        </Text>
      )}
      {!expanded && <Text style={styles.tapHint}>Tap to read full analysis →</Text>}
    </TouchableOpacity>
  )
}

export default function SectorsScreen() {
  const [tab, setTab] = useState<Tab>('live')
  const [sectors, setSectors] = useState<SectorLive[]>([])
  const [reports, setReports] = useState<SectorReport[]>([])
  const [sort, setSort] = useState<SortKey>('1D')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(async () => {
    try {
      if (tab === 'live') {
        const data = await apiSectorsLive()
        setSectors(data)
      } else {
        const data = await apiSectorReports(20)
        setReports(data)
      }
    } catch (e) {
      console.log('Sectors error', e)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [tab])

  useEffect(() => { setLoading(true); load() }, [load])

  const sortOptions: { key: SortKey; label: string }[] = [
    { key: '1D', label: '1D' }, { key: '1W', label: '1W' },
    { key: '1M', label: '1M' }, { key: 'RS', label: 'RS' },
  ]

  const sortedSectors = [...sectors].sort((a, b) => {
    switch (sort) {
      case '1D': return b.day_pct - a.day_pct
      case '1W': return b.week_pct - a.week_pct
      case '1M': return b.month_pct - a.month_pct
      case 'RS': return b.rs_nifty - a.rs_nifty
      default: return 0
    }
  })

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Sectors</Text>
      </View>

      <View style={styles.mainTabRow}>
        {[{ id: 'live', label: '📊 Live Heatmap' }, { id: 'reports', label: '📝 AI Reports' }].map(t => (
          <TouchableOpacity
            key={t.id}
            style={[styles.mainTabBtn, tab === t.id && styles.mainTabBtnActive]}
            onPress={() => setTab(t.id as Tab)}
          >
            <Text style={[styles.mainTabText, tab === t.id && styles.mainTabTextActive]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {tab === 'live' && (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.sortBar} contentContainerStyle={styles.sortRow}>
          <Text style={styles.sortLabel}>Sort by:</Text>
          {sortOptions.map(s => (
            <TouchableOpacity
              key={s.key}
              style={[styles.sortBtn, sort === s.key && styles.sortBtnActive]}
              onPress={() => setSort(s.key)}
            >
              <Text style={[styles.sortBtnText, sort === s.key && styles.sortBtnTextActive]}>{s.label}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={Colors.accent} size="large" />
          <Text style={styles.loadingText}>Loading sector data…</Text>
        </View>
      ) : (
        <FlatList
          data={tab === 'live' ? sortedSectors : (reports as any[])}
          keyExtractor={(_, i) => String(i)}
          renderItem={({ item }) =>
            tab === 'live'
              ? <SectorCard item={item as SectorLive} />
              : <SectorReportCard item={item as SectorReport} />
          }
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load() }} tintColor={Colors.accent} />}
          contentContainerStyle={styles.list}
          ListEmptyComponent={
            <View style={styles.center}>
              <Text style={{ fontSize: 40 }}>🏭</Text>
              <Text style={styles.emptyTitle}>{tab === 'live' ? 'No live sector data' : 'No sector reports'}</Text>
              <Text style={styles.emptySub}>Data refreshes at market open (9:15 AM IST)</Text>
            </View>
          }
        />
      )}
    </SafeAreaView>
  )
}

const heat = StyleSheet.create({
  track: { height: 4, backgroundColor: Colors.border, borderRadius: 2, position: 'relative', marginTop: 8 },
  midLine: { position: 'absolute', left: '50%', top: 0, bottom: 0, width: 1, backgroundColor: Colors.textMuted },
  bar: { position: 'absolute', top: 0, bottom: 0, borderRadius: 2 },
})

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.bg },
  header: {
    paddingHorizontal: Spacing.xl, paddingVertical: Spacing.lg,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  headerTitle: { fontSize: FontSize.xl, fontWeight: '900', color: Colors.textPrimary },
  mainTabRow: {
    flexDirection: 'row', padding: Spacing.lg, gap: Spacing.sm,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  mainTabBtn: {
    flex: 1, paddingVertical: Spacing.sm, alignItems: 'center',
    borderRadius: Radius.md, borderWidth: 1, borderColor: Colors.border,
  },
  mainTabBtnActive: { borderColor: Colors.accentBorder, backgroundColor: Colors.accentDim },
  mainTabText: { fontSize: FontSize.sm, color: Colors.textMuted, fontWeight: '600' },
  mainTabTextActive: { color: Colors.accent },
  sortBar: { maxHeight: 44, borderBottomWidth: 1, borderBottomColor: Colors.border },
  sortRow: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: Spacing.lg, gap: Spacing.sm, paddingVertical: Spacing.sm },
  sortLabel: { fontSize: FontSize.xs, color: Colors.textMuted, marginRight: 4 },
  sortBtn: { paddingHorizontal: Spacing.md, paddingVertical: 4, borderRadius: Radius.sm, borderWidth: 1, borderColor: Colors.border },
  sortBtnActive: { borderColor: Colors.accentBorder, backgroundColor: Colors.accentDim },
  sortBtnText: { fontSize: FontSize.xs, color: Colors.textMuted, fontWeight: '600' },
  sortBtnTextActive: { color: Colors.accent },
  list: { padding: Spacing.lg, gap: Spacing.md, paddingBottom: Spacing.xxxl },
  card: {
    backgroundColor: Colors.bgCard, borderRadius: Radius.lg,
    borderWidth: 1, borderColor: Colors.border, padding: Spacing.lg, gap: Spacing.sm,
  },
  sectorHeader: { flexDirection: 'row', alignItems: 'center' },
  sectorName: { fontSize: FontSize.base, fontWeight: '800', color: Colors.textPrimary, marginBottom: 4 },
  sentBadge: {
    alignSelf: 'flex-start', paddingHorizontal: 8, paddingVertical: 2,
    borderRadius: Radius.sm, borderWidth: 1,
  },
  sentText: { fontSize: FontSize.xs, fontWeight: '700' },
  pctCol: { alignItems: 'flex-end', marginRight: 8 },
  pct1D: { fontSize: FontSize.lg, fontWeight: '900' },
  pct1DLabel: { fontSize: FontSize.xs, color: Colors.textMuted },
  perfRow: { flexDirection: 'row', gap: Spacing.sm },
  perfCell: { flex: 1, alignItems: 'center' },
  perfVal: { fontSize: FontSize.sm, fontWeight: '700' },
  perfLabel: { fontSize: FontSize.xs, color: Colors.textMuted },
  section: { marginTop: Spacing.sm, gap: Spacing.xs },
  sectionTitle: { fontSize: FontSize.xs, fontWeight: '800', color: Colors.textMuted, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 },
  moverRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, paddingVertical: 3 },
  moverSymbol: { fontSize: FontSize.sm, fontWeight: '800', color: Colors.textPrimary, width: 64 },
  moverName: { flex: 1, fontSize: FontSize.xs, color: Colors.textSecondary },
  moverChg: { fontSize: FontSize.sm, fontWeight: '700', minWidth: 60, textAlign: 'right' },
  newsItem: { flexDirection: 'row', gap: Spacing.sm, alignItems: 'flex-start', paddingVertical: 3 },
  impDot: { width: 8, height: 8, borderRadius: 4, marginTop: 5 },
  newsTitle: { flex: 1, fontSize: FontSize.xs, color: Colors.textSecondary, lineHeight: 16 },
  reportHeader: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  reportSector: { flex: 1, fontSize: FontSize.base, fontWeight: '800', color: Colors.textPrimary },
  reportDate: { fontSize: FontSize.xs, color: Colors.textMuted },
  reportContent: { fontSize: FontSize.sm, color: Colors.textSecondary, lineHeight: 20 },
  tapHint: { fontSize: FontSize.xs, color: Colors.accent },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: Spacing.md, padding: Spacing.xxxl },
  loadingText: { color: Colors.textSecondary, fontSize: FontSize.sm },
  emptyTitle: { fontSize: FontSize.lg, fontWeight: '700', color: Colors.textPrimary },
  emptySub: { fontSize: FontSize.sm, color: Colors.textMuted, textAlign: 'center' },
})
