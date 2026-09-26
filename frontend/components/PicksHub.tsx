'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  apiPicksCurated,
  type KeplerPicksResult,
  type KeplerPick,
  type PickCategory,
} from '@/lib/api'

const CATEGORY_CFG = {
  SWING:      { label: '⚡ Swing',      color: '#f59e0b', bg: 'rgba(245,158,11,0.10)',  desc: '1-3 weeks' },
  MOMENTUM:   { label: '🚀 Momentum',   color: '#3b82f6', bg: 'rgba(59,130,246,0.10)',  desc: '3-8 weeks' },
  POSITIONAL: { label: '📈 Positional', color: '#8b5cf6', bg: 'rgba(139,92,246,0.10)',  desc: '2-4 months' },
  VALUE:      { label: '💎 Value',      color: '#10b981', bg: 'rgba(16,185,129,0.10)',  desc: '3-6 months' },
}

const CONVICTION_CFG = {
  VERY_HIGH: { label: 'Very High', color: '#10b981', glow: 'rgba(16,185,129,0.35)' },
  HIGH:      { label: 'High',      color: '#22c55e', glow: 'rgba(34,197,94,0.3)' },
  MODERATE:  { label: 'Moderate',  color: '#f59e0b', glow: 'rgba(245,158,11,0.3)' },
  WATCHLIST: { label: 'Watchlist', color: '#64748b', glow: 'rgba(100,116,139,0.2)' },
}

type TabId = 'ALL' | PickCategory

function convColor(score: number) {
  if (score >= 80) return '#10b981'
  if (score >= 65) return '#22c55e'
  if (score >= 50) return '#f59e0b'
  return '#64748b'
}

function fmt(n: number | null | undefined) {
  if (n == null) return '—'
  return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

function fmtPct(n: number | null | undefined) {
  if (n == null) return '—'
  return `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`
}

function ScoreRing({ score, size = 64 }: { score: number; size?: number }) {
  const r = (size - 8) / 2
  const circ = 2 * Math.PI * r
  const fill = (score / 100) * circ
  const col = convColor(score)
  return (
    <svg width={size} height={size} style={{ display: 'block', filter: `drop-shadow(0 0 6px ${col}60)` }}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={6} />
      <circle
        cx={size/2} cy={size/2} r={r} fill="none"
        stroke={col} strokeWidth={6}
        strokeDasharray={`${fill} ${circ - fill}`}
        strokeDashoffset={circ / 4}
        strokeLinecap="round"
      />
      <text x={size/2} y={size/2 + 1} textAnchor="middle" dominantBaseline="middle"
        style={{ fontSize: size * 0.22, fontWeight: 900, fill: col, fontFamily: 'monospace' }}>
        {score}
      </text>
    </svg>
  )
}

function MiniBar({ label, val, max, color }: { label: string; val: number; max: number; color: string }) {
  const pct = Math.min((val / max) * 100, 100)
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{ fontSize: 9, color: '#475569', fontWeight: 600, width: 44, flexShrink: 0 }}>{label}</span>
      <div style={{ flex: 1, height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 99, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 99 }} />
      </div>
      <span style={{ fontSize: 9, fontWeight: 800, color, width: 20, textAlign: 'right', fontFamily: 'monospace' }}>{val}</span>
    </div>
  )
}

