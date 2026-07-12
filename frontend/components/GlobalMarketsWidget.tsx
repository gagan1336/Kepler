'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import {
  apiGlobalMarkets,
  type GlobalMarketsResult,
  type GlobalMarketTicker,
  type GlobalGroupMeta,
} from '@/lib/api'

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmt(price: number, unit: string): string {
  if (unit === '%' || unit === '') return price.toFixed(2)
  if (price >= 1000) return price.toLocaleString('en-IN', { maximumFractionDigits: 0 })
  return price.toFixed(2)
}

function sign(v: number): string {
  return v >= 0 ? '+' : ''
}

const IMPACT_CONFIG = {
  BULLISH: { label: '🟢 Bullish for Nifty',  bg: 'rgba(16,185,129,0.12)', border: 'rgba(16,185,129,0.3)', color: '#10b981' },
  BEARISH: { label: '🔴 Bearish for Nifty',  bg: 'rgba(239,68,68,0.12)',  border: 'rgba(239,68,68,0.3)',  color: '#ef4444' },
  MIXED:   { label: '🟡 Mixed Signals',      bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.3)', color: '#f59e0b' },
}

const GROUP_ORDER = ['gift_nifty', 'us_markets', 'asia', 'europe', 'commodities', 'forex'] as const

// ── Single ticker card ────────────────────────────────────────────────────────
function TickerCard({ t, color }: { t: GlobalMarketTicker; color: string }) {
  const up       = t.direction === 'UP'
  const down     = t.direction === 'DOWN'
  const chgColor = up ? '#10b981' : down ? '#ef4444' : '#64748b'

  return (
    <div
      style={{
        background: t.key
          ? 'rgba(255,255,255,0.04)'
          : 'rgba(255,255,255,0.015)',
        border: `1px solid ${t.key ? 'rgba(255,255,255,0.1)' : 'rgba(255,255,255,0.05)'}`,
        borderRadius: '10px',
        padding: '10px 12px',
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
        minWidth: '120px',
        transition: 'all 0.15s',
        cursor: 'default',
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLDivElement).style.borderColor = color + '55'
        ;(e.currentTarget as HTMLDivElement).style.background = 'rgba(255,255,255,0.06)'
        ;(e.currentTarget as HTMLDivElement).style.transform = 'translateY(-1px)'
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.borderColor = t.key ? 'rgba(255,255,255,0.1)' : 'rgba(255,255,255,0.05)'
        ;(e.currentTarget as HTMLDivElement).style.background = t.key ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.015)'
        ;(e.currentTarget as HTMLDivElement).style.transform = 'none'
      }}
    >
      {/* Name */}
      <span style={{ fontSize: '10px', color: '#475569', fontWeight: 600, letterSpacing: '0.3px', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>
        {t.name}
      </span>

      {/* Price */}
      <span style={{ fontSize: '13px', fontWeight: 700, color: '#f1f5f9', letterSpacing: '-0.3px' }}>
        {t.unit === '₹' ? '₹' : ''}{fmt(t.current_price, t.unit)}{t.unit && t.unit !== '₹' ? ` ${t.unit}` : ''}
      </span>

      {/* Change */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        <span style={{ fontSize: '11px', fontWeight: 700, color: chgColor }}>
          {up ? '▲' : down ? '▼' : '—'} {sign(t.change_pct)}{t.change_pct.toFixed(2)}%
        </span>
      </div>
    </div>
  )
}

// ── Group section ──────────────────────────────────────────────────────────────
function MarketGroup({
  groupKey,
  tickers,
  meta,
}: {
  groupKey: string
  tickers: GlobalMarketTicker[]
  meta: GlobalGroupMeta
}) {
  if (!tickers.length) return null

  const upCount   = tickers.filter(t => t.direction === 'UP').length
  const downCount = tickers.filter(t => t.direction === 'DOWN').length
  const sentiment = upCount > downCount ? meta.color : downCount > upCount ? '#ef4444' : '#475569'

  return (
    <div style={{ marginBottom: '0' }}>
      {/* Group header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
        <span style={{ fontSize: '13px' }}>{meta.icon}</span>
        <span style={{ fontSize: '11px', fontWeight: 700, color: meta.color, letterSpacing: '0.5px', textTransform: 'uppercase' }}>
          {meta.label}
        </span>
        <span style={{
          fontSize: '10px',
          background: sentiment + '18',
          color: sentiment,
          border: `1px solid ${sentiment}30`,
          padding: '1px 6px',
          borderRadius: '99px',
          fontWeight: 700,
        }}>
          {upCount > 0 && `${upCount}▲`}{upCount > 0 && downCount > 0 && ' '}{downCount > 0 && `${downCount}▼`}
        </span>
      </div>

      {/* Ticker cards */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        {tickers.map(t => (
          <TickerCard key={t.symbol} t={t} color={meta.color} />
        ))}
      </div>
    </div>
  )
}

// ── Skeleton loader ────────────────────────────────────────────────────────────
function SkeletonCard() {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)',
      border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: '10px',
      padding: '10px 12px',
      minWidth: '120px',
      height: '65px',
      animation: 'pulse 1.5s ease-in-out infinite',
    }} />
  )
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function GlobalMarketsWidget() {
  const [data, setData]       = useState<GlobalMarketsResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)
  const [expanded, setExpanded] = useState(true)
  const [countdown, setCountdown] = useState(300)
  const countdownRef = useRef<NodeJS.Timeout | null>(null)

  const load = useCallback(async (force = false) => {
    if (!force) setLoading(true)
    setError(null)
    try {
      const result = await apiGlobalMarkets(force)
      setData(result)
      setCountdown(result.next_refresh_in)
    } catch (e: any) {
      setError(e.message || 'Failed to load global markets')
    } finally {
      setLoading(false)
    }
  }, [])

  // Initial load
  useEffect(() => { load() }, [load])

  // Countdown timer
  useEffect(() => {
    countdownRef.current = setInterval(() => {
      setCountdown(c => {
        if (c <= 1) {
          // Auto-refresh when timer hits 0
          load(true)
          return 300
        }
        return c - 1
      })
    }, 1000)
    return () => { if (countdownRef.current) clearInterval(countdownRef.current) }
  }, [load])

  const impact = data?.impact_score
  const impactCfg = impact ? IMPACT_CONFIG[impact] : IMPACT_CONFIG.MIXED
  const mins = Math.floor(countdown / 60)
  const secs = countdown % 60

  return (
    <div style={{
      background: 'rgba(255,255,255,0.015)',
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: '14px',
      padding: '14px 18px',
      marginBottom: '20px',
    }}>
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.4; }
          50%       { opacity: 0.8; }
        }
      `}</style>

      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: expanded ? '16px' : '0', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '13px', fontWeight: 800, color: '#f1f5f9', letterSpacing: '-0.2px' }}>
          🌐 Global Markets Pulse
        </span>

        {/* Impact badge */}
        {data && !loading && (
          <span style={{
            background: impactCfg.bg,
            border: `1px solid ${impactCfg.border}`,
            color: impactCfg.color,
            fontSize: '11px',
            fontWeight: 700,
            padding: '3px 10px',
            borderRadius: '99px',
          }}>
            {impactCfg.label}
          </span>
        )}

        {/* Countdown + stale indicator */}
        <span style={{ marginLeft: 'auto', fontSize: '11px', color: '#334155', display: 'flex', alignItems: 'center', gap: '8px' }}>
          {data?.stale && <span style={{ color: '#f59e0b' }}>⚠ stale</span>}
          {!loading && <span>Refreshes in {mins}:{secs.toString().padStart(2, '0')}</span>}
          {loading && <span style={{ color: '#00C48C' }}>⟳ Fetching…</span>}
        </span>

        {/* Collapse toggle */}
        <button
          onClick={() => setExpanded(e => !e)}
          style={{
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.08)',
            color: '#475569',
            fontSize: '11px',
            padding: '3px 10px',
            borderRadius: '6px',
            cursor: 'pointer',
            transition: 'all 0.15s',
          }}
        >
          {expanded ? '▲ Hide' : '▼ Show'}
        </button>
      </div>

      {/* Body */}
      {expanded && (
        <>
          {/* Error */}
          {error && !loading && (
            <div style={{ padding: '12px', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: '8px', color: '#fca5a5', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '10px' }}>
              ⚠️ {error}
              <button onClick={() => load()} style={{ marginLeft: 'auto', background: 'rgba(239,68,68,0.15)', border: 'none', color: '#fca5a5', padding: '4px 10px', borderRadius: '6px', cursor: 'pointer', fontSize: '11px', fontWeight: 600 }}>Retry</button>
            </div>
          )}

          {/* Skeleton while loading */}
          {loading && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(290px, 1fr))', gap: '16px' }}>
              {[...Array(6)].map((_, i) => (
                <div key={i} style={{ display: 'flex', gap: '8px' }}>
                  {[...Array(3)].map((_, j) => <SkeletonCard key={j} />)}
                </div>
              ))}
            </div>
          )}

          {/* Live data grid */}
          {!loading && !error && data && (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
              gap: '16px 24px',
            }}>
              {GROUP_ORDER.map(gKey => {
                const tickers = data.groups[gKey] ?? []
                const meta    = data.group_meta?.[gKey] ?? { label: gKey, icon: '📊', color: '#64748b' }
                return (
                  <MarketGroup
                    key={gKey}
                    groupKey={gKey}
                    tickers={tickers}
                    meta={meta}
                  />
                )
              })}
            </div>
          )}

          {/* Footer */}
          {!loading && data && (
            <div style={{ marginTop: '12px', paddingTop: '10px', borderTop: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '6px' }}>
              <span style={{ fontSize: '10px', color: '#1e293b' }}>
                Powered by Yahoo Finance · Nifty 50 / Bank Nifty (NSE) · US Futures (CME) · Commodities (COMEX/NYMEX)
              </span>
              <span style={{ fontSize: '10px', color: '#1e293b' }}>
                Last fetched: {new Date(data.fetched_at * 1000).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })} IST
              </span>
            </div>
          )}
        </>
      )}
    </div>
  )
}
