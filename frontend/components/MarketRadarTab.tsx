'use client'
import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import {
  apiGetCorrelations, apiRegenerateCorrelations,
  type RadarResponse, type Correlation, type CorrelationSector, type CorrelationStock,
} from '@/lib/api'

// ── Constants ─────────────────────────────────────────────────────────────────
const SENTIMENT = {
  BULLISH: { label: 'Bullish', color: '#3DDC84', bg: 'rgba(61,220,132,0.10)',  border: 'rgba(61,220,132,0.22)',  dot: '#3DDC84'  },
  BEARISH: { label: 'Bearish', color: '#E5484D', bg: 'rgba(229,72,77,0.10)',   border: 'rgba(229,72,77,0.22)',   dot: '#E5484D'  },
  NEUTRAL: { label: 'Neutral', color: '#C9A34E', bg: 'rgba(201,163,78,0.10)',  border: 'rgba(201,163,78,0.22)',  dot: '#C9A34E'  },
} as const

const MAGNITUDE = {
  HIGH:   { label: 'High',   color: '#E5484D', width: '100%' },
  MEDIUM: { label: 'Medium', color: '#F7B731', width: '60%'  },
  LOW:    { label: 'Low',    color: '#4A5568', width: '30%'  },
} as const

const CONFIDENCE = {
  HIGH:   { label: 'High',   color: '#3DDC84', bg: 'rgba(61,220,132,0.12)',  icon: '●●●' },
  MEDIUM: { label: 'Medium', color: '#F7B731', bg: 'rgba(247,183,49,0.12)',  icon: '●●○' },
  LOW:    { label: 'Low',    color: '#4A5568', bg: 'rgba(74,85,104,0.15)',   icon: '●○○' },
} as const

const HORIZON = {
  TODAY:       { label: 'Intraday',   color: '#E5484D' },
  SHORT_TERM:  { label: '1–5 Days',   color: '#F7B731' },
  MEDIUM_TERM: { label: '1–4 Weeks',  color: '#3DDC84' },
} as const

// ── Sub-components ─────────────────────────────────────────────────────────────

function PulsingDot({ color }: { color: string }) {
  return (
    <span className="relative flex h-2 w-2">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-60" style={{ background: color }} />
      <span className="relative inline-flex rounded-full h-2 w-2" style={{ background: color }} />
    </span>
  )
}

function SectorImpactRow({ sector, direction }: { sector: CorrelationSector; direction: 'impact' | 'benefit' }) {
  const s = SENTIMENT[sector.direction] || SENTIMENT.NEUTRAL
  const m = MAGNITUDE[sector.magnitude] || MAGNITUDE.LOW
  const arrow = sector.direction === 'BULLISH' ? '↑' : sector.direction === 'BEARISH' ? '↓' : '→'

  return (
    <div
      className="flex items-start gap-3 p-3 rounded-xl"
      style={{ background: `${s.color}08`, border: `1px solid ${s.color}20` }}
    >
      {/* Direction arrow */}
      <div
        className="w-9 h-9 rounded-lg flex items-center justify-center text-base font-black flex-shrink-0 mt-0.5"
        style={{ background: `${s.color}15`, color: s.color }}
      >
        {arrow}
      </div>

      <div className="flex-1 min-w-0">
        {/* Sector name + magnitude bar */}
        <div className="flex items-center justify-between gap-2 mb-1.5">
          <p className="text-[15px] font-bold text-white truncate">{sector.name}</p>
          {/* Magnitude mini-bar */}
          <div className="flex items-center gap-1.5 flex-shrink-0">
            <div className="w-16 h-1.5 rounded-full bg-white/10 overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: m.width, background: m.color }}
              />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: m.color }}>
              {m.label}
            </span>
          </div>
        </div>

        {/* Tickers */}
        {sector.ticker_examples?.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {sector.ticker_examples.map(t => (
              <span
                key={t}
                className="text-xs font-mono font-bold px-2 py-0.5 rounded"
                style={{ background: 'rgba(255,255,255,0.06)', color: '#A0AEC0' }}
              >
                {t}
              </span>
            ))}
          </div>
        )}

        {/* Reason */}
        <p className="text-sm text-[#718096] leading-relaxed">{sector.reason}</p>
      </div>
    </div>
  )
}

