/**
 * ANTIGRAVITY — API Client
 * All backend API calls. Auth tokens are provided by Supabase (see lib/supabase.ts).
 */
import { supabase } from './supabase'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/**
 * Returns the Supabase access token for the current session.
 * Supabase handles all token storage and auto-refresh internally.
 */
export async function getAccessToken(): Promise<string | null> {
  if (typeof window === 'undefined') return null
  const { data: { session } } = await supabase.auth.getSession()
  return session?.access_token ?? null
}

// ── Types ─────────────────────────────────────────────────────────────────────
export interface User {
  id: string
  email: string
  plan: 'free' | 'pro' | 'elite'
  trial_end_date: string | null
  created_at: string
}

export interface DigestItem {
  title: string
  category: 'MACRO' | 'SECTOR' | 'STOCK' | 'RESULT' | 'GLOBAL' | 'POLICY'
  importance_score: number
  summary: string
  affected_sectors: string[]
  affected_stocks: string[]
  sentiment: 'BULLISH' | 'BEARISH' | 'NEUTRAL'
  source_url: string
}

export interface Digest {
  id: string
  date: string
  market_mood: 'BULLISH' | 'BEARISH' | 'NEUTRAL'
  items: DigestItem[]
  total_items: number
  blurred_count: number
  is_restricted: boolean
}

export interface Breakout {
  id: string
  date: string
  symbol: string
  company_name: string
  setup_description: string
  technical_data: {
    current_price: number
    high_52w: number
    low_52w?: number
    pct_from_52w_high: number
    volume_ratio: number
    avg_vol_20?: number
    today_vol?: number
    rsi: number
    ema20: number
    ema50: number
    ema200?: number
    atr?: number
    macd?: number
    macd_signal?: number
    macd_above_signal?: boolean
    vcp_score?: number
    stop_loss?: number
    golden_cross?: boolean
    stock_return_30d?: number
    sector_rs?: number
    apex_score?: number
    apex_breakdown?: { A: number; P: number; E: number; X: number; S: number }
    apex_conviction?: 'HIGH' | 'MODERATE' | 'WATCHLIST'
    pattern_tags?: string[]
    sector?: string
    ai_pattern_name?: string
  }
}

export interface SectorReport {
  id: string
  date: string
  sector_name: string
  content: string
}

export interface IPOBrief {
  id: string
  company_name: string
  open_date: string
  close_date: string
  price_band: string
  industry: string
  content: string
}

export interface PublicStats {
  total_members: number
  pro_seats_remaining: number
  elite_seats_remaining: number
  elite_waitlist_count: number
}

export interface DashboardStats {
  digests_this_month: number
  chart_analyses_this_month: number
  sector_reports_this_month: number
  member_since: string
  plan: string
  trial_ends: string | null
  next_billing: string | null
  invoices: { date: string; plan: string; url: string }[]
}

// ── HTTP helper ───────────────────────────────────────────────────────────────
async function request<T>(
  path: string,
  options: RequestInit = {},
  requireAuth = false,
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  }

  if (requireAuth) {
    // Supabase getSession() auto-refreshes the token if expired
    const token = await getAccessToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })

  // On 401, try forcing a Supabase session refresh once
  if (res.status === 401 && requireAuth) {
    const { data: { session: refreshedSession } } = await supabase.auth.refreshSession()
    if (refreshedSession?.access_token) {
      headers['Authorization'] = `Bearer ${refreshedSession.access_token}`
      const retry = await fetch(`${API_BASE}${path}`, { ...options, headers })
      if (!retry.ok) throw new ApiError(retry.status, await retry.text())
      return retry.json()
    } else {
      // Token is truly expired — throw error; let the auth layer handle redirect
      throw new ApiError(401, 'Session expired. Please log in again.')
    }
  }

  if (!res.ok) {
    let detail = 'An error occurred'
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch {}
    throw new ApiError(res.status, detail)
  }

  if (res.status === 204) return null as T
  return res.json()
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

// ── Auth API ──────────────────────────────────────────────────────────────────
// Note: Login, register, and Google OAuth are now handled by the Supabase client
// in lib/auth.tsx. This endpoint syncs/fetches the backend user profile.
export async function apiGetMe(): Promise<User> {
  return request('/auth/me', {}, true)
}

// ── Public API ────────────────────────────────────────────────────────────────
export async function apiPublicStats(): Promise<PublicStats> {
  return request('/public/stats')
}

export async function apiPublicSample(): Promise<{ digests: Digest[]; sector_report: SectorReport }> {
  return request('/public/sample')
}

// ── Content API ───────────────────────────────────────────────────────────────
export async function apiDigestToday(): Promise<Digest> {
  return request('/digest/today', {}, true)
}

