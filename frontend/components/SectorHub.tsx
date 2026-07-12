'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import {
  apiSectorsLive,
  type SectorHubResult,
  type SectorLive,
  type SectorMover,
  type SectorNewsItem,
} from '@/lib/api'

// ── Constants ─────────────────────────────────────────────────────────────────

const SENTIMENT_CFG = {
  BULLISH: { label: 'BULLISH', color: '#10b981', bg: 'rgba(16,185,129,0.12)', border: 'rgba(16,185,129,0.3)' },
  BEARISH: { label: 'BEARISH', color: '#ef4444', bg: 'rgba(239,68,68,0.12)',  border: 'rgba(239,68,68,0.3)' },
  MIXED:   { label: 'MIXED',   color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.3)' },
}

const IMPACT_COLORS: Record<string, string> = {
  HIGH:   '#ef4444',
  MEDIUM: '#f59e0b',
  LOW:    '#64748b',
}

type SortKey = '1D' | '1W' | '1M' | 'YTD' | 'RS' | 'BULLISH_FIRST'

// ── Helpers ───────────────────────────────────────────────────────────────────

function sign(v: number) { return v >= 0 ? '+' : '' }
function pctColor(v: number) { return v > 0 ? '#10b981' : v < 0 ? '#ef4444' : '#64748b' }

function heatColor(v: number): string {
  if (v >= 2)   return '#10b981'
  if (v >= 0.5) return '#34d399'
  if (v >= 0)   return '#6ee7b7'
  if (v >= -0.5) return '#fca5a5'
  if (v >= -2)  return '#ef4444'
  return '#b91c1c'
}

function sortSectors(sectors: SectorLive[], key: SortKey): SectorLive[] {
  const copy = [...sectors]
  switch (key) {
    case '1D':          return copy.sort((a, b) => b.day_pct   - a.day_pct)
    case '1W':          return copy.sort((a, b) => b.week_pct  - a.week_pct)
    case '1M':          return copy.sort((a, b) => b.month_pct - a.month_pct)
    case 'YTD':         return copy.sort((a, b) => b.ytd_pct   - a.ytd_pct)
    case 'RS':          return copy.sort((a, b) => b.rs_nifty  - a.rs_nifty)
    case 'BULLISH_FIRST':
      const order = { BULLISH: 0, MIXED: 1, BEARISH: 2 }
      return copy.sort((a, b) => order[a.sentiment] - order[b.sentiment])
    default: return copy
  }
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function SentimentBadge({ s }: { s: 'BULLISH' | 'BEARISH' | 'MIXED' }) {
  const cfg = SENTIMENT_CFG[s]
  const ArrowUp = () => <svg width="9" height="9" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M12 3l9 18H3L12 3z"/></svg>
  const ArrowDn = () => <svg width="9" height="9" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M12 21L3 3h18L12 21z"/></svg>
  const Dot = () => <svg width="7" height="7" viewBox="0 0 24 24" fill="currentColor" stroke="none"><circle cx="12" cy="12" r="12"/></svg>
  return (
    <span style={{
      fontSize: '10px', fontWeight: 700, padding: '2px 8px',
      borderRadius: '99px', letterSpacing: '0.5px',
      background: cfg.bg, border: `1px solid ${cfg.border}`, color: cfg.color,
      display: 'inline-flex', alignItems: 'center', gap: '4px',
    }}>
      {s === 'BULLISH' ? <ArrowUp /> : s === 'BEARISH' ? <ArrowDn /> : <Dot />}
      {cfg.label}
    </span>
  )
}

function PctChip({ label, value }: { label: string; value: number }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px', minWidth: 40 }}>
      <span style={{ fontSize: '9px', color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.3px' }}>{label}</span>
      <span style={{ fontSize: '12px', fontWeight: 800, color: pctColor(value) }}>
        {sign(value)}{value.toFixed(2)}%
      </span>
    </div>
  )
}

function MoverChip({ m }: { m: SectorMover }) {
  const up = m.change_pct >= 0
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '4px',
      background: up ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)',
      border: `1px solid ${up ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'}`,
      borderRadius: '6px', padding: '3px 7px', fontSize: '11px',
    }}>
      <span style={{ color: '#94a3b8', fontWeight: 600 }}>{m.symbol}</span>
      <span style={{ color: up ? '#10b981' : '#ef4444', fontWeight: 700 }}>
        {sign(m.change_pct)}{m.change_pct.toFixed(1)}%
      </span>
    </span>
  )
}

