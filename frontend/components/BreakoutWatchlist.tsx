'use client'

import { useState, useMemo } from 'react'
import { Breakout } from '@/lib/api'
import { MiniChart } from './TradingViewWidget'

// ── APEX tier config ──────────────────────────────────────────────────────────
const APEX_CONFIG = {
  HIGH:      { label: 'High Conviction', color: '#10b981', bg: 'rgba(16,185,129,0.08)',  border: 'rgba(16,185,129,0.22)' },
  MODERATE:  { label: 'Moderate',        color: '#f59e0b', bg: 'rgba(245,158,11,0.08)',  border: 'rgba(245,158,11,0.22)' },
  WATCHLIST: { label: 'Watchlist',       color: '#64748b', bg: 'rgba(100,116,139,0.06)', border: 'rgba(100,116,139,0.16)' },
}

const PATTERN_COLORS: Record<string, string> = {
  'VCP':          '#a78bfa',
  '52W Breakout': '#10b981',
  'EMA Stack':    '#3b82f6',
  'Volume Surge': '#f59e0b',
  'Momentum':     '#ec4899',
  'Golden Cross': '#eab308',
}

const PILLAR_CFG = [
  { k: 'A' as const, label: 'Accumulation',  color: '#3b82f6', max: 20 },
  { k: 'P' as const, label: 'Price Action',  color: '#10b981', max: 20 },
  { k: 'E' as const, label: 'EMA Structure', color: '#a78bfa', max: 20 },
  { k: 'X' as const, label: 'Momentum',      color: '#ec4899', max: 20 },
  { k: 'S' as const, label: 'Sector RS',     color: '#f59e0b', max: 20 },
]

function fmtPrice(n: number | undefined): string {
  if (n == null) return '—'
  return '₹' + n.toLocaleString('en-IN', { maximumFractionDigits: 0 })
}

// ── SVG icons ─────────────────────────────────────────────────────────────────
const IconLock = () => (
  <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
  </svg>
)
const IconScan = () => (
  <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/>
    <rect x="2" y="2" width="5" height="5" rx="1"/><rect x="17" y="2" width="5" height="5" rx="1"/>
    <rect x="2" y="17" width="5" height="5" rx="1"/><rect x="17" y="17" width="5" height="5" rx="1"/>
  </svg>
)
const IconChevron = ({ up }: { up?: boolean }) => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points={up ? "18 15 12 9 6 15" : "6 9 12 15 18 9"}/>
  </svg>
)
const IconArrow = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
  </svg>
)
const IconAlertTriangle = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
    <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
  </svg>
)
const IconStop = () => (
  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"/><rect x="9" y="9" width="6" height="6"/>
  </svg>
)
const IconTarget = () => (
  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>
  </svg>
)

// ── APEX Score Ring ────────────────────────────────────────────────────────────
function ApexRing({ score, tier }: { score: number; tier: keyof typeof APEX_CONFIG }) {
  const cfg  = APEX_CONFIG[tier]
  const r    = 30
  const circ = 2 * Math.PI * r
  const fill = circ * Math.min(score / 100, 1)

  return (
    <div style={{ position: 'relative', width: 76, height: 76, flexShrink: 0 }}>
      {/* Glow effect behind ring */}
      <div style={{
        position: 'absolute', inset: 4, borderRadius: '50%',
        boxShadow: `0 0 16px ${cfg.color}22`,
        background: cfg.color + '05',
      }} />
      <svg width="76" height="76" style={{ transform: 'rotate(-90deg)', position: 'relative', zIndex: 1 }}>
        <circle cx="38" cy="38" r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="5" />
        <circle
          cx="38" cy="38" r={r} fill="none" stroke={cfg.color} strokeWidth="5"
          strokeDasharray={`${fill} ${circ - fill}`}
          strokeLinecap="round"
          style={{ transition: 'stroke-dasharray 0.8s cubic-bezier(0.34,1.56,0.64,1)', filter: `drop-shadow(0 0 4px ${cfg.color}60)` }}
        />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', zIndex: 2 }}>
        <span style={{ fontSize: '18px', fontWeight: 900, color: cfg.color, lineHeight: 1, fontFamily: 'var(--font-mono)' }}>{score}</span>
        <span style={{ fontSize: '7px', color: cfg.color, fontWeight: 800, letterSpacing: '1px', marginTop: 1, fontFamily: 'var(--font-mono)' }}>APEX</span>
      </div>
    </div>
  )
}

