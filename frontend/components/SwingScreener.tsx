'use client'

import { useState, useCallback, useEffect } from 'react'
import { apiSwingScreen, type SwingStock, type SwingResult } from '@/lib/api'

// ── Preset definitions ────────────────────────────────────────────────────────
const SWING_PRESETS = [
  { key: 'near_52w_high',       label: 'Near 52W High',        color: '#10b981', desc: 'Within 5% of 52-week high — breakout candidates' },
  { key: 'breakout_52w',        label: '52W Breakout',          color: '#f59e0b', desc: 'Price at/above 52W high today — confirmed breakouts' },
  { key: 'volume_surge',        label: 'Volume Surge',          color: '#6366f1', desc: 'Volume 2.5× above 10-day avg — institutional activity' },
  { key: 'momentum_leaders',    label: 'Momentum Leaders',      color: '#3b82f6', desc: 'Price > 20DMA > 50DMA > 200DMA — perfect alignment' },
  { key: 'rsi_oversold_bounce', label: 'RSI Oversold Bounce',   color: '#ec4899', desc: 'RSI 25-45 above 200DMA — potential reversal setup' },
  { key: 'rsi_momentum',        label: 'RSI Momentum',          color: '#8b5cf6', desc: 'RSI > 65 with positive trend — strong momentum' },
  { key: 'near_support',        label: 'At Strong Support',     color: '#0ea5e9', desc: 'Near 52W low but above 200DMA — value at support' },
  { key: 'golden_crossover',    label: 'Golden Crossover',      color: '#eab308', desc: '50DMA crossed above 200DMA recently — bull signal' },
  { key: 'vcp_tight',           label: 'VCP Setup',             color: '#14b8a6', desc: 'Volatility contraction near highs — coiling for breakout' },
  { key: 'high_rs',             label: 'High Rel. Strength',    color: '#f97316', desc: 'Outperforming Nifty 50 significantly — RS leaders' },
]

// ── Formatters ────────────────────────────────────────────────────────────────
const fmtPrice = (v: number | null) => v == null ? '—' : `₹${v.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
const fmtPct   = (v: number | null, suffix = '%') => v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(2)}${suffix}`
const fmtNum   = (v: number | null, dec = 1) => v == null ? '—' : v.toFixed(dec)

const rsiColor = (rsi: number | null) => {
  if (rsi == null) return 'var(--text-tertiary)'
  if (rsi >= 70)  return 'var(--loss, #E5484D)'
  if (rsi >= 55)  return 'var(--gain, #3DDC84)'
  if (rsi <= 35)  return '#f59e0b'
  return 'var(--text-secondary)'
}

const scoreBar = (score: number | null) => {
  if (score == null) return null
  const color = score >= 70 ? '#10b981' : score >= 50 ? '#3b82f6' : score >= 30 ? '#f59e0b' : '#ef4444'
  return { color, width: `${score}%` }
}

// ── Signal tag pill ───────────────────────────────────────────────────────────
function TagPill({ tag }: { tag: string }) {
  let bg = 'rgba(99,102,241,0.12)'
  let color = '#818cf8'
  if (tag.includes('Surge') || tag.includes('Vol'))   { bg = 'rgba(99,102,241,0.12)'; color = '#818cf8' }
  if (tag.includes('High') || tag.includes('Break'))  { bg = 'rgba(16,185,129,0.12)'; color = '#10b981' }
  if (tag.includes('RSI') && tag.includes('Over'))    { bg = 'rgba(245,158,11,0.12)'; color = '#f59e0b' }
  if (tag.includes('RSI') && tag.includes('Mom'))     { bg = 'rgba(139,92,246,0.12)'; color = '#a78bfa' }
  if (tag.includes('MA') || tag.includes('DMA'))      { bg = 'rgba(59,130,246,0.12)'; color = '#60a5fa' }
  if (tag.includes('Today'))                          { bg = 'rgba(16,185,129,0.10)'; color = '#34d399' }
  return (
    <span style={{
      background: bg, color, fontSize: '10px', fontWeight: 700,
      padding: '2px 7px', borderRadius: '6px', whiteSpace: 'nowrap',
      letterSpacing: '0.2px', border: `1px solid ${color}25`,
      fontFamily: 'var(--font-primary, Inter, system-ui, sans-serif)',
    }}>{tag}</span>
  )
}