function NewsItem({ n }: { n: SectorNewsItem }) {
  return (
    <a
      href={n.url}
      target="_blank"
      rel="noopener noreferrer"
      style={{
        display: 'flex', alignItems: 'flex-start', gap: '8px',
        padding: '8px 0', borderBottom: '1px solid rgba(255,255,255,0.04)',
        textDecoration: 'none', cursor: 'pointer',
        transition: 'opacity 0.15s',
      }}
      onMouseEnter={e => (e.currentTarget.style.opacity = '0.75')}
      onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
    >
      <span style={{
        flexShrink: 0, fontSize: '8px', fontWeight: 800, padding: '2px 5px',
        borderRadius: '4px', marginTop: '2px', letterSpacing: '0.3px',
        background: IMPACT_COLORS[n.impact] + '18',
        color: IMPACT_COLORS[n.impact],
        border: `1px solid ${IMPACT_COLORS[n.impact]}30`,
      }}>
        {n.impact}
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontSize: '12px', color: '#cbd5e1', fontWeight: 500, lineHeight: 1.4, margin: 0, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
          {n.title}
        </p>
        <span style={{ fontSize: '10px', color: '#475569', marginTop: '2px', display: 'block' }}>{n.source}</span>
      </div>
    </a>
  )
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.07)',
      borderRadius: '14px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px',
      animation: 'pulse 1.5s ease-in-out infinite',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ width: 120, height: 16, background: 'rgba(255,255,255,0.06)', borderRadius: '6px' }} />
        <div style={{ width: 60, height: 16, background: 'rgba(255,255,255,0.04)', borderRadius: '99px' }} />
      </div>
      <div style={{ width: '100%', height: 12, background: 'rgba(255,255,255,0.04)', borderRadius: '6px' }} />
      <div style={{ display: 'flex', gap: '8px' }}>
        {[1,2,3,4].map(i => (
          <div key={i} style={{ flex: 1, height: 36, background: 'rgba(255,255,255,0.03)', borderRadius: '8px' }} />
        ))}
      </div>
    </div>
  )
}

// ── Sector Card ───────────────────────────────────────────────────────────────