function StockBadge({ stock }: { stock: CorrelationStock }) {
  const s = SENTIMENT[stock.direction] || SENTIMENT.NEUTRAL
  const c = CONFIDENCE[stock.confidence] || CONFIDENCE.LOW

  return (
    <div
      className="flex items-start gap-3 p-3 rounded-xl"
      style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)' }}
    >
      {/* Ticker badge */}
      <div
        className="px-2.5 py-1.5 rounded-lg text-sm font-mono font-black flex-shrink-0"
        style={{ background: `${s.color}18`, color: s.color, border: `1px solid ${s.color}35` }}
      >
        {stock.symbol}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2 mb-1">
          <p className="text-[13px] font-semibold text-[#D1D5DB] truncate">{stock.company}</p>
          {/* Confidence */}
          <span
            className="text-xs font-mono flex-shrink-0 px-1.5 py-0.5 rounded"
            style={{ background: c.bg, color: c.color }}
            title={`${c.label} confidence`}
          >
            {c.icon}
          </span>
        </div>
        <p className="text-sm text-[#718096] leading-relaxed">{stock.reason}</p>
      </div>
    </div>
  )
}

// ── Causal Chain Visualiser ───────────────────────────────────────────────────
function CausalChain({ chain }: { chain: string }) {
  const steps = chain.split('→').map(s => s.trim()).filter(Boolean)

  return (
    <div className="flex flex-wrap items-center gap-2 py-3">
      {steps.map((step, i) => (
        <div key={i} className="flex items-center gap-2">
          <div
            className="px-3 py-2 rounded-lg text-sm font-medium text-[#D1D5DB] max-w-[200px]"
            style={{
              background: i === 0
                ? 'rgba(201,163,78,0.12)'
                : i === steps.length - 1
                  ? 'rgba(229,72,77,0.10)'
                  : 'rgba(255,255,255,0.05)',
              border: i === 0
                ? '1px solid rgba(201,163,78,0.25)'
                : i === steps.length - 1
                  ? '1px solid rgba(229,72,77,0.20)'
                  : '1px solid rgba(255,255,255,0.07)',
            }}
          >
            {step}
          </div>
          {i < steps.length - 1 && (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#2D3748" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          )}
        </div>
      ))}
    </div>
  )
}

// ── Correlation Card ──────────────────────────────────────────────────────────
function CorrelationCard({
  corr, index, isPro,
}: {
  corr: Correlation
  index: number
  isPro: boolean
}) {
  const [expanded, setExpanded] = useState(index === 0)
  const s = SENTIMENT[corr.sentiment] || SENTIMENT.NEUTRAL
  const c = CONFIDENCE[corr.confidence] || CONFIDENCE.LOW
  const h = HORIZON[corr.time_horizon] || HORIZON.SHORT_TERM

  if (corr.locked && !isPro) {
    return (
      <div
        className="rounded-2xl overflow-hidden"
        style={{ border: '1px solid rgba(255,255,255,0.06)', background: 'rgba(255,255,255,0.02)' }}
      >
        <div className="p-5 flex items-center gap-4">
          <div
            className="w-11 h-11 rounded-xl flex items-center justify-center text-xl flex-shrink-0"
            style={{ background: 'rgba(255,255,255,0.04)', filter: 'blur(0px)' }}
          >
            {corr.theme_icon || '📊'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-white font-bold text-sm mb-0.5 truncate">{corr.theme}</p>
            <p className="text-[#4A5568] text-xs truncate blur-sm select-none">{corr.headline}</p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <span
              className="text-[10px] font-bold uppercase px-2 py-1 rounded-full"
              style={{ background: s.bg, color: s.color, border: `1px solid ${s.border}` }}
            >
              {s.label}
            </span>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4A5568" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div
      className="rounded-2xl overflow-hidden transition-all duration-300"
      style={{
        border: `1px solid ${expanded ? s.color + '30' : 'rgba(255,255,255,0.07)'}`,
        background: expanded ? `${s.color}06` : 'rgba(255,255,255,0.02)',
      }}
    >
      {/* Card header — always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left p-5 flex items-center gap-4"
      >
        {/* Theme icon */}
        <div
          className="w-11 h-11 rounded-xl flex items-center justify-center text-xl flex-shrink-0"
          style={{ background: `${s.color}12`, border: `1px solid ${s.color}20` }}
        >
          {corr.theme_icon || '📊'}
        </div>

        <div className="flex-1 min-w-0">
          {/* Theme name */}
          <div className="flex items-center gap-2 mb-0.5 flex-wrap">
            <p className="text-[10px] font-bold uppercase tracking-widest" style={{ color: s.color }}>
              {corr.theme}
            </p>
            <span className="text-[10px] text-[#4A5568]">·</span>
            <span className="text-[10px] font-mono" style={{ color: h.color }}>{h.label}</span>
            <span className="text-[10px] text-[#4A5568]">·</span>
            <span className="text-[10px]" style={{ color: c.color }}>
              {corr.supporting_news_count} news items
            </span>
          </div>
          {/* Headline */}
          <p className="text-sm font-bold text-white leading-tight">{corr.headline}</p>
        </div>

        {/* Right badges */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <span
            className="text-[10px] font-bold uppercase px-2 py-1 rounded-full hidden sm:block"
            style={{ background: s.bg, color: s.color, border: `1px solid ${s.border}` }}
          >
            {s.label}
          </span>
          <svg
            width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4A5568"
            strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            className={`transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
          >
            <path d="M6 9l6 6 6-6" />
          </svg>
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-5 pb-5 space-y-5 border-t" style={{ borderColor: `${s.color}15` }}>

          {/* Trigger news */}
          {corr.trigger_headlines?.length > 0 && (
            <div className="pt-4">
              <p className="text-[11px] font-bold uppercase tracking-widest">Triggering News</p>
              <div className="space-y-1.5">
                {corr.trigger_headlines.map((h, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <div className="w-1 h-1 rounded-full mt-2 flex-shrink-0" style={{ background: s.color }} />
                    <p className="text-xs text-[#718096] leading-relaxed">{h}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Causal Chain */}
          <div>
            <p className="text-[11px] font-bold uppercase tracking-widest">Causal Chain</p>
            <div
              className="rounded-xl px-3 py-1 overflow-x-auto"
              style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}
            >
              <CausalChain chain={corr.causal_chain} />
            </div>
          </div>

          {/* Impact + Beneficiary sectors — side by side on desktop */}
          <div className="grid md:grid-cols-2 gap-4">
            {/* Sectors hit */}
            {corr.impact_sectors?.length > 0 && (
              <div>
                <p className="text-[10px] font-bold uppercase tracking-widest text-[#E5484D] mb-2 flex items-center gap-1.5">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="#E5484D"><path d="M12 2L2 22h20L12 2z"/></svg>
                  Sectors Under Pressure
                </p>
                <div className="space-y-2">
                  {corr.impact_sectors.map((sec, i) => (
                    <SectorImpactRow key={i} sector={sec} direction="impact" />
                  ))}
                </div>
              </div>
            )}

            {/* Beneficiaries */}
            {corr.beneficiary_sectors?.length > 0 && (
              <div>
                <p className="text-[10px] font-bold uppercase tracking-widest text-[#3DDC84] mb-2 flex items-center gap-1.5">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="#3DDC84"><path d="M12 22L2 2h20L12 22z"/></svg>
                  Sectors That Benefit
                </p>
                <div className="space-y-2">
                  {corr.beneficiary_sectors.map((sec, i) => (
                    <SectorImpactRow key={i} sector={sec} direction="benefit" />
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Stocks to watch */}
          {corr.key_stocks_to_watch?.length > 0 && (
            <div>
              <p className="text-[11px] font-bold uppercase tracking-widest">
                Stocks to Watch
              </p>
              <div className="grid sm:grid-cols-2 gap-2">
                {corr.key_stocks_to_watch.map((stock, i) => (
                  <StockBadge key={i} stock={stock} />
                ))}
              </div>
            </div>
          )}

          {/* Footer: confidence + horizon */}
          <div className="flex flex-wrap items-center gap-3 pt-2 border-t" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
            <div
              className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full"
              style={{ background: c.bg, color: c.color }}
            >
              <span className="font-mono">{c.icon}</span>
              {c.label} Confidence
            </div>
            <div
              className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full"
              style={{ background: 'rgba(255,255,255,0.04)', color: h.color, border: '1px solid rgba(255,255,255,0.07)' }}
            >
              ⏱ {h.label}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Locked / Upgrade state ───────────────────────────────────────────────────
function UpgradeTeaser({ data }: { data: RadarResponse }) {
  return (
    <div className="space-y-4">
      {/* Mood reasoning — visible to free */}
      {data.market_mood_reasoning && (
        <div
          className="p-4 rounded-xl text-sm text-[#718096] leading-relaxed italic"
          style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}
        >
          <span className="text-[10px] font-bold uppercase tracking-widest text-[#4A5568] not-italic block mb-2">
            AI Market Intelligence Preview
          </span>
          "{data.market_mood_reasoning}"
        </div>
      )}

      {/* Locked correlation cards */}
      <div className="space-y-3">
        {(data.correlations || []).map((corr, i) => (
          <CorrelationCard key={i} corr={corr} index={i} isPro={false} />
        ))}
      </div>

      {/* Upgrade CTA */}
      <div
        className="rounded-2xl p-8 text-center"
        style={{
          background: 'linear-gradient(135deg, rgba(0,212,163,0.06), rgba(201,163,78,0.04))',
          border: '1px solid rgba(0,212,163,0.12)',
        }}
      >
        <div
          className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4 text-2xl"
          style={{ background: 'rgba(0,212,163,0.10)' }}
        >
          🛰️
        </div>
        <h3 className="text-white font-black text-lg mb-2">Unlock Kepler Radar</h3>
        <p className="text-[#4A5568] text-sm mb-6 max-w-sm mx-auto">
          See full causal chains, sector ripple maps, and specific stock predictions based on today's correlated news.
          <span className="text-[#00D4A3] font-semibold"> {data.total_correlations} correlations</span> discovered today.
        </p>
        <Link href="/pricing" className="btn-brand">
          Upgrade to Pro →
        </Link>
      </div>
    </div>
  )
}

// ── Generating Skeleton ──────────────────────────────────────────────────────
function GeneratingSkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map(i => (
        <div key={i} className="rounded-2xl p-5" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
          <div className="flex items-center gap-4">
            <div className="skeleton w-11 h-11 rounded-xl flex-shrink-0" />
            <div className="flex-1">
              <div className="skeleton h-2.5 w-20 mb-2" />
              <div className="skeleton h-4 w-3/4" />
            </div>
          </div>
        </div>
      ))}
      <div className="text-center py-6 text-[#4A5568] text-sm flex items-center justify-center gap-3">
        <svg className="animate-spin text-[#C9A34E]" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M21 12a9 9 0 1 1-6.219-8.56" />
        </svg>
        Kepler Radar is cross-reading today's news…
      </div>
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────
interface Props {
  userPlan: string
  isAdmin?: boolean
}

export default function MarketRadarTab({ userPlan, isAdmin = false }: Props) {
  const [data, setData] = useState<RadarResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [polling, setPolling] = useState(false)
  const [regenLoading, setRegenLoading] = useState(false)
  const [regenMsg, setRegenMsg] = useState<string | null>(null)
  const isPro = userPlan === 'pro' || userPlan === 'elite'

  const fetchCorrelations = useCallback(async () => {
    try {
      const res = await apiGetCorrelations()
      setData(res)

      // If still generating, poll every 8 seconds
      if (res.status === 'generating') {
        setPolling(true)
        setTimeout(() => {
          setPolling(false)
          fetchCorrelations()
        }, 8000)
      } else {
        setPolling(false)
      }
    } catch (e: any) {
      setError(e.message || 'Failed to load Kepler Radar. Try again.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchCorrelations() }, [fetchCorrelations])

  const handleRegen = async () => {
    setRegenLoading(true)
    setRegenMsg(null)
    try {
      const res = await apiRegenerateCorrelations()
      setRegenMsg(res.message)
      setTimeout(() => {
        setData(null)
        setLoading(true)
        fetchCorrelations()
      }, 5000)
    } catch (e: any) {
      setRegenMsg(e.message || 'Failed')
    } finally {
      setRegenLoading(false)
    }
  }

  const generated = data?.generated_at
    ? new Date(data.generated_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
    : null

  return (
    <div className="animate-fade-in">

      {/* ── Header ── */}
      <div className="flex items-start justify-between gap-4 mb-7 flex-wrap">
        <div>
          {/* Title */}
          <div className="flex items-center gap-3 mb-1.5">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center text-lg"
              style={{ background: 'linear-gradient(135deg, rgba(201,163,78,0.2), rgba(0,212,163,0.1))', border: '1px solid rgba(201,163,78,0.25)' }}
            >
              🛰️
            </div>
            <h1 className="text-2xl font-black text-white">Kepler Radar</h1>
            <div
              className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest px-2.5 py-1 rounded-full"
              style={{ background: 'rgba(0,212,163,0.12)', color: '#00D4A3', border: '1px solid rgba(0,212,163,0.2)' }}
            >
              <PulsingDot color="#00D4A3" />
              AI Intelligence
            </div>
          </div>
          <p className="text-[#4A5568] text-sm">
            Cross-news correlation engine — finds hidden links between today's events and predicts market impact
          </p>
        </div>

        {/* Meta info + Admin regen */}
        <div className="flex items-center gap-3 flex-wrap">
          {generated && (
            <span className="text-xs text-[#333] font-mono">Updated {generated}</span>
          )}
          {isAdmin && (
            <button
              onClick={handleRegen}
              disabled={regenLoading}
              className="text-xs px-3 py-1.5 rounded-lg font-semibold transition-all"
              style={{ background: 'rgba(255,255,255,0.05)', color: '#4A5568', border: '1px solid rgba(255,255,255,0.08)' }}
            >
              {regenLoading ? '…' : '↺ Regenerate'}
            </button>
          )}
          {!loading && data?.status !== 'generating' && (
            <button
              onClick={() => { setLoading(true); fetchCorrelations() }}
              className="text-xs px-3 py-1.5 rounded-lg font-semibold transition-all hover:text-white"
              style={{ background: 'rgba(255,255,255,0.04)', color: '#4A5568', border: '1px solid rgba(255,255,255,0.07)' }}
            >
              ↺ Refresh
            </button>
          )}
        </div>
      </div>

      {/* Admin regen message */}
      {regenMsg && (
        <div className="mb-4 p-3 rounded-xl text-xs text-[#00D4A3]"
          style={{ background: 'rgba(0,212,163,0.08)', border: '1px solid rgba(0,212,163,0.15)' }}>
          {regenMsg}
        </div>
      )}

      {/* ── Loading state ── */}
      {loading && <GeneratingSkeleton />}

      {/* ── Error state ── */}
      {!loading && error && (
        <div className="glass-card p-8 text-center">
          <p className="text-[#4A5568] text-sm mb-4">{error}</p>
          <button onClick={() => { setError(null); setLoading(true); fetchCorrelations() }} className="btn-brand text-sm py-2 px-5">
            Retry
          </button>
        </div>
      )}

      {/* ── Generating state ── */}
      {!loading && !error && data?.status === 'generating' && (
        <div>
          <div
            className="mb-6 p-4 rounded-xl flex items-center gap-3 text-sm"
            style={{ background: 'rgba(201,163,78,0.08)', border: '1px solid rgba(201,163,78,0.15)' }}
          >
            <svg className="animate-spin text-[#C9A34E] flex-shrink-0" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 12a9 9 0 1 1-6.219-8.56" />
            </svg>
            <div>
              <p className="font-semibold text-white">Kepler Radar is running…</p>
              <p className="text-[#4A5568] text-xs mt-0.5">Gemini AI is cross-reading today's digest. This takes ~20-30 seconds.</p>
            </div>
          </div>
          <GeneratingSkeleton />
        </div>
      )}

      {/* ── Unavailable ── */}
      {!loading && !error && data?.status === 'unavailable' && (
        <div className="glass-card p-12 text-center">
          <div className="text-4xl mb-4">🛰️</div>
          <h3 className="text-white font-bold text-lg mb-2">No Digest Available</h3>
          <p className="text-[#4A5568] text-sm">Kepler Radar requires today's digest to be generated first. Check back after 8 AM IST on weekdays.</p>
        </div>
      )}

      {/* ── Ready — Full data (pro) ── */}
      {!loading && !error && data?.status === 'ready' && data.correlations && (
        <div className="space-y-4">
          {/* Summary header */}
          <div
            className="grid grid-cols-3 gap-3 mb-2"
            style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)' }}
          >
            {[
              {
                label: 'Correlations Found',
                value: data.total_correlations ?? data.correlations.length,
                icon: '🔗',
                color: '#00D4A3',
              },
              {
                label: 'Dominant Theme',
                value: data.dominant_theme || '—',
                icon: '📡',
                color: '#C9A34E',
                small: true,
              },
              {
                label: 'Sectors Mapped',
                value: data.correlations.reduce((acc, c) =>
                  acc + (c.impact_sectors?.length || 0) + (c.beneficiary_sectors?.length || 0), 0),
                icon: '🏭',
                color: '#9F7AEA',
              },
            ].map(stat => (
              <div
                key={stat.label}
                className="rounded-xl p-4 text-center"
                style={{ background: `${stat.color}08`, border: `1px solid ${stat.color}18` }}
              >
                <div className="text-xl mb-1">{stat.icon}</div>
                <div
                  className={`font-black text-white mb-1 ${stat.small ? 'text-xs leading-tight' : 'text-2xl'}`}
                >
                  {stat.value}
                </div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[#4A5568]">{stat.label}</p>
              </div>
            ))}
          </div>

          {/* AI Mood Reasoning */}
          {data.market_mood_reasoning && (
            <div
              className="p-4 rounded-xl flex items-start gap-3"
              style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)' }}
            >
              <span className="text-lg flex-shrink-0">🧠</span>
              <div>
                <p className="text-[10px] font-bold uppercase tracking-widest text-[#4A5568] mb-1">Radar Intelligence Summary</p>
                <p className="text-sm text-[#A0AEC0] leading-relaxed italic">"{data.market_mood_reasoning}"</p>
              </div>
            </div>
          )}

          {/* Correlation cards */}
          <div className="space-y-3">
            {data.correlations.map((corr, i) => (
              <CorrelationCard key={corr.id || i} corr={corr} index={i} isPro={true} />
            ))}
          </div>

          {/* Disclaimer */}
          <div className="mt-4 p-3 rounded-xl text-xs text-[#333] text-center"
            style={{ background: 'rgba(255,255,255,0.02)' }}>
            AI-generated correlation analysis. Not investment advice. For educational purposes only.
            Correlations are inferred from news patterns — verify before acting.
          </div>
        </div>
      )}

      {/* ── Locked state (free user, has data) ── */}
      {!loading && !error && data?.status === 'locked' && (
        <UpgradeTeaser data={data} />
      )}
    </div>
  )
}