// ── Lock icon SVG ─────────────────────────────────────────────────────────────
const IconLock = () => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
  </svg>
)
const IconChevronRight = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="9 18 15 12 9 6" />
  </svg>
)
const IconRefresh = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 4 23 10 17 10" /><polyline points="1 20 1 14 7 14" />
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
  </svg>
)

// ── Main Component ────────────────────────────────────────────────────────────
export default function SwingScreener({ userPlan = 'free' }: { userPlan?: string }) {
  const [selectedPreset, setSelectedPreset] = useState('near_52w_high')
  const [results, setResults]               = useState<SwingStock[]>([])
  const [meta, setMeta]                     = useState<{ label: string; description: string; color: string } | null>(null)
  const [loading, setLoading]               = useState(false)
  const [error, setError]                   = useState<string | null>(null)
  const [elapsed, setElapsed]               = useState(0)
  const [fetchTime, setFetchTime]           = useState<number | null>(null)
  const [fetchedAt, setFetchedAt]           = useState<string | null>(null)
  const [sortField, setSortField]           = useState('swing_score')
  const [sortDir, setSortDir]               = useState<'asc' | 'desc'>('desc')

  const isPro = userPlan === 'pro' || userPlan === 'elite'

  useEffect(() => {
    if (!loading) { setElapsed(0); return }
    const t = setInterval(() => setElapsed(s => s + 1), 1000)
    return () => clearInterval(t)
  }, [loading])

  const fetchPreset = useCallback(async (key: string) => {
    if (!isPro) return
    setLoading(true); setError(null); setFetchTime(null)
    const t0 = Date.now()
    try {
      const res: SwingResult = await apiSwingScreen(key, 30)
      setResults(res.results || [])
      setMeta({ label: res.label, description: res.description, color: (res as any).color || '#6366f1' })
      setFetchedAt(res.fetched_at)
      setFetchTime(Math.round((Date.now() - t0) / 1000))
    } catch (e: any) {
      setError(e.message || 'Screen failed')
      setResults([])
    } finally { setLoading(false) }
  }, [isPro])

  useEffect(() => { fetchPreset(selectedPreset) }, [selectedPreset, fetchPreset])

  const sorted = [...results].sort((a, b) => {
    const av = (a as any)[sortField]; const bv = (b as any)[sortField]
    if (av == null && bv == null) return 0
    if (av == null) return 1; if (bv == null) return -1
    return sortDir === 'desc' ? bv - av : av - bv
  })

  const toggleSort = (field: string) => {
    if (sortField === field) setSortDir(d => d === 'desc' ? 'asc' : 'desc')
    else { setSortField(field); setSortDir('desc') }
  }

  const presetMeta = SWING_PRESETS.find(p => p.key === selectedPreset)

  return (
    <div style={{ fontFamily: "var(--font-primary, 'Inter', system-ui, sans-serif)" }}>
      <style>{`
        .sw-preset-grid {
          display: grid;
          grid-template-columns: repeat(5, 1fr);
          gap: 8px; margin-bottom: 22px;
        }
        @media (max-width: 1100px) { .sw-preset-grid { grid-template-columns: repeat(3, 1fr); } }
        @media (max-width: 700px)  { .sw-preset-grid { grid-template-columns: repeat(2, 1fr); } }

        .sw-preset-btn {
          background: var(--bg-surface, #0F0F11);
          border: 1.5px solid var(--border, rgba(255,255,255,0.08));
          border-left: 3px solid transparent;
          border-radius: 10px;
          padding: 12px 12px 10px;
          cursor: pointer; text-align: left;
          transition: all 0.18s;
          font-family: var(--font-primary, 'Inter', system-ui, sans-serif);
          display: flex; flex-direction: column; gap: 5px;
        }
        .sw-preset-btn:hover {
          border-color: rgba(255,255,255,0.16);
          transform: translateY(-1px);
        }
        .sw-preset-btn.active {
          border-color: var(--sw-color);
          border-left-color: var(--sw-color);
          background: color-mix(in srgb, var(--sw-color) 8%, transparent);
        }
        .sw-preset-dot {
          width: 6px; height: 6px; border-radius: 50%;
          background: var(--sw-color, #64748b);
        }
        .sw-preset-label {
          font-size: 11px; font-weight: 600;
          color: var(--text-secondary, #9A9A9E); line-height: 1.3;
        }
        .sw-preset-btn.active .sw-preset-label { color: var(--sw-color); }
        .sw-preset-desc {
          font-size: 9.5px; color: var(--text-muted, #5C5C60);
          line-height: 1.4; display: none;
        }
        .sw-preset-btn.active .sw-preset-desc { display: block; }

        .sw-results-header {
          display: flex; align-items: center; gap: 12px;
          margin-bottom: 14px; padding: 13px 16px;
          background: var(--bg-surface, #0F0F11);
          border: 1px solid var(--border, rgba(255,255,255,0.08));
          border-radius: 10px;
        }
        .sw-result-title  { font-size: 14px; font-weight: 700; color: var(--text-primary, #F2F2F0); }
        .sw-result-desc   { font-size: 12px; color: var(--text-tertiary, #5C5C60); margin-top: 2px; }
        .sw-result-badge  {
          font-size: 11px; font-weight: 700;
          padding: 4px 10px; border-radius: 99px;
          white-space: nowrap;
        }

        .sw-table-wrap { overflow-x: auto; border-radius: 12px; border: 1px solid var(--border-subtle, rgba(255,255,255,0.05)); }
        .sw-table { width: 100%; border-collapse: collapse; font-size: 12px; }
        .sw-table thead th {
          background: rgba(255,255,255,0.025);
          color: var(--text-tertiary, #5C5C60);
          font-size: 10px; font-weight: 700;
          padding: 10px 12px; text-align: left;
          cursor: pointer; user-select: none; white-space: nowrap;
          border-bottom: 1px solid var(--border-subtle, rgba(255,255,255,0.05));
          text-transform: uppercase; letter-spacing: 0.4px;
          font-family: var(--font-primary, 'Inter', system-ui, sans-serif);
        }
        .sw-table thead th:hover { color: var(--text-secondary, #9A9A9E); }
        .sw-table thead th.sorted { color: var(--accent, #C9A34E); }
        .sw-table tbody tr {
          border-bottom: 1px solid var(--border-subtle, rgba(255,255,255,0.04));
          transition: background 0.1s;
        }
        .sw-table tbody tr:hover { background: rgba(255,255,255,0.025); }
        .sw-table tbody tr:last-child { border-bottom: none; }
        .sw-table td {
          padding: 10px 12px; font-size: 12px;
          color: var(--text-secondary, #9A9A9E);
          white-space: nowrap;
          font-family: var(--font-mono, 'JetBrains Mono', monospace);
        }
        .sw-table td:first-child { font-family: var(--font-primary, 'Inter', system-ui, sans-serif); }

        .sw-score-bar-wrap { display: flex; align-items: center; gap: 6px; }
        .sw-score-bar-track {
          width: 52px; height: 4px;
          background: rgba(255,255,255,0.07);
          border-radius: 99px; overflow: hidden;
        }
        .sw-score-bar-fill { height: 100%; border-radius: 99px; transition: width 0.3s; }

        .sw-loading {
          display: flex; flex-direction: column; align-items: center;
          justify-content: center; padding: 56px 24px; gap: 18px;
        }
        .sw-spinner {
          width: 36px; height: 36px; border-radius: 50%;
          border: 2.5px solid rgba(255,255,255,0.07);
          border-top-color: var(--accent, #C9A34E);
          animation: sw-spin 0.75s linear infinite;
        }
        @keyframes sw-spin { to { transform: rotate(360deg); } }
        .sw-progress-bar {
          width: 280px; height: 3px;
          background: rgba(255,255,255,0.06);
          border-radius: 99px; overflow: hidden;
        }
        .sw-progress-fill {
          height: 100%;
          background: linear-gradient(90deg, var(--accent-dark, #A8822E), var(--accent, #C9A34E), #DDB96A);
          background-size: 200% 100%;
          animation: sw-shimmer 2s linear infinite;
          border-radius: 99px; transition: width 1s linear;
        }
        @keyframes sw-shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }

        .sw-upgrade-box {
          display: flex; flex-direction: column; align-items: center;
          justify-content: center; padding: 52px 24px; gap: 14px;
          border: 1px solid var(--accent-border, rgba(201,163,78,0.2));
          border-radius: 16px;
          background: var(--accent-dim, rgba(201,163,78,0.04));
        }
        .sw-empty {
          text-align: center; padding: 40px;
          color: var(--text-muted, #5C5C60); font-size: 13px;
        }
      `}</style>

      {/* Preset grid */}
      <div className="sw-preset-grid">
        {SWING_PRESETS.map(p => (
          <button
            key={p.key}
            className={`sw-preset-btn ${selectedPreset === p.key ? 'active' : ''}`}
            style={{ '--sw-color': p.color } as any}
            onClick={() => setSelectedPreset(p.key)}
            title={p.desc}
          >
            <div className="sw-preset-dot" />
            <div className="sw-preset-label">{p.label}</div>
            <div className="sw-preset-desc">{p.desc}</div>
          </button>
        ))}
      </div>

      {/* Pro gate */}
      {!isPro ? (
        <div className="sw-upgrade-box">
          <div style={{ color: 'var(--accent)', display: 'flex' }}><IconLock /></div>
          <div style={{ color: 'var(--text-primary)', fontWeight: 700, fontSize: '16px' }}>Pro Feature</div>
          <div style={{ color: 'var(--text-tertiary)', fontSize: '13px', maxWidth: '380px', textAlign: 'center', lineHeight: 1.6 }}>
            Swing trading screeners with real-time RSI, DMA signals, volume analysis, and breakout detection require a Pro plan.
          </div>
          <a href="/pricing" style={{
            marginTop: '4px',
            background: 'linear-gradient(135deg, var(--accent-dark, #A8822E), var(--accent, #C9A34E))',
            color: '#000', padding: '10px 24px', borderRadius: '9px',
            fontWeight: 700, fontSize: '13px', textDecoration: 'none',
            display: 'flex', alignItems: 'center', gap: '6px',
          }}>
            Upgrade to Pro <IconChevronRight />
          </a>
        </div>
      ) : loading ? (
        <div className="sw-loading">
          <div className="sw-spinner" />
          <div style={{ textAlign: 'center' }}>
            <div style={{ color: 'var(--text-secondary)', fontWeight: 600, fontSize: '14px', marginBottom: '6px' }}>
              Running <strong style={{ color: 'var(--accent)' }}>{presetMeta?.label}</strong> scan
            </div>
            <div style={{ color: 'var(--text-tertiary)', fontSize: '12px', marginBottom: '16px', fontFamily: 'var(--font-mono)' }}>
              Analysing 300+ NSE stocks with real-time OHLCV data — {elapsed}s
            </div>
            <div className="sw-progress-bar">
              <div className="sw-progress-fill" style={{ width: `${Math.min(95, (elapsed / 35) * 100)}%` }} />
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: '11px', marginTop: '10px', fontFamily: 'var(--font-mono)' }}>
              First run ~30s · Cached 30 min after
            </div>
          </div>
        </div>
      ) : error ? (
        <div style={{
          padding: '16px', background: 'rgba(229,72,77,0.07)', border: '1px solid rgba(229,72,77,0.18)',
          borderRadius: '12px', color: '#fca5a5', fontSize: '13px',
          display: 'flex', alignItems: 'center', gap: '10px',
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          {error}
          <button onClick={() => fetchPreset(selectedPreset)} style={{
            marginLeft: '8px', background: 'rgba(229,72,77,0.12)',
            border: '1px solid rgba(229,72,77,0.25)', color: '#fca5a5',
            padding: '4px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px',
          }}>Retry</button>
        </div>
      ) : (
        <>
          {/* Results header */}
          {meta && (
            <div className="sw-results-header">
              <div>
                <div className="sw-result-title">{meta.label}</div>
                <div className="sw-result-desc">{meta.description}</div>
              </div>
              <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
                {fetchTime != null && (
                  <span style={{ color: 'var(--gain)', fontSize: '11px', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                    {fetchTime}s
                  </span>
                )}
                <span className="sw-result-badge" style={{
                  background: `color-mix(in srgb, ${presetMeta?.color} 12%, transparent)`,
                  color: presetMeta?.color,
                  border: `1px solid color-mix(in srgb, ${presetMeta?.color} 28%, transparent)`,
                }}>
                  {sorted.length} stocks
                </span>
                <button
                  onClick={() => fetchPreset(selectedPreset)}
                  style={{
                    background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border)',
                    color: 'var(--text-secondary)', padding: '5px 10px', borderRadius: '7px',
                    cursor: 'pointer', fontSize: '12px', fontWeight: 600, display: 'flex',
                    alignItems: 'center', gap: '5px',
                  }}
                >
                  <IconRefresh /> Refresh
                </button>
              </div>
            </div>
          )}

          {sorted.length === 0 ? (
            <div className="sw-empty">
              No stocks matched this filter right now. Try a different preset or refresh after market hours.
            </div>
          ) : (
            <div className="sw-table-wrap">
              <table className="sw-table">
                <thead>
                  <tr>
                    <th style={{ minWidth: 130 }}>Stock</th>
                    <th style={{ minWidth: 90 }} className={sortField === 'current_price' ? 'sorted' : ''} onClick={() => toggleSort('current_price')}>
                      Price {sortField === 'current_price' ? (sortDir === 'desc' ? '↓' : '↑') : '↕'}
                    </th>
                    <th style={{ minWidth: 80 }} className={sortField === 'change_pct_today' ? 'sorted' : ''} onClick={() => toggleSort('change_pct_today')}>
                      Today {sortField === 'change_pct_today' ? (sortDir === 'desc' ? '↓' : '↑') : '↕'}
                    </th>
                    <th style={{ minWidth: 90 }} className={sortField === 'pct_from_52h' ? 'sorted' : ''} onClick={() => toggleSort('pct_from_52h')}>
                      52W High {sortField === 'pct_from_52h' ? (sortDir === 'desc' ? '↓' : '↑') : '↕'}
                    </th>
                    <th style={{ minWidth: 70 }} className={sortField === 'rsi_14' ? 'sorted' : ''} onClick={() => toggleSort('rsi_14')}>
                      RSI(14) {sortField === 'rsi_14' ? (sortDir === 'desc' ? '↓' : '↑') : '↕'}
                    </th>
                    <th style={{ minWidth: 90 }} className={sortField === 'volume_ratio' ? 'sorted' : ''} onClick={() => toggleSort('volume_ratio')}>
                      Vol Ratio {sortField === 'volume_ratio' ? (sortDir === 'desc' ? '↓' : '↑') : '↕'}
                    </th>
                    <th style={{ minWidth: 120 }}>DMA Signal</th>
                    <th style={{ minWidth: 150 }}>Signal Tags</th>
                    <th style={{ minWidth: 100 }} className={sortField === 'swing_score' ? 'sorted' : ''} onClick={() => toggleSort('swing_score')}>
                      Swing Score {sortField === 'swing_score' ? (sortDir === 'desc' ? '↓' : '↑') : '↕'}
                    </th>
                    <th style={{ minWidth: 80 }} className={sortField === 'market_cap_cr' ? 'sorted' : ''} onClick={() => toggleSort('market_cap_cr')}>
                      Mkt Cap {sortField === 'market_cap_cr' ? (sortDir === 'desc' ? '↓' : '↑') : '↕'}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map(s => {
                    const chg = s.change_pct_today
                    const bar = scoreBar(s.swing_score)
                    const pctH = s.pct_from_52h
                    return (
                      <tr key={s.symbol}>
                        <td>
                          <div style={{ fontWeight: 800, color: 'var(--text-primary)', fontSize: '13px', fontFamily: 'var(--font-mono)' }}>{s.symbol}</div>
                          <div style={{ fontSize: '10px', color: 'var(--text-tertiary)', fontWeight: 400, marginTop: '2px', maxWidth: 130, overflow: 'hidden', textOverflow: 'ellipsis', fontFamily: 'var(--font-primary)' }}>
                            {s.company_name}
                          </div>
                          {s.sector && <div style={{ fontSize: '9px', color: 'var(--text-muted)', marginTop: '2px', fontFamily: 'var(--font-primary)', textTransform: 'uppercase', letterSpacing: '0.3px' }}>{s.sector}</div>}
                        </td>
                        <td style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                          {fmtPrice(s.current_price)}
                        </td>
                        <td style={{ color: chg == null ? 'var(--text-tertiary)' : chg >= 0 ? 'var(--gain)' : 'var(--loss)', fontWeight: 600 }}>
                          {chg != null ? fmtPct(chg) : '—'}
                        </td>
                        <td>
                          {pctH == null ? '—' : (
                            <span style={{ color: pctH <= 2 ? 'var(--gain)' : pctH <= 5 ? '#f59e0b' : 'var(--text-secondary)', fontWeight: pctH <= 5 ? 700 : 400 }}>
                              {pctH <= 0 ? 'ATH' : `-${pctH.toFixed(1)}%`}
                            </span>
                          )}
                        </td>
                        <td>
                          {s.rsi_14 != null ? (
                            <span style={{ color: rsiColor(s.rsi_14), fontWeight: 700 }}>
                              {s.rsi_14.toFixed(1)}
                            </span>
                          ) : '—'}
                        </td>
                        <td>
                          {s.volume_ratio != null ? (
                            <span style={{ color: s.volume_ratio >= 3 ? '#818cf8' : s.volume_ratio >= 2 ? '#a78bfa' : 'var(--text-tertiary)', fontWeight: s.volume_ratio >= 2 ? 700 : 400 }}>
                              {s.volume_ratio.toFixed(1)}×
                            </span>
                          ) : '—'}
                        </td>
                        <td>
                          <span style={{
                            fontSize: '11px',
                            color: s.dma_signal?.includes('20>50>200') ? '#10b981'
                              : s.dma_signal?.includes('Above 50') ? '#3b82f6'
                              : s.dma_signal?.includes('Above 200') ? '#f59e0b' : '#ef4444',
                            fontFamily: 'var(--font-primary)',
                          }}>
                            {s.dma_signal || '—'}
                          </span>
                        </td>
                        <td>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '3px' }}>
                            {(s.signal_tags || []).map((tag, i) => <TagPill key={i} tag={tag} />)}
                          </div>
                        </td>
                        <td>
                          {bar ? (
                            <div className="sw-score-bar-wrap">
                              <div className="sw-score-bar-track">
                                <div className="sw-score-bar-fill" style={{ width: bar.width, background: bar.color }} />
                              </div>
                              <span style={{ color: bar.color, fontWeight: 700, fontSize: '12px' }}>
                                {s.swing_score}
                              </span>
                            </div>
                          ) : '—'}
                        </td>
                        <td style={{ color: 'var(--text-tertiary)' }}>
                          {s.market_cap_cr != null
                            ? s.market_cap_cr >= 100000 ? `₹${(s.market_cap_cr / 100000).toFixed(1)}L Cr`
                              : s.market_cap_cr >= 1000 ? `₹${(s.market_cap_cr / 1000).toFixed(1)}K Cr`
                              : `₹${s.market_cap_cr.toFixed(0)} Cr`
                            : '—'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          {fetchedAt && (
            <div style={{ marginTop: '10px', fontSize: '11px', color: 'var(--text-muted)', textAlign: 'right', fontFamily: 'var(--font-mono)' }}>
              Data as of {new Date(fetchedAt).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })} · Cached 30 min · RSI & DMAs computed from 1Y daily OHLCV
            </div>
          )}
        </>
      )}
    </div>
  )
}
