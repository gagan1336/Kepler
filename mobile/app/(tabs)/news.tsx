// ANTIGRAVITY — Discover Screen (News + Research)
// Tabs: News | Market Updates | Deep Dives

import { useState, useCallback, useEffect } from 'react'
import {
  View, Text, ScrollView, StyleSheet, RefreshControl,
  TouchableOpacity, FlatList, Linking,
} from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import {
  apiLiveNews, apiMarketUpdates, apiDeepDives,
  NewsItem, MarketUpdate, DeepDiveSafe, clearAllCache,
} from '@/lib/api'
import {
  SectionHeader, CategoryPill, SentimentBadge,
  SkeletonCard, SkeletonNewsItem, EmptyState, ErrorState, TabSelector, Divider,
} from '@/components/ui'
import { Colors, Spacing, Radius, FontSize, FontWeight, MonoStyle } from '@/constants/theme'

type Tab = 'news' | 'updates' | 'deepdives'

// ── Helpers ───────────────────────────────────────────────────────────────────

function timeAgo(isoStr?: string) {
  if (!isoStr) return ''
  const diff = Date.now() - new Date(isoStr).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

const SENT_COLOR: Record<string, string> = {
  POSITIVE: Colors.positive, NEGATIVE: Colors.negative,
  NEUTRAL: Colors.textMuted, BULLISH: Colors.positive, BEARISH: Colors.negative,
}

const IMPACT_COLOR: Record<string, string> = {
  HIGH: Colors.negative, MEDIUM: Colors.warning, LOW: Colors.textMuted,
}

const UPDATE_TYPE_COLOR: Record<string, string> = {
  RBI: '#3B82F6', SEBI: '#8B5CF6', GST: '#F59E0B',
  TAX: '#F59E0B', POLICY: '#14B8A6', OTHER: Colors.textMuted,
}

// ── News Card ─────────────────────────────────────────────────────────────────

function NewsCard({ item }: { item: NewsItem }) {
  const sentColor = SENT_COLOR[item.sentiment?.toUpperCase()] ?? Colors.textMuted

  const handlePress = () => {
    if (item.source_url) Linking.openURL(item.source_url).catch(() => {})
  }

  return (
    <TouchableOpacity style={s.newsCard} onPress={handlePress} activeOpacity={0.85}>
      {/* Top row */}
      <View style={s.newsTop}>
        <CategoryPill label={item.category ?? 'MARKET'} />
        <Text style={s.newsTime}>{timeAgo(item.published_at)}</Text>
      </View>

      {/* Headline */}
      <Text style={s.newsHeadline} numberOfLines={3}>{item.title}</Text>

      {/* Summary */}
      {item.summary && item.summary !== item.title && (
        <Text style={s.newsSummary} numberOfLines={2}>{item.summary}</Text>
      )}

      {/* Footer */}
      <View style={s.newsFooter}>
        <Text style={s.newsSource}>{item.source}</Text>
        <View style={s.newsSentRow}>
          <View style={[s.sentDot, { backgroundColor: sentColor }]} />
          <Text style={[s.sentLabel, { color: sentColor }]}>
            {item.sentiment ?? 'NEUTRAL'}
          </Text>
        </View>
      </View>
    </TouchableOpacity>
  )
}

// ── News Tab ──────────────────────────────────────────────────────────────────

function NewsTab({ news, loading }: { news: NewsItem[]; loading: boolean }) {
  if (loading) return (
    <View style={s.listPad}>
      {[1, 2, 3, 4, 5].map(i => (
        <View key={i} style={s.newsCard}>
          <SkeletonNewsItem />
        </View>
      ))}
    </View>
  )

  if (!news.length) return (
    <EmptyState icon="📰" title="NO NEWS RIGHT NOW" subtitle="Pull to refresh for the latest market news." />
  )

  // Group by category
  const cats = ['BREAKING', 'MARKETS', 'IPO', 'STOCKS', 'RBI', 'SEBI', 'GLOBAL']
  const catMap: Record<string, NewsItem[]> = {}
  news.forEach(n => {
    const cat = n.category ?? 'MARKETS'
    if (!catMap[cat]) catMap[cat] = []
    catMap[cat].push(n)
  })

  // Uncategorized goes to MARKETS
  const remaining = news.filter(n => !cats.includes(n.category ?? ''))
  if (remaining.length) {
    if (!catMap['MARKETS']) catMap['MARKETS'] = []
    catMap['MARKETS'].push(...remaining)
  }

  return (
    <View style={s.listPad}>
      {cats.filter(c => catMap[c]?.length).map(cat => (
        <View key={cat} style={s.catGroup}>
          <View style={s.catGroupHeader}>
            <Text style={s.catGroupLabel}>{cat}</Text>
            <Text style={s.catGroupCount}>{catMap[cat].length}</Text>
          </View>
          {catMap[cat].map((item, i) => <NewsCard key={item.id ?? i} item={item} />)}
        </View>
      ))}
    </View>
  )
}

// ── Market Update Card ────────────────────────────────────────────────────────

function UpdateCard({ item }: { item: MarketUpdate }) {
  const typeColor = UPDATE_TYPE_COLOR[item.update_type] ?? Colors.textMuted
  const impColor  = IMPACT_COLOR[item.importance] ?? Colors.textMuted

  return (
    <View style={s.updateCard}>
      <View style={s.updateHeader}>
        <View style={[s.updateTypeBadge, { borderColor: typeColor + '40', backgroundColor: typeColor + '15' }]}>
          <Text style={[s.updateTypeText, { color: typeColor }]}>{item.update_type}</Text>
        </View>
        <View style={[s.updateImpBadge, { borderColor: impColor + '40', backgroundColor: impColor + '15' }]}>
          <Text style={[s.updateImpText, { color: impColor }]}>{item.importance}</Text>
        </View>
        {item.effective_date && (
          <Text style={s.updateDate}>
            Effective: {item.effective_date}
          </Text>
        )}
      </View>
      <Text style={s.updateTitle} numberOfLines={3}>{item.title}</Text>
      {item.summary && <Text style={s.updateSummary} numberOfLines={4}>{item.summary}</Text>}
      {item.source && (
        <Text style={s.updateSource}>{item.source}</Text>
      )}
    </View>
  )
}

// ── Market Updates Tab ────────────────────────────────────────────────────────

function UpdatesTab({ updates, loading }: { updates: MarketUpdate[]; loading: boolean }) {
  if (loading) return (
    <View style={s.listPad}>
      {[1, 2, 3].map(i => <SkeletonCard key={i} height={120} />)}
    </View>
  )

  if (!updates.length) return (
    <EmptyState icon="🏛️" title="NO REGULATORY UPDATES" subtitle="RBI, SEBI, GST and policy updates will appear here." />
  )

  return (
    <View style={s.listPad}>
      {updates.map(u => <UpdateCard key={u.id} item={u} />)}
    </View>
  )
}

// ── Deep Dive Card ────────────────────────────────────────────────────────────

function DeepDiveCard({ item }: { item: DeepDiveSafe }) {
  const riskColor = item.risk_rating === 'LOW' ? Colors.positive
    : item.risk_rating === 'HIGH' ? Colors.negative : Colors.warning

  return (
    <View style={s.diveCard}>
      <View style={s.diveHeader}>
        {item.symbol && (
          <View style={s.diveSymBox}>
            <Text style={s.diveSym}>{item.symbol}</Text>
          </View>
        )}
        <View style={{ flex: 1 }}>
          <Text style={s.diveTier}>{item.tier?.toUpperCase() ?? 'RESEARCH'}</Text>
        </View>
        {item.risk_rating && (
          <View style={[s.riskBadge, { borderColor: riskColor + '40', backgroundColor: riskColor + '15' }]}>
            <Text style={[s.riskText, { color: riskColor }]}>{item.risk_rating} RISK</Text>
          </View>
        )}
      </View>
      <Text style={s.diveTitle} numberOfLines={2}>{item.title}</Text>
      {item.summary && (
        <Text style={s.diveSummary} numberOfLines={3}>{item.summary}</Text>
      )}
      {item.sector && <Text style={s.diveSector}>{item.sector}</Text>}
      {item.tags?.length > 0 && (
        <View style={s.tagRow}>
          {item.tags.slice(0, 4).map((tag, i) => (
            <View key={i} style={s.tag}>
              <Text style={s.tagText}>{tag}</Text>
            </View>
          ))}
        </View>
      )}
    </View>
  )
}

// ── Deep Dives Tab ────────────────────────────────────────────────────────────

function DeepDivesTab({ dives, loading }: { dives: DeepDiveSafe[]; loading: boolean }) {
  if (loading) return (
    <View style={s.listPad}>
      {[1, 2, 3].map(i => <SkeletonCard key={i} height={140} />)}
    </View>
  )

  if (!dives.length) return (
    <EmptyState icon="🔬" title="NO DEEP DIVES YET" subtitle="AI research reports on individual stocks will appear here." />
  )

  return (
    <View style={s.listPad}>
      {dives.map(d => <DeepDiveCard key={d.id} item={d} />)}
    </View>
  )
}

// ── Main Screen ───────────────────────────────────────────────────────────────

const TABS = [
  { key: 'news' as Tab,      label: 'News' },
  { key: 'updates' as Tab,   label: 'Regulatory' },
  { key: 'deepdives' as Tab, label: 'Deep Dives' },
]

export default function DiscoverScreen() {
  const [tab, setTab] = useState<Tab>('news')
  const [news, setNews]       = useState<NewsItem[]>([])
  const [updates, setUpdates] = useState<MarketUpdate[]>([])
  const [dives, setDives]     = useState<DeepDiveSafe[]>([])
  const [loading, setLoading] = useState({ news: true, updates: true, dives: true })
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(async () => {
    const [n, u, d] = await Promise.allSettled([
      apiLiveNews(40),
      apiMarketUpdates(20),
      apiDeepDives(1, 20),
    ])

    if (n.status === 'fulfilled') setNews(n.value)
    setLoading(p => ({ ...p, news: false }))

    if (u.status === 'fulfilled') setUpdates(u.value)
    setLoading(p => ({ ...p, updates: false }))

    if (d.status === 'fulfilled') setDives(d.value.deepdives)
    setLoading(p => ({ ...p, dives: false }))

    setRefreshing(false)
  }, [])

  useEffect(() => { load() }, [load])

  const onRefresh = useCallback(() => {
    setRefreshing(true)
    clearAllCache()
    setLoading({ news: true, updates: true, dives: true })
    load()
  }, [load])

  return (
    <SafeAreaView style={s.safe} edges={['top']}>
      <View style={s.header}>
        <Text style={s.headerTitle}>DISCOVER</Text>
      </View>

      <View style={s.tabWrap}>
        <TabSelector tabs={TABS} active={tab} onSelect={setTab} />
      </View>

      <ScrollView
        style={s.scroll}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.accent} />
        }
      >
        {tab === 'news'      && <NewsTab news={news} loading={loading.news} />}
        {tab === 'updates'   && <UpdatesTab updates={updates} loading={loading.updates} />}
        {tab === 'deepdives' && <DeepDivesTab dives={dives} loading={loading.dives} />}

        <Text style={s.disclaimer}>
          Not SEBI registered. For educational purposes only.
        </Text>
      </ScrollView>
    </SafeAreaView>
  )
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.bg },
  scroll: { flex: 1 },
  header: {
    paddingHorizontal: Spacing.xl, paddingTop: Spacing.xl, paddingBottom: Spacing.lg,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  headerTitle: {
    fontSize: FontSize.h1, fontWeight: FontWeight.black,
    color: Colors.textPrimary, letterSpacing: -0.5,
  },
  tabWrap: { paddingHorizontal: Spacing.xl, paddingVertical: Spacing.md },
  listPad: { paddingHorizontal: Spacing.xl, paddingBottom: 40 },

  // News Card
  newsCard: {
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.lg, borderWidth: 1, borderColor: Colors.border,
    padding: Spacing.lg, marginBottom: Spacing.sm,
  },
  newsTop: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, marginBottom: Spacing.sm },
  newsTime: { fontSize: FontSize.xxs, color: Colors.textMuted, marginLeft: 'auto' },
  newsHeadline: {
    fontSize: FontSize.sm, fontWeight: FontWeight.semibold,
    color: Colors.textPrimary, lineHeight: 20, marginBottom: Spacing.xs,
  },
  newsSummary: {
    fontSize: FontSize.xs, color: Colors.textSecondary, lineHeight: 18, marginBottom: Spacing.sm,
  },
  newsFooter: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  newsSource: { fontSize: FontSize.xxs, color: Colors.textMuted },
  newsSentRow: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  sentDot: { width: 5, height: 5, borderRadius: 3 },
  sentLabel: { fontSize: FontSize.xxs, fontWeight: FontWeight.medium },

  // Category grouping
  catGroup: { marginBottom: Spacing.xl },
  catGroupHeader: {
    flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, marginBottom: Spacing.sm,
  },
  catGroupLabel: {
    fontSize: FontSize.xxs, fontWeight: FontWeight.bold,
    color: Colors.textMuted, letterSpacing: 1.5,
  },
  catGroupCount: {
    fontSize: FontSize.xxs, color: Colors.accent,
    backgroundColor: Colors.accentDim, paddingHorizontal: 6, paddingVertical: 2,
    borderRadius: Radius.full, fontWeight: FontWeight.bold,
  },

  // Update Card
  updateCard: {
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.lg, borderWidth: 1, borderColor: Colors.border,
    padding: Spacing.lg, marginBottom: Spacing.sm,
  },
  updateHeader: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, marginBottom: Spacing.md },
  updateTypeBadge: {
    paddingHorizontal: Spacing.sm, paddingVertical: 3,
    borderRadius: Radius.xs, borderWidth: 1,
  },
  updateTypeText: { fontSize: FontSize.xxs, fontWeight: FontWeight.bold, letterSpacing: 0.5 },
  updateImpBadge: {
    paddingHorizontal: Spacing.sm, paddingVertical: 3,
    borderRadius: Radius.xs, borderWidth: 1,
  },
  updateImpText: { fontSize: FontSize.xxs, fontWeight: FontWeight.bold, letterSpacing: 0.5 },
  updateDate: { fontSize: FontSize.xxs, color: Colors.textMuted, marginLeft: 'auto' },
  updateTitle: {
    fontSize: FontSize.sm, fontWeight: FontWeight.semibold,
    color: Colors.textPrimary, lineHeight: 20, marginBottom: Spacing.sm,
  },
  updateSummary: {
    fontSize: FontSize.xs, color: Colors.textSecondary, lineHeight: 18, marginBottom: Spacing.sm,
  },
  updateSource: { fontSize: FontSize.xxs, color: Colors.textMuted },

  // Deep Dive Card
  diveCard: {
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.lg, borderWidth: 1, borderColor: Colors.border,
    padding: Spacing.lg, marginBottom: Spacing.sm,
  },
  diveHeader: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, marginBottom: Spacing.md },
  diveSymBox: {
    paddingHorizontal: Spacing.sm, paddingVertical: 4,
    backgroundColor: Colors.accentDim, borderRadius: Radius.xs,
    borderWidth: 1, borderColor: Colors.accentBorder,
  },
  diveSym: { fontSize: FontSize.xxs, fontWeight: FontWeight.black, color: Colors.accent, letterSpacing: 0.5 },
  diveTier: { fontSize: FontSize.xxs, color: Colors.textMuted, fontWeight: FontWeight.bold, letterSpacing: 1 },
  riskBadge: {
    paddingHorizontal: Spacing.sm, paddingVertical: 3, borderRadius: Radius.xs, borderWidth: 1,
  },
  riskText: { fontSize: FontSize.xxs, fontWeight: FontWeight.bold, letterSpacing: 0.5 },
  diveTitle: {
    fontSize: FontSize.base, fontWeight: FontWeight.bold,
    color: Colors.textPrimary, lineHeight: 22, marginBottom: Spacing.sm,
  },
  diveSummary: {
    fontSize: FontSize.xs, color: Colors.textSecondary, lineHeight: 18, marginBottom: Spacing.sm,
  },
  diveSector: { fontSize: FontSize.xxs, color: Colors.textMuted, marginBottom: Spacing.sm },
  tagRow: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.xs },
  tag: {
    paddingHorizontal: Spacing.sm, paddingVertical: 3,
    backgroundColor: Colors.bgElevated, borderRadius: Radius.xs,
    borderWidth: 1, borderColor: Colors.border,
  },
  tagText: { fontSize: FontSize.xxs, color: Colors.textSecondary, letterSpacing: 0.3 },

  disclaimer: {
    fontSize: FontSize.xxs, color: Colors.textDisabled,
    textAlign: 'center', padding: Spacing.xl, lineHeight: 16,
  },
})
