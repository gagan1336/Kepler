'use client'
import { useState, useRef } from 'react'
import { motion, useInView, AnimatePresence } from 'framer-motion'

interface Stock {
  ticker: string
  name: string
  cmp: number
  pct52h: number
  volume: number
  rsi: number
  confidence: number
  setup: string
}

type FilterType = 'All' | 'Momentum' | 'Volume' | 'RSI'

const STOCKS: Stock[] = [
  { ticker: 'DIXON', name: 'Dixon Technologies', cmp: 14832, pct52h: 1.8, volume: 2.4, rsi: 71, confidence: 92, setup: 'Momentum' },
  { ticker: 'ZOMATO', name: 'Zomato Ltd', cmp: 243, pct52h: 3.1, volume: 3.1, rsi: 68, confidence: 85, setup: 'Volume' },
  { ticker: 'POLYCAB', name: 'Polycab India', cmp: 7241, pct52h: 2.4, volume: 1.8, rsi: 74, confidence: 88, setup: 'RSI' },
  { ticker: 'TATAPOWER', name: 'Tata Power', cmp: 423, pct52h: 4.2, volume: 2.9, rsi: 66, confidence: 79, setup: 'Volume' },
  { ticker: 'BEL', name: 'Bharat Electronics', cmp: 312, pct52h: 0.9, volume: 1.5, rsi: 72, confidence: 91, setup: 'Momentum' },
]

const FILTERS: FilterType[] = ['All', 'Momentum', 'Volume', 'RSI']

function ConfidenceBar({ score, delay }: { score: number; delay: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true })

  const color = score >= 88 ? '#C9A34E' : score >= 78 ? '#3DDC84' : '#DDB96A'

  return (
    <div ref={ref} className="flex items-center gap-2">
      <div className="confidence-bar-track flex-1" style={{ height: 5 }}>
        <motion.div
          className="confidence-bar-fill confidence-fill-eclipse h-full rounded-full"
          style={{ background: `linear-gradient(90deg, ${color}99, ${color})` }}
          initial={{ scaleX: 0 }}
          animate={inView ? { scaleX: score / 100 } : {}}
          transition={{
            duration: 1.0,
            delay,
            ease: [0.16, 1, 0.3, 1],
          }}
        />
      </div>
      <span className="text-xs font-bold font-mono" style={{ color, minWidth: 32, textAlign: 'right' }}>
        {score}%
      </span>
    </div>
  )
}

const rowVariants = {
  hidden: { opacity: 0, x: -16 },
  visible: (i: number) => ({
    opacity: 1,
    x: 0,
    transition: { delay: i * 0.08, type: 'spring' as const, stiffness: 100, damping: 18 },
  }),
}