function PickCard({ pick }: { pick: KeplerPick }) {
  const [expanded, setExpanded] = useState(false)
  const cat = CATEGORY_CFG[pick.category]
  const conv = CONVICTION_CFG[pick.conviction]
  const col = convColor(pick.conviction_score)
  const fund = pick.fundamentals
  const thesis = pick.ai_thesis
  const rsiColor = pick.rsi > 70 ? '#ef4444' : pick.rsi > 55 ? '#10b981' : '#64748b'

  return (
    <div style={{
      background: 'linear-gradient(135deg, rgba(15,23,42,0.95) 0%, rgba(20,28,50,0.95) 100%)',
      border: `1px solid ${col}22`,
      borderRadius: 16,
      overflow: 'hidden',
      transition: 'transform 0.2s, box-shadow 0.2s',
      boxShadow: '0 2px 12px rgba(0,0,0,0.3)',
    }}
      onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-2px)' }}
      onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.transform = 'translateY(0)' }}
    >
      <div style={{ height: 3, background: `linear-gradient(90deg, ${col}, ${cat.color})` }} />
      <div style={{ padding: '16px 18px' }}>

        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 14 }}>
          <div style={{ flexShrink: 0 }}>
            <ScoreRing score={pick.conviction_score} size={62} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
              <span style={{ fontSize: 17, fontWeight: 900, color: '#f1f5f9', letterSpacing: '-0.3px' }}>{pick.symbol}</span>
              <span style={{ fontSize: 9, fontWeight: 700, padding: '3px 9px', borderRadius: 99, background: cat.bg, color: cat.color, border: `1px solid ${cat.color}30` }}>
                {cat.label}
              </span>
              <span style={{ fontSize: 9, fontWeight: 700, padding: '3px 9px', borderRadius: 99, background: `${conv.color}12`, color: conv.color, border: `1px solid ${conv.color}28` }}>
                {conv.label}
              </span>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={{ fontSize: 11, color: '#64748b' }}>{pick.sector}</span>
              <span style={{ fontSize: 11, color: '#94a3b8' }}>CMP <strong style={{ color: '#f1f5f9' }}>{fmt(pick.price)}</strong></span>
              <span style={{ fontSize: 10, color: cat.color, fontWeight: 600 }}>{pick.timeframe_icon} {pick.timeframe}</span>
            </div>
          </div>
          <div style={{ flexShrink: 0, textAlign: 'center' }}>
            <div style={{ fontSize: 13, fontWeight: 800, fontFamily: 'monospace', color: pick.ret_30d >= 0 ? '#10b981' : '#ef4444' }}>
              {fmtPct(pick.ret_30d)}
            </div>
            <div style={{ fontSize: 8, color: '#475569', fontWeight: 600 }}>30D</div>
            <div style={{ fontSize: 10, fontWeight: 700, color: pick.rs_vs_nifty >= 0 ? '#22c55e' : '#f59e0b' }}>
              RS {fmtPct(pick.rs_vs_nifty)}
            </div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6, marginBottom: 12 }}>
          {[
            { label: 'ENTRY', val: `₹${pick.entry_low}–${pick.entry_high}`, color: '#3b82f6', icon: '🎯' },
            { label: 'TARGET 1', val: fmt(pick.target1), color: '#10b981', icon: '🎖' },
            { label: 'TARGET 2', val: fmt(pick.target2), color: '#22c55e', icon: '🏆' },
            { label: 'STOP LOSS', val: `${fmt(pick.stop_loss)} (${pick.sl_pct}%)`, color: '#ef4444', icon: '🛡' },
          ].map(t => (
            <div key={t.label} style={{ background: `${t.color}08`, border: `1px solid ${t.color}20`, borderRadius: 8, padding: '7px 8px', textAlign: 'center' }}>
              <div style={{ fontSize: 7, color: '#475569', fontWeight: 700, marginBottom: 2 }}>{t.icon} {t.label}</div>
              <div style={{ fontSize: 10, fontWeight: 800, color: t.color, lineHeight: 1.2 }}>{t.val}</div>
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', gap: 5, marginBottom: 12, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 9, fontWeight: 700, padding: '3px 8px', borderRadius: 99, background: pick.rr_ratio >= 2 ? 'rgba(16,185,129,0.10)' : 'rgba(245,158,11,0.10)', color: pick.rr_ratio >= 2 ? '#10b981' : '#f59e0b', border: `1px solid ${pick.rr_ratio >= 2 ? 'rgba(16,185,129,0.25)' : 'rgba(245,158,11,0.25)'}` }}>
            R:R = {pick.rr_ratio}:1
          </span>
          <span style={{ fontSize: 9, fontWeight: 700, padding: '3px 8px', borderRadius: 99, background: `${rsiColor}10`, color: rsiColor, border: `1px solid ${rsiColor}28` }}>RSI {pick.rsi.toFixed(0)}</span>
          {pick.ema_perfect && <span style={{ fontSize: 9, fontWeight: 700, padding: '3px 8px', borderRadius: 99, background: 'rgba(16,185,129,0.10)', color: '#10b981', border: '1px solid rgba(16,185,129,0.25)' }}>EMA Stack ✅</span>}
          {pick.macd_above && <span style={{ fontSize: 9, fontWeight: 700, padding: '3px 8px', borderRadius: 99, background: 'rgba(59,130,246,0.10)', color: '#3b82f6', border: '1px solid rgba(59,130,246,0.25)' }}>MACD ↗</span>}
          {pick.vcp_tightening && <span style={{ fontSize: 9, fontWeight: 700, padding: '3px 8px', borderRadius: 99, background: 'rgba(245,158,11,0.10)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.25)' }}>VCP 🔄</span>}
          {pick.golden_cross && <span style={{ fontSize: 9, fontWeight: 700, padding: '3px 8px', borderRadius: 99, background: 'rgba(234,179,8,0.10)', color: '#eab308', border: '1px solid rgba(234,179,8,0.25)' }}>✨ Golden Cross</span>}
          <span style={{ fontSize: 9, fontWeight: 700, padding: '3px 8px', borderRadius: 99, background: 'rgba(100,116,139,0.08)', color: '#64748b', border: '1px solid rgba(100,116,139,0.18)' }}>Vol {pick.vol_ratio}×</span>
          <span style={{ fontSize: 9, fontWeight: 700, padding: '3px 8px', borderRadius: 99, background: 'rgba(100,116,139,0.08)', color: '#64748b', border: '1px solid rgba(100,116,139,0.18)' }}>{pick.pct_from_52h.toFixed(1)}% below 52W high</span>
        </div>

        {thesis?.thesis && (
          <div style={{ background: 'rgba(0,196,140,0.04)', border: '1px solid rgba(0,196,140,0.12)', borderRadius: 10, padding: '10px 12px', marginBottom: 10 }}>
            <div style={{ fontSize: 8, color: '#00C48C', fontWeight: 700, letterSpacing: '0.5px', marginBottom: 5 }}>✦ KEPLER AI THESIS</div>
            <p style={{ fontSize: 11, color: '#94a3b8', lineHeight: 1.6, margin: 0 }}>{thesis.thesis}</p>
          </div>
        )}

        <button
          onClick={() => setExpanded(e => !e)}
          style={{ width: '100%', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 8, color: '#475569', fontSize: 11, fontWeight: 600, padding: '7px', cursor: 'pointer', transition: 'all 0.15s', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
          onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(0,196,140,0.08)'; (e.currentTarget as HTMLButtonElement).style.color = '#00C48C' }}
          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.03)'; (e.currentTarget as HTMLButtonElement).style.color = '#475569' }}
        >
          {expanded ? 'Less Detail ↑' : 'Full Analysis ↓'}
        </button>

        {expanded && (
          <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <p style={{ fontSize: 10, color: '#475569', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>Conviction Breakdown</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                <MiniBar label="Technical"  val={pick.tech_score}      max={30} color="#3b82f6" />
                <MiniBar label="Momentum"   val={pick.momentum_score}  max={25} color="#f59e0b" />
                <MiniBar label="Patterns"   val={pick.pattern_score}   max={20} color="#8b5cf6" />
                <MiniBar label="Fundament." val={pick.fund_score}      max={15} color="#10b981" />
                <MiniBar label="Setup"      val={pick.setup_score}     max={10} color="#ec4899" />
              </div>
            </div>

            <div>
              <p style={{ fontSize: 10, color: '#475569', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>Key Levels</p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 }}>
                {[
                  { label: '20 EMA', val: pick.ema20, good: !!pick.ema20 && pick.price > (pick.ema20 ?? 0) },
                  { label: '50 EMA', val: pick.ema50, good: !!pick.ema50 && pick.price > (pick.ema50 ?? 0) },
                  { label: '200 EMA', val: pick.ema200, good: !!pick.ema200 && pick.price > (pick.ema200 ?? 0) },
                  { label: '52W High', val: pick.high_52w, good: pick.pct_from_52h <= 5 },
                  { label: '52W Low', val: pick.low_52w, good: pick.pct_from_52l > 20 },
                  { label: 'ATR(14)', val: pick.atr, good: true },
                ].map(l => (
                  <div key={l.label} style={{ background: 'rgba(255,255,255,0.02)', borderRadius: 7, padding: '6px 8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                    <div style={{ fontSize: 8, color: '#475569', fontWeight: 600, marginBottom: 2 }}>{l.label}</div>
                    <div style={{ fontSize: 11, fontWeight: 800, color: l.good ? '#10b981' : '#94a3b8', fontFamily: 'monospace' }}>
                      {l.val != null ? `₹${l.val.toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : '—'}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {pick.patterns.length > 0 && (
              <div>
                <p style={{ fontSize: 10, color: '#475569', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>Detected Patterns</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                  {pick.patterns.map((p: string) => (
                    <span key={p} style={{ fontSize: 10, fontWeight: 600, padding: '4px 10px', borderRadius: 99, background: 'rgba(0,196,140,0.08)', color: '#00C48C', border: '1px solid rgba(0,196,140,0.2)' }}>{p}</span>
                  ))}
                </div>
              </div>
            )}

            {fund && (
              <div>
                <p style={{ fontSize: 10, color: '#475569', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>Fundamentals</p>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 5 }}>
                  {[
                    { label: 'P/E', val: fund.pe_ratio?.toFixed(1) ?? '—' },
                    { label: 'ROE', val: fund.roe ? `${fund.roe.toFixed(1)}%` : '—' },
                    { label: 'D/E', val: fund.debt_to_equity?.toFixed(2) ?? '—' },
                    { label: 'Rev CAGR', val: fund.revenue_cagr_3y ? `${fund.revenue_cagr_3y.toFixed(1)}%` : '—' },
                    { label: 'Promoter', val: fund.promoter_holding ? `${fund.promoter_holding.toFixed(1)}%` : '—' },
                    { label: 'Mkt Cap', val: fund.market_cap_cr ? `₹${Math.round(fund.market_cap_cr).toLocaleString('en-IN')}Cr` : '—' },
                    { label: 'Div Yield', val: fund.dividend_yield ? `${fund.dividend_yield.toFixed(2)}%` : '—' },
                    { label: 'EPS', val: fund.eps?.toFixed(2) ?? '—' },
                  ].map(f => (
                    <div key={f.label} style={{ background: 'rgba(255,255,255,0.02)', borderRadius: 7, padding: '6px 8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                      <div style={{ fontSize: 8, color: '#475569', fontWeight: 600, marginBottom: 2 }}>{f.label}</div>
                      <div style={{ fontSize: 10, fontWeight: 800, color: '#94a3b8', fontFamily: 'monospace' }}>{f.val}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {thesis && (
              <div>
                <p style={{ fontSize: 10, color: '#475569', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>AI Analysis</p>
                {thesis.strengths.length > 0 && <div style={{ marginBottom: 8 }}>{thesis.strengths.map((s: string, i: number) => (
                  <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 4 }}><span style={{ color: '#10b981', fontSize: 10 }}>✓</span><span style={{ fontSize: 11, color: '#94a3b8' }}>{s}</span></div>
                ))}</div>}
                {thesis.catalyst && <div style={{ background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.15)', borderRadius: 8, padding: '8px 10px', marginBottom: 6 }}>
                  <span style={{ fontSize: 9, color: '#3b82f6', fontWeight: 700 }}>📡 CATALYST  </span>
                  <span style={{ fontSize: 11, color: '#94a3b8' }}>{thesis.catalyst}</span>
                </div>}
                {thesis.risks.length > 0 && <div style={{ marginBottom: 8 }}>{thesis.risks.map((r: string, i: number) => (
                  <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 4 }}><span style={{ color: '#ef4444', fontSize: 10 }}>⚠</span><span style={{ fontSize: 11, color: '#64748b' }}>{r}</span></div>
                ))}</div>}
                {thesis.invalidation && <div style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)', borderRadius: 8, padding: '8px 10px' }}>
                  <span style={{ fontSize: 9, color: '#ef4444', fontWeight: 700 }}>🛑 INVALIDATION  </span>
                  <span style={{ fontSize: 11, color: '#94a3b8' }}>{thesis.invalidation}</span>
                </div>}
              </div>
            )}

            <p style={{ fontSize: 9, color: '#334155', lineHeight: 1.5, fontStyle: 'italic', marginTop: 4 }}>
              This is algorithmic analysis only. Not SEBI-registered investment advice. Markets carry risk. Past signals do not guarantee future returns.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

function PickSkeleton() {
  return (
    <div style={{ background: 'rgba(15,23,42,0.8)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 16, overflow: 'hidden' }}>
      <div style={{ height: 3, background: 'linear-gradient(90deg, rgba(0,196,140,0.3), rgba(59,130,246,0.3))' }} />
      <div style={{ padding: '16px 18px' }}>
        <div style={{ display: 'flex', gap: 12, marginBottom: 14, alignItems: 'center' }}>
          <div style={{ width: 62, height: 62, borderRadius: '50%', background: 'rgba(255,255,255,0.04)', animation: 'pulse 1.8s ease-in-out infinite' }} />
          <div style={{ flex: 1 }}>
            <div style={{ height: 16, width: '40%', background: 'rgba(255,255,255,0.05)', borderRadius: 4, marginBottom: 8, animation: 'pulse 1.8s ease-in-out infinite' }} />
            <div style={{ height: 10, width: '60%', background: 'rgba(255,255,255,0.03)', borderRadius: 4, animation: 'pulse 1.8s ease-in-out infinite' }} />
          </div>
        </div>
        <div style={{ height: 56, background: 'rgba(255,255,255,0.03)', borderRadius: 8, animation: 'pulse 1.8s ease-in-out infinite' }} />
      </div>
    </div>
  )
}

export default function PicksHub() {
  const [data, setData] = useState<KeplerPicksResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<TabId>('ALL')
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(async (force = false) => {
    try {
      if (force) setRefreshing(true)
      const result = await apiPicksCurated(force)
      setData(result)
      setError(null)
    } catch (e: any) {
      setError(e?.message || 'Failed to load picks')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const picks = data?.picks ?? []
  const filtered = tab === 'ALL' ? picks : picks.filter((p: KeplerPick) => p.category === tab)

  const tabs = [
    { id: 'ALL' as TabId,       label: '🔥 All Picks',    count: picks.length },
    { id: 'SWING' as TabId,     label: '⚡ Swing',         count: data?.category_counts.swing ?? 0 },
    { id: 'MOMENTUM' as TabId,  label: '🚀 Momentum',      count: data?.category_counts.momentum ?? 0 },
    { id: 'POSITIONAL' as TabId,label: '📈 Positional',    count: data?.category_counts.positional ?? 0 },
    { id: 'VALUE' as TabId,     label: '💎 Value',         count: data?.category_counts.value ?? 0 },
  ]

  return (
    <div style={{ padding: '0 0 40px' }}>
      <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} } @keyframes spin { to{transform:rotate(360deg)} }`}</style>

      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: 'linear-gradient(135deg, #00C48C, #3b82f6)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, boxShadow: '0 4px 14px rgba(0,196,140,0.4)' }}>🎯</div>
            <div>
              <h2 style={{ fontSize: 22, fontWeight: 900, color: '#f1f5f9', margin: 0 }}>Kepler Picks</h2>
              <p style={{ fontSize: 11, color: '#475569', margin: 0 }}>High-conviction stock picks · Multi-factor scoring</p>
            </div>
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
            {data && <span style={{ fontSize: 10, color: '#334155' }}>Updated {new Date(data.generated_at).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</span>}
            <button onClick={() => load(true)} disabled={refreshing || loading} style={{ background: 'rgba(0,196,140,0.08)', border: '1px solid rgba(0,196,140,0.2)', borderRadius: 8, color: '#00C48C', fontSize: 11, fontWeight: 700, padding: '7px 14px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ display: 'inline-block', animation: refreshing ? 'spin 1s linear infinite' : 'none' }}>⟳</span>
              {refreshing ? 'Scanning…' : 'Refresh Picks'}
            </button>
          </div>
        </div>

        {data && (
          <div style={{ display: 'flex', gap: 12, padding: '10px 14px', background: 'rgba(15,23,42,0.8)', borderRadius: 10, border: '1px solid rgba(255,255,255,0.06)', flexWrap: 'wrap' }}>
            <span style={{ fontSize: 10, color: '#475569' }}>Scanned: <strong style={{ color: '#94a3b8' }}>{data.universe_scanned}</strong></span>
            <span style={{ color: '#1e293b' }}>·</span>
            <span style={{ fontSize: 10, color: '#475569' }}>Candidates: <strong style={{ color: '#94a3b8' }}>{data.candidates_found}</strong></span>
            <span style={{ color: '#1e293b' }}>·</span>
            <span style={{ fontSize: 10, color: '#475569' }}>Nifty 30d: <strong style={{ color: data.nifty_ret_30d >= 0 ? '#10b981' : '#ef4444' }}>{data.nifty_ret_30d >= 0 ? '+' : ''}{data.nifty_ret_30d.toFixed(1)}%</strong></span>
            <span style={{ color: '#1e293b' }}>·</span>
            <span style={{ fontSize: 10, color: '#475569' }}>Picks: <strong style={{ color: '#00C48C' }}>{data.total}</strong></span>
            <span style={{ marginLeft: 'auto', fontSize: 9, color: '#334155', fontStyle: 'italic' }}>Not investment advice · DYOR</span>
          </div>
        )}
      </div>

      {error && (
        <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 10, padding: '14px 18px', marginBottom: 20, color: '#ef4444', fontSize: 12 }}>
          ⚠ {error} — <button onClick={() => load()} style={{ background: 'none', border: 'none', color: '#ef4444', textDecoration: 'underline', cursor: 'pointer', fontSize: 12 }}>Retry</button>
        </div>
      )}

      {loading && !data && (
        <>
          <div style={{ background: 'rgba(0,196,140,0.05)', border: '1px solid rgba(0,196,140,0.15)', borderRadius: 10, padding: '14px 18px', marginBottom: 20, display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ display: 'inline-block', animation: 'spin 1s linear infinite', fontSize: 16 }}>⟳</span>
            <div>
              <p style={{ fontSize: 12, fontWeight: 700, color: '#00C48C', margin: 0 }}>Scanning market universe…</p>
              <p style={{ fontSize: 10, color: '#475569', margin: 0 }}>Analysing 120 NSE stocks · Computing technicals, momentum, fundamentals · Generating AI thesis</p>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 16 }}>
            {[1,2,3,4,5,6].map(i => <PickSkeleton key={i} />)}
          </div>
        </>
      )}

      {data && (
        <>
          <div style={{ display: 'flex', gap: 6, marginBottom: 20, flexWrap: 'wrap' }}>
            {tabs.map(t => (
              <button key={t.id} onClick={() => setTab(t.id)} style={{ background: tab === t.id ? 'rgba(0,196,140,0.12)' : 'rgba(255,255,255,0.03)', border: `1px solid ${tab === t.id ? 'rgba(0,196,140,0.3)' : 'rgba(255,255,255,0.07)'}`, borderRadius: 8, color: tab === t.id ? '#00C48C' : '#475569', fontSize: 11, fontWeight: 700, padding: '7px 14px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
                {t.label}
                {t.count > 0 && <span style={{ background: tab === t.id ? 'rgba(0,196,140,0.2)' : 'rgba(255,255,255,0.06)', color: tab === t.id ? '#00C48C' : '#334155', fontSize: 9, fontWeight: 800, borderRadius: 99, padding: '1px 6px' }}>{t.count}</span>}
              </button>
            ))}
          </div>

          {filtered.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 20px', color: '#334155' }}>
              <div style={{ fontSize: 32, marginBottom: 8 }}>🔍</div>
              <p>No {tab.toLowerCase()} picks right now.</p>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 16 }}>
              {filtered.map((pick: KeplerPick) => <PickCard key={pick.symbol} pick={pick} />)}
            </div>
          )}
        </>
      )}
    </div>
  )
}
