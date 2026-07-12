'use client'

import { useState, useEffect, useCallback } from 'react'
import { apiGetSignals, type StockSignal } from '@/lib/api'

// ── Config ────────────────────────────────────────────────────────────────────
const SIG = {
  BULLISH: { label: 'Bullish', color: '#3DDC84', bg: 'rgba(61,220,132,0.10)',  border: 'rgba(61,220,132,0.25)',  icon: '▲' },
  BEARISH: { label: 'Bearish', color: '#E5484D', bg: 'rgba(229,72,77,0.10)',   border: 'rgba(229,72,77,0.25)',   icon: '▼' },
  NEUTRAL: { label: 'Neutral', color: '#C9A34E', bg: 'rgba(201,163,78,0.10)', border: 'rgba(201,163,78,0.25)', icon: '◆' },
} as const

const fmt = (v: number | null) =>
  v == null ? '—' : `₹${v.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`

function timeAgo(iso: string) {
  const m = Math.floor((Date.now() - new Date(iso).getTime()) / 60000)
  if (m < 60)  return `${m}m ago`
  if (m < 1440) return `${Math.floor(m / 60)}h ago`
  return `${Math.floor(m / 1440)}d ago`
}

// ── Lightbox ──────────────────────────────────────────────────────────────────
function Lightbox({ src, title, onClose }: { src: string; title: string; onClose: () => void }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', h)
    return () => document.removeEventListener('keydown', h)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-[999] flex items-center justify-center bg-black/92 backdrop-blur-md p-4"
      onClick={onClose}
    >
      <div className="relative max-w-5xl w-full" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3 px-1">
          <p className="text-white font-bold text-sm truncate pr-4">{title}</p>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-[#1a1a1a] border border-[#333] text-[#777] hover:text-white flex items-center justify-center transition-colors shrink-0"
          >✕</button>
        </div>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src} alt={title}
          className="w-full max-h-[82vh] object-contain rounded-2xl border border-[#222]"
        />
        <p className="text-center text-xs text-[#333] mt-3">Press Esc or click outside to close</p>
      </div>
    </div>
  )
}