// ── Mini metric box ───────────────────────────────────────────────────────────
function MetricBox({ label, value, color = 'var(--text-secondary)' }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ background: 'rgba(255,255,255,0.025)', borderRadius: 8, padding: '7px 10px', textAlign: 'center' }}>
      <div style={{ fontSize: '9px', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.4px', marginBottom: 3, fontFamily: 'var(--font-primary)' }}>{label}</div>
      <div style={{ fontSize: '12px', fontWeight: 800, color, fontFamily: 'var(--font-mono)' }}>{value}</div>
    </div>
  )
}

// ── Pattern tag ───────────────────────────────────────────────────────────────
function PatternTag({ tag }: { tag: string }) {
  const color = PATTERN_COLORS[tag] || '#64748b'
  return (
    <span style={{
      fontSize: '10px', fontWeight: 700,
      background: color + '14', color,
      border: `1px solid ${color}28`,
      padding: '2px 8px', borderRadius: '6px',
      whiteSpace: 'nowrap', letterSpacing: '0.2px',
      fontFamily: 'var(--font-primary)',
    }}>{tag}</span>
  )
}

// ── EMA stack badges ──────────────────────────────────────────────────────────
function EmaStack({ price, e20, e50, e200 }: { price: number; e20: number; e50: number; e200?: number }) {
  const checks = [
    { label: 'P>20',    on: price > e20 },
    { label: '20>50',   on: e20 > e50   },
    { label: '50>200',  on: e200 ? e50 > e200 : null },
  ]
  return (
    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
      {checks.map(({ label, on }) => (
        <span key={label} style={{
          fontSize: '10px', fontWeight: 700, padding: '2px 7px', borderRadius: 5,
          background: on === null ? 'rgba(255,255,255,0.03)' : on ? 'rgba(16,185,129,0.12)' : 'rgba(229,72,77,0.08)',
          color: on === null ? 'var(--text-muted)' : on ? '#10b981' : '#ef4444',
          border: `1px solid ${on === null ? 'rgba(255,255,255,0.04)' : on ? 'rgba(16,185,129,0.2)' : 'rgba(229,72,77,0.18)'}`,
          fontFamily: 'var(--font-mono)',
        }}>{label} {on === null ? '—' : on ? '✓' : '✗'}</span>
      ))}
    </div>
  )
}

// ── Volume bar ────────────────────────────────────────────────────────────────
function VolumeBar({ ratio }: { ratio: number }) {
  const pct   = Math.min(ratio / 4, 1) * 100
  const color = ratio >= 2.5 ? '#10b981' : ratio >= 1.5 ? '#f59e0b' : '#475569'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ flex: 1, height: 4, background: 'rgba(255,255,255,0.05)', borderRadius: 99, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 99, transition: 'width 0.5s ease', boxShadow: `0 0 6px ${color}50` }} />
      </div>
      <span style={{ fontSize: '12px', fontWeight: 800, color, minWidth: 36, fontFamily: 'var(--font-mono)' }}>{ratio?.toFixed(1)}×</span>
    </div>
  )
}

