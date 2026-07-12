'use client'
import { useState, useEffect, useCallback } from 'react'
import { apiNewListings, apiStockDetail, type NewListing, type StockDetail } from '@/lib/api'
import StockDetailPanel from './StockDetailPanel'

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmt(n: number | null | undefined, decimals = 2): string {
  if (n == null) return '—'
  return n.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}
function fmtCr(n: number | null | undefined): string {
  if (n == null) return '—'
  const cr = n / 1e7
  if (cr >= 1000) return `₹${(cr / 1000).toFixed(1)}K Cr`
  return `₹${cr.toFixed(0)} Cr`
}
function fmtDate(raw: string | null | undefined): string {
  if (!raw) return '—'
  try {
    const d = new Date(raw.replace(/-/g, ' '))
    if (!isNaN(d.getTime())) return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
  } catch {}
  return raw
}

// ── SVG Icons ─────────────────────────────────────────────────────────────────
const IconRocket = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/>
    <path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/>
    <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/>
    <path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>
  </svg>
)
const IconSearch = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
  </svg>
)
const IconRefresh = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
  </svg>
)
const IconArrowLeft = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M19 12H5M5 12l7 7M5 12l7-7"/>
  </svg>
)
const IconAlertTriangle = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
    <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
  </svg>
)
const IconPackage = () => (
  <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round">
    <line x1="16.5" y1="9.4" x2="7.5" y2="4.21"/>
    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
    <polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>
  </svg>
)
const IconTrendUp = () => (
  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/>
    <polyline points="16 7 22 7 22 13"/>
  </svg>
)
const IconTrendDown = () => (
  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="22 17 13.5 8.5 8.5 13.5 2 7"/>
    <polyline points="16 17 22 17 22 11"/>
  </svg>
)
const IconExternalLink = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
    <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
  </svg>
)

// ── Exchange Badge ────────────────────────────────────────────────────────────
function ExchangeBadge({ exchange }: { exchange: string }) {
  const ex = exchange?.toUpperCase()
  const isNSE = ex?.includes('NSE')
  const isSME = ex?.includes('SME')
  const color = isSME ? '#a78bfa' : isNSE ? '#60a5fa' : '#f59e0b'
  const label = isSME ? 'SME' : isNSE ? 'NSE' : 'BSE'
  return (
    <span style={{
      fontSize: 10, fontWeight: 800, padding: '2px 8px', borderRadius: 6,
      border: `1px solid ${color}35`,
      background: color + '12', color,
      letterSpacing: '0.4px',
      fontFamily: 'var(--font-primary)',
    }}>{label}</span>
  )
}

// ── Pct Badge ─────────────────────────────────────────────────────────────────
function PctBadge({ pct, label, size = 'md' }: { pct: number | null | undefined; label?: string; size?: 'sm' | 'md' | 'lg' }) {
  if (pct == null) return <span style={{ color: 'var(--text-muted)', fontSize: size === 'lg' ? 14 : 12 }}>—</span>
  const isPos = pct >= 0
  const color = isPos ? 'var(--gain, #3DDC84)' : 'var(--loss, #E5484D)'
  const fs = size === 'lg' ? 16 : size === 'sm' ? 11 : 12
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, fontSize: fs, fontWeight: 700, color, fontFamily: 'var(--font-mono)' }}>
      {isPos ? <IconTrendUp /> : <IconTrendDown />}
      {Math.abs(pct).toFixed(2)}%
      {label && <span style={{ fontWeight: 400, color: 'var(--text-muted)', marginLeft: 3, fontSize: fs - 1, fontFamily: 'var(--font-primary)' }}>{label}</span>}
    </span>
  )
}

