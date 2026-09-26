'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  apiSwingStrategies,
  apiBestStrategyStocks,
  apiSwingPresetWithProb,
  type SwingStrategy,
  type BestStrategyStock,
  type StrategyLeaderboardItem,
} from '@/lib/api'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ── Helpers ───────────────────────────────────────────────────────────────────
const fmt  = (v: number | null | undefined, dec = 1) => v == null ? '—' : v.toFixed(dec)
const fmtP = (v: number | null | undefined) => v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`
const fmtPrice = (v: number | null | undefined) =>
  v == null ? '—' : `₹${v.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`

function probColor(p: number) {
  if (p >= 70) return '#10b981'
  if (p >= 55) return '#f59e0b'
  return '#ef4444'
}
function wrColor(wr: number | null) {
  if (wr == null) return '#475569'
  if (wr >= 65) return '#10b981'
  if (wr >= 55) return '#f59e0b'
  return '#ef4444'
}
function sentimentColor(s?: string) {
  if (s === 'BULLISH') return '#10b981'
  if (s === 'BEARISH') return '#ef4444'
  return '#64748b'
}

// ── Win Probability Gauge (SVG circular) ─────────────────────────────────────
function ProbGauge({ prob, size = 72 }: { prob: number; size?: number }) {
  const r    = (size - 10) / 2
  const circ = 2 * Math.PI * r
  const fill = (prob / 100) * circ
  const col  = probColor(prob)
  return (
    <svg width={size} height={size} style={{ display: 'block', filter: `drop-shadow(0 0 8px ${col}55)` }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={7} />
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none"
        stroke={col} strokeWidth={7}
        strokeDasharray={`${fill} ${circ - fill}`}
        strokeDashoffset={circ / 4}
        strokeLinecap="round"
        style={{ transition: 'stroke-dasharray 0.8s ease' }}
      />
      <text x={size / 2} y={size / 2 - 3} textAnchor="middle" dominantBaseline="middle"
        style={{ fontSize: size * 0.21, fontWeight: 900, fill: col, fontFamily: 'monospace' }}>
        {prob.toFixed(0)}%
      </text>
      <text x={size / 2} y={size / 2 + 11} textAnchor="middle" dominantBaseline="middle"
        style={{ fontSize: 8, fontWeight: 700, fill: '#64748b', letterSpacing: '0.5px' }}>
        WIN PROB
      </text>
    </svg>
  )
}

// ── Win-rate badge bar ────────────────────────────────────────────────────────
function WinRateBar({ wr, width = 120 }: { wr: number | null; width?: number }) {
  const col = wrColor(wr)
  const pct = wr ?? 0
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ width, height: 6, background: 'rgba(255,255,255,0.07)', borderRadius: 99, overflow: 'hidden' }}>
        <div style={{
          width: `${pct}%`, height: '100%', background: col, borderRadius: 99,
          transition: 'width 0.7s ease', boxShadow: `0 0 6px ${col}66`
        }} />
      </div>
      <span style={{ fontSize: 12, fontWeight: 800, color: col, fontFamily: 'monospace', minWidth: 36 }}>
        {wr == null ? '—' : `${wr.toFixed(1)}%`}
      </span>
    </div>
  )
}

// ── Strategy Leaderboard Table ────────────────────────────────────────────────
function StrategyLeaderboard({
  strategies,
  onSelect,
  selected,
}: {
  strategies: SwingStrategy[]
  onSelect: (key: string) => void
  selected: string | null
}) {
  return (
    <div style={{
      background: 'rgba(15,23,42,0.7)',
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 16,
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 20px', borderBottom: '1px solid rgba(255,255,255,0.07)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 800, color: '#f1f5f9' }}>
            📊 Strategy Leaderboard
          </h3>
          <p style={{ margin: '2px 0 0', fontSize: 12, color: '#64748b' }}>
            Backtested on 3 years · {strategies.filter(s => s.is_active).length} active strategies
          </p>
        </div>
        <div style={{
          display: 'flex', gap: 6,
          fontSize: 11, color: '#475569', fontWeight: 600,
        }}>
          <span style={{ padding: '3px 8px', borderRadius: 6, background: 'rgba(16,185,129,0.12)', color: '#10b981' }}>
            ✅ Active ≥55% WR
          </span>
          <span style={{ padding: '3px 8px', borderRadius: 6, background: 'rgba(239,68,68,0.10)', color: '#ef4444' }}>
            ❌ Below threshold
          </span>
        </div>
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ background: 'rgba(255,255,255,0.03)' }}>
              {['Strategy', 'Win Rate', 'Avg Return', 'Profit Factor', 'Max DD', 'Sharpe', 'Trades', 'Horizon', 'Status'].map(h => (
                <th key={h} style={{
                  padding: '10px 14px', textAlign: h === 'Strategy' ? 'left' : 'center',
                  color: '#475569', fontWeight: 700, fontSize: 10, letterSpacing: '0.5px',
                  borderBottom: '1px solid rgba(255,255,255,0.06)', whiteSpace: 'nowrap',
                }}>{h.toUpperCase()}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {strategies.map((s, i) => {
              const isSelected = selected === s.key
              return (
                <tr
                  key={s.key}
                  onClick={() => onSelect(s.key)}
                  style={{
                    cursor: 'pointer',
                    background: isSelected
                      ? `${s.color}14`
                      : i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)',
                    borderLeft: isSelected ? `3px solid ${s.color}` : '3px solid transparent',
                    transition: 'background 0.2s',
                  }}
                >
                  <td style={{ padding: '11px 14px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 16 }}>{s.icon}</span>
                      <div>
                        <div style={{ fontWeight: 700, color: '#e2e8f0', fontSize: 12 }}>{s.label}</div>
                        <div style={{ fontSize: 10, color: '#475569', marginTop: 1 }}>{s.description.slice(0, 45)}…</div>
                      </div>
                    </div>
                  </td>
                  <td style={{ padding: '11px 14px', textAlign: 'center' }}>
                    <WinRateBar wr={s.win_rate} width={80} />
                  </td>
                  <td style={{ padding: '11px 14px', textAlign: 'center', fontWeight: 700, color: s.avg_return != null && s.avg_return > 0 ? '#10b981' : '#ef4444', fontFamily: 'monospace' }}>
                    {fmtP(s.avg_return)}
                  </td>
                  <td style={{ padding: '11px 14px', textAlign: 'center', fontFamily: 'monospace', fontWeight: 700, color: s.profit_factor != null && s.profit_factor >= 1.5 ? '#10b981' : '#f59e0b' }}>
                    {fmt(s.profit_factor, 2)}
                  </td>
                  <td style={{ padding: '11px 14px', textAlign: 'center', fontFamily: 'monospace', color: '#ef4444', fontWeight: 600 }}>
                    {s.max_drawdown != null ? `${s.max_drawdown.toFixed(1)}%` : '—'}
                  </td>
                  <td style={{ padding: '11px 14px', textAlign: 'center', fontFamily: 'monospace', color: '#94a3b8', fontWeight: 600 }}>
                    {fmt(s.sharpe, 2)}
                  </td>
                  <td style={{ padding: '11px 14px', textAlign: 'center', color: '#64748b', fontFamily: 'monospace' }}>
                    {s.total_trades.toLocaleString()}
                  </td>
                  <td style={{ padding: '11px 14px', textAlign: 'center', color: '#94a3b8' }}>
                    {s.target_horizon}d
                  </td>
                  <td style={{ padding: '11px 14px', textAlign: 'center' }}>
                    <span style={{
                      padding: '3px 8px', borderRadius: 6, fontSize: 10, fontWeight: 800,
                      background: s.is_active ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.10)',
                      color: s.is_active ? '#10b981' : '#ef4444',
                    }}>
                      {s.is_active ? '✅ ACTIVE' : '❌ INACTIVE'}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Probability Breakdown mini-chart ──────────────────────────────────────────
function ProbBreakdown({ stock }: { stock: BestStrategyStock }) {
  const bd = stock.probability_breakdown
  if (!bd) return null
  const items = [
    { label: 'ML Model', val: bd.ml_component, color: '#6366f1' },
    { label: 'Strategy', val: bd.strategy_component, color: '#10b981' },
    { label: 'News',     val: bd.news_component,     color: '#f59e0b' },
    { label: 'Fundmntl', val: bd.fundamental_component, color: '#3b82f6' },
  ]
  const total = items.reduce((s, i) => s + i.val, 0)
  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, marginBottom: 5, letterSpacing: '0.5px' }}>
        PROBABILITY BREAKDOWN
      </div>
      {items.map(item => (
        <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
          <span style={{ fontSize: 9, color: '#475569', fontWeight: 600, width: 48, flexShrink: 0 }}>{item.label}</span>
          <div style={{ flex: 1, height: 5, background: 'rgba(255,255,255,0.06)', borderRadius: 99, overflow: 'hidden' }}>
            <div style={{
              width: `${Math.min((item.val / Math.max(total, 1)) * 100, 100)}%`,
              height: '100%', background: item.color, borderRadius: 99,
              transition: 'width 0.6s ease',
            }} />
          </div>
          <span style={{ fontSize: 9, fontWeight: 800, color: item.color, fontFamily: 'monospace', width: 26, textAlign: 'right' }}>
            {item.val.toFixed(1)}
          </span>
        </div>
      ))}
      {bd.news_boost_pp !== 0 && (
        <div style={{ fontSize: 9, color: bd.news_boost_pp > 0 ? '#10b981' : '#ef4444', marginTop: 3 }}>
          News adjustment: {bd.news_boost_pp > 0 ? '+' : ''}{bd.news_boost_pp.toFixed(1)}pp
        </div>
      )}
    </div>
  )
}

// ── Stock Pick Card ───────────────────────────────────────────────────────────
function StockCard({ stock }: { stock: BestStrategyStock }) {
  const [expanded, setExpanded] = useState(false)
  const prob = stock.win_probability ?? 0
  const col  = probColor(prob)

  return (
    <div style={{
      background: 'rgba(15,23,42,0.8)',
      border: `1px solid ${col}30`,
      borderRadius: 14,
      padding: 16,
      cursor: 'pointer',
      transition: 'all 0.2s',
      boxShadow: expanded ? `0 0 24px ${col}20` : 'none',
    }} onClick={() => setExpanded(e => !e)}>
      {/* Top row */}
      <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
        {/* Probability gauge */}
        <ProbGauge prob={prob} size={68} />

        {/* Stock info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 16, fontWeight: 900, color: '#f1f5f9', fontFamily: 'monospace' }}>
              {stock.symbol}
            </span>
            {/* Confidence badge */}
            <span style={{
              padding: '2px 7px', borderRadius: 6, fontSize: 10, fontWeight: 800,
              background: `${col}18`, color: col, border: `1px solid ${col}30`,
            }}>
              {stock.confidence_band ?? 'MODERATE'}
            </span>
            {/* News badges */}
            {stock.news_catalyst && (
              <span style={{ padding: '2px 7px', borderRadius: 6, fontSize: 10, fontWeight: 800, background: 'rgba(16,185,129,0.15)', color: '#10b981' }}>
                🔥 Catalyst
              </span>
            )}
            {stock.news_risk && (
              <span style={{ padding: '2px 7px', borderRadius: 6, fontSize: 10, fontWeight: 800, background: 'rgba(239,68,68,0.12)', color: '#ef4444' }}>
                ⚠️ News Risk
              </span>
            )}
            {stock.news_sentiment && (
              <span style={{ padding: '2px 7px', borderRadius: 6, fontSize: 10, fontWeight: 700, color: sentimentColor(stock.news_sentiment) }}>
                {stock.news_sentiment === 'BULLISH' ? '📈' : stock.news_sentiment === 'BEARISH' ? '📉' : '➡️'} {stock.news_sentiment}
              </span>
            )}
          </div>

          <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
            {stock.company_name || stock.symbol} · {stock.sector || '—'}
          </div>

          {/* Price row */}
          <div style={{ display: 'flex', gap: 16, marginTop: 8, flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: 18, fontWeight: 900, color: '#f1f5f9', fontFamily: 'monospace' }}>
                {fmtPrice(stock.current_price)}
              </div>
              {stock.change_pct_today != null && (
                <div style={{ fontSize: 11, color: stock.change_pct_today >= 0 ? '#10b981' : '#ef4444', fontWeight: 700 }}>
                  {fmtP(stock.change_pct_today)} today
                </div>
              )}
            </div>
            <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
              <Stat label="RSI" val={stock.rsi_14 != null ? stock.rsi_14.toFixed(1) : '—'} color={stock.rsi_14 != null && stock.rsi_14 >= 65 ? '#f59e0b' : '#94a3b8'} />
              <Stat label="Vol" val={stock.volume_ratio != null ? `${stock.volume_ratio.toFixed(1)}x` : '—'} color={stock.volume_ratio != null && stock.volume_ratio >= 2 ? '#6366f1' : '#94a3b8'} />
              <Stat label="52H%" val={stock.pct_from_52h != null ? `${stock.pct_from_52h.toFixed(1)}%` : '—'} color="#94a3b8" />
              <Stat label="Hold" val={`${stock.recommended_hold_days ?? '—'}d`} color="#60a5fa" />
            </div>
          </div>

          {/* Best strategy + expected return */}
          <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            {stock.best_strategy && (
              <span style={{
                padding: '3px 9px', borderRadius: 6, fontSize: 10, fontWeight: 700,
                background: 'rgba(99,102,241,0.12)', color: '#818cf8',
                border: '1px solid rgba(99,102,241,0.2)',
              }}>
                🎯 {stock.best_strategy.replace(/_/g, ' ')}
                {stock.best_strategy_wr != null && ` · WR ${stock.best_strategy_wr.toFixed(1)}%`}
              </span>
            )}
            {stock.expected_return && (
              <span style={{ fontSize: 11, color: '#10b981', fontWeight: 700, fontFamily: 'monospace' }}>
                Exp. {fmtP(stock.expected_return.base)} ({fmtP(stock.expected_return.pessimistic)} / {fmtP(stock.expected_return.optimistic)})
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Expanded section */}
      {expanded && (
        <div style={{
          marginTop: 14, paddingTop: 14, borderTop: '1px solid rgba(255,255,255,0.06)',
          display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16,
        }}>
          {/* Probability breakdown */}
          <ProbBreakdown stock={stock} />

          {/* News headline */}
          {stock.news_headline && (
            <div>
              <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, marginBottom: 5, letterSpacing: '0.5px' }}>
                LATEST NEWS
              </div>
              <div style={{
                fontSize: 11, color: '#94a3b8', lineHeight: 1.5,
                padding: '8px 10px', background: 'rgba(255,255,255,0.04)',
                borderRadius: 8, borderLeft: `3px solid ${sentimentColor(stock.news_sentiment)}`,
              }}>
                "{stock.news_headline}"
              </div>
            </div>
          )}

          {/* Triggered strategies */}
          {stock.triggered_best_strategies?.length > 0 && (
            <div>
              <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, marginBottom: 5, letterSpacing: '0.5px' }}>
                TRIGGERED STRATEGIES
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                {stock.triggered_best_strategies.map(s => (
                  <span key={s} style={{
                    padding: '3px 8px', borderRadius: 6, fontSize: 10, fontWeight: 700,
                    background: 'rgba(16,185,129,0.12)', color: '#34d399',
                  }}>
                    ✓ {s.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function Stat({ label, val, color }: { label: string; val: string; color: string }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 12, fontWeight: 800, color, fontFamily: 'monospace' }}>{val}</div>
      <div style={{ fontSize: 9, color: '#475569', fontWeight: 600, letterSpacing: '0.4px' }}>{label}</div>
    </div>
  )
}

// ── Summary Stats Bar ─────────────────────────────────────────────────────────
function SummaryBar({ strategies, stocks }: { strategies: SwingStrategy[]; stocks: BestStrategyStock[] }) {
  const active    = strategies.filter(s => s.is_active).length
  const topWR     = Math.max(...strategies.filter(s => s.win_rate != null).map(s => s.win_rate!), 0)
  const avgProb   = stocks.length ? stocks.reduce((s, st) => s + (st.win_probability ?? 0), 0) / stocks.length : 0
  const highConf  = stocks.filter(s => (s.win_probability ?? 0) >= 70).length

  const items = [
    { icon: '✅', label: 'Active Strategies', val: `${active}/14`, color: '#10b981' },
    { icon: '🏆', label: 'Top Win Rate', val: topWR > 0 ? `${topWR.toFixed(1)}%` : '—', color: '#f59e0b' },
    { icon: '🎯', label: 'Avg Win Probability', val: avgProb > 0 ? `${avgProb.toFixed(1)}%` : '—', color: '#6366f1' },
    { icon: '🔥', label: 'High-Confidence Picks', val: String(highConf), color: '#ec4899' },
  ]

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
      gap: 12, marginBottom: 20,
    }}>
      {items.map(item => (
        <div key={item.label} style={{
          background: 'rgba(15,23,42,0.8)',
          border: `1px solid ${item.color}25`,
          borderRadius: 12, padding: '14px 16px',
          display: 'flex', alignItems: 'center', gap: 12,
        }}>
          <span style={{ fontSize: 22 }}>{item.icon}</span>
          <div>
            <div style={{ fontSize: 20, fontWeight: 900, color: item.color, fontFamily: 'monospace' }}>{item.val}</div>
            <div style={{ fontSize: 10, color: '#475569', fontWeight: 600 }}>{item.label}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Min Win Rate Slider ───────────────────────────────────────────────────────
function FilterBar({ minWR, setMinWR, loading, onRefresh }: {
  minWR: number; setMinWR: (v: number) => void; loading: boolean; onRefresh: () => void
}) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap',
      padding: '12px 16px',
      background: 'rgba(15,23,42,0.6)',
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 12, marginBottom: 16,
    }}>
      <span style={{ fontSize: 12, color: '#94a3b8', fontWeight: 700 }}>Min Strategy Win Rate:</span>
      <div style={{ display: 'flex', gap: 6 }}>
        {[55, 60, 65, 70].map(v => (
          <button key={v} onClick={() => setMinWR(v)} style={{
            padding: '5px 12px', borderRadius: 8, fontSize: 12, fontWeight: 700,
            border: `1px solid ${minWR === v ? wrColor(v) : 'rgba(255,255,255,0.1)'}`,
            background: minWR === v ? `${wrColor(v)}18` : 'transparent',
            color: minWR === v ? wrColor(v) : '#64748b', cursor: 'pointer',
            transition: 'all 0.2s',
          }}>
            ≥{v}%
          </button>
        ))}
      </div>
      <button
        onClick={onRefresh} disabled={loading}
        style={{
          marginLeft: 'auto', padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700,
          background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.3)',
          color: '#818cf8', cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.6 : 1,
        }}
      >
        {loading ? '⏳ Loading…' : '🔄 Refresh'}
      </button>
    </div>
  )
}

// ── Live Pick Card (from Continuous Scanner) ─────────────────────────────────
function LivePickCard({ pick }: { pick: any }) {
  const [expanded, setExpanded] = useState(false)
  const thesis = pick.thesis || {}
  const conf = pick.confidence
  const confColor = conf === 'HIGH' ? '#10b981' : conf === 'MODERATE' ? '#f59e0b' : '#64748b'
  const strategies = (pick.strategies || []) as string[]

  return (
    <div style={{
      background: 'rgba(15,23,42,0.8)',
      border: '1px solid rgba(255,255,255,0.09)',
      borderRadius: 16, overflow: 'hidden',
      transition: 'border-color 0.2s',
    }}>
      {/* Top bar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 14,
        padding: '16px 18px', borderBottom: '1px solid rgba(255,255,255,0.06)',
        background: `linear-gradient(90deg, ${confColor}10 0%, transparent 60%)`,
      }}>
        <ProbGauge prob={pick.win_probability} size={68} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 20, fontWeight: 900, color: '#f1f5f9', fontFamily: 'monospace' }}>
              {pick.ticker}
            </span>
            <span style={{
              fontSize: 10, fontWeight: 800, padding: '3px 8px', borderRadius: 99,
              background: confColor + '22', color: confColor, border: `1px solid ${confColor}44`,
            }}>{conf}</span>
            {thesis.trade_type && (
              <span style={{ fontSize: 10, color: '#475569', fontWeight: 600 }}>{thesis.trade_type}</span>
            )}
          </div>
          <div style={{ fontSize: 12, color: '#64748b', marginTop: 3 }}>
            {strategies.length} strategies: {strategies.slice(0,3).join(', ')}{strategies.length > 3 ? ` +${strategies.length-3}` : ''}
          </div>
        </div>
        <div style={{ textAlign: 'right', minWidth: 80 }}>
          <div style={{ fontSize: 18, fontWeight: 900, color: '#f1f5f9', fontFamily: 'monospace' }}>
            {fmtPrice(pick.price)}
          </div>
          <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>{pick.hold_days}d hold</div>
        </div>
      </div>

      {/* Entry / Target / SL row */}
      {thesis.entry_zone && (
        <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
          {[
            { label: 'Entry Zone', val: `₹${thesis.entry_zone}`, col: '#94a3b8' },
            { label: 'Target 1', val: fmtPrice(thesis.target_1), col: '#10b981' },
            { label: 'Target 2', val: fmtPrice(thesis.target_2), col: '#10b981' },
            { label: 'Stop Loss', val: fmtPrice(thesis.stop_loss), col: '#ef4444' },
          ].map(({ label, val, col }) => (
            <div key={label} style={{
              flex: 1, padding: '10px 12px', textAlign: 'center',
              borderRight: '1px solid rgba(255,255,255,0.05)',
            }}>
              <div style={{ fontSize: 9, color: '#475569', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: 3 }}>{label}</div>
              <div style={{ fontSize: 13, fontWeight: 800, color: col, fontFamily: 'monospace' }}>{val}</div>
            </div>
          ))}
        </div>
      )}

      {/* Summary / Thesis */}
      <div style={{ padding: '12px 18px' }}>
        {thesis.summary ? (
          <p style={{ margin: 0, fontSize: 12, color: '#94a3b8', lineHeight: 1.6 }}>
            {thesis.summary}
          </p>
        ) : (
          <p style={{ margin: 0, fontSize: 12, color: '#475569', fontStyle: 'italic' }}>AI thesis generating...</p>
        )}

        {thesis.catalyst && (
          <div style={{ marginTop: 8, fontSize: 11 }}>
            <span style={{ color: '#475569' }}>Catalyst: </span>
            <span style={{ color: '#f59e0b', fontWeight: 600 }}>{thesis.catalyst}</span>
          </div>
        )}

        {/* Technicals mini-row */}
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 10 }}>
          {[
            { l: 'RSI', v: pick.technicals?.rsi?.toFixed(1) },
            { l: 'Vol', v: pick.technicals?.vol_ratio ? `${pick.technicals.vol_ratio}x` : null },
            { l: '52W%', v: pick.technicals?.pct_from_52h != null ? `${pick.technicals.pct_from_52h.toFixed(1)}%` : null },
            { l: 'EMA↑', v: pick.technicals?.ema_aligned ? 'Yes' : 'No' },
          ].filter(x => x.v).map(({ l, v }) => (
            <span key={l} style={{ fontSize: 10, color: '#64748b' }}>
              <span style={{ color: '#475569' }}>{l} </span>
              <span style={{ color: '#94a3b8', fontFamily: 'monospace', fontWeight: 700 }}>{v}</span>
            </span>
          ))}
        </div>

        {/* Risks expand */}
        {thesis.risk_factors && thesis.risk_factors.length > 0 && (
          <div style={{ marginTop: 10 }}>
            <button
              onClick={() => setExpanded(x => !x)}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                fontSize: 10, color: '#475569', fontWeight: 700, padding: 0,
              }}
            >
              {expanded ? '▲' : '▼'} Risk Factors ({thesis.risk_factors.length})
            </button>
            {expanded && (
              <ul style={{ margin: '6px 0 0 14px', padding: 0, listStyle: 'disc' }}>
                {thesis.risk_factors.map((r: string, i: number) => (
                  <li key={i} style={{ fontSize: 11, color: '#64748b', marginBottom: 3 }}>{r}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Live Picks Tab ────────────────────────────────────────────────────────────
function LivePicksTab() {
  const [picks, setPicks] = useState<any[]>([])
  const [meta, setMeta]   = useState<any>({})
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confFilter, setConfFilter] = useState<'ALL' | 'MODERATE' | 'HIGH'>('ALL')

  const fetchPicks = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/v1/swing/picks?limit=20&min_confidence=LOW&with_thesis=true`, { credentials: 'include' })
      const data = await res.json()
      if (data.error && !data.picks?.length) { setError(data.error); setPicks([]) }
      else { setPicks(data.picks || []); setMeta(data) }
    } catch (e: any) {
      setError(e.message || 'Failed to load live picks')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchPicks() }, [fetchPicks])

  const triggerScan = async () => {
    setScanning(true)
    try {
      await fetch(`${API_BASE}/api/v1/swing/scan/trigger?with_thesis=false`, {
        method: 'POST', credentials: 'include'
      })
      setTimeout(fetchPicks, 3000)  // re-fetch after 3s
    } catch { }
    finally { setScanning(false) }
  }

  const filtered = confFilter === 'ALL' ? picks : picks.filter(p => p.confidence === confFilter)

  return (
    <div>
      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 1, borderRadius: 8, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.08)' }}>
          {(['ALL', 'MODERATE', 'HIGH'] as const).map(c => (
            <button key={c} onClick={() => setConfFilter(c)} style={{
              padding: '6px 14px', fontSize: 11, fontWeight: 700, cursor: 'pointer',
              background: confFilter === c ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.03)',
              color: confFilter === c ? '#818cf8' : '#475569',
              border: 'none',
            }}>{c}</button>
          ))}
        </div>
        {meta.scanned_at && (
          <span style={{ fontSize: 11, color: '#475569' }}>
            Last scan: {new Date(meta.scanned_at).toLocaleTimeString()} · {meta.total_candidates} candidates
          </span>
        )}
        <button onClick={triggerScan} disabled={scanning} style={{
          marginLeft: 'auto', padding: '6px 14px', borderRadius: 8, fontSize: 11, fontWeight: 700,
          background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.25)', color: '#10b981',
          cursor: scanning ? 'not-allowed' : 'pointer', opacity: scanning ? 0.6 : 1,
        }}>
          {scanning ? '⏳ Scanning...' : '⚡ Trigger Scan'}
        </button>
        <button onClick={fetchPicks} disabled={loading} style={{
          padding: '6px 14px', borderRadius: 8, fontSize: 11, fontWeight: 700,
          background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.25)', color: '#818cf8',
          cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.6 : 1,
        }}>🔄 Refresh</button>
      </div>

      {/* Error */}
      {error && (
        <div style={{ padding: '12px 16px', borderRadius: 10, marginBottom: 16, background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', color: '#f87171', fontSize: 13 }}>
          ⚠️ {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(420px, 1fr))', gap: 14 }}>
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} style={{ height: 200, borderRadius: 16, background: 'rgba(255,255,255,0.04)', animation: 'pulse 1.5s ease-in-out infinite' }} />
          ))}
        </div>
      )}

      {/* No picks */}
      {!loading && filtered.length === 0 && !error && (
        <div style={{ textAlign: 'center', padding: '60px 20px', color: '#475569' }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>🔍</div>
          <div style={{ fontWeight: 700, color: '#94a3b8', fontSize: 15 }}>No picks match this filter</div>
          <div style={{ marginTop: 8, fontSize: 12 }}>Try 'ALL' confidence or click Trigger Scan to run a fresh market scan.</div>
        </div>
      )}

      {/* Picks grid */}
      {!loading && filtered.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(420px, 1fr))', gap: 14 }}>
          {filtered.map((p: any) => <LivePickCard key={p.symbol} pick={p} />)}
        </div>
      )}
    </div>
  )
}

