'use client'
import { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import Link from 'next/link'
import Navbar from '@/components/Navbar'
import Disclaimer from '@/components/Disclaimer'
import { apiDeepDiveDetail } from '@/lib/api'
import { useAuth } from '@/lib/auth'

// ── Verdict config ─────────────────────────────────────────────────────────────
const VERDICT_CONFIG = {
  BUY:   { label: 'BUY',   gradient: 'from-[#00C48C]/20 to-transparent', border: 'border-[rgba(0,196,140,0.3)]',  text: 'text-[#00C48C]',  badge: 'bg-[rgba(0,196,140,0.12)] border-[rgba(0,196,140,0.3)]' },
  HOLD:  { label: 'HOLD',  gradient: 'from-[#f59e0b]/20 to-transparent', border: 'border-[rgba(245,158,11,0.3)]', text: 'text-[#f59e0b]',  badge: 'bg-[rgba(245,158,11,0.12)] border-[rgba(245,158,11,0.3)]' },
  AVOID: { label: 'AVOID', gradient: 'from-[#ef4444]/20 to-transparent', border: 'border-[rgba(239,68,68,0.3)]',  text: 'text-[#ef4444]',  badge: 'bg-[rgba(239,68,68,0.12)] border-[rgba(239,68,68,0.3)]' },
}

const RISK_CONFIG = {
  LOW:    { label: 'Low Risk',   color: 'text-[#00C48C]', bg: 'bg-[rgba(0,196,140,0.08)]' },
  MEDIUM: { label: 'Medium Risk', color: 'text-[#f59e0b]', bg: 'bg-[rgba(245,158,11,0.08)]' },
  HIGH:   { label: 'High Risk',  color: 'text-[#ef4444]', bg: 'bg-[rgba(239,68,68,0.08)]' },
}

const SIGNAL_CONFIG = {
  POSITIVE: { color: 'text-[#00C48C]', icon: '▲' },
  NEGATIVE: { color: 'text-[#ef4444]', icon: '▼' },
  NEUTRAL:  { color: 'text-[#888]',    icon: '─' },
}

// ── Helper: format INR ─────────────────────────────────────────────────────────
function fmtINR(val: any) {
  if (val == null) return 'N/A'
  const n = Number(val)
  if (isNaN(n)) return 'N/A'
  if (n >= 100000) return `₹${(n / 100000).toFixed(1)}L Cr`
  if (n >= 1000)   return `₹${Math.round(n).toLocaleString('en-IN')} Cr`
  return `₹${n.toFixed(0)}`
}

function fmt(val: any, suffix = '', decimals = 1) {
  if (val == null) return 'N/A'
  const n = Number(val)
  if (isNaN(n)) return 'N/A'
  return `${n.toFixed(decimals)}${suffix}`
}

// ── Metric Tile ────────────────────────────────────────────────────────────────
function MetricTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="glass-card p-4 flex flex-col gap-0.5">
      <span className="text-[11px] font-bold uppercase tracking-widest text-[#444]">{label}</span>
      <span className="text-xl font-black text-white mt-1">{value}</span>
      {sub && <span className="text-[11px] text-[#555]">{sub}</span>}
    </div>
  )
}

// ── Shareholding Bar ───────────────────────────────────────────────────────────
function ShareholdingBar({ label, pct, color }: { label: string; pct: number; color: string }) {
  return (
    <div>
      <div className="flex justify-between mb-1">
        <span className="text-xs text-[#666]">{label}</span>
        <span className="text-xs font-bold text-white">{pct.toFixed(1)}%</span>
      </div>
      <div className="h-1.5 bg-[#111] rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${Math.min(pct, 100)}%`, backgroundColor: color }}
        />
      </div>
    </div>
  )
}

