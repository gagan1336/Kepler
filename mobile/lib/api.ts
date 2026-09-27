// KEPLER -- API client (mobile-safe subset)
// ⚠️  NO investment advice, verdicts, price targets, or entry/exit signals shown in app

import axios from 'axios'
import * as SecureStore from 'expo-secure-store'
import Constants from 'expo-constants'

// Auto-detect backend: same host as Expo dev server but on port 8000
// This means we never need to update the IP manually again
function getBaseUrl(): string {
  // If explicitly set in .env.local, use that (REQUIRED for production builds)
  if (process.env.EXPO_PUBLIC_API_URL) return process.env.EXPO_PUBLIC_API_URL

  // In Expo Go / dev builds: derive from the Expo host (e.g. 192.168.0.x:19000 → 192.168.0.x:8000)
  try {
    const expoHost = (Constants.expoConfig as any)?.hostUri
      || (Constants as any).manifest?.debuggerHost
      || (Constants as any).manifest2?.extra?.expoGo?.debuggerHost
    if (expoHost) {
      const host = expoHost.split(':')[0]  // strip port
      const url = `http://${host}:8000`
      // NOTE: Only log in __DEV__ mode — never log URLs in production builds
      if (__DEV__) console.log('[API] Auto-detected backend:', url)
      return url
    }
  } catch {}

  return 'http://192.168.0.247:8000'  // dev fallback — must be overridden in production
}

const BASE_URL = getBaseUrl()
// ⚠️  PRODUCTION GUARD: EXPO_PUBLIC_API_URL MUST be set to https:// in production builds
if (!__DEV__ && BASE_URL.startsWith('http://')) {
  console.warn('[SECURITY] Production build is using http:// — set EXPO_PUBLIC_API_URL to https:// in production!')
}

const api = axios.create({ baseURL: BASE_URL, timeout: 30000 })

