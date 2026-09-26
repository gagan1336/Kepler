'use client'

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import DigestCard from '@/components/DigestCard'
import MarketRadarTab from '@/components/MarketRadarTab'
import MarketNewsTab from '@/components/MarketNewsTab'
import DeepDiveCard from '@/components/DeepDiveCard'
import Disclaimer from '@/components/Disclaimer'
import Link from 'next/link'
import { apiDigestToday, type Digest } from '@/lib/api'

/* ── Animation ──────────────────────────────────────────────────── */
const fadeUp = {
  hidden: { opacity: 0, y: 14 },
  show: (i: number) => ({
    opacity: 1, y: 0,
    transition: { duration: 0.4, delay: i * 0.06, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] },
  }),
}

/* ── Market mood colours ────────────────────────────────────────── */
const MOOD_CONFIG = {
  BULLISH: { textColor: '#30D158', bg: 'rgba(48,209,88,0.10)', border: 'rgba(48,209,88,0.22)', dot: '#30D158', glow: 'rgba(48,209,88,0.20)' },
  BEARISH: { textColor: '#FF453A', bg: 'rgba(255,69,58,0.10)', border: 'rgba(255,69,58,0.22)', dot: '#FF453A', glow: 'rgba(255,69,58,0.20)' },
  NEUTRAL: { textColor: '#8A8A8E', bg: 'rgba(138,138,142,0.10)', border: 'rgba(138,138,142,0.20)', dot: '#8A8A8E', glow: 'rgba(138,138,142,0.12)' },
}

/* ── Sub-tab options ────────────────────────────────────────────── */
const LEFT_TABS = [
  { id: 'digest',    label: 'Digest & Deep Dives' },
  { id: 'radar',     label: 'Kepler Radar' },
]

function SubTabPills({ active, onChange }: { active: string; onChange: (id: string) => void }) {
  return (
    <div className="flex gap-1 p-1 rounded-xl" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)' }}>
      {LEFT_TABS.map(tab => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className="relative px-4 py-1.5 rounded-lg text-sm font-semibold transition-colors duration-200"
          style={{ color: active === tab.id ? '#F0F0F0' : '#8A8A8E' }}
        >
          {active === tab.id && (
            <motion.span
              layoutId="pulse-sub-tab"
              className="absolute inset-0 rounded-lg"
              style={{ background: '#1C1C1E', border: '1px solid rgba(255,255,255,0.10)', boxShadow: '0 2px 8px rgba(0,0,0,0.4)' }}
              transition={{ type: 'spring', stiffness: 400, damping: 35 }}
            />
          )}
          <span className="relative z-10">{tab.label}</span>
        </button>
      ))}
    </div>
  )
}

/* ── Skeletons ──────────────────────────────────────────────────── */
function DigestSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3, 4].map(i => (
        <div key={i} className="rounded-2xl p-5" style={{ background: '#111111', border: '1px solid rgba(255,255,255,0.06)' }}>
          <div className="skeleton h-2.5 w-16 mb-4 rounded" />
          <div className="skeleton h-4 w-3/4 mb-3 rounded" />
          <div className="skeleton h-3 w-full mb-2 rounded" />
          <div className="skeleton h-3 w-2/3 rounded" />
        </div>
      ))}
    </div>
  )
}