export async function apiDigestHistory(limit = 30): Promise<Digest[]> {
  return request(`/digest/history?limit=${limit}`, {}, true)
}

export async function apiBreakoutToday(): Promise<Breakout[]> {
  return request('/breakout/today', {}, true)
}

export async function apiSectorLatest(): Promise<SectorReport> {
  return request('/sector/latest')
}

export async function apiSectorHistory(limit = 12): Promise<SectorReport[]> {
  return request(`/sector/history?limit=${limit}`, {}, true)
}

export async function apiIPOLatest(): Promise<IPOBrief> {
  return request('/ipo/latest')
}

export async function apiIPODetail(id: string): Promise<IPOBrief> {
  return request(`/ipo/${id}`, {}, true)
}

export async function apiDeepDiveList(): Promise<any[]> {
  return request('/deepdive/list', {}, true)
}

export async function apiDeepDiveDetail(id: string): Promise<any> {
  return request(`/deepdive/${id}`, {}, true)
}

export async function apiDeepDiveGenerate(symbol: string, tier: string = 'elite'): Promise<{ id: string; symbol: string; message: string }> {
  return request('/deepdive/generate', {
    method: 'POST',
    body: JSON.stringify({ symbol, tier }),
  }, true)
}

export async function apiDashboardStats(): Promise<DashboardStats> {
  return request('/dashboard/stats', {}, true)
}

// ── Subscription / Razorpay API ───────────────────────────────────────────────

export interface RazorpaySubscriptionResponse {
  subscription_id: string
  razorpay_key: string
  plan: string
  amount: number
  currency: string
}

export interface SubscriptionStatus {
  plan: string
  status: 'active' | 'cancelled' | 'none' | 'past_due'
  start_date: string | null
  end_date: string | null
  trial_end_date: string | null
}

/** Create a Razorpay subscription. Plans: pro_monthly | pro_annual | elite_monthly | elite_annual */
export async function apiCreateSubscription(plan: string): Promise<RazorpaySubscriptionResponse> {
  return request<RazorpaySubscriptionResponse>('/subscription/create', {
    method: 'POST',
    body: JSON.stringify({ plan }),
  }, true)
}

/**
 * Verify Razorpay payment signature after checkout — immediately activates plan.
 * Falls back gracefully if keys not configured yet.
 */
export async function apiVerifySubscription(params: {
  razorpay_payment_id: string
  razorpay_subscription_id: string
  razorpay_signature: string
  plan: string
}): Promise<{ ok: boolean; plan: string; message: string }> {
  return request<{ ok: boolean; plan: string; message: string }>('/payment/verify-subscription', {
    method: 'POST',
    body: JSON.stringify(params),
  }, true)
}

/** Get current subscription status. */
export async function apiGetSubscriptionStatus(): Promise<SubscriptionStatus> {
  return request<SubscriptionStatus>('/subscription/status', {}, true)
}

/** Cancel subscription at period end. */
export async function apiCancelSubscription(): Promise<{ message: string; access_until: string }> {
  return request<{ message: string; access_until: string }>('/subscription/cancel', { method: 'POST' }, true)
}

// -- Market Updates API --------------------------------------------------------
export interface MarketUpdate {
  id: string
  title: string
  update_type: 'GST' | 'RBI' | 'SEBI' | 'TAX' | 'POLICY' | 'OTHER'
  summary: string
  effective_date: string | null
  affected_entities: string[]
  importance: 'HIGH' | 'MEDIUM' | 'LOW'
  source: string
  source_url: string
  created_at: string
}

export async function apiMarketUpdates(updateType?: string, limit = 20): Promise<MarketUpdate[]> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (updateType) params.append('update_type', updateType)
  return request('/news/market-updates?' + params.toString())
}

// ── Live News API ─────────────────────────────────────────────────────────────
export type NewsCategory = 'ALL' | 'BREAKING' | 'MARKETS' | 'STOCKS' | 'RBI' | 'SEBI' | 'GST_TAX' | 'IPO' | 'GLOBAL'
export type NewsImpact   = 'HIGH' | 'MEDIUM' | 'LOW'

export interface LiveNewsArticle {
  id:           string
  title:        string
  description:  string
  url:          string
  source:       string
  category:     NewsCategory
  impact:       NewsImpact
  published_at: string
  time_ago:     string
  image:        string | null
}

export interface LiveNewsResult {
  articles:         LiveNewsArticle[]
  count:            number
  stats:            {
    total:        number
    high_impact:  number
    medium_impact: number
    categories:   Record<string, number>
  }
  fetched_at:       string
  cache_age_s:      number
  next_refresh_in:  number
}

export async function apiLiveNews(
  category?: NewsCategory,
  impact?: NewsImpact,
  limit = 50
): Promise<LiveNewsResult> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (category && category !== 'ALL') params.append('category', category)
  if (impact) params.append('impact', impact)
  return request('/news/live?' + params.toString())
}

