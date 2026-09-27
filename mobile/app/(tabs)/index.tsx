// KEPLER — Intelligence Screen (Tab 1)
// The most important screen. Answers: What is happening? Why? What to investigate?

import { useEffect, useState, useCallback, useRef } from 'react'
import {
  View, Text, ScrollView, StyleSheet, RefreshControl,
  TouchableOpacity, Animated, Dimensions, FlatList,
} from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { router } from 'expo-router'
import {
  apiLatestDigest, apiGlobalMarkets, apiBreakouts, apiLiveNews,
  clearAllCache, DailyDigest, GlobalMarketsResult, GlobalMarketTicker,
  NewsItem, BreakoutStock,
} from '@/lib/api'
import {
  SkeletonBox, SkeletonText, SkeletonCard, SkeletonMarketRow, SkeletonNewsItem,
  SectionHeader, ChangeBadge, MarketRow, CategoryPill, SentimentBadge,
  EmptyState, ErrorState, AIProcessing, Divider,
} from '@/components/ui'
import { Colors, Spacing, Radius, FontSize, FontWeight, MonoStyle } from '@/constants/theme'
import { useAuth } from '@/lib/auth'

const { width: SW } = Dimensions.get('window')

// ── Helpers ───────────────────────────────────────────────────────────────────

function greet() {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 17) return 'Good afternoon'
  return 'Good evening'
}

function todayStr() {
  return new Date().toLocaleDateString('en-IN', {
    day: 'numeric', month: 'long', year: 'numeric',
  })
}

function pctColor(v: number) {
  return v > 0 ? Colors.positive : v < 0 ? Colors.negative : Colors.textMuted
}

// ── Market Strip Tile ─────────────────────────────────────────────────────────

function MarketTile({ ticker }: { ticker: GlobalMarketTicker }) {
  const color = pctColor(ticker.change_pct)
  const val = ticker.unit === 'pts'
    ? ticker.current_price.toLocaleString('en-IN', { maximumFractionDigits: 0 })
    : ticker.current_price.toFixed(2)

  return (
    <View style={s.tile}>
      <Text style={s.tileName} numberOfLines={1}>{ticker.name}</Text>
      <Text style={[s.tileValue, MonoStyle]}>{val}</Text>
      <Text style={[s.tileChange, { color }, MonoStyle]}>
        {ticker.change_pct >= 0 ? '+' : ''}{ticker.change_pct.toFixed(2)}%
      </Text>
    </View>
  )
}

function SkeletonTile() {
  return (
    <View style={s.tile}>
      <SkeletonBox height={10} width={50} style={{ marginBottom: 6 }} />
      <SkeletonBox height={14} width={70} style={{ marginBottom: 5 }} />
      <SkeletonBox height={10} width={40} />
    </View>
  )
}

// ── Intelligence Hero Card ────────────────────────────────────────────────────

const MOOD_CONFIG = {
  BULLISH: { color: Colors.positive, label: 'BULLISH', dot: '●' },
  BEARISH: { color: Colors.negative, label: 'BEARISH', dot: '●' },
  NEUTRAL: { color: Colors.warning,  label: 'NEUTRAL', dot: '●' },
}