/* ── Deep Dive section (inline, below digest) ───────────────────── */
function DeepDivesSection({ dives, loading, isPro, isElite }: {
  dives: any[]; loading: boolean; isPro: boolean; isElite: boolean
}) {
  const [verdictFilter, setVerdictFilter] = useState<string | null>(null)
  const VERDICTS = ['BUY', 'HOLD', 'AVOID']
  const filtered = verdictFilter ? dives.filter(d => d.verdict === verdictFilter) : dives

  return (
    <div style={{ marginTop: 32 }}>
      {/* Section header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16, paddingTop: 16, borderTop: '1px solid rgba(255,255,255,0.06)' }}>
        <span style={{ fontSize: 13, fontWeight: 800, color: '#94a3b8', letterSpacing: '0.06em', textTransform: 'uppercase', fontFamily: 'monospace' }}>
          📖 Deep Dives
        </span>
        <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 99, background: 'rgba(0,200,180,0.10)', color: '#00C8B4', border: '1px solid rgba(0,200,180,0.2)', fontWeight: 700 }}>
          AI Research
        </span>
      </div>

      {!isPro ? (
        <div className="p-10 text-center rounded-2xl" style={{ background: '#111111', border: '1px solid rgba(0,200,180,0.15)' }}>
          <p className="font-bold mb-1" style={{ color: '#F0F0F0' }}>Deep Dives — Pro Feature</p>
          <p className="text-sm mb-4" style={{ color: '#8A8A8E' }}>Upgrade to Pro for institutional-grade stock research reports.</p>
          <Link href="/pricing" className="btn-brand text-sm">Upgrade to Pro</Link>
        </div>
      ) : loading ? (
        <DigestSkeleton />
      ) : dives.length === 0 ? (
        <div className="p-10 text-center rounded-2xl" style={{ background: '#111111', border: '1px solid rgba(255,255,255,0.07)' }}>
          <p className="text-sm" style={{ color: '#8A8A8E' }}>No deep dives published yet. Check back soon.</p>
        </div>
      ) : (
        <>
          {/* Verdict filter pills */}
          {dives.some(d => d.verdict) && (
            <div className="flex gap-2 mb-5 flex-wrap">
              {[null, ...VERDICTS].map(v => {
                const activeColor = v === 'BUY' ? '#3DDC84' : v === 'HOLD' ? '#F7B731' : v === 'AVOID' ? '#E5484D' : '#00C8B4'
                const isActive = verdictFilter === v
                return (
                  <button
                    key={v ?? 'all'}
                    onClick={() => setVerdictFilter(v)}
                    className="text-xs px-3.5 py-1.5 rounded-full border transition-all font-semibold"
                    style={
                      isActive
                        ? { background: activeColor + '22', color: activeColor, borderColor: activeColor + '55' }
                        : { background: 'transparent', color: '#8A8A8E', borderColor: 'rgba(255,255,255,0.10)' }
                    }
                  >
                    {v ?? 'All'}
                  </button>
                )
              })}
            </div>
          )}
          <div className="grid md:grid-cols-2 gap-4">
            {filtered.map((d, i) => (
              <motion.div key={d.id} custom={i} variants={fadeUp} initial="hidden" animate="show">
                <DeepDiveCard dive={d} isElite={isElite} />
              </motion.div>
            ))}
          </div>
          {!isElite && dives.length > 0 && (
            <div className="mt-6 p-8 text-center rounded-2xl relative overflow-hidden" style={{ background: '#111111', border: '1px solid rgba(0,200,180,0.18)' }}>
              <div className="absolute inset-x-0 bottom-0 h-px" style={{ background: 'linear-gradient(90deg, transparent, #00C8B4, transparent)' }} />
              <p className="font-bold mb-1" style={{ color: '#F0F0F0' }}>Full content requires Elite</p>
              <p className="text-sm mb-4" style={{ color: '#8A8A8E' }}>Upgrade to read complete structured research reports.</p>
              <Link href="/pricing?plan=elite" className="btn-brand text-sm">Upgrade to Elite</Link>
            </div>
          )}
        </>
      )}
    </div>
  )
}

/* ── Props ──────────────────────────────────────────────────────── */
interface Props {
  userPlan: string
  isAdmin?: boolean
  deepDives: any[]
  deepDivesLoading: boolean
  isPro: boolean
  isElite: boolean
  onLoadDeepDives: () => void
}