function SectorCard({ sector }: { sector: SectorLive }) {
  const [expanded, setExpanded] = useState(false)
  const cfg = SENTIMENT_CFG[sector.sentiment]

  return (
    <div
      style={{
        background: 'rgba(255,255,255,0.02)',
        border: `1px solid rgba(255,255,255,0.07)`,
        borderRadius: '14px',
        overflow: 'hidden',
        transition: 'border-color 0.2s, box-shadow 0.2s',
      }}
      onMouseEnter={e => {
        ;(e.currentTarget as HTMLDivElement).style.borderColor = sector.color + '40'
        ;(e.currentTarget as HTMLDivElement).style.boxShadow = `0 0 20px ${sector.color}10`
      }}
      onMouseLeave={e => {
        ;(e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(255,255,255,0.07)'
        ;(e.currentTarget as HTMLDivElement).style.boxShadow = 'none'
      }}
    >
      {/* Colored top accent */}
      <div style={{ height: '3px', background: `linear-gradient(90deg, ${sector.color}, ${sector.color}44)` }} />

      <div style={{ padding: '16px 18px' }}>
        {/* Header row */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px', gap: '8px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{
              width: 30, height: 30, borderRadius: '8px', flexShrink: 0,
              background: sector.color + '18', border: `1px solid ${sector.color}30`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '13px', fontWeight: 900, color: sector.color,
              fontFamily: 'var(--font-primary)',
            }}>
              {sector.name[0]}
            </div>
            <div>
              <p style={{ fontSize: '13px', fontWeight: 800, color: '#f1f5f9', margin: 0, lineHeight: 1.2 }}>{sector.name}</p>
              <p style={{ fontSize: '10px', color: '#475569', margin: 0 }}>
                {sector.current.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
              </p>
            </div>
          </div>
          <SentimentBadge s={sector.sentiment} />
        </div>

        {/* Performance row */}
        <div style={{
          display: 'flex', gap: '4px', justifyContent: 'space-between',
          background: 'rgba(255,255,255,0.02)', borderRadius: '10px',
          padding: '10px 8px', marginBottom: '12px', flexWrap: 'wrap',
        }}>
          <PctChip label="1D" value={sector.day_pct} />
          <div style={{ width: '1px', background: 'rgba(255,255,255,0.06)', margin: '4px 0' }} />
          <PctChip label="1W" value={sector.week_pct} />
          <div style={{ width: '1px', background: 'rgba(255,255,255,0.06)', margin: '4px 0' }} />
          <PctChip label="1M" value={sector.month_pct} />
          <div style={{ width: '1px', background: 'rgba(255,255,255,0.06)', margin: '4px 0' }} />
          <PctChip label="YTD" value={sector.ytd_pct} />
          <div style={{ width: '1px', background: 'rgba(255,255,255,0.06)', margin: '4px 0' }} />
          {/* RS vs Nifty */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px', minWidth: 44 }}>
            <span style={{ fontSize: '9px', color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.3px' }}>RS</span>
            <span style={{
              fontSize: '11px', fontWeight: 800,
              color: sector.rs_nifty > 1.02 ? '#10b981' : sector.rs_nifty < 0.98 ? '#ef4444' : '#64748b',
            }}>
              {sector.rs_nifty.toFixed(2)}×
            </span>
          </div>
        </div>

        {/* Top movers chips */}
        {sector.top_movers.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '12px' }}>
            {sector.top_movers.slice(0, 3).map(m => (
              <MoverChip key={m.symbol} m={m} />
            ))}
          </div>
        )}

        {/* Macro watch signals */}
        {sector.macro_watch.length > 0 && (
          <div style={{ marginBottom: '12px' }}>
            <p style={{ fontSize: '10px', color: 'var(--text-muted, #5C5C60)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '6px', fontFamily: 'var(--font-primary)' }}>
              What to Watch
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
              {sector.macro_watch.slice(0, 3).map((w, i) => (
                <span key={i} style={{
                  fontSize: '10px', padding: '3px 8px', borderRadius: '6px',
                  background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
                  color: '#64748b',
                }}>
                  {w}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* News headlines (top 2) */}
        {sector.news.length > 0 && (
          <div style={{ marginBottom: '10px' }}>
            {sector.news.slice(0, 2).map((n, i) => (
              <NewsItem key={i} n={n} />
            ))}
          </div>
        )}

        {/* Expand button */}
        <button
          onClick={() => setExpanded(e => !e)}
          style={{
            width: '100%', background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.07)', borderRadius: '8px',
            color: '#475569', fontSize: '11px', fontWeight: 600, padding: '7px',
            cursor: 'pointer', transition: 'all 0.15s', display: 'flex',
            alignItems: 'center', justifyContent: 'center', gap: '6px',
          }}
          onMouseEnter={e => {
            ;(e.currentTarget as HTMLButtonElement).style.background = sector.color + '18'
            ;(e.currentTarget as HTMLButtonElement).style.borderColor = sector.color + '40'
            ;(e.currentTarget as HTMLButtonElement).style.color = sector.color
          }}
          onMouseLeave={e => {
            ;(e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.03)'
            ;(e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,255,255,0.07)'
            ;(e.currentTarget as HTMLButtonElement).style.color = '#475569'
          }}
        >
          {expanded ? 'Hide Details ↑' : 'Full Details ↓'}
        </button>

        {/* ── Expanded panel ── */}
        {expanded && (
          <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid rgba(255,255,255,0.06)' }}>

            {/* All top movers table */}
            {sector.top_movers.length > 0 && (
              <div style={{ marginBottom: '16px' }}>
                <p style={{ fontSize: '10px', color: 'var(--text-muted, #5C5C60)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px', fontFamily: 'var(--font-primary)' }}>
                  All Top Movers
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {sector.top_movers.map((m, i) => (
                    <div key={m.symbol} style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '6px 10px', borderRadius: '8px',
                      background: i % 2 === 0 ? 'rgba(255,255,255,0.02)' : 'transparent',
                    }}>
                      <span style={{ fontSize: '12px', color: '#94a3b8', fontWeight: 600 }}>{m.symbol}</span>
                      <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                        <span style={{ fontSize: '12px', color: '#cbd5e1' }}>₹{m.price.toLocaleString('en-IN', { maximumFractionDigits: 1 })}</span>
                        <span style={{
                          fontSize: '12px', fontWeight: 700, minWidth: 55, textAlign: 'right',
                          color: m.change_pct >= 0 ? '#10b981' : '#ef4444',
                        }}>
                          {sign(m.change_pct)}{m.change_pct.toFixed(2)}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* All news */}
            {sector.news.length > 0 && (
              <div style={{ marginBottom: '16px' }}>
                <p style={{ fontSize: '10px', color: '#475569', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '4px' }}>
                  🗞️ Sector News ({sector.news_count})
                </p>
                {sector.news.map((n, i) => (
                  <NewsItem key={i} n={n} />
                ))}
              </div>
            )}

            {/* All macro watch signals */}
            {sector.macro_watch.length > 0 && (
              <div style={{ marginBottom: '14px' }}>
                <p style={{ fontSize: '10px', color: '#475569', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '6px' }}>
                  📡 All Macro Signals
                </p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
                  {sector.macro_watch.map((w, i) => (
                    <span key={i} style={{
                      fontSize: '11px', padding: '4px 9px', borderRadius: '6px',
                      background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
                      color: '#94a3b8',
                    }}>
                      {w}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Global peer + sensitivity */}
            <div style={{
              background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)',
              borderRadius: '10px', padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: '8px',
            }}>
              <div>
                <span style={{ fontSize: '10px', color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>🌐 Global Peer</span>
                <p style={{ fontSize: '12px', color: '#94a3b8', margin: '4px 0 0', lineHeight: 1.4 }}>{sector.global_peer}</p>
              </div>
              <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '8px' }}>
                <span style={{ fontSize: '10px', color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>⚡ Sensitivity</span>
                <p style={{ fontSize: '12px', color: '#94a3b8', margin: '4px 0 0', lineHeight: 1.4 }}>{sector.sensitivity}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Heatmap Strip ─────────────────────────────────────────────────────────────

function HeatmapStrip({ sectors, sortKey }: { sectors: SectorLive[]; sortKey: SortKey }) {
  const getValue = (s: SectorLive) => {
    switch (sortKey) {
      case '1W': return s.week_pct
      case '1M': return s.month_pct
      case 'YTD': return s.ytd_pct
      default: return s.day_pct
    }
  }

  const label = sortKey === '1W' ? '1W' : sortKey === '1M' ? '1M' : sortKey === 'YTD' ? 'YTD' : '1D'

  return (
    <div style={{
      background: 'rgba(255,255,255,0.015)', border: '1px solid rgba(255,255,255,0.07)',
      borderRadius: '12px', padding: '14px 18px', marginBottom: '20px', overflowX: 'auto',
    }}>
      <p style={{ fontSize: '10px', color: '#475569', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '10px' }}>
        Sector Heatmap — {label} Performance
      </p>
      <div style={{ display: 'flex', gap: '6px', minWidth: 'max-content' }}>
        {[...sectors].sort((a, b) => getValue(b) - getValue(a)).map(s => {
          const v = getValue(s)
          return (
            <div key={s.name} style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '5px',
              padding: '8px 12px', borderRadius: '8px',
              background: heatColor(v) + '18', border: `1px solid ${heatColor(v)}30`,
              minWidth: 80, cursor: 'default', transition: 'transform 0.15s',
            }}
              onMouseEnter={e => (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-2px)'}
              onMouseLeave={e => (e.currentTarget as HTMLDivElement).style.transform = 'none'}
            >
              <span style={{ fontSize: '14px' }}>{s.icon}</span>
              <span style={{ fontSize: '9px', color: '#64748b', fontWeight: 600, textAlign: 'center', lineHeight: 1.2 }}>{s.name}</span>
              <span style={{ fontSize: '11px', fontWeight: 800, color: heatColor(v) }}>
                {sign(v)}{v.toFixed(1)}%
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Main Component ─────────────────────────────────────────────────────────────

export default function SectorHub({ data: externalData, isPro }: { data: SectorHubResult | null; isPro: boolean }) {
  const [data, setData]         = useState<SectorHubResult | null>(externalData)
  const [loading, setLoading]   = useState(!externalData)
  const [error, setError]       = useState<string | null>(null)
  const [sortKey, setSortKey]   = useState<SortKey>('BULLISH_FIRST')
  const [countdown, setCountdown] = useState(externalData?.next_refresh_in ?? 900)
  const countdownRef = useRef<NodeJS.Timeout | null>(null)

  // Sync external data
  useEffect(() => {
    if (externalData) {
      setData(externalData)
      setLoading(false)
      setCountdown(externalData.next_refresh_in)
    }
  }, [externalData])

  const load = useCallback(async (force = false) => {
    setLoading(true)
    setError(null)
    try {
      const result = await apiSectorsLive(force)
      setData(result)
      setCountdown(result.next_refresh_in)
    } catch (e: any) {
      setError(e.message || 'Failed to load sector data')
    } finally {
      setLoading(false)
    }
  }, [])

  // If no external data, fetch it ourselves
  useEffect(() => {
    if (!externalData) load()
  }, [externalData, load])

  // Countdown timer
  useEffect(() => {
    countdownRef.current = setInterval(() => {
      setCountdown(c => {
        if (c <= 1) {
          load(true)
          return 900
        }
        return c - 1
      })
    }, 1000)
    return () => { if (countdownRef.current) clearInterval(countdownRef.current) }
  }, [load])

  const mins = Math.floor(countdown / 60)
  const secs = countdown % 60

  const sortedSectors = data ? sortSectors(data.sectors, sortKey) : []

  const SORT_OPTIONS: { key: SortKey; label: string }[] = [
    { key: 'BULLISH_FIRST', label: '🟢 Sentiment' },
    { key: '1D',            label: '1D %' },
    { key: '1W',            label: '1W %' },
    { key: '1M',            label: '1M %' },
    { key: 'YTD',           label: 'YTD %' },
    { key: 'RS',            label: 'RS vs Nifty' },
  ]

  return (
    <div style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.4; }
          50%       { opacity: 0.8; }
        }
      `}</style>

      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 900, color: '#f1f5f9', margin: 0, letterSpacing: '-0.5px' }}>
            🏭 Sector Intelligence Hub
          </h1>
          <p style={{ fontSize: '13px', color: '#475569', marginTop: '4px' }}>
            Live NSE sector data — 15-min cache ·{' '}
            {data && !loading && (
              <span style={{ color: '#64748b' }}>
                Refreshes in {mins}:{secs.toString().padStart(2, '0')}
              </span>
            )}
            {loading && <span style={{ color: '#00C48C' }}>⟳ Fetching…</span>}
            {data?.stale && <span style={{ color: '#f59e0b' }}> ⚠ stale</span>}
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          {data && (
            <span style={{ fontSize: '11px', color: '#334155', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', padding: '5px 10px', borderRadius: '8px' }}>
              {data.sectors.filter(s => s.sentiment === 'BULLISH').length}🟢
              &nbsp;{data.sectors.filter(s => s.sentiment === 'BEARISH').length}🔴
              &nbsp;{data.sectors.filter(s => s.sentiment === 'MIXED').length}🟡
            </span>
          )}
          <button
            onClick={() => load(true)}
            disabled={loading}
            style={{
              background: 'rgba(0,196,140,0.08)', border: '1px solid rgba(0,196,140,0.2)',
              color: '#00C48C', fontSize: '11px', fontWeight: 700, padding: '6px 14px',
              borderRadius: '8px', cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.6 : 1, transition: 'all 0.15s',
            }}
          >
            ↺ Refresh
          </button>
        </div>
      </div>

      {/* ── Error state ── */}
      {error && !loading && (
        <div style={{
          padding: '14px 18px', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
          borderRadius: '12px', color: '#fca5a5', fontSize: '13px',
          display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px',
        }}>
          ⚠️ {error}
          <button
            onClick={() => load()}
            style={{ marginLeft: 'auto', background: 'rgba(239,68,68,0.15)', border: 'none', color: '#fca5a5', padding: '5px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '11px', fontWeight: 700 }}
          >
            Retry
          </button>
        </div>
      )}

      {/* ── Skeleton ── */}
      {loading && !data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '16px' }}>
          {[...Array(6)].map((_, i) => <SkeletonCard key={i} />)}
        </div>
      )}

      {/* ── Data ── */}
      {!error && data && (
        <>
          {/* Heatmap strip */}
          <HeatmapStrip sectors={data.sectors} sortKey={sortKey} />

          {/* Sort bar */}
          <div style={{ display: 'flex', gap: '6px', marginBottom: '20px', flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: '11px', color: '#334155', fontWeight: 600, marginRight: '4px' }}>Sort:</span>
            {SORT_OPTIONS.map(o => (
              <button
                key={o.key}
                onClick={() => setSortKey(o.key)}
                style={{
                  fontSize: '11px', fontWeight: 700, padding: '5px 12px', borderRadius: '8px',
                  cursor: 'pointer', transition: 'all 0.15s',
                  background: sortKey === o.key ? 'rgba(0,196,140,0.12)' : 'rgba(255,255,255,0.03)',
                  border: `1px solid ${sortKey === o.key ? 'rgba(0,196,140,0.3)' : 'rgba(255,255,255,0.07)'}`,
                  color: sortKey === o.key ? '#00C48C' : '#64748b',
                }}
              >
                {o.label}
              </button>
            ))}
          </div>

          {/* Cards grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '16px' }}>
            {sortedSectors.map(s => <SectorCard key={s.name} sector={s} />)}
          </div>

          {/* Footer */}
          <div style={{
            marginTop: '24px', paddingTop: '14px', borderTop: '1px solid rgba(255,255,255,0.05)',
            display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px',
          }}>
            <span style={{ fontSize: '10px', color: '#1e293b' }}>
              Data via Yahoo Finance · NSE Sector Indices · {data.sectors.length} sectors · {data.news_total} news articles
            </span>
            <span style={{ fontSize: '10px', color: '#1e293b' }}>
              Last fetched: {new Date(data.fetched_at * 1000).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })} IST
            </span>
          </div>

          {/* SEBI disclaimer */}
          <div style={{
            marginTop: '12px', padding: '10px 14px',
            background: 'rgba(245,158,11,0.04)', border: '1px solid rgba(245,158,11,0.12)',
            borderRadius: '8px', fontSize: '10px', color: '#475569', lineHeight: 1.5,
          }}>
            ⚠️ <strong style={{ color: '#f59e0b' }}>Disclaimer:</strong> Sector data is for informational purposes only and does not constitute investment advice. Past performance is not indicative of future results. Consult a SEBI-registered investment advisor before making any trading decisions.
          </div>
        </>
      )}
    </div>
  )
}