export async function apiRefreshNews(): Promise<LiveNewsResult> {
  return request('/news/live/refresh', { method: 'POST' }, true)
}

// -- Stock Search API ----------------------------------------------------------

export interface StockSearchResult {
  symbol: string
  name: string
  sector: string
}

export interface StockFundamentals {
  // Valuation
  pe_ratio: number | null
  forward_pe: number | null
  pb_ratio: number | null
  ps_ratio: number | null
  peg_ratio: number | null
  ev_ebitda: number | null
  // Profitability
  roe: number | null
  roa: number | null
  roce: number | null
  profit_margin: number | null
  operating_margin: number | null
  gross_margin: number | null
  // Safety
  debt_to_equity: number | null
  current_ratio: number | null
  quick_ratio: number | null
  // Size / income
  market_cap: number | null
  enterprise_value: number | null
  book_value: number | null
  revenue_ttm: number | null
  ebitda_ttm: number | null
  free_cash_flow: number | null
  // Dividends
  dividend_yield: number | null
  dividend_rate: number | null
  payout_ratio: number | null
  // Growth
  revenue_growth_1yr: number | null
  profit_growth_1yr: number | null
  revenue_growth_3yr: number | null
  profit_growth_3yr: number | null
  // Identity
  company_name: string | null
  sector: string | null
  industry: string | null
  source: string
}

export interface StockShareholding {
  promoter: number | null
  fii: number | null
  dii: number | null
  public: number | null
}

export interface StockFIIActivity {
  trend: string
  note: string
  fii_pct: number | null
  color: string
}

export interface StockInstitutionalHolder {
  holder: string
  shares: number | null
  pct_held: number | null
  value_cr: number | null
}

export interface StockNewsItem {
  title: string
  source: string
  url: string
  published_at: string
  thumbnail: string
}

export interface StockAnalystVerdict {
  verdict: 'STRONG BUY' | 'BUY' | 'HOLD' | 'WEAK' | 'AVOID' | 'INSUFFICIENT DATA'
  verdict_color: string
  summary: string
  score: number
  max_score: number
  insights: string[]
  risks: string[]
  disclaimer: string
}

export interface StockDetail {
  symbol: string
  company_name: string
  exchange: string
  currency: string
  current_price: number | null
  prev_close: number | null
  change: number | null
  change_pct: number | null
  day_high: number | null
  day_low: number | null
  week_52_high: number | null
  week_52_low: number | null
  volume: number | null
  avg_volume: number | null
  eps: number | null
  beta: number | null
  sector_yf: string
  industry_yf: string
  description: string
  fundamentals: StockFundamentals
  shareholding: StockShareholding
  fii_activity: StockFIIActivity
  institutional_holders: StockInstitutionalHolder[]
  recent_news: StockNewsItem[]
  analyst_verdict: StockAnalystVerdict
  fetched_at: string
  market_cap_yf?: number | null
  // ── Exclusive differentiating data ─────────────────────────────────────────
  piotroski?: {
    score: number | null
    max: number
    signals: { name: string; pass: boolean }[]
    interpretation: string
  } | null
  altman_z?: {
    z_score: number | null
    zone: string
    zone_color: string
    zone_desc: string
  } | null
  graham_number?: {
    graham_number: number
    eps_used: number
    bvps_used: number
    current_price?: number
    premium_pct?: number | null
    is_undervalued?: boolean
  } | null
  earnings_surprise?: {
    quarter: string
    actual: number
    estimate: number
    surprise_pct: number
    beat: boolean
  }[]
}

export async function apiStockSearch(q: string, limit = 10): Promise<{ results: StockSearchResult[]; query: string }> {
  const params = new URLSearchParams({ q, limit: String(limit) })
  return request('/stock/search?' + params.toString())
}

export async function apiStockDetail(symbol: string): Promise<StockDetail> {
  return request(`/stock/${symbol.toUpperCase()}`, {}, true)
}

export async function apiStockLive(symbol: string): Promise<{
  symbol: string
  current_price: number | null
  prev_close: number | null
  change: number | null
  change_pct: number | null
  day_high: number | null
  day_low: number | null
  volume: number | null
  fetched_at: string
  error?: string
}> {
  return request(`/stock/${symbol.toUpperCase()}/live`, {}, true)
}


// ── Screener API ──────────────────────────────────────────────────────────────

export interface ScreenerPreset {
  key: string
  label: string
  icon: string
  desc: string
}