// ── Signal Card ───────────────────────────────────────────────────────────────
function SignalCard({
  signal, onImageClick,
}: {
  signal: StockSignal
  onImageClick: (url: string, title: string) => void
}) {
  const cfg = SIG[signal.signal_type] ?? SIG.NEUTRAL
  const locked = signal.locked

  return (
    <div
      className="rounded-2xl border overflow-hidden flex flex-col transition-all duration-300 group hover:-translate-y-1"
      style={{
        background: '#131315',
        borderColor: locked ? 'rgba(255,255,255,0.06)' : cfg.border,
        boxShadow: locked ? 'none' : `0 0 28px ${cfg.bg}`,
      }}
    >
      {/* ── Chart image area ── */}
      <div className="relative w-full aspect-video bg-[#0a0a0b] overflow-hidden shrink-0">
        {!locked && signal.image_url ? (
          <>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={signal.image_url}
              alt={signal.title}
              className="w-full h-full object-cover cursor-zoom-in group-hover:scale-[1.025] transition-transform duration-500"
              onClick={() => onImageClick(signal.image_url!, signal.title)}
            />
            {/* Expand hint */}
            <div className="absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
            <button
              onClick={() => onImageClick(signal.image_url!, signal.title)}
              className="absolute bottom-3 right-3 flex items-center gap-1.5 bg-black/70 backdrop-blur-sm border border-white/10 text-white text-xs px-2.5 py-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-all hover:bg-black/90"
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>
              </svg>
              Full view
            </button>
          </>
        ) : (
          /* Locked overlay */
          <div className="w-full h-full flex flex-col items-center justify-center gap-3 px-6 text-center">
            <div
              className="w-12 h-12 rounded-full flex items-center justify-center border"
              style={{ background: 'rgba(201,163,78,0.08)', borderColor: 'rgba(201,163,78,0.2)' }}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#C9A34E" strokeWidth="2">
                <rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
              </svg>
            </div>
            <div>
              <p className="text-sm font-bold text-white mb-1">
                {signal.plan_required === 'elite' ? 'Elite' : 'Pro'} Access Required
              </p>
              <p className="text-xs text-[#444]">{signal.title}</p>
            </div>
            <a
              href="/pricing"
              className="text-xs font-semibold border px-4 py-1.5 rounded-full transition-colors"
              style={{ color: '#C9A34E', borderColor: 'rgba(201,163,78,0.3)' }}
            >
              Upgrade →
            </a>
          </div>
        )}
      </div>

      {/* ── Card body ── */}
      <div className="p-4 flex flex-col flex-1">
        {/* Symbol + timeframe + signal badge */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span
                className="text-xs font-black tracking-widest px-2 py-0.5 rounded"
                style={{ background: 'rgba(255,255,255,0.05)', color: '#9A9A9E' }}
              >{signal.symbol}</span>
              {signal.timeframe && (
                <span className="text-xs text-[#3a3a3a] border border-[#1e1e1e] px-1.5 py-0.5 rounded">
                  {signal.timeframe}
                </span>
              )}
            </div>
            <p className="text-sm font-bold text-white leading-snug">{signal.title}</p>
          </div>
          <span
            className="text-xs font-black px-2.5 py-1 rounded-full border shrink-0 flex items-center gap-1 mt-0.5"
            style={{ color: cfg.color, background: cfg.bg, borderColor: cfg.border }}
          >
            {cfg.icon} {cfg.label}
          </span>
        </div>

        {/* Description */}
        {!locked && signal.description && (
          <p className="text-sm text-[#555] leading-relaxed mb-3">{signal.description}</p>
        )}

        {/* Price levels */}
        {!locked && (signal.support || signal.resistance || signal.target || signal.stoploss) && (
          <div className="grid grid-cols-2 gap-2 mb-3 mt-auto">
            {signal.support != null && (
              <div className="rounded-xl p-2.5" style={{ background: 'rgba(61,220,132,0.06)', border: '1px solid rgba(61,220,132,0.14)' }}>
                <p className="text-[11px] uppercase tracking-wide text-[#444] mb-1">Support</p>
                <p className="text-sm font-black" style={{ color: '#3DDC84' }}>{fmt(signal.support)}</p>
              </div>
            )}
            {signal.resistance != null && (
              <div className="rounded-xl p-2.5" style={{ background: 'rgba(229,72,77,0.06)', border: '1px solid rgba(229,72,77,0.14)' }}>
                <p className="text-[11px] uppercase tracking-wide text-[#444] mb-1">Resistance</p>
                <p className="text-sm font-black" style={{ color: '#E5484D' }}>{fmt(signal.resistance)}</p>
              </div>
            )}
            {signal.target != null && (
              <div className="rounded-xl p-2.5" style={{ background: 'rgba(201,163,78,0.06)', border: '1px solid rgba(201,163,78,0.14)' }}>
                <p className="text-[11px] uppercase tracking-wide text-[#444] mb-1">Target</p>
                <p className="text-sm font-black" style={{ color: '#C9A34E' }}>{fmt(signal.target)}</p>
              </div>
            )}
            {signal.stoploss != null && (
              <div className="rounded-xl p-2.5" style={{ background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.06)' }}>
                <p className="text-[11px] uppercase tracking-wide text-[#444] mb-1">Stop Loss</p>
                <p className="text-sm font-black text-[#9A9A9E]">{fmt(signal.stoploss)}</p>
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between pt-2.5 border-t border-[rgba(255,255,255,0.05)] mt-auto">
          <span className="text-xs text-[#333]">{timeAgo(signal.created_at)}</span>
          {locked && (
            <span className="text-[11px] font-semibold" style={{ color: '#C9A34E' }}>
              🔒 {signal.plan_required === 'elite' ? 'Elite' : 'Pro'} only
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────
export default function SignalsFeedTab({ userPlan = 'free' }: { userPlan?: string }) {
  const [signals, setSignals]       = useState<StockSignal[]>([])
  const [total, setTotal]           = useState(0)
  const [page, setPage]             = useState(1)
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState<string | null>(null)
  const [typeFilter, setTypeFilter] = useState<'ALL' | 'BULLISH' | 'BEARISH' | 'NEUTRAL'>('ALL')
  const [lightbox, setLightbox]     = useState<{ src: string; title: string } | null>(null)
  const LIMIT = 12

  const load = useCallback(async (p: number) => {
    setLoading(true); setError(null)
    try {
      const data = await apiGetSignals(p, LIMIT)
      setSignals(data.signals); setTotal(data.total); setPage(p)
    } catch (e: any) {
      setError(e.message || 'Could not load signals')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load(1) }, [load])

  const displayed  = typeFilter === 'ALL' ? signals : signals.filter(s => s.signal_type === typeFilter)
  const totalPages = Math.ceil(total / LIMIT)

  return (
    <div>
      {lightbox && <Lightbox src={lightbox.src} title={lightbox.title} onClose={() => setLightbox(null)} />}

      {/* Header */}
      <div className="mb-6">
        <span className="section-label">Manual Research</span>
        <h1 className="text-2xl font-black text-white mb-1">Stock Signals</h1>
        <p className="text-sm text-[#555]">
          Hand-picked chart analysis — support, resistance &amp; next-move predictions
        </p>
      </div>

      {/* Filter pills + count */}
      <div className="flex items-center gap-2 mb-6 flex-wrap">
        {(['ALL', 'BULLISH', 'BEARISH', 'NEUTRAL'] as const).map(t => {
          const cfg = t !== 'ALL' ? SIG[t] : null
          const active = typeFilter === t
          return (
            <button
              key={t}
              onClick={() => setTypeFilter(t)}
              className="text-xs font-bold px-4 py-1.5 rounded-full border transition-all"
              style={active && cfg
                ? { background: cfg.bg, borderColor: cfg.border, color: cfg.color }
                : active
                ? { background: 'rgba(255,255,255,0.08)', borderColor: 'rgba(255,255,255,0.2)', color: '#fff' }
                : { background: 'transparent', borderColor: 'rgba(255,255,255,0.07)', color: '#444' }
              }
            >
              {t === 'ALL' ? 'All' : `${SIG[t].icon} ${t.charAt(0) + t.slice(1).toLowerCase()}`}
            </button>
          )
        })}
        <span className="ml-auto text-sm text-[#444] font-mono">{total} signal{total !== 1 ? 's' : ''}</span>
      </div>

      {/* Loading skeleton */}
      {loading && (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="rounded-2xl border border-[rgba(255,255,255,0.05)] overflow-hidden animate-pulse bg-[#131315]">
              <div className="aspect-video bg-[#0f0f11]" />
              <div className="p-4 space-y-3">
                <div className="skeleton h-3 w-20 rounded-full" />
                <div className="skeleton h-4 w-full rounded" />
                <div className="grid grid-cols-2 gap-2 mt-2">
                  <div className="skeleton h-11 rounded-xl" />
                  <div className="skeleton h-11 rounded-xl" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="glass-card p-8 text-center max-w-sm mx-auto" style={{ borderColor: 'rgba(229,72,77,0.2)' }}>
          <p className="text-2xl mb-3">⚠️</p>
          <p className="text-white font-bold mb-2">Failed to load signals</p>
          <p className="text-sm text-[#555] mb-4">{error}</p>
          <button onClick={() => load(1)} className="btn-brand text-sm py-2 px-6">Retry</button>
        </div>
      )}

      {/* Empty */}
      {!loading && !error && displayed.length === 0 && (
        <div className="text-center py-20">
          <p className="text-5xl mb-4">📊</p>
          <p className="text-lg font-black text-white mb-2">No signals yet</p>
          <p className="text-sm text-[#444]">
            {typeFilter !== 'ALL'
              ? `No ${typeFilter.toLowerCase()} signals right now. Try a different filter.`
              : 'Your analyst is preparing chart analysis. Check back soon.'}
          </p>
        </div>
      )}

      {/* Cards grid */}
      {!loading && !error && displayed.length > 0 && (
        <>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {displayed.map(s => (
              <SignalCard
                key={s.id}
                signal={s}
                onImageClick={(src, title) => setLightbox({ src, title })}
              />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-3 mt-8">
              <button
                onClick={() => load(page - 1)}
                disabled={page === 1}
                className="text-sm px-4 py-2 rounded-lg border border-[rgba(255,255,255,0.08)] text-[#555] hover:text-white hover:border-[rgba(255,255,255,0.2)] disabled:opacity-30 disabled:cursor-not-allowed transition-all"
              >← Prev</button>
              <span className="text-sm text-[#444] font-mono">Page {page} / {totalPages}</span>
              <button
                onClick={() => load(page + 1)}
                disabled={page === totalPages}
                className="text-sm px-4 py-2 rounded-lg border border-[rgba(255,255,255,0.08)] text-[#555] hover:text-white hover:border-[rgba(255,255,255,0.2)] disabled:opacity-30 disabled:cursor-not-allowed transition-all"
              >Next →</button>
            </div>
          )}
        </>
      )}

      <p className="text-center text-[11px] text-[#222] mt-10 pb-2">
        Chart analysis is educational only. Not SEBI-registered investment advice.
      </p>
    </div>
  )
}
