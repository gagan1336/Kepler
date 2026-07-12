'use client'

import { useState, useCallback, useEffect } from 'react'
import {
  apiScreenerPreset,
  apiScreenerCustom,
  apiScreenerQuality,
  apiScreenerValue,
  apiScreenerDividend,
  apiStockDetail,
  type ScreenerStock,
  type ScreenerResult,
  type ScreenerFilterBody,
  type StockDetail,
} from '@/lib/api'
import SwingScreener from './SwingScreener'
import StockDetailPanel from './StockDetailPanel'

// ── Types ─────────────────────────────────────────────────────────────────────
type ScreenTab = 'curated' | 'preset' | 'custom' | 'swing'
type CuratedType = 'quality' | 'value' | 'dividend'
type SortDir = 'asc' | 'desc'

// ── Helper formatters ─────────────────────────────────────────────────────────
const fmt = (v: number | null | undefined, dec = 2, suffix = '') =>
  v == null ? '—' : `${v.toFixed(dec)}${suffix}`

const fmtCr = (v: number | null | undefined) => {
  if (v == null) return '—'
  if (v >= 100000) return `₹${(v / 100000).toFixed(1)}L Cr`
  if (v >= 1000) return `₹${(v / 1000).toFixed(1)}K Cr`
  return `₹${v.toFixed(0)} Cr`
}

const fmtChg = (v: number | null | undefined) => {
  if (v == null) return <span style={{ color: 'var(--text-tertiary)' }}>—</span>
  const pos = v >= 0
  return (
    <span style={{ color: pos ? 'var(--gain)' : 'var(--loss)', fontWeight: 600 }}>
      {pos ? '+' : ''}{v.toFixed(2)}%
    </span>
  )
}

const scoreColor = (s?: number) => {
  if (s == null) return 'var(--text-tertiary)'
  if (s >= 75) return '#10b981'
  if (s >= 55) return '#3b82f6'
  if (s >= 35) return '#f59e0b'
  return '#ef4444'
}

// ── SVG Icons ─────────────────────────────────────────────────────────────────
const IconDiamond = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2" />
    <line x1="12" y1="2" x2="12" y2="22" />
    <path d="m2 8.5 10 7 10-7" />
  </svg>
)
const IconColumns = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="18" rx="1" />
    <rect x="14" y="3" width="7" height="18" rx="1" />
  </svg>
)
const IconTrendUp = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
    <polyline points="16 7 22 7 22 13" />
  </svg>
)
const IconSettings = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.07 4.93a10 10 0 0 1 1.99 3.4M4.93 4.93a10 10 0 0 0-1.99 3.4M2.05 13A10 10 0 0 0 4.93 19.07M19.07 19.07A10 10 0 0 0 21.95 13" />
  </svg>
)
const IconActivity = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
  </svg>
)
const IconFilter = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
  </svg>
)
const IconStar = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
  </svg>
)
const IconLock = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
  </svg>
)
const IconSearch = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
  </svg>
)
const IconRefresh = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 4 23 10 17 10" /><polyline points="1 20 1 14 7 14" />
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
  </svg>
)

// ── Curated screen definitions ────────────────────────────────────────────────
const CURATED_SCREENS = [
  {
    key: 'quality' as CuratedType,
    label: 'Quality Compounders',
    icon: <IconDiamond />,
    desc: 'ROE > 15% · D/E < 1.0 · PE < 50 · positive growth',
    color: '#10b981',
    accentBg: 'rgba(16,185,129,0.06)',
    accentBorder: 'rgba(16,185,129,0.25)',
    badge: 'ANTIGRAVITY PICK',
  },
  {
    key: 'value' as CuratedType,
    label: 'Value Picks',
    icon: <IconColumns />,
    desc: 'PE < 20 · PB < 3 · ROE > 8% · D/E < 1.5',
    color: '#3b82f6',
    accentBg: 'rgba(59,130,246,0.06)',
    accentBorder: 'rgba(59,130,246,0.25)',
    badge: 'DEEP VALUE',
  },
  {
    key: 'dividend' as CuratedType,
    label: 'Dividend Income',
    icon: <IconStar />,
    desc: 'Yield > 2% · PE < 30 · profit margin > 5%',
    color: '#f59e0b',
    accentBg: 'rgba(245,158,11,0.06)',
    accentBorder: 'rgba(245,158,11,0.25)',
    badge: 'INCOME',
  },
]

// ── Preset screen definitions ─────────────────────────────────────────────────
const PRESET_OPTIONS = [
  { key: 'most_actives',          label: 'Most Active',          color: '#ef4444' },
  { key: 'day_gainers',           label: 'Top Gainers',          color: '#10b981' },
  { key: 'day_losers',            label: 'Top Losers',           color: '#ef4444' },
  { key: 'undervalued_growth',    label: 'Undervalued Growth',   color: '#6366f1' },
  { key: 'growth_technology',     label: 'Technology Growth',    color: '#3b82f6' },
  { key: 'aggressive_small_caps', label: 'Aggressive Small Cap', color: '#8b5cf6' },
  { key: 'small_cap_gainers',     label: 'Small Cap Gainers',    color: '#a78bfa' },
  { key: 'undervalued_large_caps','label': 'Undervalued Large Cap','color': '#0ea5e9' },
]

