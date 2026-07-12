'use client'
import { useState, useEffect, useRef, useCallback } from 'react'
import {
  apiStockSearch, apiStockDetail,
  StockSearchResult, StockDetail,
} from '@/lib/api'
import StockDetailPanel from './StockDetailPanel'

// Popular quick-access stocks — expanded to 16 across all sectors
const QUICK_PICKS = [
  { symbol: 'RELIANCE',   name: 'Reliance Industries',       sector: 'Energy' },
  { symbol: 'TCS',        name: 'Tata Consultancy Services', sector: 'IT' },
  { symbol: 'HDFCBANK',   name: 'HDFC Bank',                 sector: 'Banking' },
  { symbol: 'INFY',       name: 'Infosys',                   sector: 'IT' },
  { symbol: 'ICICIBANK',  name: 'ICICI Bank',                sector: 'Banking' },
  { symbol: 'SBIN',       name: 'State Bank of India',       sector: 'Banking' },
  { symbol: 'ZOMATO',     name: 'Zomato',                    sector: 'Consumer Tech' },
  { symbol: 'TATAMOTORS', name: 'Tata Motors',               sector: 'Auto' },
  { symbol: 'HAL',        name: 'Hindustan Aeronautics',     sector: 'Defence' },
  { symbol: 'SUNPHARMA',  name: 'Sun Pharmaceutical',        sector: 'Pharma' },
  { symbol: 'ADANIENT',   name: 'Adani Enterprises',         sector: 'Conglomerate' },
  { symbol: 'BAJFINANCE', name: 'Bajaj Finance',             sector: 'NBFC' },
  { symbol: 'IRCTC',      name: 'IRCTC',                     sector: 'Tourism' },
  { symbol: 'DLF',        name: 'DLF Limited',               sector: 'Real Estate' },
  { symbol: 'TATAPOWER',  name: 'Tata Power',                sector: 'Utilities' },
  { symbol: 'DIXON',      name: 'Dixon Technologies',        sector: 'Electronics' },
]

const SECTOR_FILTERS = [
  { label: 'All',           value: '' },
  { label: 'IT',            value: 'IT' },
  { label: 'Banking',       value: 'Banking' },
  { label: 'Pharma',        value: 'Pharma' },
  { label: 'Auto',          value: 'Auto' },
  { label: 'FMCG',          value: 'FMCG' },
  { label: 'Defence',       value: 'Defence' },
  { label: 'Energy',        value: 'Energy' },
  { label: 'NBFC',          value: 'NBFC' },
  { label: 'Real Estate',   value: 'Real Estate' },
  { label: 'Consumer Tech', value: 'Consumer Tech' },
]


const SECTOR_COLORS: Record<string, string> = {
  'IT':           'text-[#60a5fa] bg-[rgba(96,165,250,0.08)] border-[rgba(96,165,250,0.2)]',
  'Banking':      'text-[#00C48C] bg-[rgba(0,196,140,0.08)] border-[rgba(0,196,140,0.2)]',
  'Energy':       'text-[#f59e0b] bg-[rgba(245,158,11,0.08)] border-[rgba(245,158,11,0.2)]',
  'Pharma':       'text-[#a78bfa] bg-[rgba(167,139,250,0.08)] border-[rgba(167,139,250,0.2)]',
  'Auto':         'text-[#34d399] bg-[rgba(52,211,153,0.08)] border-[rgba(52,211,153,0.2)]',
  'FMCG':         'text-[#f87171] bg-[rgba(248,113,113,0.08)] border-[rgba(248,113,113,0.2)]',
  'Tech':         'text-[#60a5fa] bg-[rgba(96,165,250,0.08)] border-[rgba(96,165,250,0.2)]',
  'Metals':       'text-[#9ca3af] bg-[rgba(156,163,175,0.08)] border-[rgba(156,163,175,0.2)]',
  'Fintech':      'text-[#fb923c] bg-[rgba(251,146,60,0.08)] border-[rgba(251,146,60,0.2)]',
  'NBFC':         'text-[#e879f9] bg-[rgba(232,121,249,0.08)] border-[rgba(232,121,249,0.2)]',
  'Consumer Tech':'text-[#60a5fa] bg-[rgba(96,165,250,0.08)] border-[rgba(96,165,250,0.2)]',
  'Defence':      'text-[#f59e0b] bg-[rgba(245,158,11,0.08)] border-[rgba(245,158,11,0.2)]',
  'Utilities':    'text-[#34d399] bg-[rgba(52,211,153,0.08)] border-[rgba(52,211,153,0.2)]',
  'Infrastructure':'text-[#9ca3af] bg-[rgba(156,163,175,0.08)] border-[rgba(156,163,175,0.2)]',
  'Real Estate':  'text-[#f87171] bg-[rgba(248,113,113,0.08)] border-[rgba(248,113,113,0.2)]',
  'Insurance':    'text-[#a78bfa] bg-[rgba(167,139,250,0.08)] border-[rgba(167,139,250,0.2)]',
}
function sectorCls(sector: string): string {
  return SECTOR_COLORS[sector] || 'text-[#888] bg-[#111] border-[#222]'
}

