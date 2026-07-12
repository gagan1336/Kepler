'use client'
import { useState, useEffect, useRef } from 'react'
import type {
  StockDetail, StockFundamentals, StockShareholding,
  StockInstitutionalHolder, StockNewsItem, StockAnalystVerdict,
} from '@/lib/api'
import { apiStockLive } from '@/lib/api'


// ── Helpers ───────────────────────────────────────────────────────────────────
function fmt(val: number | null | undefined, prefix = '', suffix = '', digits = 2): string {
  if (val === null || val === undefined) return '—'
  const n = Number(val)
  if (isNaN(n)) return '—'
  return `${prefix}${n.toLocaleString('en-IN', { minimumFractionDigits: digits, maximumFractionDigits: digits })}${suffix}`
}

function fmtCr(val: number | null | undefined): string {
  if (val === null || val === undefined) return '—'
  const n = Number(val)
  if (isNaN(n)) return '—'
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)} Lcr`
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(2)} L Cr`
  return `₹${n.toLocaleString('en-IN')} Cr`
}

function fmtVol(val: number | null | undefined): string {
  if (!val) return '—'
  if (val >= 1e7) return `${(val / 1e7).toFixed(2)}Cr`
  if (val >= 1e5) return `${(val / 1e5).toFixed(2)}L`
  if (val >= 1e3) return `${(val / 1e3).toFixed(1)}K`
  return String(val)
}

const VERDICT_STYLES: Record<string, { bg: string; border: string; text: string; badge: string }> = {
  'STRONG BUY': {
    bg:     'bg-[rgba(0,196,140,0.07)]',
    border: 'border-[rgba(0,196,140,0.35)]',
    text:   'text-[#00C48C]',
    badge:  'bg-[rgba(0,196,140,0.15)] text-[#00C48C] border-[rgba(0,196,140,0.4)]',
  },
  'BUY': {
    bg:     'bg-[rgba(74,222,128,0.07)]',
    border: 'border-[rgba(74,222,128,0.3)]',
    text:   'text-[#4ade80]',
    badge:  'bg-[rgba(74,222,128,0.12)] text-[#4ade80] border-[rgba(74,222,128,0.35)]',
  },
  'HOLD': {
    bg:     'bg-[rgba(245,158,11,0.07)]',
    border: 'border-[rgba(245,158,11,0.3)]',
    text:   'text-[#f59e0b]',
    badge:  'bg-[rgba(245,158,11,0.12)] text-[#f59e0b] border-[rgba(245,158,11,0.35)]',
  },
  'WEAK': {
    bg:     'bg-[rgba(251,146,60,0.07)]',
    border: 'border-[rgba(251,146,60,0.3)]',
    text:   'text-[#fb923c]',
    badge:  'bg-[rgba(251,146,60,0.12)] text-[#fb923c] border-[rgba(251,146,60,0.35)]',
  },
  'AVOID': {
    bg:     'bg-[rgba(239,68,68,0.07)]',
    border: 'border-[rgba(239,68,68,0.3)]',
    text:   'text-[#ef4444]',
    badge:  'bg-[rgba(239,68,68,0.12)] text-[#ef4444] border-[rgba(239,68,68,0.35)]',
  },
}

const VERDICT_ICONS: Record<string, string> = {
  'STRONG BUY': '🚀',
  'BUY':        '📈',
  'HOLD':       '⚖️',
  'WEAK':       '⚠️',
  'AVOID':      '🚫',
  'INSUFFICIENT DATA': '📊',
}

// ── Sub-components ─────────────────────────────────────────────────────────────
function MetricCard({ label, value, sub, highlight }: {
  label: string; value: string; sub?: string; highlight?: boolean
}) {
  return (
    <div className={`rounded-xl p-4 border ${highlight ? 'border-[rgba(0,196,140,0.25)] bg-[rgba(0,196,140,0.04)]' : 'border-[#1e1e1e] bg-[#111]'}`}>
      <p className="text-[12px] font-bold tracking-widest uppercase text-[#555] mb-1">{label}</p>
      <p className={`text-lg font-black ${highlight ? 'text-[#00C48C]' : 'text-white'}`}>{value}</p>
      {sub && <p className="text-[12px] text-[#444] mt-0.5">{sub}</p>}
    </div>
  )
}