// ── GMP Chip ──────────────────────────────────────────────────────────────────
function GmpChip({ gmpPrice, gmpPct }: { gmpPrice: number | null; gmpPct: number | null }) {
  if (gmpPrice == null) return null
  const isPos = gmpPrice >= 0
  const color = isPos ? 'var(--gain, #3DDC84)' : 'var(--loss, #E5484D)'
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      background: isPos ? 'rgba(61,220,132,0.07)' : 'rgba(229,72,77,0.07)',
      border: `1px solid ${isPos ? 'rgba(61,220,132,0.22)' : 'rgba(229,72,77,0.22)'}`,
      borderRadius: 7, padding: '3px 10px',
    }}>
      <span style={{ fontSize: 8, color: 'var(--text-muted)', fontWeight: 700, letterSpacing: '0.6px', textTransform: 'uppercase', fontFamily: 'var(--font-primary)' }}>GMP</span>
      <span style={{ fontSize: 12, fontWeight: 800, color, fontFamily: 'var(--font-mono)' }}>
        {isPos ? '+' : ''}₹{gmpPrice}
      </span>
      {gmpPct != null && (
        <span style={{ fontSize: 10, color, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
          {isPos ? '+' : ''}{gmpPct.toFixed(1)}%
        </span>
      )}
    </div>
  )
}

// ── Stat pill ─────────────────────────────────────────────────────────────────
function StatPill({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div style={{
      background: color + '0A', border: `1px solid ${color}20`,
      borderRadius: 10, padding: '10px 16px',
      display: 'flex', flexDirection: 'column', gap: 3, minWidth: 110,
    }}>
      <span style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', fontFamily: 'var(--font-primary)' }}>{label}</span>
      <span style={{ fontSize: 16, fontWeight: 800, color, fontFamily: 'var(--font-mono)' }}>{value}</span>
    </div>
  )
}

// ── Listing Card ──────────────────────────────────────────────────────────────
function ListingCard({ item, onSelect }: {
  item: NewListing & { gmp_price?: number | null; gmp_pct?: number | null }
  onSelect: (sym: string) => void
}) {
  const hasPrice = item.current_price != null
  const hasGain  = item.listing_gain_pct != null
  const gainPos  = (item.listing_gain_pct ?? 0) >= 0
  const accentColor = hasGain ? (gainPos ? 'var(--gain, #3DDC84)' : 'var(--loss, #E5484D)') : 'var(--accent, #C9A34E)'

  return (
    <div
      onClick={() => onSelect(item.symbol)}
      className="nl-card"
      style={{ borderLeft: `3px solid ${accentColor}` }}
    >
      {/* Subtle gradient overlay based on gain */}
      <div style={{
        position: 'absolute', inset: 0, borderRadius: 'inherit', pointerEvents: 'none',
        background: hasGain
          ? `linear-gradient(135deg, ${gainPos ? 'rgba(61,220,132,0.04)' : 'rgba(229,72,77,0.04)'} 0%, transparent 60%)`
          : 'none',
      }} />

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, position: 'relative' }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap', marginBottom: 4 }}>
            <span style={{ fontWeight: 900, color: 'var(--text-primary)', fontSize: 14, letterSpacing: '0.2px', fontFamily: 'var(--font-mono)' }}>
              {item.symbol}
            </span>
            <ExchangeBadge exchange={item.exchange} />
            {item.series && item.series !== 'EQ' && (
              <span style={{
                fontSize: 9, fontWeight: 700, padding: '2px 6px', borderRadius: 5,
                background: 'rgba(167,139,250,0.08)', border: '1px solid rgba(167,139,250,0.25)', color: '#a78bfa',
                fontFamily: 'var(--font-primary)',
              }}>{item.series}</span>
            )}
          </div>
          <span style={{ color: 'var(--text-tertiary)', fontSize: 11, lineHeight: 1.3, display: 'block', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: 'var(--font-primary)' }}>
            {item.company_name}
          </span>
        </div>

        <div style={{ textAlign: 'right', flexShrink: 0, position: 'relative' }}>
          {hasPrice ? (
            <>
              <div style={{ fontSize: 16, fontWeight: 800, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                ₹{fmt(item.current_price)}
              </div>
              <PctBadge pct={item.change_pct} label="today" size="sm" />
            </>
          ) : (
            <span style={{ color: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--font-primary)' }}>No price</span>
          )}
        </div>
      </div>

      {/* Metrics grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, position: 'relative' }}>
        {[
          { label: 'Listed',      value: fmtDate(item.listing_date), mono: false },
          { label: 'Issue Price', value: item.issue_price ? `₹${fmt(item.issue_price, 0)}` : '—', mono: true },
          { label: 'Since IPO',   value: null },
        ].map(({ label, value, mono }) => (
          <div key={label} style={{ background: 'rgba(255,255,255,0.025)', borderRadius: 8, padding: '7px 10px' }}>
            <div style={{ fontSize: 9, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.4px', marginBottom: 3, fontFamily: 'var(--font-primary)' }}>{label}</div>
            {label === 'Since IPO' ? (
              <PctBadge pct={item.listing_gain_pct} size="sm" />
            ) : (
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', fontFamily: mono ? 'var(--font-mono)' : 'var(--font-primary)' }}>{value}</div>
            )}
          </div>
        ))}
      </div>

      {/* GMP + Mkt Cap row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 6, position: 'relative' }}>
        {(item as any).gmp_price != null ? (
          <GmpChip gmpPrice={(item as any).gmp_price} gmpPct={(item as any).gmp_pct} />
        ) : <span />}
        {item.market_cap != null && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{ fontSize: 9, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', fontFamily: 'var(--font-primary)' }}>Mkt Cap</span>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>{fmtCr(item.market_cap)}</span>
          </div>
        )}
      </div>

      {/* View detail link hint */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 4, position: 'relative' }}>
        <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-primary)', display: 'flex', alignItems: 'center', gap: 4 }}>
          View Analysis <IconExternalLink />
        </span>
      </div>
    </div>
  )
}