/* ── Main component ─────────────────────────────────────────────── */
export default function MarketPulsePage({ userPlan, isAdmin, deepDives, deepDivesLoading, isPro, isElite, onLoadDeepDives }: Props) {
  const [leftTab, setLeftTab] = useState('digest')
  const [digest, setDigest] = useState<Digest | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    apiDigestToday().then(setDigest).catch(() => setDigest(null)).finally(() => setLoading(false))
    // Also trigger deep dive load
    onLoadDeepDives()
  }, [])

  const mood = digest?.market_mood as keyof typeof MOOD_CONFIG | undefined
  const mc   = mood ? (MOOD_CONFIG[mood] ?? MOOD_CONFIG.NEUTRAL) : null

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }} className="h-full">

      {/* ── Page header ──────────────────────────────────────────── */}
      <motion.div custom={0} variants={fadeUp} initial="hidden" animate="show"
        className="flex items-start justify-between mb-8 flex-wrap gap-4"
      >
        <div>
          <h1 className="text-[1.8rem] font-bold tracking-[-0.03em] leading-tight" style={{ color: '#F0F0F0' }}>
            Market Pulse
          </h1>
          <p className="text-sm mt-1" style={{ color: '#8A8A8E' }}>
            {new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' })}
          </p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)' }}>
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-60" style={{ background: '#30D158' }} />
              <span className="relative inline-flex rounded-full h-2 w-2" style={{ background: '#30D158' }} />
            </span>
            <span className="text-[11px] font-mono font-semibold tracking-widest uppercase" style={{ color: '#8A8A8E' }}>Live</span>
          </div>
          {mc && (
            <motion.div
              initial={{ scale: 0.85, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.3, type: 'spring', stiffness: 300 }}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full"
              style={{ background: mc.bg, border: `1px solid ${mc.border}`, boxShadow: `0 0 20px ${mc.glow}` }}
            >
              <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: mc.dot }} />
              <span className="text-[11px] font-bold font-mono tracking-widest uppercase" style={{ color: mc.textColor }}>{mood}</span>
            </motion.div>
          )}
        </div>
      </motion.div>

      {/* ── Two-column layout ────────────────────────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-6 h-full">

        {/* Left column — Digest+DeepDives / Radar */}
        <div className="flex flex-col gap-4 min-w-0">
          <motion.div custom={1} variants={fadeUp} initial="hidden" animate="show">
            <SubTabPills active={leftTab} onChange={setLeftTab} />
          </motion.div>

          <AnimatePresence mode="wait">
            <motion.div
              key={leftTab}
              initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.2 }}
            >
              {leftTab === 'digest' ? (
                <>
                  {/* Today's Digest */}
                  {loading && <DigestSkeleton />}
                  {!loading && !digest && (
                    <div className="p-12 text-center rounded-2xl" style={{ background: '#111111', border: '1px solid rgba(255,255,255,0.07)' }}>
                      <p className="text-sm" style={{ color: '#8A8A8E' }}>No digest yet. Check back after 8 AM IST on weekdays.</p>
                    </div>
                  )}
                  {digest && (
                    <div className="space-y-3">
                      {digest.items.map((item, i) => (
                        <motion.div key={i} custom={i} variants={fadeUp} initial="hidden" animate="show">
                          <DigestCard item={item} index={i} />
                        </motion.div>
                      ))}
                      {digest.is_restricted && digest.blurred_count > 0 && (
                        <motion.div
                          custom={digest.items.length} variants={fadeUp} initial="hidden" animate="show"
                          className="p-8 text-center rounded-2xl relative overflow-hidden"
                          style={{ background: '#111111', border: '1px solid rgba(0,200,180,0.18)' }}
                        >
                          <div className="absolute inset-x-0 bottom-0 h-px" style={{ background: 'linear-gradient(90deg, transparent, #00C8B4, transparent)' }} />
                          <p className="font-bold mb-1" style={{ color: '#F0F0F0' }}>{digest.blurred_count} more items locked</p>
                          <p className="text-sm mb-5" style={{ color: '#8A8A8E' }}>Upgrade to Pro for the full daily digest.</p>
                          <Link href="/pricing" className="btn-brand text-sm">Upgrade to Pro</Link>
                        </motion.div>
                      )}
                      <div className="pt-2"><Disclaimer compact /></div>
                    </div>
                  )}

                  {/* Deep Dives merged below digest */}
                  <DeepDivesSection
                    dives={deepDives}
                    loading={deepDivesLoading}
                    isPro={isPro}
                    isElite={isElite}
                  />
                </>
              ) : (
                <MarketRadarTab userPlan={userPlan} isAdmin={isAdmin ?? false} />
              )}
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Right column — Live News */}
        <motion.div custom={2} variants={fadeUp} initial="hidden" animate="show" className="flex flex-col min-w-0">
          <div className="flex items-center gap-2 mb-4 pb-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-60" style={{ background: '#30D158' }} />
              <span className="relative inline-flex rounded-full h-2 w-2" style={{ background: '#30D158' }} />
            </span>
            <span className="text-[11px] font-bold tracking-[0.12em] uppercase font-mono" style={{ color: '#48484A' }}>Live News Feed</span>
          </div>
          <div className="flex-1 overflow-auto scrollbar-none" style={{ maxHeight: 'calc(100vh - 240px)' }}>
            <MarketNewsTab userPlan={userPlan} />
          </div>
        </motion.div>

      </div>
    </motion.div>
  )
}