api.interceptors.request.use(async (config) => {
  const token = await SecureStore.getItemAsync('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// ── In-memory cache (stale-while-revalidate) ──────────────────────────────────
// Eliminates repeat network calls when navigating between tabs.
// Data loads INSTANTLY on second visit — fresh data revalidates silently.

interface CacheEntry { data: any; ts: number }
const _cache: Record<string, CacheEntry> = {}

const TTL: Record<string, number> = {
  // Fast-changing — 2 min
  '/markets/global': 2 * 60 * 1000,
  '/breakout/today': 2 * 60 * 1000,
  '/sectors/live':   2 * 60 * 1000,
  '/ipo/hub':        2 * 60 * 1000,
  // Moderate — 5 min
  '/news/live':            5 * 60 * 1000,
  '/news/market-updates':  5 * 60 * 1000,
  '/digest/today':         5 * 60 * 1000,
  // Slow-changing — 15 min (screener scans 2600+ stocks)
  '/screener/quality':  15 * 60 * 1000,
  '/screener/value':    15 * 60 * 1000,
  '/screener/dividend': 15 * 60 * 1000,
  '/deepdive/list':     10 * 60 * 1000,
}

function getCached(key: string): any | null {
  const entry = _cache[key]
  if (!entry) return null
  const ttl = TTL[key] ?? 5 * 60 * 1000
  if (Date.now() - entry.ts < ttl) return entry.data
  return null  // stale
}
function getStale(key: string): any | null {
  return _cache[key]?.data ?? null
}
function setCache(key: string, data: any) {
  _cache[key] = { data, ts: Date.now() }
}

// Stale-while-revalidate GET — returns cached data INSTANTLY, refreshes in bg
async function cachedGet(path: string, params?: object): Promise<any> {
  const cacheKey = params ? `${path}?${JSON.stringify(params)}` : path
  const fresh = getCached(cacheKey)
  if (fresh !== null) return fresh  // ← instant return from cache

  // Check for stale data to return while fetching fresh
  const stale = getStale(cacheKey)

  const fetchFresh = async () => {
    try {
      const { data } = await api.get(path, { params })
      setCache(cacheKey, data)
      return data
    } catch (e) {
      if (stale !== null) return stale  // network error → use stale
      throw e
    }
  }

  if (stale !== null) {
    // Return stale immediately, revalidate in background
    fetchFresh().catch(() => {})
    return stale
  }

  // No cache at all — must wait for network
  return fetchFresh()
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface DigestItem {
  headline: string; summary: string; category: string
  sentiment: 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL'; source: string; url?: string
}
export interface DailyDigest {
  id: string; date: string; market_mood: 'BULLISH' | 'BEARISH' | 'NEUTRAL' | null
  items: DigestItem[]
}

export interface BreakoutStock {
  id: string; date: string; symbol: string; company_name: string | null
  setup_description: string | null
  technical_data: { rsi?: number; ema20?: number; ema50?: number; vol_ratio?: number; price?: number } | null
}

export interface SectorLive {
  symbol: string; name: string; day_pct: number; week_pct: number
  month_pct: number; ytd_pct: number; rs_nifty: number
  sentiment: 'BULLISH' | 'BEARISH' | 'MIXED'
  top_movers: { symbol: string; name: string; change_pct: number }[]
  news: { title: string; summary: string; impact: 'HIGH' | 'MEDIUM' | 'LOW'; source: string }[]
}

export interface SectorReport {
  id: string; date: string; sector_name: string | null; content: string | null
}

export interface IpoGmp {
  gmp_price: number; premium_pct: number | null; est_listing: number | null; source: string
}
export interface IpoSubscription {
  qib: number; nii: number; rii: number; total: number; updated_at: string
}
export interface IpoScoreData {
  composite_score: number; grade: string
  gmp_reach_probability: 'VERY_HIGH' | 'HIGH' | 'MODERATE' | 'LOW'
  gmp_reach_label: string
  nifty_regime: 'BULLISH' | 'BEARISH' | 'NEUTRAL'
  nifty_20d_ret: number; allotment_chance: string; listing_day: string
  score_positives: string[]; score_risks: string[]
  gmp_score: number; sub_score: number; qual_score: number
  val_score: number; time_score: number; fund_score: number
}
// ⚠️  ai_verdict intentionally omitted — APPLY/CAUTIOUS/AVOID is investment advice
export interface IpoBrief {
  id: string; company_name: string; symbol: string; industry: string
  price_band: string | null; price_band_min: number | null; price_band_max: number | null
  lot_size: number | null; min_investment: number | null; issue_size_cr: number | null
  issue_type: string; exchange: string; registrar: string
  open_date: string | null; close_date: string | null
  allotment_date: string | null; listing_date: string | null
  days_to_open: number | null; days_to_close: number | null; days_to_listing: number | null
  status: 'OPEN' | 'UPCOMING' | 'ALLOTMENT' | 'LISTED' | 'UNKNOWN'
  rhp_url: string; source: string
  gmp: IpoGmp | null; subscription: IpoSubscription | null
  allotment_chance: string; listing_day_of_week: string; score_data: IpoScoreData | null
}

export interface IpoHubResult {
  ipos: IpoBrief[]
  stats: { total: number; open: number; upcoming: number; allotment: number; listed: number }
  gmp_count: number
}

export interface ScreenerStock {
  symbol: string; company_name: string; sector: string; industry: string
  current_price: number | null; today_change_pct: number | null; change_pct: number | null
  week_52_high: number | null; week_52_low: number | null
  pe_ratio: number | null; forward_pe: number | null; pb_ratio: number | null
  peg_ratio: number | null; ev_ebitda: number | null
  roe: number | null; roa: number | null
  profit_margin: number | null; operating_margin: number | null
  debt_to_equity: number | null; current_ratio: number | null
  market_cap_cr: number | null; eps: number | null; book_value: number | null
  beta: number | null; dividend_yield: number | null
  revenue_growth: number | null; earnings_growth: number | null
  avg_volume: number | null; avg_volume_10d: number | null
  quality_score?: number; score?: number
}

export interface DeepDiveSafe {
  id: string; title: string; summary: string | null; symbol: string | null
  sector: string | null; risk_rating: 'LOW' | 'MEDIUM' | 'HIGH' | null
  tags: string[]; tier: string
  sections?: Array<{ heading: string; body: string }> | null
  created_at: string; locked?: boolean
}

export interface NewsItem {
  id?: string; title: string; summary: string; category: string
  sentiment: string; source: string; source_url?: string
  published_at?: string; importance_score?: number
}

export interface MarketUpdate {
  id: string; title: string
  update_type: 'GST' | 'RBI' | 'SEBI' | 'TAX' | 'POLICY' | 'OTHER'
  summary: string | null; effective_date: string | null
  importance: 'HIGH' | 'MEDIUM' | 'LOW'; source: string | null; source_url: string | null
  created_at: string
}

export interface UserProfile {
  id: string; email: string; plan: 'free' | 'pro' | 'elite'
  trial_end_date: string | null; created_at: string
}

export interface GlobalMarketTicker {
  symbol: string; name: string; unit: string; key: boolean
  current_price: number; prev_close: number | null
  change: number; change_pct: number; direction: 'UP' | 'DOWN' | 'FLAT'
}
export interface GlobalMarketsResult {
  groups: {
    gift_nifty?: GlobalMarketTicker[]
    us?: GlobalMarketTicker[]
    asia?: GlobalMarketTicker[]
    europe?: GlobalMarketTicker[]
    commodities?: GlobalMarketTicker[]
    crypto?: GlobalMarketTicker[]
    forex?: GlobalMarketTicker[]
  }
  group_meta: Record<string, { label: string; icon: string; color: string }>
  impact_score: string
  fetched_at: number
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function stripIpoVerdict(ipo: Record<string, any>): IpoBrief {
  const { ai_verdict, ...safe } = ipo
  return safe as IpoBrief
}

function stripDeepDiveFields(d: Record<string, any>): DeepDiveSafe {
  const { verdict, price_target_12m, ...safe } = d
  return safe as DeepDiveSafe
}

function extractStocks(data: any): ScreenerStock[] {
  if (Array.isArray(data)) return data
  return (data.results ?? data.stocks ?? []) as ScreenerStock[]
}

// ── Digest ────────────────────────────────────────────────────────────────────

export async function apiLatestDigest(): Promise<DailyDigest | null> {
  try {
    const data = await cachedGet('/digest/today')
    return data as DailyDigest
  } catch { return null }
}

export async function apiDigestList(page = 1, limit = 10) {
  const data = await cachedGet('/digest/history', { page, limit })
  const digests = Array.isArray(data) ? data : (data.digests ?? data.items ?? [])
  return { digests: digests as DailyDigest[], total: data.total ?? digests.length }
}

// ── Breakouts ─────────────────────────────────────────────────────────────────

export async function apiBreakouts(date?: string) {
  try {
    const data = await cachedGet('/breakout/today', date ? { date } : undefined)
    const stocks = Array.isArray(data) ? data : (data.stocks ?? data.breakouts ?? [])
    return { stocks: stocks as BreakoutStock[], date: data.date ?? '' }
  } catch { return { stocks: [], date: '' } }
}

// ── Sectors ───────────────────────────────────────────────────────────────────

export async function apiSectorsLive(): Promise<SectorLive[]> {
  try {
    const data = await cachedGet('/sectors/live')
    return (data.sectors ?? data ?? []) as SectorLive[]
  } catch { return [] }
}

export async function apiSectorReports(limit = 10): Promise<SectorReport[]> {
  try {
    const data = await cachedGet('/sector/history', { limit })
    return (Array.isArray(data) ? data : (data.reports ?? [])) as SectorReport[]
  } catch { return [] }
}

// ── IPO Hub ───────────────────────────────────────────────────────────────────

export async function apiIPOHub(): Promise<IpoHubResult | null> {
  try {
    const data = await cachedGet('/ipo/hub')
    const ipos: IpoBrief[] = (data.ipos ?? []).map(stripIpoVerdict)
    return { ipos, stats: data.stats ?? {}, gmp_count: data.gmp_count ?? 0 }
  } catch (e: any) {
    console.log('[IPO Hub]', e?.response?.status, e?.message)
    return null
  }
}

// ── News ──────────────────────────────────────────────────────────────────────

export async function apiLiveNews(limit = 30): Promise<NewsItem[]> {
  try {
    const data = await cachedGet('/news/live', { limit })
    // Backend returns { articles: [...], count, stats } OR array directly
    return (Array.isArray(data) ? data : (data.articles ?? data.news ?? data.items ?? [])) as NewsItem[]
  } catch { return [] }
}

export async function apiMarketUpdates(limit = 20): Promise<MarketUpdate[]> {
  try {
    const data = await cachedGet('/news/market-updates', { limit })
    return (Array.isArray(data) ? data : (data.updates ?? data.items ?? [])) as MarketUpdate[]
  } catch { return [] }
}

// ── Screener ──────────────────────────────────────────────────────────────────
// These scan 2,600+ stocks via yfinance — first call is slow (30-60s),
// subsequent calls are instant from cache.

export async function apiScreenerQuality(): Promise<ScreenerStock[]> {
  const data = await cachedGet('/screener/quality', { limit: 30 })
  return extractStocks(data)
}

export async function apiScreenerValue(): Promise<ScreenerStock[]> {
  const data = await cachedGet('/screener/value', { limit: 30 })
  return extractStocks(data)
}

export async function apiScreenerDividend(): Promise<ScreenerStock[]> {
  const data = await cachedGet('/screener/dividend', { limit: 30 })
  return extractStocks(data)
}

export async function apiScreenerPresets() {
  try {
    const data = await cachedGet('/screener/presets')
    return (data.presets ?? data) as Array<{ key: string; label: string; icon: string; desc: string }>
  } catch { return [] }
}

export async function apiScreenerPreset(name: string): Promise<ScreenerStock[]> {
  try {
    const data = await cachedGet(`/screener/preset/${name}`, { limit: 30 })
    return extractStocks(data)
  } catch { return [] }
}

export async function apiSwingPresets() {
  try {
    const data = await cachedGet('/screener/swing')
    return (data.presets ?? []) as Array<{ key: string; label: string; description: string; timeframe: string }>
  } catch { return [] }
}

export async function apiScreenerSwing(preset: string): Promise<{ stocks: ScreenerStock[]; count: number; preset_name: string }> {
  try {
    const data = await cachedGet(`/screener/swing/${preset}`, { limit: 30 })
    return {
      stocks: extractStocks(data),
      count: data.count ?? 0,
      preset_name: data.preset_name ?? preset,
    }
  } catch { return { stocks: [], count: 0, preset_name: preset } }
}

export async function apiStockSearch(q: string): Promise<ScreenerStock[]> {
  try {
    // Search is always fresh — no cache
    const { data } = await api.get('/stock/search', { params: { q }, timeout: 15000 })
    return extractStocks(data)
  } catch { return [] }
}

// ── Deep Dives ────────────────────────────────────────────────────────────────

export async function apiDeepDives(page = 1, limit = 20) {
  const data = await cachedGet('/deepdive/list', { page, limit })
  const raw = Array.isArray(data) ? data : (data.deepdives ?? data.items ?? [])
  return { deepdives: raw.map(stripDeepDiveFields) as DeepDiveSafe[], total: data.total ?? raw.length }
}

export async function apiDeepDive(id: string): Promise<DeepDiveSafe> {
  const { data } = await api.get(`/deepdive/${id}`)
  return stripDeepDiveFields(data)
}

// ── Global Markets ────────────────────────────────────────────────────────────

export async function apiGlobalMarkets(): Promise<GlobalMarketsResult | null> {
  try {
    const data = await cachedGet('/markets/global')
    return data as GlobalMarketsResult
  } catch (e: any) {
    console.log('[GlobalMarkets]', e?.message)
    return null
  }
}

// ── Push Notifications ────────────────────────────────────────────────────────

export async function apiRegisterPushToken(token: string, platform: 'ios' | 'android') {
  try {
    await api.post('/notifications/register', { token, platform })
  } catch {
    // Non-critical — silent fail
  }
}

// ── Auth / User ───────────────────────────────────────────────────────────────

export async function apiMe(): Promise<UserProfile> {
  const { data } = await api.get('/auth/me')
  return data as UserProfile
}

export async function apiPublicStats() {
  try {
    const data = await cachedGet('/public/stats')
    return data
  } catch { return null }
}

// ── Cache utilities (call from pull-to-refresh) ───────────────────────────────

/** Invalidate a specific cached path */
export function invalidateCache(path: string) {
  Object.keys(_cache).forEach(k => { if (k.startsWith(path)) delete _cache[k] })
}

/** Invalidate all cache (call on pull-to-refresh) */
export function clearAllCache() {
  Object.keys(_cache).forEach(k => delete _cache[k])
}