export interface ScreenerStock {
  symbol: string
  company_name: string
  sector: string
  industry: string
  current_price: number | null
  change_pct: number | null
  week_52_high: number | null
  week_52_low: number | null
  pe_ratio: number | null
  forward_pe: number | null
  pb_ratio: number | null
  peg_ratio: number | null
  ev_ebitda: number | null
  roe: number | null
  roa: number | null
  profit_margin: number | null
  operating_margin: number | null
  debt_to_equity: number | null
  current_ratio: number | null
  market_cap: number | null
  market_cap_cr: number | null
  eps: number | null
  book_value: number | null
  beta: number | null
  dividend_yield: number | null
  revenue_growth: number | null
  earnings_growth: number | null
  avg_volume: number | null
  score?: number
  exchange?: string
  volume?: number
}

export interface ScreenerResult {
  screen?: string
  results: ScreenerStock[]
  count: number
  fetched_at: string
  filters_applied?: Record<string, any>
  error?: string
}

export interface ScreenerFilterBody {
  min_pe?: number | null
  max_pe?: number | null
  min_roe?: number | null
  max_de?: number | null
  min_market_cap_cr?: number | null
  max_market_cap_cr?: number | null
  min_div_yield?: number | null
  min_revenue_growth?: number | null
  min_profit_margin?: number | null
  max_pb?: number | null
  sectors?: string[] | null
  sort_by?: string
  sort_desc?: boolean
  limit?: number
}

/** List available preset screen definitions */
export async function apiScreenerPresets(): Promise<{ presets: ScreenerPreset[] }> {
  return request('/screener/presets')
}

/** Run a predefined Yahoo Finance screen */
export async function apiScreenerPreset(screenName: string, limit = 25): Promise<ScreenerResult> {
  return request(`/screener/preset/${screenName}?limit=${limit}`, {}, true)
}

/** Custom NSE fundamental screener (Pro/Elite) */
export async function apiScreenerCustom(filters: ScreenerFilterBody): Promise<ScreenerResult> {
  return request('/screener/custom', {
    method: 'POST',
    body: JSON.stringify(filters),
  }, true)
}

/** Antigravity Quality Compounders screen */
export async function apiScreenerQuality(limit = 20): Promise<ScreenerResult> {
  return request(`/screener/quality?limit=${limit}`, {}, true)
}

/** Value picks screen */
export async function apiScreenerValue(limit = 20): Promise<ScreenerResult> {
  return request(`/screener/value?limit=${limit}`, {}, true)
}

/** High dividend yield screen */
export async function apiScreenerDividend(limit = 20): Promise<ScreenerResult> {
  return request(`/screener/dividend?limit=${limit}`, {}, true)
}

/** Enriched fundamentals for a single symbol */
export async function apiScreenerFundamentals(symbol: string): Promise<Record<string, any>> {
  return request(`/screener/fundamentals/${symbol.toUpperCase()}`, {}, true)
}


// ── New Listings API ──────────────────────────────────────────────────────────

export interface NewListing {
  symbol: string
  company_name: string
  listing_date: string
  listing_dt?: string
  exchange: 'NSE' | 'BSE' | string
  issue_price: number | null
  current_price: number | null
  change_pct: number | null
  listing_gain_pct: number | null
  market_cap: number | null
  series?: string
  gmp_price?: number | null
  gmp_pct?: number | null
}

export interface NewListingsResponse {
  listings: NewListing[]
  count: number
  days: number
}

export async function apiNewListings(days = 90, refresh = false): Promise<NewListingsResponse> {
  return request(`/new-listings?days=${days}&refresh=${refresh}`)
}


// ── Swing Trading Screener API ────────────────────────────────────────────────

export interface SwingStock {
  symbol: string
  company_name: string
  sector: string
  current_price: number | null
  change_pct_today: number | null
  week_52_high: number | null
  week_52_low: number | null
  pct_from_52h: number | null        // % below 52W high (positive = below)
  pct_from_52l: number | null        // % above 52W low
  rsi_14: number | null              // RSI(14)
  volume_ratio: number | null        // today_vol / 10d avg vol
  dma_20: number | null
  dma_50: number | null
  dma_200: number | null
  dma_signal: string | null          // e.g. "20>50>200 ✅" or "Below 200 ⚠️"
  market_cap_cr: number | null
  pe_ratio: number | null
  swing_score: number | null         // 0-100 composite swing signal
  signal_tags: string[]              // e.g. ["Near High", "High Volume", "RSI OK"]
}

export interface SwingResult {
  preset: string
  label: string
  description: string
  results: SwingStock[]
  count: number
  fetched_at: string
  fetch_time_sec?: number
}

/** Run a swing trading preset screen (Pro/Elite only) */
export async function apiSwingScreen(presetName: string, limit = 30): Promise<SwingResult> {
  return request(`/screener/swing/${presetName}?limit=${limit}`, {}, true)
}


// ── Global Markets Pulse API ──────────────────────────────────────────────────