function IntelligenceCard({ digest, loading }: { digest: DailyDigest | null; loading: boolean }) {
  if (loading) {
    return (
      <View style={s.heroCard}>
        <SkeletonBox height={10} width={120} style={{ marginBottom: 16 }} />
        <SkeletonText lines={3} style={{ marginBottom: 20 }} />
        <Divider style={{ marginVertical: 16 }} />
        <SkeletonBox height={11} width={180} />
      </View>
    )
  }

  if (!digest) {
    return (
      <View style={s.heroCard}>
        <Text style={s.heroLabel}>AI MARKET BRIEF</Text>
        <Text style={s.heroEmpty}>Daily intelligence digest is being prepared.</Text>
        <Text style={s.heroEmptySub}>Check back after 8:30 AM IST.</Text>
      </View>
    )
  }

  const mood = MOOD_CONFIG[digest.market_mood ?? 'NEUTRAL'] ?? MOOD_CONFIG.NEUTRAL
  const firstItem = digest.items?.[0]

  return (
    <TouchableOpacity
      style={s.heroCard}
      activeOpacity={0.92}
      onPress={() => router.push('/news' as any)}
    >
      {/* Header row */}
      <View style={s.heroHeader}>
        <Text style={s.heroLabel}>AI MARKET BRIEF</Text>
        <View style={[s.moodPill, { backgroundColor: mood.color + '15', borderColor: mood.color + '30' }]}>
          <Text style={[s.moodDot, { color: mood.color }]}>{mood.dot}</Text>
          <Text style={[s.moodText, { color: mood.color }]}>{mood.label}</Text>
        </View>
      </View>

      {/* Lead summary */}
      {firstItem && (
        <Text style={s.heroSummary} numberOfLines={4}>
          {firstItem.summary}
        </Text>
      )}

      {/* Signal rows */}
      {digest.items?.slice(1, 4).map((item, i) => (
        <View key={i} style={s.signalRow}>
          <Text style={s.signalNum}>{String(i + 1).padStart(2, '0')}</Text>
          <Text style={s.signalText} numberOfLines={2}>{item.headline}</Text>
          <View style={[s.signalDot, {
            backgroundColor: item.sentiment === 'POSITIVE' ? Colors.positive
              : item.sentiment === 'NEGATIVE' ? Colors.negative : Colors.textDisabled,
          }]} />
        </View>
      ))}

      <Divider style={{ marginTop: Spacing.lg, marginBottom: Spacing.md }} />

      <View style={s.heroFooter}>
        <Text style={s.heroFooterText}>
          {digest.items?.length ?? 0} MARKET SIGNALS TODAY
        </Text>
        <Text style={s.heroArrow}>→</Text>
      </View>
    </TouchableOpacity>
  )
}

// ── Market Pulse Section ──────────────────────────────────────────────────────

const GROUP_META: Record<string, { label: string }> = {
  gift_nifty:  { label: 'INDIA' },
  us:          { label: 'US' },
  asia:        { label: 'ASIA' },
  commodities: { label: 'COMMODITIES' },
  forex:       { label: 'FOREX' },
  crypto:      { label: 'CRYPTO' },
}

function MarketPulseSection({ markets, loading }: {
  markets: GlobalMarketsResult | null; loading: boolean
}) {
  const keyGroups = ['gift_nifty', 'us', 'commodities', 'forex']

  if (loading) {
    return (
      <View style={s.pulseSection}>
        {[1, 2, 3, 4, 5].map(i => <SkeletonMarketRow key={i} />)}
      </View>
    )
  }

  if (!markets) return null

  const rows: Array<{ name: string; value: number; change: number; unit: string }> = []
  keyGroups.forEach(g => {
    const tickers = (markets.groups as any)[g] ?? []
    tickers.filter((t: GlobalMarketTicker) => t.key).slice(0, g === 'gift_nifty' ? 3 : 2).forEach((t: GlobalMarketTicker) => {
      rows.push({ name: t.name, value: t.current_price, change: t.change_pct, unit: t.unit })
    })
  })

  return (
    <View style={s.pulseSection}>
      {rows.map((r, i) => (
        <MarketRow key={i} name={r.name} value={r.value} change={r.change} unit={r.unit} />
      ))}
    </View>
  )
}

// ── Breakout Preview ──────────────────────────────────────────────────────────

