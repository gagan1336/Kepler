'use client'
import { useState } from 'react'
import { Breakout } from '@/lib/api'
import { MiniChart } from './TradingViewWidget'

interface BreakoutTableProps {
  breakouts: Breakout[]
  locked?: boolean
}

export default function BreakoutTable({ breakouts, locked = false }: BreakoutTableProps) {
  const [expanded, setExpanded] = useState<string | null>(null)

  if (locked) {
    return (
      <div className="glass-card p-12 text-center">
        <div className="w-14 h-14 rounded-full bg-[rgba(0,196,140,0.1)] flex items-center justify-center mx-auto mb-4">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <rect x="5" y="11" width="14" height="10" rx="2" stroke="#00C48C" strokeWidth="1.5" />
            <path d="M8 11V7a4 4 0 018 0v4" stroke="#00C48C" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </div>
        <h3 className="text-white font-bold text-lg mb-2">Pro Feature</h3>
        <p className="text-[#666] text-sm mb-6 max-w-xs mx-auto">
          The Breakout Watchlist is available on Pro and Elite plans.
          Upgrade to access daily pre-breakout setups from Nifty 500.
        </p>
        <a href="/pricing" className="btn-brand">Upgrade to Pro →</a>
      </div>
    )
  }

  if (!breakouts || breakouts.length === 0) {
    return (
      <div className="glass-card p-12 text-center">
        <p className="text-[#555] text-sm">No breakout setups found for today. Check back after 7 AM IST on weekdays.</p>
      </div>
    )
  }

  return (
    <div className="glass-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full table-dark">
          <thead>
            <tr>
              <th>Symbol</th>
              <th className="hidden md:table-cell">Company</th>
              <th>RSI</th>
              <th>Vol Ratio</th>
              <th className="hidden md:table-cell">% from 52W High</th>
              <th>Chart</th>
            </tr>
          </thead>
          <tbody>
            {breakouts.map((b) => {
              const tech = b.technical_data || {} as any
              const isExpanded = expanded === b.id
              return (
                <>
                  <tr
                    key={b.id}
                    className={`cursor-pointer transition-colors ${isExpanded ? 'bg-[rgba(0,196,140,0.04)]' : ''}`}
                    onClick={() => setExpanded(isExpanded ? null : b.id)}
                  >
                    <td>
                      <div className="flex flex-col">
                        <span className="font-mono font-bold text-[#00C48C] text-sm">{b.symbol}</span>
                        <span className="text-xs text-[#444] md:hidden truncate max-w-[100px]">{b.company_name}</span>
                      </div>
                    </td>
                    <td className="hidden md:table-cell">
                      <span className="text-white text-sm">{b.company_name}</span>
                    </td>
                    <td>
                      <RSIBadge rsi={tech.rsi} />
                    </td>
                    <td>
                      <span className={`font-mono text-sm font-semibold ${
                        tech.volume_ratio >= 2 ? 'text-[#00C48C]' : 'text-[#f59e0b]'
                      }`}>
                        {tech.volume_ratio?.toFixed(1)}x
                      </span>
                    </td>
                    <td className="hidden md:table-cell">
                      <span className="text-sm font-mono text-[#888]">
                        {tech.pct_from_52w_high?.toFixed(1)}% below
                      </span>
                    </td>
                    <td>
                      <button className="inline-flex items-center gap-1.5 text-xs text-[#00C48C] font-medium bg-[rgba(0,196,140,0.08)] hover:bg-[rgba(0,196,140,0.15)] px-2.5 py-1.5 rounded-lg transition-colors">
                        {isExpanded ? (
                          <>
                            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                              <path d="M1 7l4-4 4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                            </svg>
                            Close
                          </>
                        ) : (
                          <>
                            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                              <path d="M1 3l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                            </svg>
                            Chart
                          </>
                        )}
                      </button>
                    </td>
                  </tr>

                  {/* Expanded row with MiniChart + technical breakdown */}
                  {isExpanded && (
                    <tr key={`${b.id}-expanded`}>
                      <td colSpan={6} className="!p-0">
                        <div className="bg-[#0c0c0c] border-t border-[#1e1e1e] p-5 animate-fade-in">
                          <div className="grid md:grid-cols-2 gap-6">

                            {/* Left: TradingView MiniChart */}
                            <div>
                              <p className="text-xs font-bold uppercase tracking-widest text-[#444] mb-3">
                                1-Month Chart — NSE:{b.symbol}
                              </p>
                              <MiniChart symbol={b.symbol} />
                              <p className="text-xs text-[#333] mt-2">
                                Key level: 52W High ₹{tech.high_52w?.toLocaleString('en-IN')} —{' '}
                                {tech.pct_from_52w_high?.toFixed(1)}% away
                              </p>
                            </div>

                            {/* Right: Tech stats + setup description */}
                            <div>
                              <p className="text-xs font-bold uppercase tracking-widest text-[#444] mb-3">
                                Technical Setup
                              </p>
                              <p className="text-sm text-[#888] leading-relaxed mb-4 border-l-2 border-[#00C48C]/30 pl-3">
                                {b.setup_description}
                              </p>
                              <div className="grid grid-cols-2 gap-3 mt-4">
                                <TechStat label="Current Price" value={`₹${tech.current_price?.toLocaleString('en-IN')}`} highlight />
                                <TechStat label="52-Week High" value={`₹${tech.high_52w?.toLocaleString('en-IN')}`} />
                                <TechStat label="EMA 20" value={`₹${tech.ema20?.toFixed(0)}`} />
                                <TechStat label="EMA 50" value={`₹${tech.ema50?.toFixed(0)}`} />
                                <TechStat label="RSI (14)" value={tech.rsi?.toFixed(1)} />
                                <TechStat label="Volume Surge" value={`${tech.volume_ratio?.toFixed(1)}× avg`} />
                              </div>
                              <p className="text-xs text-[#333] mt-4">
                                ⚠️ Educational analysis only — not investment advice
                              </p>
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="p-4 border-t border-[#1e1e1e] flex items-center justify-between text-xs text-[#444]">
        <span>{breakouts.length} setup{breakouts.length !== 1 ? 's' : ''} today</span>
        <span>Click any row to expand chart · Educational only</span>
      </div>
    </div>
  )
}

function RSIBadge({ rsi }: { rsi: number }) {
  let color = 'text-[#888] bg-[#1a1a1a]'
  if (rsi >= 60) color = 'text-[#00C48C] bg-[rgba(0,196,140,0.1)]'
  else if (rsi >= 50) color = 'text-[#f59e0b] bg-[rgba(245,158,11,0.1)]'
  return (
    <span className={`font-mono text-sm font-bold px-2 py-0.5 rounded ${color}`}>
      {rsi?.toFixed(0)}
    </span>
  )
}

function TechStat({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="bg-[#111] rounded-lg p-3 border border-[#1a1a1a]">
      <p className="text-xs text-[#555] mb-1">{label}</p>
      <p className={`text-sm font-semibold font-mono ${highlight ? 'text-[#00C48C]' : 'text-white'}`}>{value}</p>
    </div>
  )
}