export interface GlobalMarketTicker {
  symbol: string
  name: string
  unit: string
  key: boolean
  current_price: number
  prev_close: number | null
  change: number
  change_pct: number
  direction: 'UP' | 'DOWN' | 'FLAT'
}

export interface GlobalGroupMeta {
  label: string
  icon: string
  color: string
}

export interface GlobalMarketsResult {
  groups: {
    gift_nifty: GlobalMarketTicker[]
    us_markets: GlobalMarketTicker[]
    asia: GlobalMarketTicker[]
    europe: GlobalMarketTicker[]
    commodities: GlobalMarketTicker[]
    forex: GlobalMarketTicker[]
  }
  group_meta: Record<string, GlobalGroupMeta>
  impact_score: 'BULLISH' | 'BEARISH' | 'MIXED'
  fetched_at: number
  cache_age_s: number
  next_refresh_in: number
  stale?: boolean
}

/** Live global markets pulse — Gift Nifty, US, Asia, Europe, Commodities, Forex. Public. */
export async function apiGlobalMarkets(forceRefresh = false): Promise<GlobalMarketsResult> {
  return request(`/markets/global${forceRefresh ? '?force_refresh=true' : ''}`)
}


// ── Sector Intelligence Hub API ───────────────────────────────────────────────

export interface SectorMover {
  symbol: string
  price: number
  change_pct: number
}

export interface SectorNewsItem {
  title: string
  url: string
  source: string
  impact: 'HIGH' | 'MEDIUM' | 'LOW'
  published: string
}

export interface SectorLive {
  name: string
  symbol: string
  icon: string
  color: string
  current: number
  day_pct: number
  week_pct: number
  month_pct: number
  ytd_pct: number
  rs_nifty: number
  sentiment: 'BULLISH' | 'BEARISH' | 'MIXED'
  top_movers: SectorMover[]
  news: SectorNewsItem[]
  macro_watch: string[]
  global_peer: string
  sensitivity: string
  news_count: number
}

export interface SectorHubResult {
  sectors: SectorLive[]
  fetched_at: number
  cache_age_s: number
  next_refresh_in: number
  news_total: number
  stale?: boolean
}

/** Live sector hub — all 15 NSE sector indices, movers, news, macro signals. Public. 15-min cache. */
export async function apiSectorsLive(forceRefresh = false): Promise<SectorHubResult> {
  return request(`/sectors/live${forceRefresh ? '?force_refresh=true' : ''}`)
}


// ── IPO Intelligence Hub API ──────────────────────────────────────────────────

export interface IpoGmp {
  gmp_price: number
  premium_pct: number | null
  est_listing: number | null
  source: string
}

export interface IpoSubscription {
  qib: number
  nii: number
  rii: number
  total: number
  updated_at: string
}

export interface IpoAiVerdict {
  verdict: 'APPLY' | 'CAUTIOUS' | 'AVOID'
  confidence: 'HIGH' | 'MEDIUM' | 'LOW'
  summary: string
  reasons: string[]
  risks: string[]
  listing_outlook: 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE'
  score_commentary?: string
}

export interface IpoScoreData {
  composite_score: number
  grade: 'S' | 'A' | 'B+' | 'B' | 'C+' | 'C' | 'D'
  gmp_score: number
  sub_score: number
  qual_score: number
  val_score: number
  time_score: number
  fund_score: number
  max_scores: { gmp: number; sub: number; qual: number; val: number; timing: number; fund: number }
  gmp_reach_probability: 'VERY_HIGH' | 'HIGH' | 'MODERATE' | 'LOW'
  gmp_reach_label: string
  nifty_regime: 'BULLISH' | 'NEUTRAL' | 'BEARISH'
  nifty_20d_ret: number
  allotment_chance?: string
  listing_day?: string
  score_positives: string[]
  score_risks: string[]
}

export interface IpoDetail {
  id: string
  company_name: string
  symbol: string
  industry: string
  price_band: string
  price_band_min: number | null
  price_band_max: number | null
  lot_size: number | null
  min_investment: number | null
  issue_size_cr: number | null
  issue_type: string
  exchange: string
  registrar: string
  open_date: string | null
  close_date: string | null
  allotment_date: string | null
  listing_date: string | null
  days_to_open: number | null
  days_to_close: number | null
  days_to_listing: number | null
  status: 'UPCOMING' | 'OPEN' | 'ALLOTMENT' | 'LISTED' | 'UNKNOWN'
  rhp_url: string
  drhp_url: string
  source: string
  gmp: IpoGmp | null
  subscription: IpoSubscription | null
  ai_verdict: IpoAiVerdict
  score_data: IpoScoreData | null
  allotment_chance?: string
  listing_day_of_week?: string
}

export interface IpoHubStats {
  total: number
  open: number
  upcoming: number
  allotment: number
  listed: number
}