// ── APEX pillar breakdown ─────────────────────────────────────────────────────
function ApexBreakdown({ bd }: { bd: { A: number; P: number; E: number; X: number; S: number } }) {
  const total = PILLAR_CFG.reduce((s, p) => s + (bd[p.k] ?? 0), 0)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {PILLAR_CFG.map(({ k, label, color, max }) => {
        const v = bd[k] ?? 0
        return (
          <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: '10px', fontWeight: 900, color, width: 14, fontFamily: 'var(--font-mono)' }}>{k}</span>
            <span style={{ fontSize: '10px', color: 'var(--text-tertiary)', width: 100, flexShrink: 0, fontFamily: 'var(--font-primary)' }}>{label}</span>
            <div style={{ flex: 1, height: 4, background: 'rgba(255,255,255,0.05)', borderRadius: 99, overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${(v / max) * 100}%`, background: color, borderRadius: 99, transition: 'width 0.5s ease', boxShadow: `0 0 5px ${color}40` }} />
            </div>
            <span style={{ fontSize: '10px', color, fontWeight: 800, width: 28, textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{v}/{max}</span>
          </div>
        )
      })}
      <div style={{ marginTop: 2, paddingTop: 8, borderTop: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-primary)' }}>Total APEX Score</span>
        <span style={{ fontSize: '14px', fontWeight: 900, color: total >= 75 ? '#10b981' : total >= 55 ? '#f59e0b' : '#64748b', fontFamily: 'var(--font-mono)' }}>{total}/100</span>
      </div>
    </div>
  )
}

// ── Single breakout card ───────────────────────────────────────────────────────
function BreakoutCard({ b, expanded, onToggle }: {
  b: Breakout
  expanded: boolean
  onToggle: () => void
}) {
  const t    = b.technical_data
  const apex = t.apex_score ?? 0
  const tier = (t.apex_conviction ?? (apex >= 75 ? 'HIGH' : apex >= 55 ? 'MODERATE' : 'WATCHLIST')) as keyof typeof APEX_CONFIG
  const cfg  = APEX_CONFIG[tier]
  const tags = t.pattern_tags ?? []

  const rsiColor  = t.rsi >= 65 ? '#10b981' : t.rsi >= 50 ? '#f59e0b' : '#ef4444'
  const distColor = t.pct_from_52w_high != null ? (t.pct_from_52w_high <= 2 ? '#10b981' : t.pct_from_52w_high <= 5 ? '#f59e0b' : 'var(--text-tertiary)') : 'var(--text-muted)'

  return (
    <div className={`bw-card ${expanded ? 'bw-card-expanded' : ''}`}
      style={{ '--tier-color': cfg.color, '--tier-border': cfg.border } as any}>

      {/* Colored left border line */}
      <div className="bw-tier-line" style={{ background: cfg.color }} />

      {/* Top accent glow strip */}
      {expanded && <div className="bw-glow-strip" style={{ background: `linear-gradient(90deg, ${cfg.color}30, transparent)` }} />}

      {/* ── Collapsed header (always visible) ── */}
      <div className="bw-card-header" onClick={onToggle}>
        {/* APEX ring */}
        <ApexRing score={apex} tier={tier} />

        {/* Stock info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Row 1: symbol + badges */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap', marginBottom: 4 }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 900, fontSize: '15px', color: 'var(--gain, #3DDC84)', letterSpacing: '-0.3px' }}>{b.symbol}</span>
            <span className="bw-tier-badge" style={{ background: cfg.bg, color: cfg.color, borderColor: cfg.border }}>{cfg.label}</span>
            {t.sector && <span className="bw-sector-badge">{t.sector}</span>}
          </div>
          {/* Row 2: company name */}
          <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginBottom: 10, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: 'var(--font-primary)' }}>
            {b.company_name}
          </div>

          {/* Pattern tags */}
          {tags.length > 0 && (
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 10 }}>
              {tags.map(tag => <PatternTag key={tag} tag={tag} />)}
            </div>
          )}

          {/* Mini metric row */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6, marginBottom: 10 }}>
            <MetricBox label="Price"    value={fmtPrice(t.current_price)} color="var(--text-primary)" />
            <MetricBox label="RSI(14)"  value={t.rsi?.toFixed(1) ?? '—'} color={rsiColor} />
            <MetricBox label="Vol Ratio" value={`${t.volume_ratio?.toFixed(1)}×`} color={t.volume_ratio >= 2 ? '#10b981' : '#f59e0b'} />
            <MetricBox label="Stop Loss" value={fmtPrice(t.stop_loss)} color="var(--loss, #E5484D)" />
          </div>

          {/* EMA alignment */}
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: '9px', color: 'var(--text-muted)', fontWeight: 700, letterSpacing: '0.5px', textTransform: 'uppercase', marginBottom: 5, fontFamily: 'var(--font-primary)' }}>EMA Alignment</div>
            <EmaStack price={t.current_price} e20={t.ema20} e50={t.ema50} e200={t.ema200} />
          </div>

          {/* Volume bar */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 5 }}>
              <span style={{ fontSize: '9px', color: 'var(--text-muted)', fontWeight: 700, letterSpacing: '0.5px', textTransform: 'uppercase', fontFamily: 'var(--font-primary)' }}>Volume vs 20D Avg</span>
              {t.pct_from_52w_high != null && (
                <span style={{ fontSize: '10px', color: distColor, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                  {t.pct_from_52w_high <= 0 ? 'ATH' : `-${t.pct_from_52w_high.toFixed(1)}% from 52W`}
                </span>
              )}
            </div>
            <VolumeBar ratio={t.volume_ratio} />
          </div>
        </div>

        {/* Expand toggle */}
        <button className="bw-chevron-btn" style={{ borderColor: expanded ? cfg.border : 'var(--border)', color: expanded ? cfg.color : 'var(--text-tertiary)' }}>
          <IconChevron up={expanded} />
        </button>
      </div>

      {/* ── Expanded drill-down ── */}
      {expanded && (
        <div className="bw-expanded-panel">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>

            {/* LEFT: Chart + trade levels */}
            <div>
              <div className="bw-section-label">3-Month Chart — NSE:{b.symbol}</div>
              <div style={{ borderRadius: 10, overflow: 'hidden', border: '1px solid var(--border-subtle)' }}>
                <MiniChart symbol={b.symbol} />
              </div>
              {/* Trade levels */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 12 }}>
                <div style={{ background: 'rgba(229,72,77,0.07)', border: '1px solid rgba(229,72,77,0.18)', borderRadius: 9, padding: '10px 12px' }}>
                  <div style={{ fontSize: '9px', color: '#ef4444', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.4px', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 4, fontFamily: 'var(--font-primary)' }}>
                    <IconStop /> Stop Loss
                  </div>
                  <div style={{ fontSize: '15px', fontWeight: 900, color: '#ef4444', fontFamily: 'var(--font-mono)' }}>{fmtPrice(t.stop_loss)}</div>
                </div>
                <div style={{ background: 'rgba(245,158,11,0.07)', border: '1px solid rgba(245,158,11,0.18)', borderRadius: 9, padding: '10px 12px' }}>
                  <div style={{ fontSize: '9px', color: '#f59e0b', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.4px', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 4, fontFamily: 'var(--font-primary)' }}>
                    <IconTarget /> Resistance
                  </div>
                  <div style={{ fontSize: '15px', fontWeight: 900, color: '#f59e0b', fontFamily: 'var(--font-mono)' }}>{fmtPrice(t.high_52w)}</div>
                </div>
              </div>
            </div>

            {/* RIGHT: Analysis + APEX breakdown */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

              {/* Setup description */}
              <div>
                <div className="bw-section-label">{t.ai_pattern_name || tags.join(', ') || 'Technical Setup'}</div>
                <p style={{
                  fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.7,
                  borderLeft: `2px solid ${cfg.color}`, paddingLeft: '12px', margin: 0,
                  fontFamily: 'var(--font-primary)',
                }}>
                  {b.setup_description}
                </p>
              </div>

              {/* APEX breakdown */}
              {t.apex_breakdown && (
                <div>
                  <div className="bw-section-label">APEX Score Breakdown</div>
                  <ApexBreakdown bd={t.apex_breakdown} />
                </div>
              )}

              {/* Key levels */}
              <div>
                <div className="bw-section-label">Key Levels</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                  {[
                    { label: 'Current Price', val: fmtPrice(t.current_price), hi: true },
                    { label: '52W High',      val: fmtPrice(t.high_52w) },
                    { label: 'EMA 20',        val: fmtPrice(t.ema20) },
                    { label: 'EMA 50',        val: fmtPrice(t.ema50) },
                    { label: 'EMA 200',       val: fmtPrice(t.ema200) },
                    { label: 'ATR (14)',       val: fmtPrice(t.atr) },
                  ].map(({ label, val, hi }) => (
                    <div key={label} style={{ background: 'rgba(255,255,255,0.025)', borderRadius: 8, padding: '7px 10px' }}>
                      <div style={{ fontSize: '9px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.3px', marginBottom: 3, fontFamily: 'var(--font-primary)' }}>{label}</div>
                      <div style={{ fontSize: '12px', fontWeight: 700, color: hi ? 'var(--gain)' : 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{val}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Sector heatmap row ────────────────────────────────────────────────────────
function SectorHeatmap({ breakouts }: { breakouts: Breakout[] }) {
  const map: Record<string, { count: number; totalApex: number }> = {}
  for (const b of breakouts) {
    const s = b.technical_data?.sector || 'Other'
    if (!map[s]) map[s] = { count: 0, totalApex: 0 }
    map[s].count++
    map[s].totalApex += b.technical_data?.apex_score || 0
  }
  const sorted = Object.entries(map)
    .map(([s, d]) => ({ s, count: d.count, avg: Math.round(d.totalApex / d.count) }))
    .sort((a, b) => b.count - a.count)
  if (!sorted.length) return null

  return (
    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 18 }}>
      {sorted.map(({ s, count, avg }) => {
        const color = avg >= 75 ? '#10b981' : avg >= 55 ? '#f59e0b' : '#64748b'
        return (
          <div key={s} style={{
            background: color + '0C', border: `1px solid ${color}22`,
            borderRadius: 8, padding: '4px 10px',
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color, fontFamily: 'var(--font-primary)' }}>{s}</span>
            <span style={{ fontSize: '10px', background: color + '22', color, padding: '0 5px', borderRadius: 4, fontWeight: 800, fontFamily: 'var(--font-mono)' }}>{count}</span>
          </div>
        )
      })}
    </div>
  )
}

// ── Locked / empty states ─────────────────────────────────────────────────────
function LockedState() {
  return (
    <div style={{
      textAlign: 'center', padding: '72px 24px',
      background: 'radial-gradient(ellipse at center, rgba(201,163,78,0.06) 0%, transparent 70%)',
      border: '1px solid var(--accent-border, rgba(201,163,78,0.15))', borderRadius: 18,
    }}>
      <div style={{ color: 'var(--accent)', marginBottom: 18, display: 'flex', justifyContent: 'center', opacity: 0.8 }}>
        <IconLock />
      </div>
      <h3 style={{ color: 'var(--text-primary)', fontWeight: 800, fontSize: '20px', margin: '0 0 10px', fontFamily: 'var(--font-primary)', letterSpacing: '-0.4px' }}>
        Pro Feature
      </h3>
      <p style={{ color: 'var(--text-tertiary)', fontSize: '13px', maxWidth: 340, margin: '0 auto 24px', lineHeight: 1.7, fontFamily: 'var(--font-primary)' }}>
        The <strong style={{ color: 'var(--accent)' }}>APEX Breakout Watchlist</strong> is available on Pro and Elite plans.
        Daily pre-breakout setups with APEX scoring, VCP detection, and AI technical analysis.
      </p>
      <a href="/pricing" style={{
        display: 'inline-flex', alignItems: 'center', gap: 8,
        background: 'linear-gradient(135deg, var(--accent-dark, #A8822E), var(--accent, #C9A34E))',
        color: '#000', fontWeight: 800, fontSize: '13px',
        padding: '10px 24px', borderRadius: 10, textDecoration: 'none',
        boxShadow: '0 4px 20px rgba(201,163,78,0.3)',
      }}>Upgrade to Pro <IconArrow /></a>
    </div>
  )
}

function EmptyState() {
  return (
    <div style={{
      textAlign: 'center', padding: '64px 24px',
      background: 'var(--bg-surface, #0F0F11)',
      border: '1px solid var(--border)', borderRadius: 16,
    }}>
      <div style={{ color: 'var(--text-muted)', marginBottom: 16, display: 'flex', justifyContent: 'center' }}>
        <IconScan />
      </div>
      <p style={{ color: 'var(--text-secondary)', fontWeight: 700, fontSize: '15px', marginBottom: 6, fontFamily: 'var(--font-primary)' }}>No breakout setups today</p>
      <p style={{ color: 'var(--text-muted)', fontSize: '12px', fontFamily: 'var(--font-primary)', lineHeight: 1.6 }}>Scan runs daily at 11:15 AM IST on market days.<br/>Check back during trading hours.</p>
    </div>
  )
}

// ── Filter pill button ────────────────────────────────────────────────────────
function FilterBtn({ active, onClick, label, color = 'var(--gain)' }: {
  active: boolean; onClick: () => void; label: string; color?: string
}) {
  return (
    <button onClick={onClick} style={{
      background: active ? color + '14' : 'rgba(255,255,255,0.02)',
      border: `1px solid ${active ? color + '40' : 'var(--border)'}`,
      color: active ? color : 'var(--text-tertiary)',
      fontSize: '11px', fontWeight: active ? 700 : 500,
      padding: '4px 12px', borderRadius: '99px', cursor: 'pointer',
      transition: 'all 0.15s', whiteSpace: 'nowrap',
      fontFamily: 'var(--font-primary)',
    }}>{label}</button>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
interface Props { breakouts: Breakout[]; locked?: boolean }

export default function BreakoutWatchlist({ breakouts, locked = false }: Props) {
  const [expanded, setExpanded]           = useState<string | null>(null)
  const [filterTier, setFilterTier]       = useState<'ALL' | 'HIGH' | 'MODERATE' | 'WATCHLIST'>('ALL')
  const [filterSector, setFilterSector]   = useState('ALL')
  const [filterPattern, setFilterPattern] = useState('ALL')
  const [sortBy, setSortBy]               = useState<'apex' | 'vol' | 'rsi' | 'dist'>('apex')

  if (locked)                                    return <LockedState />
  if (!breakouts || breakouts.length === 0)      return <EmptyState />

  const sectors  = ['ALL', ...Array.from(new Set(breakouts.map(b => b.technical_data?.sector || 'Other')))]
  const patterns = ['ALL', ...Array.from(new Set(breakouts.flatMap(b => b.technical_data?.pattern_tags || [])))]

  const filtered = useMemo(() => {
    let list = [...breakouts]
    if (filterTier !== 'ALL')    list = list.filter(b => (b.technical_data?.apex_conviction || 'WATCHLIST') === filterTier)
    if (filterSector !== 'ALL')  list = list.filter(b => (b.technical_data?.sector || 'Other') === filterSector)
    if (filterPattern !== 'ALL') list = list.filter(b => (b.technical_data?.pattern_tags || []).includes(filterPattern))
    list.sort((a, b) => {
      const ta = a.technical_data, tb = b.technical_data
      if (sortBy === 'apex') return (tb.apex_score || 0)    - (ta.apex_score || 0)
      if (sortBy === 'vol')  return (tb.volume_ratio || 0)  - (ta.volume_ratio || 0)
      if (sortBy === 'rsi')  return (tb.rsi || 0)           - (ta.rsi || 0)
      if (sortBy === 'dist') return (ta.pct_from_52w_high || 0) - (tb.pct_from_52w_high || 0)
      return 0
    })
    return list
  }, [breakouts, filterTier, filterSector, filterPattern, sortBy])

  const hiCount  = breakouts.filter(b => (b.technical_data?.apex_score || 0) >= 75).length
  const modCount = breakouts.filter(b => { const a = b.technical_data?.apex_score || 0; return a >= 55 && a < 75 }).length
  const avgApex  = breakouts.length > 0
    ? Math.round(breakouts.reduce((s, b) => s + (b.technical_data?.apex_score || 0), 0) / breakouts.length)
    : 0

  return (
    <div style={{ fontFamily: "var(--font-primary, 'Inter', system-ui, sans-serif)" }}>
      <style>{`
        /* ── CARD ── */
        .bw-card {
          background: var(--bg-surface, #0F0F11);
          border: 1px solid var(--border, rgba(255,255,255,0.07));
          border-radius: 16px; overflow: hidden;
          transition: border-color 0.2s, box-shadow 0.2s;
          position: relative;
        }
        .bw-card:hover { border-color: rgba(255,255,255,0.14); box-shadow: 0 4px 28px rgba(0,0,0,0.28); }
        .bw-card-expanded {
          border-color: var(--tier-border) !important;
          box-shadow: 0 0 28px color-mix(in srgb, var(--tier-color) 12%, transparent) !important;
        }

        /* ── Tier left border line ── */
        .bw-tier-line {
          position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
          border-radius: 16px 0 0 16px;
        }
        .bw-card-expanded .bw-tier-line { opacity: 1; }
        .bw-card:not(.bw-card-expanded) .bw-tier-line { opacity: 0; }

        /* ── Expanded glow header strip ── */
        .bw-glow-strip {
          position: absolute; top: 0; left: 0; right: 0; height: 80px;
          pointer-events: none; z-index: 0;
        }

        /* ── Header ── */
        .bw-card-header {
          padding: 18px 18px 18px 22px;
          cursor: pointer; display: flex; gap: 16px; align-items: flex-start;
          position: relative; z-index: 1;
        }

        /* ── Badges ── */
        .bw-tier-badge {
          font-size: 10px; font-weight: 700; padding: 2px 9px; border-radius: 7px;
          border: 1px solid transparent; letter-spacing: '0.3px';
          font-family: var(--font-primary);
        }
        .bw-sector-badge {
          font-size: 10px; color: var(--text-muted); background: rgba(255,255,255,0.03);
          padding: 2px 8px; border-radius: 5px; border: 1px solid rgba(255,255,255,0.05);
          font-family: var(--font-primary);
        }

        /* ── Chevron button ── */
        .bw-chevron-btn {
          flex-shrink: 0; align-self: center;
          background: rgba(255,255,255,0.03);
          border: 1px solid var(--border); border-radius: 9px;
          padding: 8px 11px; cursor: pointer;
          transition: all 0.15s; display: flex; align-items: center;
        }
        .bw-chevron-btn:hover { background: rgba(255,255,255,0.07); }

        /* ── Expanded panel ── */
        .bw-expanded-panel {
          border-top: 1px solid var(--border-subtle, rgba(255,255,255,0.05));
          background: rgba(0,0,0,0.18); padding: 22px 22px 22px;
        }
        .bw-section-label {
          font-size: 10px; font-weight: 700;
          color: var(--text-muted); letter-spacing: '1px';
          text-transform: uppercase; margin-bottom: 10px;
          font-family: var(--font-primary);
        }

        /* ── Scan summary boxes ── */
        .bw-summary-card {
          background: var(--bg-surface, #0F0F11);
          border: 1px solid var(--border);
          border-radius: 12px; padding: 12px 16px;
          display: flex; flex-direction: column; gap: 4; min-width: 110px;
        }
        .bw-summary-label {
          font-size: 9px; font-weight: 700; color: var(--text-muted);
          text-transform: uppercase; letter-spacing: 0.6px;
          font-family: var(--font-primary);
        }
        .bw-summary-value {
          font-size: 20px; font-weight: 900;
          font-family: var(--font-mono);
        }
      `}</style>

      {/* ── Header ── */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 6 }}>
          <h2 style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-primary)', margin: 0, letterSpacing: '-0.4px' }}>
            APEX Breakout Watchlist
          </h2>
          <span style={{ fontSize: '12px', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
            {breakouts.length} setups
          </span>
        </div>
        <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '0 0 16px', fontFamily: 'var(--font-primary)' }}>
          Pre-breakout technical setups identified by the APEX scanner — updated daily at 11:15 AM IST
        </p>

        {/* Scan summary row */}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 18 }}>
          <div className="bw-summary-card">
            <div className="bw-summary-label">High Conviction</div>
            <div className="bw-summary-value" style={{ color: '#10b981' }}>{hiCount}</div>
          </div>
          <div className="bw-summary-card">
            <div className="bw-summary-label">Moderate</div>
            <div className="bw-summary-value" style={{ color: '#f59e0b' }}>{modCount}</div>
          </div>
          <div className="bw-summary-card">
            <div className="bw-summary-label">Avg APEX</div>
            <div className="bw-summary-value" style={{ color: avgApex >= 70 ? '#10b981' : avgApex >= 50 ? '#f59e0b' : '#64748b' }}>{avgApex}</div>
          </div>
          <div className="bw-summary-card">
            <div className="bw-summary-label">Total Setups</div>
            <div className="bw-summary-value" style={{ color: 'var(--text-primary)' }}>{breakouts.length}</div>
          </div>
        </div>
      </div>

      {/* ── APEX legend ── */}
      <div style={{
        display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16,
        padding: '10px 14px', background: 'var(--bg-surface)', borderRadius: 10,
        border: '1px solid var(--border-subtle)',
      }}>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 700, alignSelf: 'center', fontFamily: 'var(--font-primary)' }}>APEX™</span>
        {Object.entries(APEX_CONFIG).map(([tier, cfg]) => (
          <span key={tier} style={{
            fontSize: '11px', color: cfg.color, fontWeight: 700,
            background: cfg.bg, border: `1px solid ${cfg.border}`,
            padding: '2px 9px', borderRadius: 7, display: 'inline-block',
            fontFamily: 'var(--font-primary)',
          }}>
            {tier === 'HIGH' ? '≥75' : tier === 'MODERATE' ? '55–74' : '<55'} {cfg.label}
          </span>
        ))}
        <span style={{ fontSize: '10px', color: 'var(--text-muted)', marginLeft: 'auto', alignSelf: 'center', fontFamily: 'var(--font-mono)' }}>
          A·P·E·X·S = Accum · Price · EMA · Momentum · Sector
        </span>
      </div>

      {/* ── Sector heatmap ── */}
      <SectorHeatmap breakouts={filtered} />

      {/* ── Filters ── */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8, alignItems: 'center' }}>
        <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 700, fontFamily: 'var(--font-primary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Conviction</span>
        {(['ALL','HIGH','MODERATE','WATCHLIST'] as const).map(t => (
          <FilterBtn key={t} active={filterTier === t} onClick={() => setFilterTier(t)}
            label={t === 'ALL' ? 'All' : APEX_CONFIG[t].label}
            color={t === 'HIGH' ? '#10b981' : t === 'MODERATE' ? '#f59e0b' : t === 'WATCHLIST' ? '#64748b' : 'var(--gain)'} />
        ))}
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8, alignItems: 'center' }}>
        <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 700, fontFamily: 'var(--font-primary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Sector</span>
        {sectors.slice(0, 8).map(s => <FilterBtn key={s} active={filterSector === s} onClick={() => setFilterSector(s)} label={s} />)}
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 14, alignItems: 'center' }}>
        <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 700, fontFamily: 'var(--font-primary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Pattern</span>
        {patterns.map(p => <FilterBtn key={p} active={filterPattern === p} onClick={() => setFilterPattern(p)} label={p} color={PATTERN_COLORS[p] || 'var(--gain)'} />)}
        <span style={{ marginLeft: 'auto', fontSize: '10px', color: 'var(--text-muted)', fontWeight: 700, fontFamily: 'var(--font-primary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Sort</span>
        {[['apex','APEX'],['vol','Volume'],['rsi','RSI'],['dist','52W Dist']].map(([k,l]) => (
          <FilterBtn key={k} active={sortBy === k as any} onClick={() => setSortBy(k as any)} label={l} />
        ))}
      </div>

      {/* ── Results meta ── */}
      <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: 14, paddingBottom: 12, borderBottom: '1px solid var(--border-subtle)', fontFamily: 'var(--font-mono)' }}>
        Showing {filtered.length} of {breakouts.length} setups
      </div>

      {/* ── Empty filter result ── */}
      {filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)', fontSize: '13px', fontFamily: 'var(--font-primary)' }}>
          No setups match this filter — try clearing some filters
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {filtered.map(b => (
            <BreakoutCard
              key={b.id} b={b}
              expanded={expanded === b.id}
              onToggle={() => setExpanded(prev => prev === b.id ? null : b.id)}
            />
          ))}
        </div>
      )}

      {/* ── Disclaimer ── */}
      <div style={{
        marginTop: 28, padding: '12px 16px',
        background: 'rgba(229,72,77,0.04)',
        border: '1px solid rgba(229,72,77,0.10)',
        borderRadius: 11, fontSize: '11px', color: 'var(--text-tertiary)', lineHeight: 1.7,
        display: 'flex', gap: 10, alignItems: 'flex-start',
        fontFamily: 'var(--font-primary)',
      }}>
        <span style={{ color: '#ef4444', flexShrink: 0, marginTop: 1 }}><IconAlertTriangle /></span>
        <span>
          <strong style={{ color: '#f87171' }}>Educational Analysis Only.</strong>{' '}
          APEX scores and technical setups are generated algorithmically for educational purposes.
          They do not constitute investment advice or a buy/sell recommendation.
          Past breakout pattern performance does not guarantee future results.
          Consult a SEBI-registered advisor before making any financial decision.
        </span>
      </div>
    </div>
  )
}