// ── Skeleton ──────────────────────────────────────────────────────────────────
function CardSkeleton() {
  return (
    <div className="nl-card-skeleton">
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div className="skel-bar" style={{ width: 100, height: 15 }} />
          <div className="skel-bar" style={{ width: 160, height: 11 }} />
        </div>
        <div className="skel-bar" style={{ width: 70, height: 32, borderRadius: 8 }} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 6 }}>
        {[0,1,2].map(i => <div key={i} className="skel-bar" style={{ height: 44, borderRadius: 8 }} />)}
      </div>
    </div>
  )
}

// ── Control pill group ────────────────────────────────────────────────────────
function PillGroup<T extends string>({
  options, value, onChange, activeColor = 'var(--accent)',
}: {
  options: { key: T; label: string }[]
  value: T
  onChange: (v: T) => void
  activeColor?: string
}) {
  return (
    <div style={{
      display: 'flex',
      background: 'rgba(255,255,255,0.02)',
      border: '1px solid var(--border)',
      borderRadius: 10, overflow: 'hidden',
    }}>
      {options.map(({ key, label }, i) => (
        <button key={key} onClick={() => onChange(key)} style={{
          padding: '7px 13px', fontSize: 12, fontWeight: 600, border: 'none',
          cursor: 'pointer', transition: 'all 0.15s',
          background: value === key ? activeColor + '16' : 'transparent',
          color: value === key ? activeColor : 'var(--text-tertiary)',
          borderRight: i < options.length - 1 ? '1px solid var(--border-subtle)' : 'none',
          fontFamily: 'var(--font-primary)',
        }}>{label}</button>
      ))}
    </div>
  )
}