export default function BreakoutShowcase() {
  const [filter, setFilter] = useState<FilterType>('All')
  const containerRef = useRef<HTMLDivElement>(null)
  const inView = useInView(containerRef, { once: true, margin: '-80px' })

  const filtered = filter === 'All' ? STOCKS : STOCKS.filter(s => s.setup === filter)

  return (
    <section className="py-24" ref={containerRef}>
      <div className="max-w-6xl mx-auto px-6">

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5 }}
          className="flex flex-col sm:flex-row sm:items-end justify-between mb-10 gap-6"
        >
          <div>
            <div className="section-label">Breakout Scanner</div>
            <h2 className="text-3xl md:text-4xl font-black text-white leading-tight">
              Live setups from<br />
              <span className="gradient-text">Nifty 500</span>
            </h2>
          </div>
          <div className="flex items-center gap-2 text-[11px] text-[#3D4F63] font-mono">
            <span className="w-1.5 h-1.5 rounded-full bg-[#10B981] animate-pulse" />
            Updated 8:05 AM IST
          </div>
        </motion.div>

        {/* Filter tabs */}
        <div className="relative flex gap-1 mb-6 p-1 rounded-xl bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] w-fit">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`relative px-4 py-1.5 text-xs font-semibold rounded-lg transition-colors duration-200 z-10 font-mono ${
                filter === f ? 'text-[#F2F2F0]' : 'text-[#5C5C60] hover:text-[#9A9A9E]'
              }`}
            >
              {filter === f && (
                <motion.span
                  layoutId="tabBg"
                  className="absolute inset-0 rounded-lg"
                  style={{ background: 'rgba(201,163,78,0.14)', border: '1px solid rgba(201,163,78,0.28)' }}
                  transition={{ type: 'spring', stiffness: 350, damping: 30 }}
                />
              )}
              <span className="relative z-10">{f}</span>
            </button>
          ))}
        </div>

        {/* Table */}
        <div
          className="relative rounded-2xl overflow-hidden"
          style={{
            background: 'rgba(13,13,15,0.95)',
            border: '1px solid rgba(255,255,255,0.07)',
            boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
          }}
        >
          {/* Scan line */}
          <div className="absolute inset-0 overflow-hidden pointer-events-none z-10">
            <div className="scan-line" style={{ height: '100%' }} />
          </div>

          {/* Top border accent */}
          <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[rgba(201,163,78,0.4)] to-transparent" />

          {/* Table header */}
          <div className="grid grid-cols-[1fr_80px_72px_72px_1fr] gap-4 px-5 py-3 border-b border-[rgba(255,255,255,0.05)]">
            {['Stock', 'CMP', '% to High', 'Vol', 'Confidence'].map((h) => (
              <div key={h} className="text-[10px] font-bold tracking-[0.12em] uppercase text-[#3D4F63]">
                {h}
              </div>
            ))}
          </div>

          {/* Rows */}
          <AnimatePresence mode="popLayout">
            {filtered.map((stock, i) => (
              <motion.div
                key={stock.ticker}
                custom={i}
                variants={rowVariants}
                initial="hidden"
                animate={inView ? 'visible' : 'hidden'}
                exit={{ opacity: 0, x: -10, transition: { duration: 0.15 } }}
                className="grid grid-cols-[1fr_80px_72px_72px_1fr] gap-4 px-5 py-4 border-b border-[rgba(255,255,255,0.04)] last:border-0 hover:bg-[rgba(201,163,78,0.025)] transition-colors duration-150 group"
              >
                {/* Stock name */}
                <div>
                  <div className="text-sm font-bold text-[#F2F2F0] font-mono group-hover:text-[#DDB96A] transition-colors">
                    {stock.ticker}
                  </div>
                  <div className="text-[11px] text-[#5C5C60] mt-0.5 truncate">{stock.name}</div>
                </div>
                {/* CMP */}
                <div className="font-mono text-sm text-[#F1F5F9] col-price self-center">
                  ₹{stock.cmp.toLocaleString('en-IN')}
                </div>
                {/* % to 52W High */}
                <div
                  className="font-mono text-sm font-semibold self-center"
                  style={{ color: stock.pct52h < 3 ? '#3DDC84' : '#C9A34E' }}
                >
                  -{stock.pct52h.toFixed(1)}%
                </div>
                {/* Volume */}
                <div className="font-mono text-sm text-[#9A9A9E] self-center">
                  {stock.volume.toFixed(1)}×
                </div>
                {/* Confidence bar */}
                <div className="self-center">
                  <ConfidenceBar score={stock.confidence} delay={i * 0.1 + 0.3} />
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {/* Bottom CTA */}
          <div className="px-5 py-4 flex items-center justify-between bg-[rgba(201,163,78,0.025)] border-t border-[rgba(201,163,78,0.1)]">
            <span className="text-xs text-[#5C5C60] font-mono">Showing {filtered.length} of 47 setups today</span>
            <a href="/request-access" className="text-xs font-semibold text-[#C9A34E] hover:text-[#DDB96A] transition-colors flex items-center gap-1">
              Request Access to unlock all
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M2.5 6h7M6.5 3l3 3-3 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </a>
          </div>
        </div>

        {/* Disclaimer */}
        <p className="text-[11px] text-[#3D4F63] mt-4 text-center">
          Scanner results are research tools, not buy/sell recommendations. Always do your own analysis.
        </p>
      </div>
    </section>
  )
}