export interface IpoHubResult {
  ipos: IpoDetail[]
  stats: IpoHubStats
  gmp_count: number
  fetched_at: number
  cache_age_s: number
  next_refresh_in: number
  stale?: boolean
}

/** Live IPO Intelligence Hub — all IPOs with GMP, subscription, AI verdict. Public. 30-min cache. */
export async function apiIpoHub(forceRefresh = false): Promise<IpoHubResult> {
  return request(`/ipo/hub${forceRefresh ? '?force_refresh=true' : ''}`)
}

// ── Stock Signals ─────────────────────────────────────────────────────────────

export interface StockSignal {
  id:            string
  symbol:        string
  title:         string
  description:   string | null
  timeframe:     string | null
  signal_type:   'BULLISH' | 'BEARISH' | 'NEUTRAL'
  support:       number | null
  resistance:    number | null
  target:        number | null
  stoploss:      number | null
  image_url:     string | null
  plan_required: 'free' | 'pro' | 'elite'
  is_published:  boolean
  locked:        boolean
  created_at:    string
}

export interface StockSignalList {
  signals: StockSignal[]
  total:   number
  page:    number
  limit:   number
}

/** Fetch paginated list of signals (requires auth). */
export async function apiGetSignals(page = 1, limit = 20, symbol?: string): Promise<StockSignalList> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) })
  if (symbol) params.set('symbol', symbol)
  return request<StockSignalList>(`/signals?${params}`, {}, true)
}

/** Upload a new signal chart image with metadata (elite admin only). */
export async function apiUploadSignal(form: FormData): Promise<{ ok: boolean; signal: StockSignal }> {
  const token = await getAccessToken()
  const res = await fetch(`${API_BASE}/signals/upload`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: 'Upload failed' }))
    throw new ApiError(res.status, body.detail || 'Upload failed')
  }
  return res.json()
}

/** Delete a signal by ID (elite admin only). */
export async function apiDeleteSignal(id: string): Promise<{ ok: boolean }> {
  return request(`/signals/${id}`, { method: 'DELETE' }, true)
}

// ── Crypto Payments ───────────────────────────────────────────────────────────

export interface CryptoCreateRequest {
  plan: 'pro' | 'elite'
  billing_period: 'monthly' | 'yearly'
  coin: 'usdttrc20' | 'btc' | 'eth'
}

export interface CryptoPaymentResponse {
  payment_id: string
  nowpay_id: string
  pay_address: string
  pay_amount: number
  pay_currency: string
  coin_display: string
  amount_inr: number
  plan: string
  billing_period: string
  expires_at: string
  status: string
}

export interface CryptoPaymentStatus {
  payment_id: string
  status: 'waiting' | 'confirming' | 'confirmed' | 'failed' | 'expired' | 'refunded'
  plan: string
  pay_currency: string
  pay_address: string
  pay_amount: number
  amount_inr: number
  confirmed_at: string | null
  subscription_end: string | null
}

/** Create a NOWPayments crypto invoice (requires auth). */
export async function apiCreateCryptoPayment(body: CryptoCreateRequest): Promise<CryptoPaymentResponse> {
  return request<CryptoPaymentResponse>('/crypto/create-payment', {
    method: 'POST',
    body: JSON.stringify(body),
  }, true)
}

/** Poll the status of a crypto payment (requires auth). */
export async function apiGetCryptoStatus(paymentId: string): Promise<CryptoPaymentStatus> {
  return request<CryptoPaymentStatus>(`/crypto/payment-status/${paymentId}`, {}, true)
}

// ── Kepler Radar (Digest Correlations) ───────────────────────────────────────

export interface CorrelationSector {
  name: string
  ticker_examples: string[]
  direction: 'BULLISH' | 'BEARISH' | 'NEUTRAL'
  magnitude: 'HIGH' | 'MEDIUM' | 'LOW'
  reason: string
}

export interface CorrelationStock {
  symbol: string
  company: string
  direction: 'BULLISH' | 'BEARISH'
  reason: string
  confidence: 'HIGH' | 'MEDIUM' | 'LOW'
}

export interface Correlation {
  id: string
  theme: string
  theme_icon: string
  headline: string
  trigger_headlines: string[]
  causal_chain: string
  impact_sectors: CorrelationSector[]
  beneficiary_sectors: CorrelationSector[]
  key_stocks_to_watch: CorrelationStock[]
  confidence: 'HIGH' | 'MEDIUM' | 'LOW'
  time_horizon: 'TODAY' | 'SHORT_TERM' | 'MEDIUM_TERM'
  sentiment: 'BULLISH' | 'BEARISH' | 'NEUTRAL'
  supporting_news_count: number
  locked?: boolean   // set for free users
}