// ── Hermes Brain Status Tab ───────────────────────────────────────────────────
function HermesBrainTab() {
  const [status, setStatus] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/swing/hermes-status`)
      .then(r => r.json()).then(setStatus).catch(() => setStatus(null))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div style={{ height: 200, borderRadius: 16, background: 'rgba(255,255,255,0.04)', animation: 'pulse 1.5s ease-in-out infinite' }} />
  if (!status || status.status === 'not_initialized') return (
    <div style={{ textAlign: 'center', padding: '60px 20px', color: '#475569' }}>
      <div style={{ fontSize: 36, marginBottom: 12 }}>🧠</div>
      <div style={{ fontWeight: 700, color: '#94a3b8' }}>Hermes not yet initialized</div>
      <div style={{ marginTop: 6, fontSize: 12 }}>Hermes runs every Sunday at 03:30 IST.</div>
    </div>
  )

  const w = status.weights || {}
  const weightEntries = [['α ML Model', w.alpha], ['β Strategy WR', w.beta], ['γ News Sentiment', w.gamma], ['δ Fundamentals', w.delta]] as [string, number][]

  return (
    <div style={{ display: 'grid', gap: 14 }}>
      {/* Status header */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
        {[
          { label: 'Learning Iteration', val: `#${status.iteration}`, col: '#6366f1' },
          { label: 'Top Strategy', val: status.top_strategy || '—', col: '#10b981' },
          { label: 'Weakest Strategy', val: status.worst_strategy || '—', col: '#ef4444' },
          { label: 'Last L1 Update', val: status.updated_at ? new Date(status.updated_at).toLocaleDateString() : '—', col: '#f59e0b' },
        ].map(({ label, val, col }) => (
          <div key={label} style={{ padding: '14px 16px', borderRadius: 12, background: 'rgba(15,23,42,0.8)', border: `1px solid ${col}22` }}>
            <div style={{ fontSize: 11, color: '#475569', fontWeight: 700, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{label}</div>
            <div style={{ fontSize: 16, fontWeight: 900, color: col, fontFamily: 'monospace' }}>{val}</div>
          </div>
        ))}
      </div>

      {/* Weights visualization */}
      <div style={{ padding: 20, borderRadius: 14, background: 'rgba(15,23,42,0.8)', border: '1px solid rgba(255,255,255,0.08)' }}>
        <h4 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 800, color: '#f1f5f9' }}>🔬 Current Scoring Weights</h4>
        <div style={{ display: 'grid', gap: 12 }}>
          {weightEntries.map(([label, val]) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 12, color: '#94a3b8', minWidth: 130, fontWeight: 600 }}>{label}</span>
              <div style={{ flex: 1, height: 8, background: 'rgba(255,255,255,0.07)', borderRadius: 99, overflow: 'hidden' }}>
                <div style={{
                  width: `${(val || 0) * 100}%`, height: '100%',
                  background: 'linear-gradient(90deg, #6366f1, #818cf8)',
                  borderRadius: 99, transition: 'width 0.6s ease',
                }} />
              </div>
              <span style={{ fontSize: 13, fontWeight: 900, color: '#818cf8', fontFamily: 'monospace', minWidth: 40 }}>{((val || 0) * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      </div>

      {/* Key insights */}
      {status.key_insights?.length > 0 && (
        <div style={{ padding: 20, borderRadius: 14, background: 'rgba(15,23,42,0.8)', border: '1px solid rgba(255,255,255,0.08)' }}>
          <h4 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 800, color: '#f1f5f9' }}>💡 Key Insights from Last Run</h4>
          <ul style={{ margin: 0, padding: '0 0 0 18px', display: 'grid', gap: 8 }}>
            {status.key_insights.map((ins: string, i: number) => (
              <li key={i} style={{ fontSize: 13, color: '#94a3b8', lineHeight: 1.5 }}>{ins}</li>
            ))}
          </ul>
        </div>
      )}

      {/* L3 paper trade learning */}
      {status.l3_recommendation && (
        <div style={{ padding: 20, borderRadius: 14, background: 'rgba(15,23,42,0.8)', border: '1px solid rgba(239,68,68,0.15)' }}>
          <h4 style={{ margin: '0 0 8px', fontSize: 14, fontWeight: 800, color: '#f1f5f9' }}>📉 L3 Paper Trade Learning</h4>
          <p style={{ margin: '0 0 12px', fontSize: 13, color: '#94a3b8', lineHeight: 1.6 }}>{status.l3_recommendation}</p>
          {status.l3_failure_patterns?.length > 0 && (
            <div>
              <div style={{ fontSize: 11, color: '#475569', fontWeight: 700, marginBottom: 6 }}>FAILURE PATTERNS IDENTIFIED:</div>
              <ul style={{ margin: 0, padding: '0 0 0 16px', display: 'grid', gap: 4 }}>
                {status.l3_failure_patterns.map((p: string, i: number) => (
                  <li key={i} style={{ fontSize: 12, color: '#ef4444' }}>{p}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function SwingStrategiesHub() {
  const [tab, setTab] = useState<'live' | 'picks' | 'leaderboard' | 'hermes'>('live')
  const [strategies, setStrategies]  = useState<SwingStrategy[]>([])
  const [stocks, setStocks]          = useState<BestStrategyStock[]>([])
  const [selectedStrat, setSelectedStrat] = useState<string | null>(null)
  const [minWR, setMinWR]   = useState(60)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState<string | null>(null)
  const [lastFetch, setLastFetch] = useState<Date | null>(null)

  const fetchAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [stratRes, stockRes] = await Promise.allSettled([
        apiSwingStrategies(),
        apiBestStrategyStocks(minWR, 25),
      ])
      if (stratRes.status === 'fulfilled') setStrategies(stratRes.value.strategies)
      if (stockRes.status === 'fulfilled') setStocks(stockRes.value.stocks)
      else if (stockRes.status === 'rejected') {
        // Try with lower threshold
        try {
          const fallback = await apiBestStrategyStocks(55, 20)
          setStocks(fallback.stocks)
        } catch { setStocks([]) }
      }
      setLastFetch(new Date())
    } catch (e: any) {
      setError(e?.message || 'Failed to load strategy data')
    } finally {
      setLoading(false)
    }
  }, [minWR])

  useEffect(() => { fetchAll() }, [fetchAll])

  const activeStrategies = strategies.filter(s => s.is_active)

  return (
    <div style={{ fontFamily: 'Inter, system-ui, sans-serif', minHeight: '100vh' }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 24, fontWeight: 900, color: '#f1f5f9' }}>
              ⚡ Swing Trading Intelligence
            </h1>
            <p style={{ margin: '4px 0 0', fontSize: 13, color: '#64748b' }}>
              14 strategies backtested · ML win probability · News sentiment fusion · Hermes self-learning
            </p>
          </div>
          {lastFetch && (
            <div style={{ fontSize: 11, color: '#475569' }}>
              Last updated: {lastFetch.toLocaleTimeString()}
            </div>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div style={{
          padding: '12px 16px', borderRadius: 10, marginBottom: 16,
          background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', color: '#f87171', fontSize: 13,
        }}>
          ⚠️ {error} — <button onClick={fetchAll} style={{ color: '#f87171', textDecoration: 'underline', background: 'none', border: 'none', cursor: 'pointer' }}>retry</button>
        </div>
      )}

      {/* Summary bar */}
      {!loading && <SummaryBar strategies={strategies} stocks={stocks} />}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid rgba(255,255,255,0.07)', paddingBottom: 0 }}>
        {[
          { id: 'live' as const,        label: '⚡ Live Picks' },
          { id: 'picks' as const,       label: '🎯 Best-Strategy Picks' },
          { id: 'leaderboard' as const, label: '📊 Strategy Leaderboard' },
          { id: 'hermes' as const,      label: '🧠 Hermes Brain' },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: '10px 18px', background: 'none', border: 'none', cursor: 'pointer',
            fontSize: 13, fontWeight: 700,
            color: tab === t.id ? '#818cf8' : '#475569',
            borderBottom: tab === t.id ? '2px solid #6366f1' : '2px solid transparent',
            marginBottom: -1, transition: 'all 0.2s',
          }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── LIVE PICKS TAB ────────────────────────────────────────────────────── */}
      {tab === 'live' && <LivePicksTab />}

      {/* ── PICKS TAB ────────────────────────────────────────────────────────── */}
      {tab === 'picks' && (
        <>
          <FilterBar minWR={minWR} setMinWR={setMinWR} loading={loading} onRefresh={fetchAll} />

          {loading ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(420px, 1fr))', gap: 12 }}>
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} style={{
                  height: 140, borderRadius: 14,
                  background: 'rgba(255,255,255,0.04)',
                  animation: 'pulse 1.5s ease-in-out infinite',
                }} />
              ))}
            </div>
          ) : stocks.length === 0 ? (
            <div style={{
              textAlign: 'center', padding: '60px 20px',
              color: '#475569', fontSize: 14,
            }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>📊</div>
              <div style={{ fontWeight: 700, color: '#94a3b8' }}>No stocks match this criteria right now</div>
              <div style={{ marginTop: 6, fontSize: 12 }}>
                Try lowering the minimum win rate filter, or the backtest may still be running.
              </div>
              <button onClick={() => setMinWR(55)} style={{
                marginTop: 16, padding: '8px 20px', borderRadius: 8, fontSize: 12, fontWeight: 700,
                background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.3)',
                color: '#818cf8', cursor: 'pointer',
              }}>Use 55% Threshold</button>
            </div>
          ) : (
            <>
              <div style={{ marginBottom: 10, fontSize: 12, color: '#475569' }}>
                {stocks.length} stocks triggering strategies with ≥{minWR}% historical win rate
                · sorted by win probability
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(420px, 1fr))', gap: 12 }}>
                {stocks.map(s => <StockCard key={s.symbol} stock={s} />)}
              </div>
            </>
          )}
        </>
      )}

      {/* ── LEADERBOARD TAB ──────────────────────────────────────────────────── */}
      {tab === 'leaderboard' && (
        <>
          {loading ? (
            <div style={{ height: 400, borderRadius: 16, background: 'rgba(255,255,255,0.04)', animation: 'pulse 1.5s ease-in-out infinite' }} />
          ) : (
            <>
              <StrategyLeaderboard
                strategies={strategies}
                onSelect={setSelectedStrat}
                selected={selectedStrat}
              />

              {/* Strategy detail panel */}
              {selectedStrat && (() => {
                const s = strategies.find(st => st.key === selectedStrat)
                if (!s) return null
                return (
                  <div style={{
                    marginTop: 16, padding: 20,
                    background: 'rgba(15,23,42,0.8)',
                    border: `1px solid ${s.color}30`, borderRadius: 14,
                  }}>
                    <h3 style={{ margin: '0 0 12px', fontSize: 16, fontWeight: 800, color: '#f1f5f9' }}>
                      {s.icon} {s.label} — Horizon Breakdown
                    </h3>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12 }}>
                      {Object.entries(s.horizon_stats).map(([h, stats]) => (
                        <div key={h} style={{
                          padding: '12px 14px', borderRadius: 10,
                          background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)',
                        }}>
                          <div style={{ fontSize: 14, fontWeight: 900, color: s.color, marginBottom: 8 }}>{h} horizon</div>
                          {stats.insufficient_data ? (
                            <div style={{ fontSize: 11, color: '#475569' }}>Insufficient data</div>
                          ) : (
                            <>
                              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                                <span style={{ fontSize: 10, color: '#475569' }}>Win Rate</span>
                                <span style={{ fontSize: 12, fontWeight: 800, color: wrColor(stats.win_rate), fontFamily: 'monospace' }}>
                                  {stats.win_rate?.toFixed(1)}%
                                </span>
                              </div>
                              <WinRateBar wr={stats.win_rate} width={140} />
                              <div style={{ marginTop: 8, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
                                {[
                                  ['Avg Ret', fmtP(stats.avg_return)],
                                  ['Prof. F', fmt(stats.profit_factor, 2)],
                                  ['Max DD', stats.max_drawdown != null ? stats.max_drawdown.toFixed(1) + '%' : '—'],
                                  ['Trades', String(stats.total_trades)],
                                ].map(([l, v]) => (
                                  <div key={l} style={{ fontSize: 10 }}>
                                    <span style={{ color: '#475569' }}>{l}: </span>
                                    <span style={{ color: '#94a3b8', fontFamily: 'monospace', fontWeight: 700 }}>{v}</span>
                                  </div>
                                ))}
                              </div>
                            </>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })()}
            </>
          )}
        </>
      )}

      {/* ── HERMES BRAIN TAB ─────────────────────────────────────────────────── */}
      {tab === 'hermes' && <HermesBrainTab />}

      <style>{`@keyframes pulse { 0%,100%{opacity:0.4} 50%{opacity:0.8} }`}</style>
    </div>
  )
}