// ── Column config ─────────────────────────────────────────────────────────────
const COLUMNS = [
  { key: 'symbol',           label: 'Symbol',    sortable: true,  width: '140px' },
  { key: 'current_price',    label: 'Price',     sortable: true,  width: '90px'  },
  { key: 'today_change_pct', label: 'Day Chg',   sortable: true,  width: '82px'  },
  { key: 'change_pct',       label: '52W Chg',   sortable: true,  width: '82px'  },
  { key: 'market_cap_cr',    label: 'Mkt Cap',   sortable: true,  width: '110px' },
  { key: 'pe_ratio',         label: 'PE',        sortable: true,  width: '70px'  },
  { key: 'pb_ratio',         label: 'PB',        sortable: true,  width: '70px'  },
  { key: 'roe',              label: 'ROE %',     sortable: true,  width: '76px'  },
  { key: 'debt_to_equity',   label: 'D/E',       sortable: true,  width: '70px'  },
  { key: 'dividend_yield',   label: 'Div Yld',   sortable: true,  width: '78px'  },
  { key: 'profit_margin',    label: 'Margin %',  sortable: true,  width: '78px'  },
  { key: 'revenue_growth',   label: 'Rev Grw',   sortable: true,  width: '78px'  },
  { key: 'quality_score',    label: 'Score',     sortable: true,  width: '70px'  },
]