export interface RadarResponse {
  status: 'ready' | 'generating' | 'unavailable' | 'locked'
  date: string
  is_pro: boolean
  message?: string
  generated_at?: string
  market_mood_reasoning?: string
  dominant_theme?: string
  total_correlations?: number
  correlations: Correlation[] | null
}

/** Fetch Kepler Radar correlation intelligence for today's digest (requires auth). */
export async function apiGetCorrelations(): Promise<RadarResponse> {
  return request<RadarResponse>('/digest/correlations', {}, true)
}

/** Admin: force-regenerate today's Kepler Radar correlations. */
export async function apiRegenerateCorrelations(): Promise<{ ok: boolean; message: string }> {
  return request('/admin/regenerate-correlations', { method: 'POST' }, true)
}

// ── Kepler Picks Types ────────────────────────────────────────────────────────

export type PickConviction = 'VERY_HIGH' | 'HIGH' | 'MODERATE' | 'WATCHLIST'
export type PickCategory   = 'SWING' | 'MOMENTUM' | 'POSITIONAL' | 'VALUE'

export interface PickFundamentals {
  pe_ratio?: number | null
  pb_ratio?: number | null
  roe?: number | null
  market_cap_cr?: number | null
  dividend_yield?: number | null
  debt_to_equity?: number | null
  revenue_cagr_3y?: number | null
  promoter_holding?: number | null
  eps?: number | null
}

export interface PickThesis {
  thesis: string
  strengths: string[]
  risks: string[]
  catalyst: string
  invalidation: string
}

export interface KeplerPick {
  // Identity
  symbol: string
  symbol_ns: string
  sector: string
  price: number

  // Conviction
  conviction: PickConviction
  conviction_label: string
  conviction_color: string
  conviction_score: number
  category: PickCategory
  timeframe: string
  timeframe_icon: string

  // Score dimensions
  tech_score: number
  momentum_score: number
  pattern_score: number
  fund_score: number
  setup_score: number

  // Technical indicators
  ema20?: number | null
  ema50?: number | null
  ema200?: number | null
  rsi: number
  macd: number
  macd_signal: number
  macd_above: boolean
  high_52w?: number | null
  low_52w?: number | null
  pct_from_52h: number
  pct_from_52l: number
  vol_ratio: number
  ret_30d: number
  rs_vs_nifty: number
  vcp_tightening: boolean
  ema_perfect: boolean
  ema_above_50_200: boolean
  golden_cross: boolean
  patterns: string[]
  atr: number

  // Trade levels
  entry_low: number
  entry_high: number
  stop_loss: number
  sl_pct: number
  target1: number
  target2: number
  rr_ratio: number

  // Enriched data
  fundamentals?: PickFundamentals | null
  ai_thesis: PickThesis
}

export interface KeplerPicksResult {
  picks: KeplerPick[]
  total: number
  category_counts: { swing: number; momentum: number; positional: number; value: number }
  nifty_ret_30d: number
  universe_scanned: number
  candidates_found: number
  generated_at: string
  fetched_at: number
  cache_age_s: number
  next_refresh_in: number
  stale?: boolean
}

/** Kepler Picks — high-conviction stock picks with AI thesis. 4-hour cache. */
export async function apiPicksCurated(forceRefresh = false): Promise<KeplerPicksResult> {
  const qs = forceRefresh ? '?force_refresh=true' : ''
  return request<KeplerPicksResult>(`/picks/curated${qs}`)
}

// ── Swing Strategy Types ───────────────────────────────────────────────────────

export interface HorizonStats {
  total_trades: number
  win_rate: number | null
  avg_return: number | null
  avg_win: number | null
  avg_loss: number | null
  max_drawdown: number | null
  profit_factor: number | null
  expectancy: number | null
  sharpe: number | null
  insufficient_data: boolean
}

export interface SwingStrategy {
  key: string
  label: string
  icon: string
  description: string
  color: string
  is_active: boolean
  status_reason: string
  win_rate: number | null
  avg_return: number | null
  profit_factor: number | null
  max_drawdown: number | null
  sharpe: number | null
  expectancy: number | null
  total_trades: number
  target_horizon: number
  horizon_stats: Record<string, HorizonStats>
}

export interface StrategyLeaderboardItem {
  key: string
  label: string
  icon: string
  color: string
  is_active: boolean
  win_rate: number | null
  avg_return: number | null
  profit_factor: number | null
  max_drawdown: number | null
  sharpe: number | null
  expectancy: number | null
  total_trades: number
  target_horizon: number
  status_reason: string
}

export interface ProbabilityBreakdown {
  ml_component: number
  strategy_component: number
  news_component: number
  fundamental_component: number
  news_boost_pp: number
  ml_raw_score: number
  strategy_win_rate: number | null
}

