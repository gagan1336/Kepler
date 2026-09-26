'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import BreakoutWatchlist from '@/components/BreakoutWatchlist'
import SignalsFeedTab from '@/components/SignalsFeedTab'
import StockScreener from '@/components/StockScreener'

/* ── Sub-tabs ───────────────────────────────────────────────────── */
const TABS = [
  {
    id: 'breakouts',
    label: 'Breakouts',
    desc: 'Technical breakout setups',
    icon: (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" /><polyline points="16 7 22 7 22 13" />
      </svg>
    ),
  },
  {
    id: 'signals',
    label: 'Signals',
    desc: 'AI-generated trade signals',
    icon: (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M2 20h20"/><path d="m6 16 4-8 4 6 3-4 3 6"/>
      </svg>
    ),
  },
  {
    id: 'screener',
    label: 'Screener',
    desc: 'Filter the entire NSE universe',
    icon: (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
      </svg>
    ),
  },
]

/* ── Animation variants ─────────────────────────────────────────── */
const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: (i: number) => ({
    opacity: 1, y: 0,
    transition: { duration: 0.38, delay: i * 0.06, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] },
  }),
}

interface Props {
  userPlan: string
  breakouts: any[]
  breakoutsLoading: boolean
}

export default function TradeIdeasPage({ userPlan, breakouts, breakoutsLoading }: Props) {
  const [active, setActive] = useState('breakouts')
  const tab = TABS.find(t => t.id === active)!

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.25 }}
    >
      {/* ── Page header ──────────────────────────────────────────── */}
      <motion.div custom={0} variants={fadeUp} initial="hidden" animate="show" className="mb-8">
        <p className="text-[11px] font-semibold tracking-[0.14em] uppercase font-mono mb-3" style={{ color: '#48484A' }}>
          — your daily edge
        </p>
        <h1 className="text-[2rem] font-bold tracking-[-0.03em] leading-tight" style={{ color: '#F0F0F0' }}>Trade Ideas</h1>
        <p className="text-sm mt-2 leading-relaxed" style={{ color: '#8A8A8E' }}>Setups, signals &amp; screening — act with conviction</p>
      </motion.div>

      {/* ── Pill tab bar ─────────────────────────────────────────── */}
      <motion.div
        custom={1} variants={fadeUp} initial="hidden" animate="show"
        className="flex gap-2 mb-6 flex-wrap"
      >
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setActive(t.id)}
            className="relative flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-colors duration-200"
            style={{ color: active === t.id ? '#F0F0F0' : '#8A8A8E' }}
          >
            {active === t.id && (
              <motion.span
                layoutId="trade-tab-bg"
                className="absolute inset-0 rounded-xl"
                style={{ background: '#1C1C1E', border: '1px solid rgba(255,255,255,0.10)', boxShadow: '0 2px 8px rgba(0,0,0,0.5)' }}
                transition={{ type: 'spring', stiffness: 400, damping: 35 }}
              />
            )}
            <span className="relative z-10 flex items-center gap-1.5">
              {t.icon}
              {t.label}
            </span>
          </button>
        ))}
      </motion.div>

      {/* ── Tab description chip ─────────────────────────────────── */}
      <motion.div
        key={active + '-desc'}
        initial={{ opacity: 0, x: -8 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.2 }}
        className="mb-5 flex items-center gap-2"
      >
        <span className="w-1 h-4 rounded-full" style={{ background: '#00C8B4' }} />
        <span className="text-xs font-mono" style={{ color: '#8A8A8E' }}>{tab.desc}</span>
      </motion.div>

      {/* ── Content ──────────────────────────────────────────────── */}
      <AnimatePresence mode="wait">
        <motion.div
          key={active}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -12 }}
          transition={{ duration: 0.22 }}
        >
          {active === 'breakouts' && (
            <>
              {breakoutsLoading && <BreakoutSkeleton />}
              {!breakoutsLoading && breakouts.length === 0 && (
                <EmptyState message="No breakout signals detected today. Check back after market hours." />
              )}
              {breakouts.length > 0 && (
                <div className="space-y-4">
                  {breakouts.map((b, i) => (
                    <motion.div
                      key={i}
                      custom={i}
                      variants={fadeUp}
                      initial="hidden"
                      animate="show"
                    >
                      <BreakoutWatchlist breakouts={[b]} />
                    </motion.div>
                  ))}
                </div>
              )}
            </>
          )}

          {active === 'signals' && <SignalsFeedTab userPlan={userPlan} />}
          {active === 'screener' && <StockScreener userPlan={userPlan} />}
        </motion.div>
      </AnimatePresence>
    </motion.div>
  )
}

/* ── Helpers ────────────────────────────────────────────────────── */
function BreakoutSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map(i => (
        <div key={i} className="rounded-2xl p-5" style={{ background: '#111111', border: '1px solid rgba(255,255,255,0.06)' }}>
          <div className="skeleton h-3 w-20 mb-4 rounded" />
          <div className="skeleton h-5 w-1/2 mb-3 rounded" />
          <div className="skeleton h-3 w-full mb-2 rounded" />
          <div className="skeleton h-3 w-3/4 rounded" />
        </div>
      ))}
    </div>
  )
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="p-12 text-center rounded-2xl" style={{ background: '#111111', border: '1px solid rgba(255,255,255,0.07)' }}>
      <div className="w-12 h-12 rounded-2xl flex items-center justify-center mx-auto mb-4" style={{ background: 'rgba(255,255,255,0.04)' }}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#48484A" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" /><polyline points="16 7 22 7 22 13" />
        </svg>
      </div>
      <p className="text-sm" style={{ color: '#8A8A8E' }}>{message}</p>
    </div>
  )
}