// ── Number input for filter panel ─────────────────────────────────────────────
function NumInput({
  label, value, onChange, placeholder,
}: { label: string; value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <div className="ss-filter-field">
      <label className="ss-filter-label">{label}</label>
      <input
        type="number"
        className="ss-filter-input"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function StockScreener({ userPlan = 'free' }: { userPlan?: string }) {
  const [tab, setTab]             = useState<ScreenTab>('curated')
  const [curatedType, setCuratedType] = useState<CuratedType>('quality')
  const [presetKey, setPresetKey] = useState('most_actives')
  const [results, setResults]     = useState<ScreenerStock[]>([])
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState<string | null>(null)
  const [fetchedAt, setFetchedAt] = useState<string | null>(null)
  const [fetchTime, setFetchTime] = useState<number | null>(null)
  const [elapsed, setElapsed]     = useState(0)
  const [sortField, setSortField] = useState<string>('market_cap_cr')
  const [sortDir, setSortDir]     = useState<SortDir>('desc')

  // Stock detail panel state
  const [selectedStock, setSelectedStock] = useState<StockDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [detailError, setDetailError]     = useState<string | null>(null)

  const handleSelectStock = useCallback(async (symbol: string) => {
    setDetailError(null)
    setLoadingDetail(true)
    setSelectedStock(null)
    try {
      const detail = await apiStockDetail(symbol)
      setSelectedStock(detail)
    } catch (e: any) {
      setDetailError(e.message || `Could not load data for ${symbol}. Please try again.`)
    } finally {
      setLoadingDetail(false)
    }
  }, [])

  const handleBack = () => {
    setSelectedStock(null)
    setDetailError(null)
  }

  useEffect(() => {
    if (!loading) { setElapsed(0); return }
    setElapsed(0)
    const t = setInterval(() => setElapsed(s => s + 1), 1000)
    return () => clearInterval(t)
  }, [loading])

  const [filters, setFilters] = useState({
    min_pe: '', max_pe: '', min_roe: '', max_de: '',
    min_market_cap_cr: '', max_market_cap_cr: '',
    min_div_yield: '', min_revenue_growth: '',
    min_profit_margin: '', max_pb: '',
  })

  const isPro = userPlan === 'pro' || userPlan === 'elite'
  const setFilter = (key: string) => (val: string) =>
    setFilters(prev => ({ ...prev, [key]: val }))
  const toNum = (v: string) => v === '' ? null : parseFloat(v)

  const fetchCurated = useCallback(async (type: CuratedType) => {
    setLoading(true); setError(null); setFetchTime(null)
    const t0 = Date.now()
    try {
      let res: ScreenerResult
      if (type === 'quality')   res = await apiScreenerQuality(30)
      else if (type === 'value') res = await apiScreenerValue(30)
      else                       res = await apiScreenerDividend(30)
      setResults(res.results || [])
      setFetchedAt(res.fetched_at)
      setFetchTime(Math.round((Date.now() - t0) / 1000))
    } catch (e: any) {
      setError(e.message || 'Failed to load screen')
      setResults([])
    } finally { setLoading(false) }
  }, [])

  const fetchPreset = useCallback(async (key: string) => {
    setLoading(true); setError(null); setFetchTime(null)
    const t0 = Date.now()
    try {
      const res = await apiScreenerPreset(key, 30)
      setResults(res.results || [])
      setFetchedAt(res.fetched_at)
      setFetchTime(Math.round((Date.now() - t0) / 1000))
    } catch (e: any) {
      setError(e.message || 'Failed to load preset')
      setResults([])
    } finally { setLoading(false) }
  }, [])

  const runCustom = useCallback(async () => {
    if (!isPro) return
    setLoading(true); setError(null); setFetchTime(null)
    const t0 = Date.now()
    try {
      const body: ScreenerFilterBody = {
        min_pe: toNum(filters.min_pe), max_pe: toNum(filters.max_pe),
        min_roe: toNum(filters.min_roe), max_de: toNum(filters.max_de),
        min_market_cap_cr: toNum(filters.min_market_cap_cr),
        max_market_cap_cr: toNum(filters.max_market_cap_cr),
        min_div_yield: toNum(filters.min_div_yield),
        min_revenue_growth: toNum(filters.min_revenue_growth),
        min_profit_margin: toNum(filters.min_profit_margin),
        max_pb: toNum(filters.max_pb),
        sort_by: sortField, sort_desc: sortDir === 'desc', limit: 50,
      }
      const res = await apiScreenerCustom(body)
      setResults(res.results || [])
      setFetchedAt(res.fetched_at)
      setFetchTime(Math.round((Date.now() - t0) / 1000))
    } catch (e: any) {
      setError(e.message || 'Screen failed')
      setResults([])
    } finally { setLoading(false) }
  }, [filters, sortField, sortDir, isPro])

  useEffect(() => {
    if (tab === 'curated') fetchCurated(curatedType)
    else if (tab === 'preset') fetchPreset(presetKey)
  }, [tab, curatedType, presetKey, fetchCurated, fetchPreset])

  const sorted = [...results].sort((a, b) => {
    const av = (a as any)[sortField]
    const bv = (b as any)[sortField]
    if (av == null && bv == null) return 0
    if (av == null) return 1
    if (bv == null) return -1
    return sortDir === 'desc' ? bv - av : av - bv
  })

  const toggleSort = (field: string) => {
    if (sortField === field) setSortDir(d => d === 'desc' ? 'asc' : 'desc')
    else { setSortField(field); setSortDir('desc') }
  }

  const TABS_DEF = [
    { key: 'curated' as ScreenTab, label: 'Curated Picks',   icon: <IconStar /> },
    { key: 'swing'   as ScreenTab, label: 'Swing Trading',   icon: <IconActivity /> },
    { key: 'preset'  as ScreenTab, label: 'Market Presets',  icon: <IconTrendUp /> },
    { key: 'custom'  as ScreenTab, label: 'Custom Filter',   icon: <IconSettings /> },
  ]

  // If a stock detail is selected, render the detail panel instead of the screener
  if (loadingDetail) {
    return (
      <div className="ss-wrap">
        <div className="space-y-5 animate-pulse max-w-3xl">
          <div className="glass-card p-6">
            <div className="skeleton h-7 w-40 mb-2" />
            <div className="skeleton h-10 w-64 mb-4" />
            <div className="grid grid-cols-4 gap-3">
              {[1,2,3,4].map(i => <div key={i} className="skeleton h-12 rounded-xl" />)}
            </div>
          </div>
          <div className="glass-card p-5">
            <div className="skeleton h-4 w-32 mb-4" />
            <div className="grid grid-cols-4 gap-3">
              {[1,2,3,4,5,6,7,8].map(i => <div key={i} className="skeleton h-16 rounded-xl" />)}
            </div>
          </div>
          <p className="text-center text-sm text-[#333] animate-pulse">
            ⏳ Fetching live data from NSE… (10–15 seconds)
          </p>
        </div>
      </div>
    )
  }

  if (selectedStock) {
    return (
      <div className="ss-wrap">
        <StockDetailPanel stock={selectedStock} onBack={handleBack} />
      </div>
    )
  }

  if (detailError) {
    return (
      <div className="ss-wrap">
        <div className="glass-card p-8 text-center border-[rgba(239,68,68,0.2)] max-w-xl">
          <div className="text-4xl mb-3">⚠️</div>
          <h3 className="text-white font-bold mb-2">Could Not Load Stock Data</h3>
          <p className="text-sm text-[#555] mb-5">{detailError}</p>
          <button onClick={handleBack} className="btn-brand text-sm py-2 px-6">Back to Screener</button>
        </div>
      </div>
    )
  }

  return (
    <div className="ss-wrap">
      <style>{`
        .ss-wrap {
          background: var(--bg-elevated, #131315);
          border-radius: 16px;
          padding: 24px;
          border: 1px solid var(--border, rgba(255,255,255,0.08));
          font-family: var(--font-primary, 'Inter', system-ui, sans-serif);
        }

        /* ── Section Header ── */
        .ss-header {
          display: flex;
          align-items: center;
          gap: 14px;
          margin-bottom: 22px;
          padding-bottom: 18px;
          border-bottom: 1px solid var(--border-subtle, rgba(255,255,255,0.04));
        }
        .ss-header-icon {
          width: 40px; height: 40px;
          background: var(--accent-dim, rgba(201,163,78,0.10));
          border: 1px solid var(--accent-border, rgba(201,163,78,0.25));
          border-radius: 10px;
          display: flex; align-items: center; justify-content: center;
          color: var(--accent, #C9A34E);
          flex-shrink: 0;
        }
        .ss-header-text { flex: 1; }
        .ss-header-title {
          font-size: 17px; font-weight: 700;
          color: var(--text-primary, #F2F2F0);
          letter-spacing: -0.3px; margin: 0 0 3px;
        }
        .ss-header-sub {
          font-size: 12px;
          color: var(--text-tertiary, #5C5C60);
          margin: 0;
        }
        .ss-header-badge {
          background: var(--accent-dim, rgba(201,163,78,0.1));
          color: var(--accent, #C9A34E);
          border: 1px solid var(--accent-border, rgba(201,163,78,0.25));
          font-size: 11px; font-weight: 700;
          padding: 4px 10px; border-radius: 99px;
          letter-spacing: 0.6px; white-space: nowrap;
        }
        .ss-header-status {
          font-size: 12px;
          color: var(--text-tertiary, #5C5C60);
          font-family: var(--font-mono, 'JetBrains Mono', monospace);
          white-space: nowrap;
        }
        .ss-header-status.scanning { color: #818cf8; }
        .ss-header-status.done     { color: var(--gain, #3DDC84); }

        /* ── Tabs ── */
        .ss-tab-row {
          display: flex; gap: 4px;
          margin-bottom: 22px;
          border-bottom: 1px solid var(--border-subtle, rgba(255,255,255,0.04));
          padding-bottom: 0;
        }
        .ss-tab-btn {
          display: flex; align-items: center; gap: 7px;
          background: none; border: none;
          padding: 9px 16px 11px;
          cursor: pointer; font-size: 14px; font-weight: 600;
          color: var(--text-tertiary, #5C5C60);
          border-bottom: 2px solid transparent;
          transition: all 0.18s;
          border-radius: 8px 8px 0 0;
          font-family: var(--font-primary, 'Inter', system-ui, sans-serif);
        }
        .ss-tab-btn.active {
          color: var(--accent, #C9A34E);
          border-bottom-color: var(--accent, #C9A34E);
        }
        .ss-tab-btn.active-swing {
          color: #818cf8;
          border-bottom-color: #818cf8;
        }
        .ss-tab-btn:hover:not(.active):not(.active-swing) {
          color: var(--text-secondary, #9A9A9E);
          background: rgba(255,255,255,0.03);
        }

        /* ── Curated cards ── */
        .ss-curated-row {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 12px; margin-bottom: 22px;
        }
        .ss-curated-card {
          background: var(--bg-surface, #0F0F11);
          border: 1px solid var(--border, rgba(255,255,255,0.08));
          border-left: 3px solid transparent;
          border-radius: 12px; padding: 16px;
          cursor: pointer; transition: all 0.2s;
          position: relative; overflow: hidden;
        }
        .ss-curated-card:hover {
          border-color: var(--border-hairline, rgba(255,255,255,0.12));
          transform: translateY(-1px);
        }
        .ss-curated-card.active {
          border-left-color: var(--c-color);
          background: var(--c-bg);
          border-color: var(--c-border);
          border-left-color: var(--c-color);
          box-shadow: 0 0 20px var(--c-shadow, transparent);
        }
        .ss-curated-icon {
          width: 32px; height: 32px; border-radius: 8px;
          display: flex; align-items: center; justify-content: center;
          margin-bottom: 10px;
          background: var(--c-bg, rgba(255,255,255,0.04));
          color: var(--c-color, #94a3b8);
        }
        .ss-curated-label {
          font-size: 14px; font-weight: 700;
          color: var(--text-primary, #F2F2F0); margin-bottom: 5px;
        }
        .ss-curated-desc {
          font-size: 12px; color: var(--text-tertiary, #5C5C60);
          line-height: 1.5; font-family: var(--font-mono, monospace);
        }
        .ss-curated-badge {
          position: absolute; top: 12px; right: 12px;
          font-size: 11px; font-weight: 700; letter-spacing: 0.4px;
          padding: 2px 7px; border-radius: 6px;
          color: var(--c-color); border: 1px solid var(--c-border);
          background: var(--c-bg);
        }

        /* ── Preset grid ── */
        .ss-preset-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 8px; margin-bottom: 22px;
        }
        .ss-preset-btn {
          background: var(--bg-surface, #0F0F11);
          border: 1px solid var(--border, rgba(255,255,255,0.08));
          border-radius: 10px; padding: 11px 14px;
          cursor: pointer; text-align: left;
          transition: all 0.18s; display: flex;
          flex-direction: column; gap: 4px;
          font-family: var(--font-primary, 'Inter', system-ui, sans-serif);
        }
        .ss-preset-btn:hover { border-color: rgba(255,255,255,0.16); }
        .ss-preset-btn.active {
          border-color: var(--p-color);
          background: color-mix(in srgb, var(--p-color) 8%, transparent);
        }
        .ss-preset-dot {
          width: 7px; height: 7px; border-radius: 50%;
          background: var(--p-color, #64748b);
          margin-bottom: 2px;
        }
        .ss-preset-label {
          font-size: 12px; font-weight: 600;
          color: var(--text-secondary, #9A9A9E); line-height: 1.3;
        }
        .ss-preset-btn.active .ss-preset-label { color: var(--p-color); }

        /* ── Custom filter panel ── */
        .ss-filter-panel {
          background: var(--bg-surface, #0F0F11);
          border: 1px solid var(--border, rgba(255,255,255,0.08));
          border-radius: 12px; padding: 18px 20px; margin-bottom: 18px;
        }
        .ss-filter-title {
          font-size: 12px; font-weight: 700;
          color: var(--text-tertiary, #5C5C60);
          letter-spacing: 0.6px; text-transform: uppercase;
          margin-bottom: 14px;
        }
        .ss-filter-grid {
          display: grid; grid-template-columns: repeat(5, 1fr);
          gap: 12px; margin-bottom: 16px;
        }
        .ss-filter-field { display: flex; flex-direction: column; gap: 5px; }
        .ss-filter-label {
          font-size: 11px; font-weight: 600;
          color: var(--text-tertiary, #5C5C60); letter-spacing: 0.3px;
          text-transform: uppercase;
        }
        .ss-filter-input {
          background: rgba(255,255,255,0.04);
          border: 1px solid var(--border, rgba(255,255,255,0.08));
          border-radius: 8px; padding: 8px 10px;
          color: var(--text-primary, #F2F2F0);
          font-size: 13px; width: 100%;
          transition: border-color 0.2s; outline: none;
          font-family: var(--font-mono, monospace);
        }
        .ss-filter-input:focus {
          border-color: var(--accent, #C9A34E);
        }
        .ss-filter-input::placeholder { color: var(--text-muted, #3a3a3f); }
        .ss-filter-actions { display: flex; gap: 10px; align-items: center; }
        .ss-btn-run {
          background: linear-gradient(135deg, var(--accent, #C9A34E), var(--accent-dark, #A8822E));
          color: #000; border: none; border-radius: 8px;
          padding: 9px 20px; font-size: 13px; font-weight: 700;
          cursor: pointer; transition: opacity 0.2s;
          display: flex; align-items: center; gap: 7px;
          font-family: var(--font-primary, 'Inter', system-ui, sans-serif);
        }
        .ss-btn-run:hover { opacity: 0.9; }
        .ss-btn-run:disabled { opacity: 0.45; cursor: not-allowed; }
        .ss-btn-clear {
          background: none;
          border: 1px solid var(--border, rgba(255,255,255,0.08));
          border-radius: 8px; padding: 9px 14px; font-size: 12px;
          color: var(--text-secondary, #9A9A9E); cursor: pointer;
          transition: all 0.2s;
          font-family: var(--font-primary, 'Inter', system-ui, sans-serif);
        }
        .ss-btn-clear:hover {
          border-color: rgba(255,255,255,0.2);
          color: var(--text-primary, #F2F2F0);
        }
        .ss-pro-lock {
          background: rgba(201,163,78,0.04);
          border: 1px solid rgba(201,163,78,0.15);
          border-radius: 12px; padding: 28px 20px;
          text-align: center;
        }
        .ss-pro-lock-icon {
          color: var(--accent, #C9A34E); margin-bottom: 12px;
          display: flex; justify-content: center;
        }
        .ss-pro-lock-title {
          color: var(--text-primary, #F2F2F0);
          font-size: 15px; font-weight: 700; margin-bottom: 8px;
        }
        .ss-pro-lock-desc {
          color: var(--text-tertiary, #5C5C60);
          font-size: 12px; line-height: 1.6; max-width: 340px; margin: 0 auto;
        }

        /* ── Results ── */
        .ss-results-bar {
          display: flex; align-items: center; gap: 12px; margin-bottom: 12px;
        }
        .ss-results-count {
          font-size: 12px; font-weight: 600;
          color: var(--text-secondary, #9A9A9E);
          font-family: var(--font-mono, monospace);
        }
        .ss-results-count span { color: var(--text-primary, #F2F2F0); }
        .ss-fetched-at {
          font-size: 11px; color: var(--text-muted, #5C5C60);
          margin-left: auto; font-family: var(--font-mono, monospace);
        }

        /* ── Table ── */
        .ss-table-wrap {
          overflow-x: auto; border-radius: 12px;
          border: 1px solid var(--border-subtle, rgba(255,255,255,0.05));
        }
        .ss-table {
          width: 100%; border-collapse: collapse;
          font-size: 13.5px;
        }
        .ss-table th {
          background: rgba(255,255,255,0.025);
          padding: 11px 12px; text-align: right;
          color: var(--text-tertiary, #5C5C60);
          font-size: 11px; font-weight: 700;
          letter-spacing: 0.4px; white-space: nowrap;
          cursor: pointer; user-select: none;
          border-bottom: 1px solid var(--border-subtle, rgba(255,255,255,0.05));
          transition: color 0.15s; text-transform: uppercase;
        }
        .ss-table th:first-child { text-align: left; }
        .ss-table th.sorted { color: var(--accent, #C9A34E); }
        .ss-table th:hover:not(.sorted) { color: var(--text-secondary, #9A9A9E); }
        .ss-sort-icon { margin-left: 4px; opacity: 0.6; }

        .ss-table tr:hover td { background: rgba(201,163,78,0.03); }
        .ss-table tbody tr { cursor: pointer; transition: background 0.12s; }
        .ss-table tbody tr:hover td:first-child { border-left: 2px solid rgba(201,163,78,0.4); padding-left: 10px; }
        .ss-table td {
          padding: 11px 12px; text-align: right;
          color: var(--text-secondary, #9A9A9E);
          border-bottom: 1px solid var(--border-subtle, rgba(255,255,255,0.04));
          white-space: nowrap; transition: background 0.12s;
          font-family: var(--font-mono, monospace);
        }
        .ss-table td:first-child { text-align: left; font-family: var(--font-primary, 'Inter', system-ui, sans-serif); }
        .ss-table tr:last-child td { border-bottom: none; }

        .ss-sym-cell { display: flex; flex-direction: column; gap: 2px; }
        .ss-sym-name {
          font-weight: 800; color: var(--text-primary, #F2F2F0);
          font-size: 14px; letter-spacing: -0.2px;
          font-family: var(--font-mono, monospace);
        }
        .ss-sym-company {
          font-size: 12px; color: var(--text-tertiary, #5C5C60);
          max-width: 130px; overflow: hidden; text-overflow: ellipsis;
          font-family: var(--font-primary, 'Inter', system-ui, sans-serif);
        }
        .ss-sym-sector {
          font-size: 11px; color: var(--text-muted, #5C5C60);
          background: rgba(255,255,255,0.04);
          padding: 2px 7px; border-radius: 4px;
          display: inline-block; margin-top: 2px;
          border: 1px solid rgba(255,255,255,0.05);
          text-transform: uppercase; letter-spacing: 0.3px;
          font-family: var(--font-primary, 'Inter', system-ui, sans-serif);
        }
        .ss-score-pill {
          display: inline-flex; align-items: center; justify-content: center;
          width: 34px; height: 22px; border-radius: 6px;
          font-size: 11px; font-weight: 800; color: #000;
        }

        /* ── Loading ── */
        .ss-loading {
          display: flex; align-items: center; justify-content: center;
          padding: 64px 0; gap: 16px; flex-direction: column;
        }
        .ss-spinner {
          width: 36px; height: 36px;
          border: 2.5px solid rgba(255,255,255,0.08);
          border-top-color: var(--accent, #C9A34E);
          border-radius: 50%; animation: ss-spin 0.75s linear infinite;
        }
        @keyframes ss-spin { to { transform: rotate(360deg); } }
        .ss-loading-text {
          text-align: center;
        }
        .ss-loading-title { color: var(--text-secondary, #9A9A9E); font-size: 14px; margin-bottom: 6px; }
        .ss-loading-sub { color: var(--text-tertiary, #5C5C60); font-size: 12px; margin-bottom: 14px; }
        .ss-progress-track {
          width: 240px; height: 3px;
          background: rgba(255,255,255,0.06);
          border-radius: 99px; overflow: hidden; margin: 0 auto;
        }
        .ss-progress-fill {
          height: 100%;
          background: linear-gradient(90deg, var(--accent-dark, #A8822E), var(--accent, #C9A34E));
          border-radius: 99px; transition: width 1s linear;
        }
        .ss-loading-note {
          color: var(--text-muted, #3a3a3f); font-size: 11px; margin-top: 8px;
          font-family: var(--font-mono, monospace);
        }

        /* ── Empty / Error ── */
        .ss-empty {
          text-align: center; padding: 52px 0;
          color: var(--text-muted, #5C5C60); font-size: 13px;
        }
        .ss-error-banner {
          background: rgba(229,72,77,0.08);
          border: 1px solid rgba(229,72,77,0.2);
          border-radius: 10px; padding: 12px 16px;
          color: #fca5a5; font-size: 13px; margin-bottom: 14px;
          display: flex; align-items: center; gap: 8px;
        }

        @media (max-width: 768px) {
          .ss-curated-row { grid-template-columns: 1fr; }
          .ss-preset-grid  { grid-template-columns: repeat(2, 1fr); }
          .ss-filter-grid  { grid-template-columns: repeat(2, 1fr); }
          .ss-tab-btn span:last-child { display: none; }
        }
      `}</style>

      {/* ── Section Header ── */}
      <div className="ss-header">
        <div className="ss-header-icon">
          <IconFilter />
        </div>
        <div className="ss-header-text">
          <h2 className="ss-header-title">Stock Screener</h2>
          <p className="ss-header-sub">Fundamental analysis across 210+ NSE stocks</p>
        </div>
        <span className="ss-header-badge">REAL-TIME</span>
        <span className={`ss-header-status ${loading ? 'scanning' : fetchTime != null ? 'done' : ''}`}>
          {loading
            ? `Scanning · ${elapsed}s`
            : fetchTime != null
            ? `Fetched in ${fetchTime}s`
            : fetchedAt
            ? new Date(fetchedAt).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
            : 'Live fundamentals'}
        </span>
      </div>

      {/* ── Tab row ── */}
      <div className="ss-tab-row">
        {TABS_DEF.map(t => (
          <button
            key={t.key}
            className={`ss-tab-btn ${tab === t.key ? (t.key === 'swing' ? 'active-swing' : 'active') : ''}`}
            onClick={() => setTab(t.key)}
          >
            {t.icon}
            <span>{t.label}</span>
          </button>
        ))}
      </div>

      {/* ── SWING TAB ── */}
      {tab === 'swing' && <SwingScreener userPlan={userPlan} />}

      {/* ── CURATED TAB ── */}
      {tab === 'curated' && (
        <div className="ss-curated-row">
          {CURATED_SCREENS.map(c => (
            <div
              key={c.key}
              className={`ss-curated-card ${curatedType === c.key ? 'active' : ''}`}
              style={{
                '--c-color': c.color,
                '--c-bg': c.accentBg,
                '--c-border': c.accentBorder,
                '--c-shadow': c.color + '18',
              } as any}
              onClick={() => setCuratedType(c.key)}
            >
              <div className="ss-curated-icon">{c.icon}</div>
              <div className="ss-curated-label">{c.label}</div>
              <div className="ss-curated-desc">{c.desc}</div>
              <div className="ss-curated-badge">{c.badge}</div>
            </div>
          ))}
        </div>
      )}

      {/* ── PRESET TAB ── */}
      {tab === 'preset' && (
        <div className="ss-preset-grid">
          {PRESET_OPTIONS.map(p => (
            <button
              key={p.key}
              className={`ss-preset-btn ${presetKey === p.key ? 'active' : ''}`}
              style={{ '--p-color': p.color } as any}
              onClick={() => setPresetKey(p.key)}
            >
              <div className="ss-preset-dot" />
              <div className="ss-preset-label">{p.label}</div>
            </button>
          ))}
        </div>
      )}

      {/* ── CUSTOM TAB ── */}
      {tab === 'custom' && (
        isPro ? (
          <div className="ss-filter-panel">
            <div className="ss-filter-title">Custom Filters</div>
            <div className="ss-filter-grid">
              <NumInput label="Min PE"           value={filters.min_pe}            onChange={setFilter('min_pe')}            placeholder="e.g. 5"    />
              <NumInput label="Max PE"           value={filters.max_pe}            onChange={setFilter('max_pe')}            placeholder="e.g. 25"   />
              <NumInput label="Min ROE %"        value={filters.min_roe}           onChange={setFilter('min_roe')}           placeholder="e.g. 15"   />
              <NumInput label="Max D/E"          value={filters.max_de}            onChange={setFilter('max_de')}            placeholder="e.g. 1.0"  />
              <NumInput label="Max PB"           value={filters.max_pb}            onChange={setFilter('max_pb')}            placeholder="e.g. 4"    />
              <NumInput label="Min Mkt Cap (Cr)" value={filters.min_market_cap_cr} onChange={setFilter('min_market_cap_cr')} placeholder="e.g. 500"  />
              <NumInput label="Max Mkt Cap (Cr)" value={filters.max_market_cap_cr} onChange={setFilter('max_market_cap_cr')} placeholder="e.g. 50000"/>
              <NumInput label="Min Div Yield %"  value={filters.min_div_yield}     onChange={setFilter('min_div_yield')}     placeholder="e.g. 1.5"  />
              <NumInput label="Min Rev Growth %" value={filters.min_revenue_growth} onChange={setFilter('min_revenue_growth')} placeholder="e.g. 10" />
              <NumInput label="Min Margin %"     value={filters.min_profit_margin} onChange={setFilter('min_profit_margin')} placeholder="e.g. 10"   />
            </div>
            <div className="ss-filter-actions">
              <button className="ss-btn-run" onClick={runCustom} disabled={loading}>
                {loading
                  ? <><div className="ss-spinner" style={{ width: 13, height: 13 }} />Screening…</>
                  : <><IconSearch />Run Screen</>}
              </button>
              <button className="ss-btn-clear" onClick={() => setFilters({
                min_pe: '', max_pe: '', min_roe: '', max_de: '',
                min_market_cap_cr: '', max_market_cap_cr: '',
                min_div_yield: '', min_revenue_growth: '',
                min_profit_margin: '', max_pb: '',
              })}>Clear all</button>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 'auto', fontFamily: 'var(--font-mono)' }}>
                {results.length > 0 ? `${results.length} stocks matched` : 'Set filters and run'}
              </span>
            </div>
          </div>
        ) : (
          <div className="ss-pro-lock">
            <div className="ss-pro-lock-icon"><IconLock /></div>
            <div className="ss-pro-lock-title">Pro Feature</div>
            <p className="ss-pro-lock-desc">
              Custom screener is available on <strong style={{ color: 'var(--accent)' }}>Pro & Elite</strong> plans.
              Build your own fundamental screens across 100+ NSE stocks.
            </p>
          </div>
        )
      )}

      {/* ── Error ── */}
      {error && (
        <div className="ss-error-banner">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          {error}
        </div>
      )}

      {/* ── Results ── */}
      {tab !== 'swing' && loading ? (
        <div className="ss-loading">
          <div className="ss-spinner" />
          <div className="ss-loading-text">
            <div className="ss-loading-title">
              Scanning <strong style={{ color: 'var(--accent)' }}>210+ stocks</strong> in real-time
            </div>
            <div className="ss-loading-sub">
              Fetching live fundamentals — {elapsed}s elapsed
            </div>
            <div className="ss-progress-track">
              <div className="ss-progress-fill" style={{ width: `${Math.min(100, (elapsed / 25) * 100)}%` }} />
            </div>
            <div className="ss-loading-note">Results cached for 1 hour after first load</div>
          </div>
        </div>
      ) : sorted.length === 0 && !error ? (
        tab !== 'custom' || results.length === 0 ? (
          <div className="ss-empty">
            {tab === 'custom' && !isPro ? null : 'No results — try different filters or refresh'}
          </div>
        ) : null
      ) : sorted.length > 0 ? (
        <>
          <div className="ss-results-bar">
            <div className="ss-results-count">
              Showing <span>{sorted.length}</span> stocks
            </div>
            {fetchedAt && (
              <div className="ss-fetched-at">
                {new Date(fetchedAt).toLocaleString('en-IN', {
                  day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
                })}
              </div>
            )}
          </div>

          <div className="ss-table-wrap">
            <table className="ss-table">
              <thead>
                <tr>
                  {COLUMNS.map(col => (
                    <th
                      key={col.key}
                      className={sortField === col.key ? 'sorted' : ''}
                      onClick={() => col.sortable && toggleSort(col.key)}
                      style={{ width: col.width }}
                    >
                      {col.label}
                      {col.sortable && (
                        <span className="ss-sort-icon">
                          {sortField === col.key ? (sortDir === 'desc' ? ' ↓' : ' ↑') : ' ↕'}
                        </span>
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.map((s, i) => (
                  <tr
                    key={`${s.symbol}-${i}`}
                    onClick={() => handleSelectStock(s.symbol)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td>
                      <div className="ss-sym-cell">
                        <span className="ss-sym-name">{s.symbol}</span>
                        <span className="ss-sym-company" title={s.company_name}>
                          {s.company_name || '—'}
                        </span>
                        {s.sector && <span className="ss-sym-sector">{s.sector}</span>}
                      </div>
                    </td>
                    <td style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                      {s.current_price != null ? `₹${s.current_price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'}
                    </td>
                    <td>
                      {(s as any).today_change_pct != null ? (
                        <span style={{ color: (s as any).today_change_pct >= 0 ? 'var(--gain)' : 'var(--loss)', fontWeight: 600 }}>
                          {(s as any).today_change_pct >= 0 ? '+' : ''}{((s as any).today_change_pct).toFixed(2)}%
                        </span>
                      ) : '—'}
                    </td>
                    <td>{fmtChg(s.change_pct)}</td>
                    <td style={{ color: 'var(--text-secondary)' }}>{fmtCr(s.market_cap_cr)}</td>
                    <td>
                      {s.pe_ratio != null ? (
                        <span style={{ color: s.pe_ratio < 20 ? '#10b981' : s.pe_ratio < 40 ? '#f59e0b' : '#ef4444' }}>
                          {s.pe_ratio.toFixed(1)}
                        </span>
                      ) : '—'}
                    </td>
                    <td>{fmt(s.pb_ratio, 1)}</td>
                    <td>
                      {s.roe != null ? (
                        <span style={{ color: s.roe >= 20 ? '#10b981' : s.roe >= 12 ? '#3b82f6' : 'var(--text-secondary)' }}>
                          {s.roe.toFixed(1)}%
                        </span>
                      ) : '—'}
                    </td>
                    <td>
                      {s.debt_to_equity != null ? (
                        <span style={{ color: s.debt_to_equity <= 0.5 ? '#10b981' : s.debt_to_equity <= 1.5 ? '#f59e0b' : '#ef4444' }}>
                          {s.debt_to_equity.toFixed(2)}
                        </span>
                      ) : '—'}
                    </td>
                    <td>
                      {s.dividend_yield != null && s.dividend_yield > 0
                        ? <span style={{ color: '#f59e0b' }}>{s.dividend_yield.toFixed(2)}%</span>
                        : '—'}
                    </td>
                    <td>{fmt(s.profit_margin, 1, '%')}</td>
                    <td>
                      {s.revenue_growth != null ? (
                        <span style={{ color: s.revenue_growth >= 15 ? '#10b981' : s.revenue_growth >= 0 ? 'var(--text-secondary)' : '#ef4444' }}>
                          {s.revenue_growth >= 0 ? '+' : ''}{s.revenue_growth.toFixed(1)}%
                        </span>
                      ) : '—'}
                    </td>
                    <td>
                      {((s as any).quality_score ?? s.score) != null ? (
                        <div
                          className="ss-score-pill"
                          style={{ background: scoreColor((s as any).quality_score ?? s.score) }}
                          title={`Quality score: ${(s as any).quality_score ?? s.score}/100`}
                        >
                          {(s as any).quality_score ?? s.score}
                        </div>
                      ) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </div>
  )
}