function BreakoutPreview({ stocks, loading }: { stocks: BreakoutStock[]; loading: boolean }) {
  if (loading) return (
    <View>
      {[1, 2, 3].map(i => <SkeletonCard key={i} height={56} />)}
    </View>
  )

  if (!stocks.length) return null

  return (
    <View style={s.breakoutList}>
      {stocks.slice(0, 5).map((s_, i) => (
        <View key={s_.id} style={bs.row}>
          <Text style={bs.num}>{String(i + 1).padStart(2, '0')}</Text>
          <Text style={bs.sym}>{s_.symbol?.replace('.NS', '')}</Text>
          <Text style={bs.name} numberOfLines={1}>{s_.company_name ?? '—'}</Text>
          {s_.technical_data?.price != null && (
            <Text style={[bs.price, MonoStyle]}>
              ₹{s_.technical_data.price.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
            </Text>
          )}
        </View>
      ))}
    </View>
  )
}

const bs = StyleSheet.create({
  row: {
    flexDirection: 'row', alignItems: 'center', paddingVertical: Spacing.md,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  num: {
    fontSize: FontSize.xxs, color: Colors.accent, fontWeight: FontWeight.bold,
    width: 24, letterSpacing: 0.5,
  },
  sym: {
    fontSize: FontSize.sm, color: Colors.textPrimary, fontWeight: FontWeight.bold,
    width: 72, letterSpacing: 0.3,
  },
  name: {
    flex: 1, fontSize: FontSize.xs, color: Colors.textSecondary,
  },
  price: {
    fontSize: FontSize.xs, color: Colors.textMuted, fontWeight: FontWeight.medium,
  },
})

// ── News Preview Card ─────────────────────────────────────────────────────────

const SENT_DOT: Record<string, string> = {
  POSITIVE: Colors.positive, NEGATIVE: Colors.negative, NEUTRAL: Colors.textDisabled,
}

function NewsPreviewItem({ item }: { item: NewsItem }) {
  const sentColor = SENT_DOT[item.sentiment?.toUpperCase()] ?? Colors.textDisabled
  return (
    <View style={s.newsItem}>
      <View style={s.newsItemHeader}>
        <CategoryPill label={item.category ?? 'MARKET'} />
        {item.published_at && (
          <Text style={s.newsTime}>
            {new Date(item.published_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
          </Text>
        )}
      </View>
      <Text style={s.newsHeadline} numberOfLines={3}>{item.title}</Text>
      <View style={s.newsFooter}>
        <Text style={s.newsSource}>{item.source}</Text>
        <View style={[s.newsSentDot, { backgroundColor: sentColor }]} />
        <Text style={[s.newsSentLabel, { color: sentColor }]}>
          {item.sentiment ?? 'NEUTRAL'}
        </Text>
      </View>
    </View>
  )
}

// ── Main Screen ───────────────────────────────────────────────────────────────

export default function IntelligenceScreen() {
  const { user } = useAuth()
  const [digest, setDigest] = useState<DailyDigest | null>(null)
  const [markets, setMarkets] = useState<GlobalMarketsResult | null>(null)
  const [breakouts, setBreakouts] = useState<BreakoutStock[]>([])
  const [news, setNews] = useState<NewsItem[]>([])
  const [loadingDigest, setLoadingDigest] = useState(true)
  const [loadingMarkets, setLoadingMarkets] = useState(true)
  const [loadingBreakouts, setLoadingBreakouts] = useState(true)
  const [loadingNews, setLoadingNews] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const headerOpacity = useRef(new Animated.Value(0)).current

  const load = useCallback(async () => {
    // All requests fire simultaneously
    const [d, m, b, n] = await Promise.allSettled([
      apiLatestDigest(),
      apiGlobalMarkets(),
      apiBreakouts(),
      apiLiveNews(8),
    ])

    if (d.status === 'fulfilled') { setDigest(d.value); setLoadingDigest(false) }
    else setLoadingDigest(false)

    if (m.status === 'fulfilled') { setMarkets(m.value); setLoadingMarkets(false) }
    else setLoadingMarkets(false)

    if (b.status === 'fulfilled') {
      const result = b.value
      const stocks = Array.isArray(result) ? result : ((result as any)?.stocks ?? [])
      setBreakouts(stocks)
      setLoadingBreakouts(false)
    } else setLoadingBreakouts(false)

    if (n.status === 'fulfilled') { setNews(n.value); setLoadingNews(false) }
    else setLoadingNews(false)

    setRefreshing(false)

    // Fade-in animation
    Animated.timing(headerOpacity, {
      toValue: 1, duration: 300, useNativeDriver: true,
    }).start()
  }, [])

  useEffect(() => { load() }, [load])

  const onRefresh = useCallback(() => {
    setRefreshing(true)
    clearAllCache()
    setLoadingDigest(true); setLoadingMarkets(true)
    setLoadingBreakouts(true); setLoadingNews(true)
    load()
  }, [load])

  return (
    <SafeAreaView style={s.safe} edges={['top']}>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={s.content}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={Colors.accent}
          />
        }
      >
        {/* ── Header ───────────────────────────────────────────── */}
        <View style={s.header}>
          <View>
            <Text style={s.brandName}>KEPLER</Text>
            <Text style={s.greeting}>Your daily market intelligence</Text>
            <Text style={s.date}>{todayStr()}</Text>
          </View>
          <TouchableOpacity
            style={s.avatarBtn}
            onPress={() => router.push('/account' as any)}
          >
            <View style={s.avatar}>
              <Text style={s.avatarText}>
                {user?.email?.[0]?.toUpperCase() ?? 'A'}
              </Text>
            </View>
          </TouchableOpacity>
        </View>

        {/* ── Market Strip (scrollable) ─────────────────────────── */}
        <View style={s.stripWrap}>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={s.strip}
          >
            {loadingMarkets
              ? [1, 2, 3, 4, 5].map(i => <SkeletonTile key={i} />)
              : markets
                ? (() => {
                    const tiles: GlobalMarketTicker[] = []
                    ;['gift_nifty', 'us', 'asia', 'commodities', 'forex'].forEach(g => {
                      ((markets.groups as any)[g] ?? []).filter((t: GlobalMarketTicker) => t.key).forEach((t: GlobalMarketTicker) => tiles.push(t))
                    })
                    return tiles.slice(0, 8).map((t, i) => <MarketTile key={i} ticker={t} />)
                  })()
                : null
            }
          </ScrollView>
        </View>

        {/* ── Intelligence Hero ─────────────────────────────────── */}
        <View style={s.section}>
          <SectionHeader title="TODAY'S INTELLIGENCE" />
          <IntelligenceCard digest={digest} loading={loadingDigest} />
        </View>

        {/* ── Market Pulse ──────────────────────────────────────── */}
        <View style={s.section}>
          <SectionHeader
            title="MARKET PULSE"
            action="MARKETS →"
            onAction={() => router.push('/markets' as any)}
          />
          <View style={s.card}>
            <MarketPulseSection markets={markets} loading={loadingMarkets} />
          </View>
        </View>

        {/* ── Breakout Watch ────────────────────────────────────── */}
        {(loadingBreakouts || breakouts.length > 0) && (
          <View style={s.section}>
            <SectionHeader
              title="BREAKOUT WATCH"
              subtitle={breakouts.length > 0 ? `${breakouts.length} setups identified` : undefined}
              action="EXPLORE →"
              onAction={() => router.push('/markets' as any)}
            />
            <View style={s.card}>
              <BreakoutPreview stocks={breakouts} loading={loadingBreakouts} />
            </View>
          </View>
        )}

        {/* ── Market Signals (News) ─────────────────────────────── */}
        <View style={s.section}>
          <SectionHeader
            title="MARKET INTELLIGENCE"
            action="VIEW ALL →"
            onAction={() => router.push('/news' as any)}
          />
          {loadingNews
            ? [1, 2, 3].map(i => (
                <View key={i} style={s.card}>
                  <SkeletonNewsItem />
                </View>
              ))
            : news.slice(0, 5).map((item, i) => (
                <TouchableOpacity
                  key={item.id ?? i}
                  style={s.card}
                  activeOpacity={0.85}
                  onPress={() => router.push('/news' as any)}
                >
                  <NewsPreviewItem item={item} />
                </TouchableOpacity>
              ))
          }
        </View>

        {/* ── Disclaimer ────────────────────────────────────────── */}
        <Text style={s.disclaimer}>
          Not SEBI registered. For educational purposes only.{'\n'}
          Market data may be delayed.
        </Text>
      </ScrollView>
    </SafeAreaView>
  )
}

// ── Styles ────────────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.bg },
  scroll: { flex: 1 },
  content: { paddingBottom: 40 },

  // Header
  header: {
    flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between',
    paddingHorizontal: Spacing.xl, paddingTop: Spacing.xl, paddingBottom: Spacing.lg,
  },
  brandName: {
    fontSize: FontSize.xxs, fontWeight: FontWeight.bold,
    color: Colors.accent, letterSpacing: 2.5, marginBottom: 8,
  },
  greeting: {
    fontSize: FontSize.h2, fontWeight: FontWeight.bold,
    color: Colors.textPrimary, marginBottom: 2,
  },
  date: {
    fontSize: FontSize.xs, color: Colors.textMuted, letterSpacing: 0.3,
  },
  avatarBtn: { marginTop: 4 },
  avatar: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: Colors.bgElevated, borderWidth: 1, borderColor: Colors.border,
    alignItems: 'center', justifyContent: 'center',
  },
  avatarText: {
    fontSize: FontSize.sm, fontWeight: FontWeight.bold,
    color: Colors.accent,
  },

  // Market Strip
  stripWrap: {
    borderTopWidth: 1, borderBottomWidth: 1, borderColor: Colors.border,
    backgroundColor: Colors.bgCard,
  },
  strip: { paddingHorizontal: Spacing.xl, paddingVertical: Spacing.md, gap: Spacing.sm },
  tile: {
    paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm,
    borderRightWidth: 1, borderRightColor: Colors.border, minWidth: 90,
  },
  tileName: {
    fontSize: FontSize.xxs, color: Colors.textMuted,
    fontWeight: FontWeight.bold, letterSpacing: 0.5, marginBottom: 4,
  },
  tileValue: {
    fontSize: FontSize.sm, fontWeight: FontWeight.bold,
    color: Colors.textPrimary, marginBottom: 2,
  },
  tileChange: { fontSize: FontSize.xxs, fontWeight: FontWeight.semibold },

  // Sections
  section: { paddingHorizontal: Spacing.xl },
  card: {
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.lg, borderWidth: 1, borderColor: Colors.border,
    padding: Spacing.lg, marginBottom: Spacing.sm,
  },

  // Intelligence Hero Card
  heroCard: {
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.xl, borderWidth: 1, borderColor: Colors.border,
    padding: Spacing.xl, marginBottom: Spacing.sm,
  },
  heroHeader: {
    flexDirection: 'row', alignItems: 'center',
    justifyContent: 'space-between', marginBottom: Spacing.lg,
  },
  heroLabel: {
    fontSize: FontSize.xxs, fontWeight: FontWeight.bold,
    color: Colors.textMuted, letterSpacing: 1.5,
  },
  moodPill: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: Spacing.sm, paddingVertical: 4,
    borderRadius: Radius.full, borderWidth: 1,
  },
  moodDot: { fontSize: 8 },
  moodText: { fontSize: FontSize.xxs, fontWeight: FontWeight.bold, letterSpacing: 0.5 },

  heroSummary: {
    fontSize: FontSize.base, color: Colors.textSecondary,
    lineHeight: 24, marginBottom: Spacing.xl, fontWeight: FontWeight.regular,
  },
  heroEmpty: {
    fontSize: FontSize.base, color: Colors.textSecondary, marginBottom: Spacing.sm,
  },
  heroEmptySub: { fontSize: FontSize.xs, color: Colors.textMuted },

  // Signal rows
  signalRow: {
    flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  signalNum: {
    fontSize: FontSize.xxs, color: Colors.accent, fontWeight: FontWeight.bold,
    letterSpacing: 0.5, width: 22, paddingTop: 2,
  },
  signalText: {
    flex: 1, fontSize: FontSize.xs, color: Colors.textSecondary, lineHeight: 18,
  },
  signalDot: { width: 6, height: 6, borderRadius: 3, marginTop: 5 },

  heroFooter: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
  },
  heroFooterText: {
    fontSize: FontSize.xxs, color: Colors.textMuted,
    fontWeight: FontWeight.semibold, letterSpacing: 0.8,
  },
  heroArrow: { fontSize: FontSize.sm, color: Colors.accent },

  // Market Pulse card content
  pulseSection: {},

  // Breakout list
  breakoutList: {},

  // News
  newsItem: {},
  newsItemHeader: {
    flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, marginBottom: Spacing.sm,
  },
  newsTime: { fontSize: FontSize.xxs, color: Colors.textMuted },
  newsHeadline: {
    fontSize: FontSize.sm, fontWeight: FontWeight.semibold,
    color: Colors.textPrimary, lineHeight: 20, marginBottom: Spacing.sm,
  },
  newsFooter: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  newsSource: { fontSize: FontSize.xxs, color: Colors.textMuted },
  newsSentDot: { width: 5, height: 5, borderRadius: 3 },
  newsSentLabel: { fontSize: FontSize.xxs, fontWeight: FontWeight.medium },

  // Disclaimer
  disclaimer: {
    fontSize: FontSize.xxs, color: Colors.textDisabled,
    textAlign: 'center', lineHeight: 16,
    paddingHorizontal: Spacing.xl, marginTop: Spacing.xl,
  },
})