// ── Section renderer ───────────────────────────────────────────────────────────
function SectionCard({ section, index }: { section: any; index: number }) {
  const [open, setOpen] = useState(index < 2)

  return (
    <div className="glass-card overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-6 py-4 hover:bg-[#0f0f0f] transition-colors text-left"
      >
        <h2 className="text-base font-bold text-white">{section.title}</h2>
        <svg
          width="16" height="16" viewBox="0 0 16 16" fill="none"
          className={`shrink-0 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        >
          <path d="M4 6l4 4 4-4" stroke="#555" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>

      {open && (
        <div className="px-6 pb-6 border-t border-[#111]">
          {/* Main text */}
          {section.content && (
            <p className="text-[#aaa] text-sm leading-relaxed mt-4">{section.content}</p>
          )}

          {/* Highlights (financial metrics) */}
          {section.highlights && section.highlights.length > 0 && (
            <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-2">
              {section.highlights.map((h: any, i: number) => {
                const sig = SIGNAL_CONFIG[h.signal as keyof typeof SIGNAL_CONFIG] || SIGNAL_CONFIG.NEUTRAL
                return (
                  <div key={i} className="bg-[#0c0c0c] border border-[#1a1a1a] rounded-lg p-3">
                    <span className="text-[11px] text-[#444] block">{h.label}</span>
                    <div className="flex items-center gap-1.5 mt-1">
                      <span className={`text-xs font-bold ${sig.color}`}>{sig.icon}</span>
                      <span className="text-sm font-bold text-white">{h.value}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* Risk flags */}
          {section.risk_flags && section.risk_flags.length > 0 && (
            <div className="mt-4 space-y-2">
              {section.risk_flags.map((flag: string, i: number) => (
                <div key={i} className="flex gap-2.5 items-start text-sm text-[#aaa]">
                  <span className="text-[#ef4444] mt-0.5 shrink-0">⚠</span>
                  <span>{flag}</span>
                </div>
              ))}
            </div>
          )}

          {/* Governance flags */}
          {section.flags && section.flags.length > 0 && (
            <div className="mt-4 space-y-2">
              {section.flags.map((flag: string, i: number) => (
                <div key={i} className="flex gap-2.5 items-start text-sm text-[#aaa]">
                  <span className="text-[#f59e0b] mt-0.5 shrink-0">◉</span>
                  <span>{flag}</span>
                </div>
              ))}
            </div>
          )}

          {/* Catalysts */}
          {section.catalysts && section.catalysts.length > 0 && (
            <div className="mt-4 space-y-2">
              {section.catalysts.map((c: string, i: number) => (
                <div key={i} className="flex gap-2.5 items-start text-sm text-[#aaa]">
                  <span className="text-[#00C48C] mt-0.5 shrink-0">▸</span>
                  <span>{c}</span>
                </div>
              ))}
            </div>
          )}

          {/* Verdict-specific stop-loss */}
          {section.id === 'verdict' && section.stop_loss && (
            <div className="mt-4 p-3 bg-[rgba(239,68,68,0.05)] border border-[rgba(239,68,68,0.15)] rounded-lg">
              <span className="text-xs text-[#ef4444] font-bold">Stop Loss: ₹{Number(section.stop_loss).toLocaleString('en-IN')}</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────────
export default function DeepDivePage() {
  const router = useRouter()
  const params = useParams()
  const id = params?.id as string

  const [dive, setDive] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const { isAuthenticated, loading: authLoading } = useAuth()

  useEffect(() => {
    if (authLoading) return
    if (!isAuthenticated) { router.push('/login'); return }
    if (!id) return

    apiDeepDiveDetail(id)
      .then(setDive)
      .catch((err) => {
        if (err.status === 403) setError('elite_only')
        else if (err.status === 404) setError('not_found')
        else setError('generic')
      })
      .finally(() => setLoading(false))
  }, [id])

  // ── Error / Loading states ───────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="min-h-screen bg-[#090909]">
        <Navbar />
        <div className="max-w-4xl mx-auto px-6 pt-28 pb-20 space-y-6 animate-pulse">
          <div className="h-4 w-24 bg-[#1e1e1e] rounded" />
          <div className="h-10 w-2/3 bg-[#1e1e1e] rounded" />
          <div className="grid grid-cols-4 gap-4">
            {[1,2,3,4].map(i => <div key={i} className="h-20 bg-[#1e1e1e] rounded-xl" />)}
          </div>
          {[1,2,3].map(i => <div key={i} className="h-24 bg-[#1e1e1e] rounded-xl" />)}
        </div>
      </div>
    )
  }

  if (error === 'elite_only') {
    return (
      <div className="min-h-screen bg-[#090909]"><Navbar />
        <div className="max-w-3xl mx-auto px-6 pt-28 pb-20">
          <div className="glass-card p-12 text-center">
            <div className="text-5xl mb-5">🔒</div>
            <h1 className="text-2xl font-black text-white mb-3">Elite Members Only</h1>
            <p className="text-[#555] text-sm mb-8 max-w-sm mx-auto">
              Deep Dive research reports are exclusive to Elite plan members. Upgrade to access long-form institutional-grade analysis.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Link href="/pricing?plan=elite" className="btn-brand">Upgrade to Elite →</Link>
              <Link href="/dashboard" className="btn-outline">Back to Dashboard</Link>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-[#090909]"><Navbar />
        <div className="max-w-3xl mx-auto px-6 pt-28 pb-20">
          <div className="glass-card p-12 text-center">
            <div className="text-5xl mb-5">{error === 'not_found' ? '🔍' : '⚠️'}</div>
            <h1 className="text-2xl font-black text-white mb-3">
              {error === 'not_found' ? 'Report Not Found' : 'Something went wrong'}
            </h1>
            <p className="text-[#555] text-sm mb-8">
              {error === 'not_found' ? "This deep dive doesn't exist or has been removed." : 'We couldn\'t load this report. Please try again.'}
            </p>
            <Link href="/dashboard?tab=deepdive" className="btn-brand">← All Deep Dives</Link>
          </div>
        </div>
      </div>
    )
  }

  // ── Render rich deep dive ────────────────────────────────────────────────────
  const m = dive?.metrics_snapshot || {}
  const verdict   = VERDICT_CONFIG[dive?.verdict as keyof typeof VERDICT_CONFIG]
  const riskCfg   = RISK_CONFIG[dive?.risk_rating as keyof typeof RISK_CONFIG]
  const dateStr   = new Date(dive?.created_at).toLocaleDateString('en-IN', {
    day: 'numeric', month: 'long', year: 'numeric',
  })

  const promoter = m.promoter_holding
  const fii      = m.fii_holding
  const dii      = m.dii_holding
  const publicF  = (promoter != null && fii != null && dii != null)
    ? Math.max(0, 100 - promoter - fii - dii)
    : null

  const hasSections = dive?.sections && dive.sections.length > 0
  const hasShareholding = promoter != null

  return (
    <div className="min-h-screen bg-[#090909]">
      <Navbar />

      <div className="max-w-4xl mx-auto px-6 pt-28 pb-20">

        {/* Back */}
        <Link
          href="/dashboard?tab=deepdive"
          className="inline-flex items-center gap-2 text-sm text-[#444] hover:text-white transition-colors mb-8 group"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="group-hover:-translate-x-0.5 transition-transform">
            <path d="M10 12L6 8l4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          All Deep Dives
        </Link>

        {/* ── Hero ────────────────────────────────────────────────────────────── */}
        <div className={`glass-card p-8 mb-6 border bg-gradient-to-br ${verdict?.gradient || 'from-[#111]/20 to-transparent'} ${verdict?.border || 'border-[#1e1e1e]'}`}>
          {/* Badges row */}
          <div className="flex flex-wrap items-center gap-2 mb-4">
            <span className="badge badge-elite">ELITE — Deep Dive</span>
            {dive.symbol && (
              <span className="text-xs font-black text-white px-3 py-1 bg-[#111] border border-[#222] rounded-full tracking-widest">
                {dive.symbol}
              </span>
            )}
            {dive.sector && (
              <span className="text-xs text-[#666] px-3 py-1 bg-[#111] border border-[#1a1a1a] rounded-full">{dive.sector}</span>
            )}
            {riskCfg && (
              <span className={`text-xs font-bold px-2 py-1 rounded-full ${riskCfg.color} ${riskCfg.bg}`}>
                {riskCfg.label}
              </span>
            )}
            <span className="text-xs text-[#444] ml-auto">{dateStr}</span>
          </div>

          <h1 className="text-3xl md:text-4xl font-black text-white leading-tight mb-3">{dive.title}</h1>

          {dive.summary && (
            <p className="text-[#888] leading-relaxed text-sm max-w-2xl">{dive.summary}</p>
          )}

          {/* Verdict + Price Target */}
          {verdict && (
            <div className="mt-6 flex flex-wrap items-center gap-4">
              <div className={`flex items-center gap-3 px-5 py-3 rounded-xl border ${verdict.badge}`}>
                <span className={`text-2xl font-black ${verdict.text}`}>{verdict.label}</span>
                <div className="w-px h-6 bg-current opacity-20" />
                <div>
                  <p className="text-xs text-[#555]">12-Month Verdict</p>
                  <p className={`text-sm font-bold ${verdict.text}`}>
                    {dive.verdict === 'BUY' ? 'Accumulate on dips' : dive.verdict === 'HOLD' ? 'Hold current position' : 'Exit or avoid'}
                  </p>
                </div>
              </div>
              {dive.price_target_12m && (
                <div className="flex items-center gap-3 px-5 py-3 rounded-xl border border-[#1e1e1e] bg-[#0f0f0f]">
                  <div>
                    <p className="text-xs text-[#555]">Price Target (12M)</p>
                    <p className="text-2xl font-black text-white">₹{Number(dive.price_target_12m).toLocaleString('en-IN')}</p>
                  </div>
                  {m.current_price && (
                    <div>
                      <p className="text-xs text-[#555]">Current</p>
                      <p className="text-sm font-bold text-[#888]">₹{Number(m.current_price).toLocaleString('en-IN')}</p>
                      {/* Upside % */}
                      {dive.verdict === 'BUY' && (
                        <p className="text-xs text-[#00C48C] font-bold">
                          +{(((dive.price_target_12m - m.current_price) / m.current_price) * 100).toFixed(0)}% upside
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Key Metrics Grid ─────────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          <MetricTile label="PE Ratio"   value={fmt(m.pe_ratio, 'x')}        sub="Trailing" />
          <MetricTile label="ROE"        value={fmt(m.roe, '%')}              sub="Return on Equity" />
          <MetricTile label="ROCE"       value={fmt(m.roce, '%')}             sub="Return on Capital" />
          <MetricTile label="D/E Ratio"  value={fmt(m.debt_to_equity, '', 2)} sub="Debt/Equity" />
          <MetricTile label="Mkt Cap"    value={fmtINR(m.market_cap_cr)}      sub="Market Cap" />
          <MetricTile label="52W High"   value={m.high_52w ? `₹${Math.round(m.high_52w).toLocaleString('en-IN')}` : 'N/A'} />
          <MetricTile label="52W Low"    value={m.low_52w  ? `₹${Math.round(m.low_52w).toLocaleString('en-IN')}`  : 'N/A'} />
          <MetricTile label="Div Yield"  value={fmt(m.dividend_yield, '%')}   sub="Annual" />
        </div>

        {/* ── Growth Snapshot ──────────────────────────────────────────────────── */}
        {(m.revenue_growth_3yr != null || m.profit_growth_3yr != null) && (
          <div className="glass-card p-5 mb-6">
            <h3 className="text-xs font-bold uppercase tracking-widest text-[#444] mb-4">Growth Snapshot</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {m.revenue_growth_3yr != null && (
                <div className="text-center">
                  <p className={`text-2xl font-black ${m.revenue_growth_3yr >= 0 ? 'text-[#00C48C]' : 'text-[#ef4444]'}`}>
                    {m.revenue_growth_3yr >= 0 ? '+' : ''}{m.revenue_growth_3yr.toFixed(1)}%
                  </p>
                  <p className="text-xs text-[#555] mt-1">3yr Revenue CAGR</p>
                </div>
              )}
              {m.profit_growth_3yr != null && (
                <div className="text-center">
                  <p className={`text-2xl font-black ${m.profit_growth_3yr >= 0 ? 'text-[#00C48C]' : 'text-[#ef4444]'}`}>
                    {m.profit_growth_3yr >= 0 ? '+' : ''}{m.profit_growth_3yr.toFixed(1)}%
                  </p>
                  <p className="text-xs text-[#555] mt-1">3yr PAT CAGR</p>
                </div>
              )}
              {m.profit_margin != null && (
                <div className="text-center">
                  <p className="text-2xl font-black text-white">{m.profit_margin.toFixed(1)}%</p>
                  <p className="text-xs text-[#555] mt-1">Net Margin</p>
                </div>
              )}
              {m.operating_margin != null && (
                <div className="text-center">
                  <p className="text-2xl font-black text-white">{m.operating_margin.toFixed(1)}%</p>
                  <p className="text-xs text-[#555] mt-1">Oper. Margin</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Shareholding Pattern ─────────────────────────────────────────────── */}
        {hasShareholding && (
          <div className="glass-card p-5 mb-6">
            <h3 className="text-xs font-bold uppercase tracking-widest text-[#444] mb-4">Shareholding Pattern</h3>
            <div className="space-y-3">
              {promoter != null && <ShareholdingBar label="Promoter"  pct={promoter} color="#00C48C" />}
              {fii      != null && <ShareholdingBar label="FII"       pct={fii}      color="#60a5fa" />}
              {dii      != null && <ShareholdingBar label="DII"       pct={dii}      color="#a78bfa" />}
              {publicF  != null && <ShareholdingBar label="Public"    pct={publicF}  color="#6b7280" />}
            </div>
            <p className="text-[11px] text-[#333] mt-3">* FII/DII split is estimated from institutional total. Verify on BSE for exact figures.</p>
          </div>
        )}

        {/* ── Structured Sections ─────────────────────────────────────────────── */}
        {hasSections && (
          <div className="space-y-3 mb-8">
            {dive.sections.map((section: any, i: number) => (
              <SectionCard key={section.id || i} section={section} index={i} />
            ))}
          </div>
        )}

        {/* ── Legacy plain-text fallback ───────────────────────────────────────── */}
        {!hasSections && dive?.content && (
          <div className="glass-card p-6 mb-8">
            <div className="prose-dark">
              {dive.content.split('\n').map((line: string, i: number) => {
                if (!line.trim()) return <div key={i} className="h-4" />
                if (line.startsWith('## ')) return <h2 key={i} className="text-xl font-bold text-white mt-8 mb-3">{line.replace(/^## /, '')}</h2>
                if (line.startsWith('# '))  return <h1 key={i} className="text-2xl font-black text-white mt-10 mb-4">{line.replace(/^# /, '')}</h1>
                if (line.startsWith('- ') || line.startsWith('• ')) return (
                  <div key={i} className="flex gap-3 text-[#aaa] text-sm leading-relaxed mb-1.5">
                    <span className="text-[#00C48C] mt-1 shrink-0">▸</span>
                    <span>{line.replace(/^[-•]\s/, '')}</span>
                  </div>
                )
                return <p key={i} className="text-[#aaa] leading-relaxed mb-2 text-[15px]">{line}</p>
              })}
            </div>
          </div>
        )}

        {/* ── Tags ─────────────────────────────────────────────────────────────── */}
        {dive?.tags && dive.tags.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-8">
            {dive.tags.map((tag: string) => (
              <span key={tag} className="text-xs px-3 py-1 rounded-full bg-[#0f0f0f] text-[#444] border border-[#1a1a1a] uppercase tracking-wide">
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* ── Footer ───────────────────────────────────────────────────────────── */}
        <div className="mt-4 pt-8 border-t border-[#1e1e1e]">
          <Disclaimer />
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mt-8">
            <Link href="/dashboard?tab=deepdive" className="text-sm text-[#555] hover:text-white transition-colors">
              ← All Deep Dives
            </Link>
            <div className="flex items-center gap-2 text-xs text-[#444]">
              <span className="badge badge-elite">Elite Research</span>
              <span>Antigravity Intelligence</span>
            </div>
          </div>
        </div>

      </div>
    </div>
  )
}
