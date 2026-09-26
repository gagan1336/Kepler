'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import SectorHub from '@/components/SectorHub'
import IpoHub from '@/components/IpoHub'
import Link from 'next/link'
import type { SectorHubResult, IpoHubResult } from '@/lib/api'

/* ── Sub-tabs ───────────────────────────────────────────────────── */
const TABS = [
  {
    id: 'sectors',
    label: 'Sectors',
    desc: 'Live NSE sector performance & rotation',
    icon: (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" /><path d="M12 2a14.5 14.5 0 0 1 0 20" /><path d="M2 12h20" />
      </svg>
    ),
  },
  {
    id: 'ipo',
    label: 'IPO Hub',
    desc: 'Upcoming IPOs, GMP & subscription tracker',
    icon: (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
      </svg>
    ),
  },
]

/* ── Animation ──────────────────────────────────────────────────── */
const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: (i: number) => ({
    opacity: 1, y: 0,
    transition: { duration: 0.38, delay: i * 0.06, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] },
  }),
}

/* ── Props ──────────────────────────────────────────────────────── */
interface Props {
  userPlan: string
  isPro: boolean
  isElite: boolean
  sectorHub: SectorHubResult | null
  sectorLoading: boolean
  ipoHub: IpoHubResult | null
  ipoLoading: boolean
}

export default function ResearchPage({
  userPlan, isPro, isElite, sectorHub, sectorLoading, ipoHub, ipoLoading,
}: Props) {
  const [active, setActive] = useState('sectors')
  const tab = TABS.find(t => t.id === active)!

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>

      {/* ── Page header ──────────────────────────────────────────── */}
      <motion.div custom={0} variants={fadeUp} initial="hidden" animate="show" className="mb-8">
        <h1 className="text-[1.8rem] font-bold tracking-[-0.03em] leading-tight" style={{ color: '#F0F0F0' }}>Research</h1>
        <p className="text-sm mt-1" style={{ color: '#8A8A8E' }}>Sectors & IPOs — due diligence before you buy</p>
      </motion.div>

      {/* ── Pill tab bar ─────────────────────────────────────────── */}
      <motion.div custom={1} variants={fadeUp} initial="hidden" animate="show" className="flex gap-2 mb-6 flex-wrap">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setActive(t.id)}
            className="relative flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-colors duration-200"
            style={{ color: active === t.id ? '#F0F0F0' : '#8A8A8E' }}
          >
            {active === t.id && (
              <motion.span
                layoutId="research-tab-bg"
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

      {/* ── Tab description ──────────────────────────────────────── */}
      <motion.div
        key={active + '-desc'}
        initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.2 }}
        className="mb-5 flex items-center gap-2"
      >
        <span className="w-1 h-4 rounded-full" style={{ background: '#00C8B4' }} />
        <span className="text-xs font-mono" style={{ color: '#8A8A8E' }}>{tab.desc}</span>
      </motion.div>

      {/* ── Content ──────────────────────────────────────────────── */}
      <AnimatePresence mode="wait">
        <motion.div
          key={active}
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.22 }}
        >
          {/* Sectors */}
          {active === 'sectors' && (
            <>
              {sectorLoading && <ResearchSkeleton />}
              {!sectorLoading && !sectorHub && <EmptyState message="Sector data unavailable. Try again in a moment." />}
              {sectorHub && <SectorHub data={sectorHub} isPro={isPro} />}
            </>
          )}

          {/* IPO Hub */}
          {active === 'ipo' && (
            <>
              {ipoLoading && <ResearchSkeleton rows={2} />}
              {!ipoLoading && !ipoHub && <EmptyState message="IPO data unavailable. Try again in a moment." />}
              {ipoHub && <IpoHub data={ipoHub} />}
            </>
          )}
        </motion.div>
      </AnimatePresence>
    </motion.div>
  )
}

/* ── Helper components ──────────────────────────────────────────── */
function ResearchSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="rounded-2xl p-5" style={{ background: '#111111', border: '1px solid rgba(255,255,255,0.06)' }}>
          <div className="skeleton h-3 w-20 mb-4 rounded" />
          <div className="skeleton h-4 w-1/2 mb-3 rounded" />
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
      <p className="text-sm" style={{ color: '#8A8A8E' }}>{message}</p>
    </div>
  )
}