export default function StockSearchTab() {
  const [query, setQuery] = useState('')
  const [suggestions, setSuggestions] = useState<StockSearchResult[]>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [loadingSuggest, setLoadingSuggest] = useState(false)
  const [selectedStock, setSelectedStock] = useState<StockDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sectorFilter, setSectorFilter] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<NodeJS.Timeout | null>(null)

  const filteredQuickPicks = sectorFilter
    ? QUICK_PICKS.filter(s => s.sector === sectorFilter)
    : QUICK_PICKS


  // Debounced search
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (query.trim().length < 1) {
      setSuggestions([])
      setShowSuggestions(false)
      return
    }
    debounceRef.current = setTimeout(async () => {
      setLoadingSuggest(true)
      try {
        const res = await apiStockSearch(query.trim())
        setSuggestions(res.results || [])
        setShowSuggestions(true)
      } catch {
        setSuggestions([])
      } finally {
        setLoadingSuggest(false)
      }
    }, 300)
  }, [query])

  const handleSelectStock = useCallback(async (symbol: string) => {
    setShowSuggestions(false)
    setQuery('')
    setError(null)
    setLoadingDetail(true)
    setSelectedStock(null)
    try {
      const detail = await apiStockDetail(symbol)
      setSelectedStock(detail)
    } catch (e: any) {
      setError(e.message || `Could not load data for ${symbol}. Please try again.`)
    } finally {
      setLoadingDetail(false)
    }
  }, [])

  const handleBack = () => {
    setSelectedStock(null)
    setError(null)
    setTimeout(() => inputRef.current?.focus(), 100)
  }

  // Close suggestions on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      if (!target.closest('#stock-search-container')) {
        setShowSuggestions(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-black text-white">Stock Search</h1>
        <p className="text-[#555] text-sm mt-1">
          Search any NSE/BSE stock — get live price, financials, FII data, news & expert verdict
        </p>
      </div>

      {/* ── Search Bar ─────────────────────────────────────────────────────────── */}
      {!loadingDetail && !selectedStock && (
        <div id="stock-search-container" className="relative mb-6 max-w-2xl">
          <div className="relative">
            <div className="absolute left-4 top-1/2 -translate-y-1/2 text-[#555]">
              {loadingSuggest ? (
                <svg className="animate-spin" width="18" height="18" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" opacity="0.25" />
                  <path d="M12 2a10 10 0 0110 10" stroke="#00C48C" strokeWidth="2" strokeLinecap="round" />
                </svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                  <circle cx="11" cy="11" r="8" stroke="currentColor" strokeWidth="2" />
                  <path d="M21 21l-4.35-4.35" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
              )}
            </div>
            <input
              ref={inputRef}
              id="stock-search-input"
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => query.length > 0 && suggestions.length > 0 && setShowSuggestions(true)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && suggestions.length > 0) handleSelectStock(suggestions[0].symbol)
                if (e.key === 'Escape') setShowSuggestions(false)
              }}
              placeholder="Search by symbol or company name (e.g. RELIANCE, HDFC Bank…)"
              className="w-full bg-[#111] border border-[#1e1e1e] rounded-xl pl-11 pr-10 py-3.5 text-white placeholder-[#444] focus:outline-none focus:border-[#00C48C]/50 focus:ring-1 focus:ring-[#00C48C]/20 transition-all text-sm"
              autoComplete="off"
              autoFocus
            />
            {query && (
              <button
                onClick={() => { setQuery(''); setSuggestions([]); setShowSuggestions(false); inputRef.current?.focus() }}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-[#444] hover:text-white transition-colors"
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M1 1l12 12M13 1L1 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </button>
            )}
          </div>

          {/* Suggestions dropdown */}
          {showSuggestions && suggestions.length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-2 bg-[#111] border border-[#1e1e1e] rounded-xl overflow-hidden shadow-2xl z-50 animate-fade-in">
              {suggestions.map((s) => (
                <button
                  key={s.symbol}
                  onClick={() => handleSelectStock(s.symbol)}
                  className="w-full flex items-center gap-3 px-4 py-3 hover:bg-[#1a1a1a] transition-colors text-left group border-b border-[#151515] last:border-0"
                >
                  <div className="w-9 h-9 rounded-lg bg-[#1a1a1a] border border-[#222] flex items-center justify-center font-black text-[10px] text-[#555] group-hover:border-[#00C48C]/30 group-hover:text-[#00C48C] transition-colors shrink-0">
                    {s.symbol.slice(0, 3)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold text-white truncate">{s.symbol}</p>
                    <p className="text-xs text-[#555] truncate">{s.name}</p>
                  </div>
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border shrink-0 ${sectorCls(s.sector)}`}>
                    {s.sector}
                  </span>
                </button>
              ))}
            </div>
          )}

          {/* No results */}
          {showSuggestions && !loadingSuggest && suggestions.length === 0 && query.length > 1 && (
            <div className="absolute top-full left-0 right-0 mt-2 bg-[#111] border border-[#1e1e1e] rounded-xl px-4 py-4 shadow-2xl z-50">
              <p className="text-sm text-[#444] text-center">No results for &ldquo;{query}&rdquo;</p>
              <p className="text-xs text-[#333] text-center mt-1 mb-3">Try the exact NSE symbol (e.g. TATAMOTORS)</p>
              <button
                onClick={() => { handleSelectStock(query.trim().toUpperCase()); setShowSuggestions(false) }}
                className="w-full text-xs text-[#00C48C] border border-[rgba(0,196,140,0.2)] rounded-lg py-2 hover:bg-[rgba(0,196,140,0.05)] transition-colors"
              >
                → Load &ldquo;{query.toUpperCase()}&rdquo; directly as NSE symbol
              </button>
            </div>
          )}

        </div>
      )}

      {/* ── Loading Detail ─────────────────────────────────────────────────────── */}
      {loadingDetail && (
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
          <div className="glass-card p-5">
            <div className="skeleton h-4 w-32 mb-4" />
            <div className="space-y-4">
              {[1,2,3].map(i => <div key={i} className="skeleton h-8 rounded-lg" />)}
            </div>
          </div>
          <p className="text-center text-sm text-[#333] animate-pulse">
            ⏳ Fetching live data from NSE & Screener.in… (10-15 seconds)
          </p>
        </div>
      )}

      {/* ── Error ─────────────────────────────────────────────────────────────── */}
      {error && !loadingDetail && (
        <div className="glass-card p-8 text-center border-[rgba(239,68,68,0.2)] max-w-xl">
          <div className="text-4xl mb-3">⚠️</div>
          <h3 className="text-white font-bold mb-2">Could Not Load Stock Data</h3>
          <p className="text-sm text-[#555] mb-5">{error}</p>
          <button onClick={handleBack} className="btn-brand text-sm py-2 px-6">
            Try Another Stock
          </button>
        </div>
      )}

      {/* ── Stock Detail ──────────────────────────────────────────────────────── */}
      {selectedStock && !loadingDetail && (
        <div className="max-w-3xl">
          <StockDetailPanel stock={selectedStock} onBack={handleBack} />
        </div>
      )}

      {/* ── Empty State — Quick Picks ─────────────────────────────────────────── */}
      {!selectedStock && !loadingDetail && !error && (
        <div className="max-w-3xl">
          {/* Sector filter chips */}
          <div className="mb-4">
            <p className="text-[10px] font-black tracking-widest uppercase text-[#333] mb-2">Browse by Sector</p>
            <div className="flex flex-wrap gap-2">
              {SECTOR_FILTERS.map((f) => (
                <button
                  key={f.value}
                  onClick={() => setSectorFilter(f.value)}
                  className={`text-[11px] font-semibold px-3 py-1.5 rounded-full border transition-all ${
                    sectorFilter === f.value
                      ? 'bg-[rgba(0,196,140,0.15)] border-[rgba(0,196,140,0.4)] text-[#00C48C]'
                      : 'bg-[#0a0a0a] border-[#1a1a1a] text-[#444] hover:border-[#333] hover:text-[#888]'
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          {/* Quick picks grid */}
          <div className="mb-6">
            <p className="text-[10px] font-black tracking-widest uppercase text-[#444] mb-3">
              🔥 {sectorFilter ? `${sectorFilter} Stocks` : 'Popular Stocks'}
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {filteredQuickPicks.map((s) => (
                <button
                  key={s.symbol}
                  id={`quick-pick-${s.symbol.toLowerCase()}`}
                  onClick={() => handleSelectStock(s.symbol)}
                  className="p-3 rounded-xl bg-[#0f0f0f] border border-[#1a1a1a] hover:border-[#00C48C]/40 hover:bg-[#111] transition-all text-left group"
                >
                  <p className="text-sm font-black text-white group-hover:text-[#00C48C] transition-colors">{s.symbol}</p>
                  <p className="text-[10px] text-[#444] mt-0.5 truncate">{s.name}</p>
                  <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded-full border mt-2 inline-block ${sectorCls(s.sector)}`}>
                    {s.sector}
                  </span>
                </button>
              ))}
              {filteredQuickPicks.length === 0 && (
                <p className="col-span-4 text-xs text-[#333] text-center py-4">No quick picks in this sector. Use the search above.</p>
              )}
            </div>
          </div>

          {/* Feature highlights */}
          <div className="grid sm:grid-cols-4 gap-3">
            {[
              { icon: '💰', title: 'Live Price', desc: 'Real-time NSE price with LIVE indicator during market hours' },
              { icon: '🎯', title: 'Piotroski Score', desc: '9-point accounting quality test — rarely shown on Indian sites' },
              { icon: '⚡', title: 'Altman Z-Score', desc: 'Bankruptcy risk gauge — unique data point for smart investors' },
              { icon: '📈', title: 'Graham Number', desc: 'Benjamin Graham’s intrinsic value vs. current market price' },
            ].map((f) => (
              <div key={f.title} className="p-4 rounded-xl bg-[#0a0a0a] border border-[#161616]">
                <div className="text-2xl mb-2">{f.icon}</div>
                <p className="text-xs font-bold text-white mb-1">{f.title}</p>
                <p className="text-[11px] text-[#444] leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>

          <p className="text-[10px] text-[#2a2a2a] mt-5 text-center">
            900+ NSE stocks · Live prices from yfinance · Data for educational purposes only
          </p>
        </div>

      )}
    </div>
  )
}