// ── Main Component ─────────────────────────────────────────────────────────────
export default function NewListingsTab() {
  const [listings, setListings]       = useState<any[]>([])
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState<string | null>(null)
  const [days, setDays]               = useState(30)
  const [exchange, setExchange]       = useState<'ALL' | 'NSE' | 'BSE'>('ALL')
  const [search, setSearch]           = useState('')
  const [selectedStock, setSelectedStock] = useState<StockDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [sortBy, setSortBy]           = useState<'date' | 'gain' | 'gmp' | 'price'>('date')

  const loadListings = useCallback(async (d: number, forceRefresh = false) => {
    setLoading(true); setError(null)
    try {
      const res = await apiNewListings(d, forceRefresh)
      setListings((res.listings || []) as any[])
    } catch (e: any) {
      setError(e.message || 'Failed to load new listings')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { loadListings(days) }, [days, loadListings])

  const handleSelect = useCallback(async (symbol: string) => {
    setLoadingDetail(true); setSelectedStock(null)
    try {
      const detail = await apiStockDetail(symbol)
      setSelectedStock(detail)
    } catch {} finally { setLoadingDetail(false) }
  }, [])

  const filtered = listings
    .filter(l => {
      const ex = l.exchange?.toUpperCase()
      if (exchange === 'NSE' && !ex?.includes('NSE')) return false
      if (exchange === 'BSE' && !ex?.includes('BSE')) return false
      if (search) {
        const q = search.toUpperCase()
        return l.symbol?.includes(q) || l.company_name?.toUpperCase().includes(q)
      }
      return true
    })
    .sort((a, b) => {
      if (sortBy === 'gain')  return (b.listing_gain_pct ?? -999) - (a.listing_gain_pct ?? -999)
      if (sortBy === 'gmp')   return (b.gmp_price ?? -999) - (a.gmp_price ?? -999)
      if (sortBy === 'price') return (b.current_price ?? 0) - (a.current_price ?? 0)
      return 0
    })

  const withGain  = listings.filter(l => l.listing_gain_pct != null).length
  const avgGain   = withGain > 0
    ? (listings.reduce((s, l) => s + (l.listing_gain_pct ?? 0), 0) / listings.length).toFixed(1)
    : null
  const topGainer = listings.reduce((best: any, l) =>
    (l.listing_gain_pct ?? -999) > (best?.listing_gain_pct ?? -999) ? l : best, null)

  // Detail panel view
  if (selectedStock) {
    return (
      <div style={{ fontFamily: "var(--font-primary, 'Inter', system-ui, sans-serif)" }}>
        <button onClick={() => setSelectedStock(null)} style={{
          display: 'flex', alignItems: 'center', gap: 8,
          color: 'var(--text-tertiary)', fontSize: 13, fontWeight: 600, background: 'none', border: 'none',
          cursor: 'pointer', marginBottom: 18, padding: 0, fontFamily: 'var(--font-primary)',
          transition: 'color 0.15s',
        }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-primary)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-tertiary)')}
        >
          <IconArrowLeft /> Back to New Listings
        </button>
        <StockDetailPanel stock={selectedStock} onBack={() => setSelectedStock(null)} />
      </div>
    )
  }

  return (
    <div style={{ fontFamily: "var(--font-primary, 'Inter', system-ui, sans-serif)" }}>
      <style>{`
        /* ── Layout ── */
        .nl-card {
          background: var(--bg-surface, #0F0F11);
          border: 1px solid var(--border, rgba(255,255,255,0.07));
          border-radius: 14px;
          padding: 16px 18px;
          cursor: pointer;
          display: flex; flex-direction: column; gap: 12px;
          transition: border-color 0.18s, box-shadow 0.18s, transform 0.18s;
          position: relative; overflow: hidden;
        }
        .nl-card:hover {
          border-color: rgba(255,255,255,0.16) !important;
          box-shadow: 0 6px 28px rgba(0,0,0,0.35);
          transform: translateY(-2px);
        }
        .nl-card-skeleton {
          background: var(--bg-surface, #0F0F11);
          border: 1px solid var(--border, rgba(255,255,255,0.07));
          border-radius: 14px; padding: 16px 18px;
          display: flex; flex-direction: column; gap: 12px;
        }
        .skel-bar {
          background: rgba(255,255,255,0.05);
          border-radius: 6px;
          animation: nl-pulse 1.5s ease-in-out infinite;
        }
        @keyframes nl-pulse { 0%,100%{opacity:.4} 50%{opacity:.9} }
        @keyframes nl-spin  { to { transform: rotate(360deg); } }

        /* ── Controls search input ── */
        .nl-search-input {
          width: 100%; background: rgba(255,255,255,0.02);
          border: 1px solid var(--border);
          border-radius: 10px; padding: 7px 10px 7px 32px;
          color: var(--text-primary); font-size: 12px;
          outline: none; box-sizing: border-box;
          font-family: var(--font-primary, 'Inter', system-ui, sans-serif);
          transition: border-color 0.18s;
        }
        .nl-search-input:focus { border-color: var(--accent, #C9A34E); }
        .nl-search-input::placeholder { color: var(--text-muted); }

        /* ── Gain performance bar ── */
        .nl-perf-bar-track {
          height: 3px; background: rgba(255,255,255,0.06);
          border-radius: 99px; overflow: hidden; margin-top: 4px;
        }
        .nl-perf-bar-fill {
          height: 100%; border-radius: 99px; transition: width 0.5s ease;
        }

        @media (max-width: 640px) {
          .nl-controls { flex-direction: column !important; }
        }
      `}</style>

      {/* ── Section Header ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 22, paddingBottom: 18, borderBottom: '1px solid var(--border-subtle, rgba(255,255,255,0.04))' }}>
        <div style={{
          width: 42, height: 42, borderRadius: 11,
          background: 'var(--accent-dim, rgba(201,163,78,0.10))',
          border: '1px solid var(--accent-border, rgba(201,163,78,0.25))',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'var(--accent, #C9A34E)', flexShrink: 0,
        }}>
          <IconRocket />
        </div>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 17, fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 3px', letterSpacing: '-0.3px' }}>New Listings</h2>
          <p style={{ fontSize: 12, color: 'var(--text-tertiary)', margin: 0, fontFamily: 'var(--font-primary)' }}>
            Recently listed on NSE & BSE — live prices, IPO gains, grey market premium
          </p>
        </div>
        {!loading && (
          <span style={{
            fontSize: 10, fontWeight: 700, padding: '4px 10px', borderRadius: 99,
            background: 'var(--gain-dim, rgba(61,220,132,0.08))',
            border: '1px solid var(--gain-border, rgba(61,220,132,0.2))',
            color: 'var(--gain)', letterSpacing: '0.6px', whiteSpace: 'nowrap',
            fontFamily: 'var(--font-primary)',
          }}>
            {filtered.length} STOCKS
          </span>
        )}
      </div>

      {/* ── Stats strip ── */}
      {!loading && listings.length > 0 && (
        <div style={{ display: 'flex', gap: 10, marginBottom: 22, flexWrap: 'wrap' }}>
          <StatPill label="Total Listed"    value={listings.length}                                     color="var(--text-secondary, #9A9A9E)" />
          <StatPill label="With Gain Data"  value={withGain}                                            color="#60a5fa" />
          <StatPill label="Avg IPO Return"  value={avgGain != null ? `${avgGain}%` : '—'}              color={parseFloat(avgGain ?? '0') >= 0 ? 'var(--gain)' : 'var(--loss)'} />
          {topGainer?.symbol && (
            <StatPill label="Top Performer" value={topGainer.symbol}                                    color="var(--accent, #C9A34E)" />
          )}
        </div>
      )}

      {/* ── Controls ── */}
      <div className="nl-controls" style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 20 }}>
        {/* Days range */}
        <PillGroup
          options={[7,14,30,60,90].map(d => ({ key: String(d) as any, label: `${d}D` }))}
          value={String(days) as any}
          onChange={(v: any) => setDays(Number(v))}
          activeColor="var(--gain)"
        />

        {/* Exchange */}
        <PillGroup
          options={(['ALL','NSE','BSE'] as const).map(e => ({ key: e, label: e }))}
          value={exchange}
          onChange={setExchange}
          activeColor="#60a5fa"
        />

        {/* Sort */}
        <PillGroup
          options={[
            { key: 'date'  as any, label: 'Date'  },
            { key: 'gain'  as any, label: 'Gain'  },
            { key: 'gmp'   as any, label: 'GMP'   },
            { key: 'price' as any, label: 'Price' },
          ]}
          value={sortBy as any}
          onChange={(v: any) => setSortBy(v)}
          activeColor="#a78bfa"
        />

        {/* Search */}
        <div style={{ flex: 1, minWidth: 160, position: 'relative' }}>
          <span style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}>
            <IconSearch />
          </span>
          <input
            type="text" value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Symbol or company name…"
            className="nl-search-input"
          />
        </div>

        {/* Refresh */}
        <button onClick={() => loadListings(days, true)} disabled={loading} style={{
          padding: '7px 14px',
          background: 'var(--bg-surface, rgba(255,255,255,0.02))',
          border: '1px solid var(--border)', borderRadius: 10,
          color: 'var(--text-secondary)', fontSize: 12, fontWeight: 600,
          cursor: loading ? 'not-allowed' : 'pointer',
          display: 'flex', alignItems: 'center', gap: 6,
          opacity: loading ? 0.5 : 1, transition: 'all 0.15s',
          fontFamily: 'var(--font-primary)',
        }}>
          <span style={{ display: 'inline-block', animation: loading ? 'nl-spin 1s linear infinite' : 'none' }}>
            <IconRefresh />
          </span>
          Refresh
        </button>
      </div>

      {/* ── Loading detail ── */}
      {loadingDetail && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, padding: '11px 16px',
          background: 'var(--bg-surface)', border: '1px solid var(--border)',
          borderRadius: 10, marginBottom: 14, color: 'var(--text-tertiary)', fontSize: 13,
          fontFamily: 'var(--font-primary)',
        }}>
          <span style={{ display: 'inline-block', animation: 'nl-spin 0.75s linear infinite', color: 'var(--gain)' }}>
            <IconRefresh />
          </span>
          Loading stock analysis…
        </div>
      )}

      {/* ── Error ── */}
      {error && !loading && (
        <div style={{
          padding: '12px 16px', background: 'rgba(229,72,77,0.07)',
          border: '1px solid rgba(229,72,77,0.2)', borderRadius: 12,
          color: '#fca5a5', fontSize: 13, marginBottom: 16,
          display: 'flex', alignItems: 'center', gap: 10, fontFamily: 'var(--font-primary)',
        }}>
          <IconAlertTriangle /> {error}
          <button onClick={() => loadListings(days)} style={{
            marginLeft: 'auto', background: 'rgba(229,72,77,0.15)',
            border: 'none', color: '#fca5a5', padding: '4px 12px',
            borderRadius: 7, cursor: 'pointer', fontSize: 12, fontWeight: 600,
          }}>Retry</button>
        </div>
      )}

      {/* ── Empty state ── */}
      {!loading && !error && filtered.length === 0 && (
        <div style={{
          textAlign: 'center', padding: '64px 20px',
          background: 'var(--bg-surface)', border: '1px solid var(--border)',
          borderRadius: 16,
        }}>
          <div style={{ color: 'var(--text-muted)', marginBottom: 14, display: 'flex', justifyContent: 'center' }}>
            <IconPackage />
          </div>
          <p style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-secondary)', margin: '0 0 8px', fontFamily: 'var(--font-primary)' }}>No listings found</p>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', fontFamily: 'var(--font-primary)' }}>Try a wider time range or clear your filters</p>
        </div>
      )}

      {/* ── Loading skeleton ── */}
      {loading && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px,1fr))', gap: 14, marginBottom: 20 }}>
          {Array.from({ length: 9 }).map((_, i) => <CardSkeleton key={i} />)}
        </div>
      )}

      {/* ── Cards grid ── */}
      {!loading && filtered.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px,1fr))', gap: 14 }}>
          {filtered.map(item => (
            <ListingCard
              key={`${item.symbol}-${item.exchange}`}
              item={item}
              onSelect={handleSelect}
            />
          ))}
        </div>
      )}

      {/* ── GMP Disclaimer ── */}
      {!loading && listings.some(l => l.gmp_price != null) && (
        <div style={{
          marginTop: 24, padding: '11px 16px',
          background: 'rgba(245,158,11,0.04)', border: '1px solid rgba(245,158,11,0.12)',
          borderRadius: 10, fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.6,
          display: 'flex', gap: 8, alignItems: 'flex-start', fontFamily: 'var(--font-primary)',
        }}>
          <span style={{ color: '#f59e0b', flexShrink: 0, marginTop: 1 }}><IconAlertTriangle /></span>
          <span>
            <strong style={{ color: '#fbbf24' }}>GMP Disclaimer:</strong> Grey Market Premium data is sourced from unofficial channels (ipopremium.in). It is speculative, unverified, and <strong>NOT endorsed by SEBI</strong> or any exchange. Do not make investment decisions based solely on GMP.
          </span>
        </div>
      )}
    </div>
  )
}
