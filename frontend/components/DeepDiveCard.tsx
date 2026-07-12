'use client'
import Link from 'next/link'

interface DeepDiveCardProps {
  dive: {
    id: string
    title: string
    summary?: string
    symbol?: string
    sector?: string
    verdict?: string
    risk_rating?: string
    price_target_12m?: number
    tags?: string[]
    metrics_snapshot?: Record<string, any>
    created_at: string
    tier: string
  }
  isElite?: boolean
}

const VERDICT_CONFIG = {
  BUY:   { label: 'BUY',   color: 'text-[#00C48C]', bg: 'bg-[rgba(0,196,140,0.1)]',  border: 'border-[rgba(0,196,140,0.25)]',  dot: 'bg-[#00C48C]' },
  HOLD:  { label: 'HOLD',  color: 'text-[#f59e0b]', bg: 'bg-[rgba(245,158,11,0.1)]', border: 'border-[rgba(245,158,11,0.25)]', dot: 'bg-[#f59e0b]' },
  AVOID: { label: 'AVOID', color: 'text-[#ef4444]', bg: 'bg-[rgba(239,68,68,0.1)]',  border: 'border-[rgba(239,68,68,0.25)]',  dot: 'bg-[#ef4444]' },
}

const RISK_CONFIG = {
  LOW:    { label: 'Low Risk',    color: 'text-[#00C48C]' },
  MEDIUM: { label: 'Med Risk',   color: 'text-[#f59e0b]' },
  HIGH:   { label: 'High Risk',  color: 'text-[#ef4444]' },
}

function MetricPill({ label, value }: { label: string; value: any }) {
  if (value == null) return null
  return (
    <div className="flex flex-col items-center px-3 py-1.5 bg-[#111] rounded-lg border border-[#1e1e1e]">
      <span className="text-xs text-[#444] leading-tight">{label}</span>
      <span className="text-sm font-bold text-white mt-0.5">{value}</span>
    </div>
  )
}

export default function DeepDiveCard({ dive, isElite = false }: DeepDiveCardProps) {
  const verdict = VERDICT_CONFIG[dive.verdict as keyof typeof VERDICT_CONFIG]
  const risk    = RISK_CONFIG[dive.risk_rating as keyof typeof RISK_CONFIG]
  const m       = dive.metrics_snapshot || {}

  const isGenerating = dive.title?.includes('Generating...')
  const isFailed     = dive.title?.includes('Generation Failed')

  const dateStr = new Date(dive.created_at).toLocaleDateString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric',
  })

  // Format market cap
  const mktCapStr = m.market_cap_cr
    ? m.market_cap_cr > 100000
      ? `₹${(m.market_cap_cr / 100000).toFixed(1)}L Cr`
      : `₹${Math.round(m.market_cap_cr).toLocaleString('en-IN')} Cr`
    : null

  return (
    <div className={`glass-card overflow-hidden transition-all duration-200 hover:border-[#2a2a2a] group ${
      isGenerating ? 'opacity-60' : ''
    }`}>
      {/* Top bar: symbol + verdict */}
      <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-[#141414]">
        <div className="flex items-center gap-3">
          {dive.symbol && (
            <div className="w-10 h-10 rounded-xl bg-[#111] border border-[#222] flex items-center justify-center shrink-0">
              <span className="text-[10px] font-black text-[#666]">{dive.symbol.slice(0, 4)}</span>
            </div>
          )}
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              {dive.symbol && (
                <span className="text-xs font-bold text-white tracking-wide">{dive.symbol}</span>
              )}
              {dive.sector && (
                <span className="text-xs text-[#444] px-2 py-0.5 bg-[#111] rounded-full border border-[#1e1e1e]">
                  {dive.sector}
                </span>
              )}
            </div>
            <p className="text-[11px] text-[#444] mt-0.5">{dateStr}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {isGenerating && (
            <span className="text-xs text-[#f59e0b] flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-[#f59e0b] animate-pulse" />
              Generating...
            </span>
          )}
          {verdict && !isGenerating && (
            <span className={`flex items-center gap-1.5 text-xs font-black px-3 py-1.5 rounded-lg border ${verdict.color} ${verdict.bg} ${verdict.border}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${verdict.dot}`} />
              {verdict.label}
            </span>
          )}
          {risk && !isGenerating && (
            <span className={`text-[11px] font-medium ${risk.color}`}>{risk.label}</span>
          )}
        </div>
      </div>

      {/* Main content */}
      <div className="px-5 py-4">
        <h3 className="text-white font-bold text-[15px] leading-snug mb-2 line-clamp-2 group-hover:text-[#00C48C] transition-colors">
          {dive.title}
        </h3>
        {dive.summary && !isGenerating && (
          <p className="text-sm text-[#666] leading-relaxed line-clamp-2">{dive.summary}</p>
        )}
        {isGenerating && (
          <p className="text-sm text-[#444] italic">AI research in progress — check back in ~60 seconds</p>
        )}
        {isFailed && (
          <p className="text-sm text-[#ef4444]">Generation failed. Try again from admin panel.</p>
        )}
      </div>

      {/* Metrics strip */}
      {!isGenerating && !isFailed && (m.pe_ratio || m.roe || m.debt_to_equity || mktCapStr) && (
        <div className="px-5 pb-4 flex gap-2 flex-wrap">
          {m.pe_ratio    && <MetricPill label="PE"        value={`${m.pe_ratio.toFixed(1)}x`} />}
          {m.roe         && <MetricPill label="ROE"       value={`${m.roe.toFixed(1)}%`} />}
          {m.debt_to_equity != null && <MetricPill label="D/E"   value={m.debt_to_equity.toFixed(2)} />}
          {mktCapStr     && <MetricPill label="Mkt Cap"   value={mktCapStr} />}
          {dive.price_target_12m && (
            <div className="flex flex-col items-center px-3 py-1.5 bg-[rgba(0,196,140,0.05)] rounded-lg border border-[rgba(0,196,140,0.15)]">
              <span className="text-xs text-[#555] leading-tight">Target</span>
              <span className="text-sm font-bold text-[#00C48C] mt-0.5">₹{dive.price_target_12m.toLocaleString('en-IN')}</span>
            </div>
          )}
        </div>
      )}

      {/* Tags */}
      {dive.tags && dive.tags.length > 0 && !isGenerating && (
        <div className="px-5 pb-3 flex gap-1.5 flex-wrap">
          {dive.tags.slice(0, 4).map((tag) => (
            <span key={tag} className="text-[11px] px-2 py-0.5 rounded-full bg-[#0f0f0f] text-[#444] border border-[#1a1a1a] uppercase tracking-wide">
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Footer: CTA */}
      <div className="px-5 pb-5 pt-1 border-t border-[#111] mt-1 flex items-center justify-between">
        <span className="text-[11px] text-[#333] uppercase tracking-widest font-bold">
          {dive.tier === 'elite' ? 'Elite Research' : 'Pro Research'}
        </span>
        {isElite && !isGenerating && !isFailed ? (
          <Link
            href={`/deepdive/${dive.id}`}
            className="text-xs font-bold text-[#00C48C] hover:text-white transition-colors flex items-center gap-1"
          >
            Read Full Report
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M2 6h8M6 2l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </Link>
        ) : !isElite && !isGenerating ? (
          <Link href="/pricing?plan=elite" className="text-xs font-bold text-[#555] hover:text-[#00C48C] transition-colors flex items-center gap-1">
            🔒 Elite Only
          </Link>
        ) : null}
      </div>
    </div>
  )
}