function ShareholdingBar({ label, pct, color }: { label: string; pct: number | null; color: string }) {
  const val = pct ?? 0
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-[#888]">{label}</span>
        <span className={`text-xs font-black ${color}`}>{pct !== null ? `${pct}%` : '—'}</span>
      </div>
      <div className="h-2 rounded-full bg-[#1a1a1a] overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${color.replace('text-', 'bg-')}`}
          style={{ width: `${Math.min(val, 100)}%` }}
        />
      </div>
    </div>
  )
}

function SectionHeader({ icon, title }: { icon: string; title: string }) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <span className="text-lg">{icon}</span>
      <h3 className="text-sm font-black tracking-widest uppercase text-[#555]">{title}</h3>
    </div>
  )
}

// ── Main Panel ─────────────────────────────────────────────────────────────────
export default function StockDetailPanel({ stock, onBack }: {
  stock: StockDetail
  onBack: () => void
}) {
  const [showFullDesc, setShowFullDesc] = useState(false)


  const f = stock.fundamentals || {}
  const s = stock.shareholding || {}
  const verdict = stock.analyst_verdict || {}
  const vs = VERDICT_STYLES[verdict.verdict] || VERDICT_STYLES['HOLD']

  const rangePos = stock.week_52_high && stock.week_52_low && stock.current_price
    ? Math.max(0, Math.min(100,
        ((stock.current_price - stock.week_52_low) / (stock.week_52_high - stock.week_52_low)) * 100
      ))
    : null

  // ── Live price refresh ─────────────────────────────────────────────────────
  const [livePrice, setLivePrice]     = useState<number | null>(stock.current_price)
  const [liveChange, setLiveChange]   = useState<number | null>(stock.change)
  const [livePct, setLivePct]         = useState<number | null>(stock.change_pct)
  const [isLive, setIsLive]           = useState(false)
  const liveRef = useRef<NodeJS.Timeout | null>(null)

  // Market hours: Mon–Fri 9:15–15:30 IST
  function isMarketOpen(): boolean {
    const now = new Date()
    const ist = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }))
    const day = ist.getDay() // 0=Sun, 6=Sat
    if (day === 0 || day === 6) return false
    const h = ist.getHours(), m = ist.getMinutes()
    const mins = h * 60 + m
    return mins >= 555 && mins <= 930  // 9:15=555, 15:30=930
  }

  useEffect(() => {
    if (!isMarketOpen()) return
    setIsLive(true)
    const refresh = async () => {
      try {
        const data = await apiStockLive(stock.symbol)
        if (data.current_price) {
          setLivePrice(data.current_price)
          setLiveChange(data.change)
          setLivePct(data.change_pct)
        }
      } catch {}
    }
    refresh()
    liveRef.current = setInterval(refresh, 60000) // refresh every 60s
    return () => { if (liveRef.current) clearInterval(liveRef.current) }
  }, [stock.symbol])

  const displayPrice  = livePrice ?? stock.current_price
  const displayChange = liveChange ?? stock.change
  const displayPct    = livePct ?? stock.change_pct
  const isPositive    = (displayChange ?? 0) >= 0
  const changeCls     = isPositive ? 'text-[#00C48C]' : 'text-[#ef4444]'
  const changeArrow   = isPositive ? '▲' : '▼'


  return (
    <div className="space-y-5 animate-fade-in">
      {/* Back button */}
      <button
        onClick={onBack}
        className="flex items-center gap-2 text-sm text-[#555] hover:text-white transition-colors group"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M10 3L5 8L10 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Back to Search
      </button>

      {/* ── Price Card ─────────────────────────────────────────────────────────── */}
      <div className="glass-card p-6">
        <div className="flex flex-wrap items-start justify-between gap-4 mb-5">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-[#1a1a1a] text-[#555] border border-[#222]">
                {stock.exchange || 'NSE'}
              </span>
              <span className="text-xs text-[#444] font-mono">{stock.symbol}</span>
              {stock.sector_yf && (
                <span className="text-xs text-[#444] hidden sm:block">· {stock.sector_yf}</span>
              )}
            </div>
            <h2 className="text-2xl font-black text-white leading-tight">{stock.company_name}</h2>
            {stock.industry_yf && (
              <p className="text-xs text-[#555] mt-1">{stock.industry_yf}</p>
            )}
          </div>

            <div className="text-right">
              <div className="flex items-end gap-2 justify-end">
                <div className="text-3xl font-black text-white tabular-nums">
                  {displayPrice != null ? `₹${displayPrice.toLocaleString('en-IN')}` : '—'}
                </div>
                {isLive && (
                  <span className="flex items-center gap-1 text-[11px] font-black text-[#00C48C] bg-[rgba(0,196,140,0.12)] border border-[rgba(0,196,140,0.3)] px-1.5 py-0.5 rounded-full mb-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#00C48C] animate-pulse inline-block" />
                    LIVE
                  </span>
                )}
              </div>
              <div className={`flex items-center gap-1 justify-end mt-1 text-sm font-bold ${changeCls}`}>
                <span>{changeArrow}</span>
                <span>{displayChange != null ? Math.abs(displayChange).toFixed(2) : '—'}</span>
                <span className="text-xs">
                  ({displayPct != null ? `${Math.abs(displayPct).toFixed(2)}%` : '—'})
                </span>
              </div>
            </div>

        </div>

        {/* Day range */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5 text-sm">
          <div>
            <p className="text-[12px] text-[#444] uppercase tracking-widest mb-0.5">Day Low</p>
            <p className="text-white font-semibold">{fmt(stock.day_low, '₹', '', 2)}</p>
          </div>
          <div>
            <p className="text-[12px] text-[#444] uppercase tracking-widest mb-0.5">Day High</p>
            <p className="text-white font-semibold">{fmt(stock.day_high, '₹', '', 2)}</p>
          </div>
          <div>
            <p className="text-[12px] text-[#444] uppercase tracking-widest mb-0.5">Volume</p>
            <p className="text-white font-semibold">{fmtVol(stock.volume)}</p>
          </div>
          <div>
            <p className="text-[12px] text-[#444] uppercase tracking-widest mb-0.5">Avg Vol</p>
            <p className="text-white font-semibold">{fmtVol(stock.avg_volume)}</p>
          </div>
        </div>

        {/* 52W range bar */}
        {rangePos !== null && (
          <div>
            <div className="flex justify-between text-[12px] text-[#444] mb-1">
              <span>52W Low: {fmt(stock.week_52_low, '₹', '', 2)}</span>
              <span>52W High: {fmt(stock.week_52_high, '₹', '', 2)}</span>
            </div>
            <div className="relative h-2 bg-[#1a1a1a] rounded-full overflow-visible">
              <div
                className="absolute h-full bg-gradient-to-r from-[#ef4444] via-[#f59e0b] to-[#00C48C] rounded-full opacity-30"
                style={{ width: '100%' }}
              />
              <div
                className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-white border-2 border-[#00C48C] shadow-lg shadow-[#00C48C]/30 transition-all"
                style={{ left: `calc(${rangePos}% - 6px)` }}
              />
            </div>
            <p className="text-[12px] text-[#444] text-right mt-1">
              {rangePos.toFixed(0)}% of 52W range
            </p>
          </div>
        )}

        {/* Description */}
        {stock.description && (
          <div className="mt-5 pt-5 border-t border-[#1e1e1e]">
            <p className="text-xs text-[#555] leading-relaxed">
              {showFullDesc ? stock.description : stock.description.slice(0, 200) + (stock.description.length > 200 ? '...' : '')}
            </p>
            {stock.description.length > 200 && (
              <button
                onClick={() => setShowFullDesc(!showFullDesc)}
                className="text-[11px] text-[#00C48C] mt-1 hover:underline"
              >
                {showFullDesc ? 'Show less' : 'Read more'}
              </button>
            )}
          </div>
        )}
      </div>

      {/* ── Analyst Verdict ───────────────────────────────────────────────────── */}
      {verdict.verdict && (
        <div className={`rounded-2xl p-5 border ${vs.bg} ${vs.border}`}>
          <div className="flex items-start justify-between gap-3 mb-4">
            <div>
              <SectionHeader icon="🧠" title="Antigravity Analyst Verdict" />
              <div className="flex items-center gap-2">
                <span className="text-2xl">{VERDICT_ICONS[verdict.verdict] || '📊'}</span>
                <span className={`text-xl font-black tracking-wide ${vs.text}`}>{verdict.verdict}</span>
                <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full border ${vs.badge}`}>
                  Score: {verdict.score}/{verdict.max_score}
                </span>
              </div>
            </div>
          </div>

          <p className="text-sm text-[#aaa] leading-relaxed mb-4">{verdict.summary}</p>

          <div className="grid sm:grid-cols-2 gap-4 mb-4">
            {verdict.insights?.length > 0 && (
              <div>
                <p className="text-[12px] font-black tracking-widest uppercase text-[#00C48C] mb-2">✅ Strengths</p>
                <ul className="space-y-1.5">
                  {verdict.insights.map((insight, i) => (
                    <li key={i} className="text-xs text-[#888] flex gap-2">
                      <span className="text-[#00C48C] mt-0.5 shrink-0">•</span>
                      {insight}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {verdict.risks?.length > 0 && (
              <div>
                <p className="text-[12px] font-black tracking-widest uppercase text-[#ef4444] mb-2">⚠️ Watch Out</p>
                <ul className="space-y-1.5">
                  {verdict.risks.map((risk, i) => (
                    <li key={i} className="text-xs text-[#888] flex gap-2">
                      <span className="text-[#ef4444] mt-0.5 shrink-0">•</span>
                      {risk}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <p className="text-[10px] text-[#333] border-t border-[#1e1e1e] pt-3">{verdict.disclaimer}</p>
        </div>
      )}

      {/* ── Financial Summary ──────────────────────────────────────────────────── */}
      <div className="glass-card p-5">
        <SectionHeader icon="💰" title="Financial Summary" />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <MetricCard label="P/E Ratio" value={fmt(f.pe_ratio, '', 'x', 1)} sub="Price to Earnings" />
          <MetricCard label="P/B Ratio" value={fmt(f.pb_ratio, '', 'x', 1)} sub="Price to Book" />
          <MetricCard label="ROE" value={fmt(f.roe, '', '%', 1)} sub="Return on Equity" highlight={!!(f.roe && f.roe >= 15)} />
          <MetricCard label="ROCE" value={fmt(f.roce, '', '%', 1)} sub="Return on Capital" highlight={!!(f.roce && f.roce >= 15)} />
          <MetricCard label="Debt / Equity" value={fmt(f.debt_to_equity, '', 'x', 2)} sub="Leverage ratio" />
          <MetricCard label="Div. Yield" value={fmt(f.dividend_yield, '', '%', 2)} sub="Annual dividend %" />
          <MetricCard
            label="Market Cap"
            value={f.market_cap != null ? fmtCr(f.market_cap) : (stock.market_cap_yf ? fmtCr(stock.market_cap_yf / 1e7) : '—')}
            sub="Total market value"
          />
          <MetricCard label="EPS" value={fmt((f as any).eps ?? stock.eps, '₹', '', 2)} sub="Earnings per Share" />
        </div>

        {/* Growth */}
        {(f.revenue_growth_3yr != null || f.profit_growth_3yr != null || f.revenue_growth_1yr != null) && (
          <div className="mt-4 pt-4 border-t border-[#1e1e1e]">
            <p className="text-[12px] font-black tracking-widest uppercase text-[#555] mb-3">Growth Metrics</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {f.revenue_growth_1yr != null && (
                <MetricCard
                  label="Revenue (1Y)"
                  value={fmt(f.revenue_growth_1yr, '', '%', 1)}
                  sub="YoY growth"
                  highlight={!!(f.revenue_growth_1yr && f.revenue_growth_1yr >= 10)}
                />
              )}
              {f.profit_growth_1yr != null && (
                <MetricCard
                  label="Earnings (1Y)"
                  value={fmt(f.profit_growth_1yr, '', '%', 1)}
                  sub="YoY growth"
                  highlight={!!(f.profit_growth_1yr && f.profit_growth_1yr >= 10)}
                />
              )}
              {f.revenue_growth_3yr != null && (
                <MetricCard
                  label="Revenue (3Y CAGR)"
                  value={fmt(f.revenue_growth_3yr, '', '%', 1)}
                  sub="3Y Compounded"
                  highlight={!!(f.revenue_growth_3yr && f.revenue_growth_3yr >= 12)}
                />
              )}
              {f.profit_growth_3yr != null && (
                <MetricCard
                  label="Profit (3Y CAGR)"
                  value={fmt(f.profit_growth_3yr, '', '%', 1)}
                  sub="3Y Compounded"
                  highlight={!!(f.profit_growth_3yr && f.profit_growth_3yr >= 12)}
                />
              )}
            </div>
          </div>
        )}

        {/* Margins row */}
        {(f.profit_margin != null || f.operating_margin != null || f.roa != null || f.forward_pe != null) && (
          <div className="mt-4 pt-4 border-t border-[#1e1e1e]">
            <p className="text-[12px] font-black tracking-widest uppercase text-[#555] mb-3">Profitability & Efficiency</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {f.profit_margin != null && (
                <MetricCard label="Net Margin" value={fmt(f.profit_margin, '', '%', 1)} sub="Profit / Revenue" />
              )}
              {f.operating_margin != null && (
                <MetricCard label="Op. Margin" value={fmt(f.operating_margin, '', '%', 1)} sub="EBIT / Revenue" />
              )}
              {f.roa != null && (
                <MetricCard label="ROA" value={fmt(f.roa, '', '%', 1)} sub="Return on Assets" />
              )}
              {f.forward_pe != null && (
                <MetricCard label="Forward PE" value={fmt(f.forward_pe, '', 'x', 1)} sub="Next 12M earnings" />
              )}
            </div>
          </div>
        )}

        {/* Beta */}
        {stock.beta != null && (
          <div className="mt-3 flex items-center gap-2">
            <span className="text-xs text-[#555]">Beta: <span className="text-white font-semibold">{stock.beta}</span></span>
            <span className="text-[10px] text-[#333]">
              {stock.beta > 1.3 ? '— High volatility vs market' : stock.beta < 0.7 ? '— Low volatility vs market' : '— Similar to market'}
            </span>
          </div>
        )}

        {/* Data source */}
        <div className="mt-3 pt-3 border-t border-[#1e1e1e] flex items-center gap-2">
          <span className="text-[11px] font-bold tracking-widest uppercase text-[#2d2d2d] bg-[#111] px-2 py-1 rounded">
            📡 Source: {f.source || 'yfinance'} · cached 24h
          </span>
        </div>
      </div>

      {/* ── Shareholding Pattern ──────────────────────────────────────────────── */}
      {(s.promoter != null || s.fii != null || s.dii != null) && (
        <div className="glass-card p-5">
          <SectionHeader icon="🏦" title="Shareholding Pattern" />
          <div className="space-y-4">
            <ShareholdingBar label="Promoters" pct={s.promoter} color="text-[#00C48C]" />
            <ShareholdingBar label="FII / Foreign Institutions" pct={s.fii} color="text-[#60a5fa]" />
            <ShareholdingBar label="DII / Domestic Institutions" pct={s.dii} color="text-[#a78bfa]" />
            <ShareholdingBar label="Public / Retail" pct={s.public} color="text-[#f59e0b]" />
          </div>

          {/* FII Activity Signal */}
          {stock.fii_activity && stock.fii_activity.trend !== 'UNKNOWN' && (
            <div className="mt-5 p-3 rounded-xl bg-[#111] border border-[#1e1e1e]">
              <p className="text-[12px] font-black tracking-widest uppercase text-[#555] mb-1">FII Activity Signal</p>
              <p className="text-sm text-[#aaa]">{stock.fii_activity.note}</p>
            </div>
          )}
        </div>
      )}

      {/* ── Institutional Holders ─────────────────────────────────────────────── */}
      {stock.institutional_holders?.length > 0 && (
        <div className="glass-card p-5">
          <SectionHeader icon="🏢" title="Top Institutional Holders" />
          <div className="space-y-3">
            {stock.institutional_holders.map((h, i) => (
              <div key={i} className="flex items-center justify-between py-2.5 border-b border-[#111] last:border-0">
                <div className="flex items-center gap-3">
                  <div className="w-7 h-7 rounded-lg bg-[#111] border border-[#1e1e1e] flex items-center justify-center text-[10px] font-black text-[#555]">
                    {i + 1}
                  </div>
                  <p className="text-sm text-white font-medium">{h.holder}</p>
                </div>
                <div className="text-right">
                  {h.pct_held != null && (
                    <p className="text-sm font-bold text-[#00C48C]">{h.pct_held}%</p>
                  )}
                  {h.value_cr != null && (
                    <p className="text-[12px] text-[#444]">₹{h.value_cr.toLocaleString('en-IN')} Cr</p>
                  )}
                </div>
              </div>
            ))}
          </div>
          <p className="text-[12px] text-[#333] mt-3">Source: NSE regulatory filings via yfinance</p>
        </div>
      )}

      {/* ── Recent News ───────────────────────────────────────────────────────── */}
      {stock.recent_news?.length > 0 && (
        <div className="glass-card p-5">
          <SectionHeader icon="📰" title={`Recent News — ${stock.company_name}`} />
          <div className="space-y-3">
            {stock.recent_news.map((item, i) => (
              <a
                key={i}
                href={item.url || '#'}
                target="_blank"
                rel="noopener noreferrer"
                className="block p-3.5 rounded-xl bg-[#111] border border-[#1a1a1a] hover:border-[#00C48C]/30 hover:bg-[#131313] transition-all group"
              >
                <div className="flex items-start gap-3">
                  <div className="shrink-0 mt-0.5">
                    <div className="w-8 h-8 rounded-lg bg-[#1a1a1a] border border-[#222] flex items-center justify-center text-sm">
                      📄
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white font-medium leading-snug group-hover:text-[#00C48C] transition-colors line-clamp-2">
                      {item.title}
                    </p>
                    <div className="flex items-center gap-2 mt-1.5">
                      {item.source && (
                        <span className="text-[12px] font-semibold text-[#555]">{item.source}</span>
                      )}
                      {item.published_at && (
                        <>
                          <span className="text-[#333] text-[12px]">·</span>
                          <span className="text-[12px] text-[#444]">{item.published_at}</span>
                        </>
                      )}
                    </div>
                  </div>
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="shrink-0 text-[#333] group-hover:text-[#00C48C] transition-colors mt-1">
                    <path d="M2 10L10 2M10 2H4M10 2V8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Empty news state */}
      {(!stock.recent_news || stock.recent_news.length === 0) && (
        <div className="glass-card p-5">
          <SectionHeader icon="📰" title="Recent News" />
          <p className="text-sm text-[#444] text-center py-4">No recent news found for {stock.symbol}</p>
        </div>
      )}

      {/* ── EXCLUSIVE: Graham Number ────────────────────────────────────────── */}
      {stock.graham_number && (
        <div className="glass-card p-5">
          <SectionHeader icon="📐" title="Intrinsic Value — Graham Number" />
          <div className="flex flex-wrap gap-4 items-center">
            <div className="flex-1 min-w-[140px]">
              <p className="text-[12px] text-[#555] uppercase tracking-widest mb-1">Graham Number</p>
              <p className="text-2xl font-black text-white">
                {stock.graham_number.graham_number != null ? `₹${stock.graham_number.graham_number.toLocaleString('en-IN')}` : '—'}
              </p>
              <p className="text-[12px] text-[#444] mt-1">
                Based on EPS ₹{stock.graham_number.eps_used} × BVPS ₹{stock.graham_number.bvps_used}
              </p>
            </div>
            {stock.graham_number.premium_pct != null && (
              <div className={`rounded-xl px-5 py-3 border text-center ${
                stock.graham_number.is_undervalued
                  ? 'bg-[rgba(0,196,140,0.07)] border-[rgba(0,196,140,0.25)]'
                  : 'bg-[rgba(239,68,68,0.07)] border-[rgba(239,68,68,0.25)]'
              }`}>
                <p className="text-[12px] uppercase tracking-widest text-[#555] mb-1">
                  {stock.graham_number.is_undervalued ? 'Undervalued' : 'Premium to Graham'}
                </p>
                <p className={`text-2xl font-black ${stock.graham_number.is_undervalued ? 'text-[#00C48C]' : 'text-[#ef4444]'}`}>
                  {Math.abs(stock.graham_number.premium_pct).toFixed(1)}%
                </p>
                <p className="text-[12px] text-[#444] mt-1">
                  {stock.graham_number.is_undervalued ? 'Below fair value' : 'Above fair value'}
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── EXCLUSIVE: Piotroski F-Score ────────────────────────────────────── */}
      {stock.piotroski && stock.piotroski.score !== null && (
        <div className="glass-card p-5">
          <SectionHeader icon="🎯" title="Piotroski F-Score — Accounting Quality" />
          <div className="flex items-start gap-5 flex-wrap">
            {/* Score Badge */}
            <div className={`rounded-2xl px-6 py-4 text-center border flex-shrink-0 ${
              stock.piotroski.score >= 8 ? 'bg-[rgba(0,196,140,0.08)] border-[rgba(0,196,140,0.3)]' :
              stock.piotroski.score >= 6 ? 'bg-[rgba(74,222,128,0.08)] border-[rgba(74,222,128,0.25)]' :
              stock.piotroski.score >= 3 ? 'bg-[rgba(245,158,11,0.08)] border-[rgba(245,158,11,0.25)]' :
              'bg-[rgba(239,68,68,0.08)] border-[rgba(239,68,68,0.25)]'
            }`}>
              <p className="text-[12px] text-[#555] uppercase tracking-widest mb-1">F-Score</p>
              <p className={`text-4xl font-black ${
                stock.piotroski.score >= 8 ? 'text-[#00C48C]' :
                stock.piotroski.score >= 6 ? 'text-[#4ade80]' :
                stock.piotroski.score >= 3 ? 'text-[#f59e0b]' : 'text-[#ef4444]'
              }`}>{stock.piotroski.score}<span className="text-lg text-[#333]">/9</span></p>
            </div>
            {/* Signals */}
            <div className="flex-1 min-w-[200px]">
              <p className="text-xs text-[#555] mb-3">{stock.piotroski.interpretation}</p>
              <div className="grid grid-cols-1 gap-1.5">
                {stock.piotroski.signals.map((sig, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className={`text-xs ${sig.pass ? 'text-[#00C48C]' : 'text-[#333]'}`}>
                      {sig.pass ? '✓' : '✗'}
                    </span>
                    <span className={`text-[12px] ${sig.pass ? 'text-[#aaa]' : 'text-[#333]'}`}>{sig.name}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── EXCLUSIVE: Altman Z-Score ───────────────────────────────────────── */}
      {stock.altman_z && stock.altman_z.z_score !== null && (
        <div className="glass-card p-5">
          <SectionHeader icon="⚡" title="Altman Z-Score — Financial Distress Risk" />
          <div className="flex items-center gap-5 flex-wrap">
            <div className="rounded-2xl px-6 py-4 border text-center flex-shrink-0"
              style={{ borderColor: stock.altman_z.zone_color + '55', background: stock.altman_z.zone_color + '11' }}>
              <p className="text-[12px] text-[#555] uppercase tracking-widest mb-1">Z-Score</p>
              <p className="text-4xl font-black" style={{ color: stock.altman_z.zone_color }}>
                {stock.altman_z.z_score.toFixed(2)}
              </p>
            </div>
            <div>
              <p className="text-sm font-bold text-white mb-1" style={{ color: stock.altman_z.zone_color }}>
                {stock.altman_z.zone}
              </p>
              <p className="text-xs text-[#555] mb-3">{stock.altman_z.zone_desc}</p>
              <div className="flex gap-3 text-[12px]">
                <span className="text-[#ef4444]">▸ &lt;1.1 Distress</span>
                <span className="text-[#f59e0b]">▸ 1.1–2.6 Grey</span>
                <span className="text-[#00C48C]">▸ &gt;2.6 Safe</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── EXCLUSIVE: Earnings Surprise ────────────────────────────────────── */}
      {stock.earnings_surprise && stock.earnings_surprise.length > 0 && (
        <div className="glass-card p-5">
          <SectionHeader icon="📊" title="Earnings Surprise — Last 4 Quarters" />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {stock.earnings_surprise.map((q, i) => (
              <div key={i} className={`rounded-xl p-3 border ${
                q.beat
                  ? 'bg-[rgba(0,196,140,0.06)] border-[rgba(0,196,140,0.2)]'
                  : 'bg-[rgba(239,68,68,0.06)] border-[rgba(239,68,68,0.2)]'
              }`}>
                <p className="text-[12px] text-[#444] mb-1">{q.quarter}</p>
                <p className={`text-base font-black ${q.beat ? 'text-[#00C48C]' : 'text-[#ef4444]'}`}>
                  {q.beat ? '+' : ''}{q.surprise_pct.toFixed(1)}%
                </p>
                <p className="text-[12px] text-[#444] mt-0.5">
                  {q.beat ? 'Beat' : 'Miss'} · ₹{q.actual} vs ₹{q.estimate}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Data freshness ────────────────────────────────────────────────────── */}
      <p className="text-[10px] text-[#2a2a2a] text-center pb-2">
        Data fetched: {stock.fetched_at ? new Date(stock.fetched_at).toLocaleString('en-IN') : 'Unknown'} · Cached up to 4 hours
      </p>

    </div>
  )
}