export interface ExpectedReturn {
  base: number
  pessimistic: number
  optimistic: number
}

export interface NewsSentiment {
  symbol: string
  sentiment_score: number
  sentiment_label: 'BULLISH' | 'BEARISH' | 'NEUTRAL'
  news_catalyst: boolean
  news_risk: boolean
  top_headline: string | null
  reasoning: string
  article_count: number
  sentiment_boost: number
  source: string
}

export interface StockProbability {
  win_probability: number
  confidence_band: 'HIGH' | 'MODERATE' | 'LOW'
  confidence_color: string
  best_strategy: string | null
  best_strategy_wr: number | null
  triggered_strategies: string[]
  recommended_hold_days: number
  expected_return: ExpectedReturn
  probability_breakdown: ProbabilityBreakdown
  news_catalyst: boolean
  news_risk: boolean
  news_headline: string | null
  weights_source: 'hermes' | 'default'
}

export interface SwingStrategiesResult {
  strategies: SwingStrategy[]
  total: number
  active_count: number
  universe_size: number
  gain_threshold: number
  win_rate_min: number
  computed_at: string | null
  from_cache: boolean
}

export interface BestStrategyStock extends StockProbability {
  symbol: string
  company_name: string
  sector: string
  current_price: number
  change_pct_today: number | null
  rsi_14: number | null
  volume_ratio: number | null
  pct_from_52h: number | null
  pct_from_52l: number | null
  dma_signal: string | null
  swing_score: number | null
  signal_tags: string[]
  triggered_best_strategies: string[]
  news_sentiment?: string
  news_score?: number
  news_catalyst: boolean
  news_risk: boolean
  news_headline: string | null
}

export interface BestStrategyStocksResult {
  stocks: BestStrategyStock[]
  total: number
  best_strategies: string[]
  min_win_rate: number
  generated_at: string
}

// ── New Picks Result (with probability fields) ─────────────────────────────────
export interface KeplerPickV2 extends KeplerPick {
  win_probability?: number
  confidence_band?: 'HIGH' | 'MODERATE' | 'LOW'
  confidence_color?: string
  best_strategy?: string | null
  best_strategy_wr?: number | null
  triggered_strategies?: string[]
  recommended_hold_days?: number
  expected_return?: ExpectedReturn
  probability_breakdown?: ProbabilityBreakdown
  news_sentiment?: 'BULLISH' | 'BEARISH' | 'NEUTRAL'
  news_score?: number
  news_catalyst?: boolean
  news_risk?: boolean
  news_headline?: string | null
}

export interface KeplerPicksV2Result extends KeplerPicksResult {
  picks: KeplerPickV2[]
  avg_win_probability?: number
  high_prob_picks?: number
  strategy_leaderboard?: StrategyLeaderboardItem[]
}

// ── Swing Strategy API Functions ───────────────────────────────────────────────

/** Get all 14 strategies with backtest stats (cached weekly) */
export async function apiSwingStrategies(): Promise<SwingStrategiesResult> {
  return request<SwingStrategiesResult>('/api/v1/swing/strategies')
}

/** Get strategy leaderboard sorted by win rate */
export async function apiSwingLeaderboard(topN = 14): Promise<{ leaderboard: StrategyLeaderboardItem[]; top_n: number }> {
  return request(`/api/v1/swing/leaderboard?top_n=${topN}`)
}

/** Get full backtest detail for one strategy */
export async function apiStrategyBacktest(strategyKey: string): Promise<SwingStrategy & { computed_at: string }> {
  return request(`/api/v1/swing/backtest/${strategyKey}`)
}

/** Get win probability for a single stock */
export async function apiStockProbability(symbol: string): Promise<StockProbability & { symbol: string; price: number; rsi: number }> {
  return request(`/api/v1/picks/probability/${symbol}`)
}

/** Get stocks filtered by best-performing strategies only */
export async function apiBestStrategyStocks(minWinRate = 60, limit = 20): Promise<BestStrategyStocksResult> {
  return request<BestStrategyStocksResult>(
    `/api/v1/swing/best-strategy-stocks?min_win_rate=${minWinRate}&limit=${limit}`,
    {}, true
  )
}

/** Get enhanced picks with probability and news (new endpoint) */
export async function apiPicksV2(forceRefresh = false): Promise<KeplerPicksV2Result> {
  const qs = forceRefresh ? '?force_refresh=true' : ''
  return request<KeplerPicksV2Result>(`/api/v1/picks${qs}`, {}, true)
}

/** Run a swing preset with optional probability enrichment */
export async function apiSwingPresetWithProb(preset: string, limit = 30): Promise<{ results: BestStrategyStock[]; count: number; label: string; icon: string; color: string }> {
  return request(`/api/v1/swing/preset/${preset}?limit=${limit}&with_probability=true`, {}, true)
}

