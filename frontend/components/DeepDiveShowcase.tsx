'use client'
import { useRef } from 'react'
import useEmblaCarousel from 'embla-carousel-react'
import { motion, useInView } from 'framer-motion'
import Link from 'next/link'

interface DeepDive {
  id: number
  title: string
  sector: string
  summary: string
  date: string
  readTime: string
  tier: 'Pro' | 'Elite'
  accentColor: string
}

const DEEP_DIVES: DeepDive[] = [
  {
    id: 1,
    title: 'Why India\'s Defence Sector Is a 5-Year Structural Story',
    sector: 'Defence',
    summary: 'HAL, BEL, BDL — indigenous production mandates and a ₹6L Cr defence budget create compounding tailwinds most retail investors are early on.',
    date: 'Jun 2026',
    readTime: '18 min',
    tier: 'Elite',
    accentColor: '#C9A34E',
  },
  {
    id: 2,
    title: 'Cement Consolidation: The Hidden Value in Pricing Power',
    sector: 'Cement',
    summary: 'Ultra Tech and Adani\'s land grab is reshaping pricing across 8 markets. Who captures margin expansion — and who gets squeezed.',
    date: 'May 2026',
    readTime: '14 min',
    tier: 'Pro',
    accentColor: '#C9A34E',
  },
  {
    id: 3,
    title: 'The EV Supply Chain Play: It\'s Not the Carmakers',
    sector: 'Auto Ancillary',
    summary: 'As EV penetration crosses 8%, the suppliers building battery management systems and charging infrastructure are quietly compounding.',
    date: 'Apr 2026',
    readTime: '16 min',
    tier: 'Elite',
    accentColor: '#3DDC84',
  },
  {
    id: 4,
    title: 'QSR in India: The Unit Economics That Will Separate Winners',
    sector: 'Consumer',
    summary: 'Zomato, Swiggy, and the aggregator squeeze — why restaurant-owned digital channels are the moat that matters in the next cycle.',
    date: 'Mar 2026',
    readTime: '12 min',
    tier: 'Pro',
    accentColor: '#DDB96A',
  },
]

function DeepDiveCard({ dive, index }: { dive: DeepDive; index: number }) {
  const isElite = dive.tier === 'Elite'

  return (
    <div
      className="embla__slide px-2"
      style={{ flex: '0 0 340px' }}
    >
      <motion.div
        whileHover={{ scale: 1.02, y: -4 }}
        transition={{ type: 'spring', stiffness: 200, damping: 20 }}
        className="h-full rounded-2xl p-6 cursor-pointer relative overflow-hidden"
        style={{
          background: 'linear-gradient(135deg, rgba(19,19,21,0.97) 0%, rgba(10,10,11,0.99) 100%)',
          border: `1px solid ${isElite ? 'rgba(201,163,78,0.22)' : 'rgba(201,163,78,0.12)'}`,
          boxShadow: isElite
            ? '0 8px 40px rgba(201,163,78,0.06)'
            : '0 8px 40px rgba(0,0,0,0.3)',
          minHeight: 280,
        }}
      >
        {/* Top accent line */}
        <div
          className="absolute top-0 left-0 right-0 h-px"
          style={{ background: `linear-gradient(90deg, transparent, ${dive.accentColor}88, transparent)` }}
        />

        {/* Tier badge */}
        <div className="flex items-center justify-between mb-4">
          <span
            className="text-[9px] font-bold tracking-[0.15em] uppercase px-2.5 py-1 rounded-full font-mono"
            style={{
              color: dive.accentColor,
              background: `${dive.accentColor}18`,
              border: `1px solid ${dive.accentColor}30`,
            }}
          >
            {isElite ? '🔒 Elite' : '✓ Pro'}
          </span>
          <span className="text-[10px] text-[#3D4F63] font-mono">{dive.readTime} read</span>
        </div>

        {/* Sector tag */}
        <div
          className="text-[10px] font-bold tracking-[0.15em] uppercase mb-3"
          style={{ color: dive.accentColor }}
        >
          {dive.sector}
        </div>

        {/* Title */}
        <h3 className="text-base font-bold text-[#F1F5F9] leading-snug mb-3">
          {dive.title}
        </h3>

        {/* Summary */}
        <p className="text-sm text-[#7A8FA6] leading-relaxed line-clamp-3 mb-6">
          {dive.summary}
        </p>

        {/* Footer */}
        <div className="flex items-center justify-between mt-auto">
          <span className="text-[11px] text-[#3D4F63] font-mono">{dive.date}</span>
          {isElite ? (
            <Link
              href="/request-access"
              className="text-xs font-semibold text-[#C9A34E] hover:text-[#DDB96A] transition-colors flex items-center gap-1"
            >
              Unlock Elite
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M2.5 6h7M6.5 3l3 3-3 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </Link>
          ) : (
            <Link
              href="/deepdive"
              className="text-xs font-semibold text-[#C9A34E] hover:text-[#DDB96A] transition-colors flex items-center gap-1"
            >
              Read report
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M2.5 6h7M6.5 3l3 3-3 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </Link>
          )}
        </div>

        {/* Background glow */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: `radial-gradient(ellipse 50% 50% at 50% 100%, ${dive.accentColor}08, transparent)`,
          }}
        />
      </motion.div>
    </div>
  )
}

export default function DeepDiveShowcase() {
  const sectionRef = useRef<HTMLDivElement>(null)
  const inView = useInView(sectionRef, { once: true, margin: '-80px' })
  const [emblaRef] = useEmblaCarousel({
    loop: false,
    dragFree: false,
    align: 'start',
    containScroll: 'trimSnaps',
  })

  return (
    <section className="py-24 overflow-hidden" ref={sectionRef} style={{ background: 'rgba(13,13,15,0.6)' }}>
      <div className="max-w-6xl mx-auto px-6">

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5 }}
          className="flex flex-col sm:flex-row sm:items-end justify-between mb-10 gap-4"
        >
          <div>
            <div className="section-label">Deep Dives</div>
            <h2 className="text-3xl md:text-4xl font-black text-white leading-tight">
              Long-form research for<br />
              <span className="gradient-text-gold">high-conviction investors</span>
            </h2>
          </div>
          <p className="text-sm text-[#3D4F63] max-w-xs leading-relaxed">
            Monthly 2,000–4,000 word reports on a company, sector, or macro theme. Elite tier only.
          </p>
        </motion.div>

        {/* Carousel */}
        <motion.div
          initial={{ opacity: 0, x: 30 }}
          animate={inView ? { opacity: 1, x: 0 } : {}}
          transition={{ duration: 0.6, delay: 0.2 }}
        >
          <div className="embla" ref={emblaRef}>
            <div className="embla__container">
              {DEEP_DIVES.map((dive, i) => (
                <DeepDiveCard key={dive.id} dive={dive} index={i} />
              ))}
              {/* Peek card prompt */}
              <div className="embla__slide px-2" style={{ flex: '0 0 160px' }}>
                <div
                  className="h-full rounded-2xl flex flex-col items-center justify-center gap-3 text-center px-4 cursor-pointer"
                  style={{
                    background: 'rgba(201,163,78,0.04)',
                    border: '1px dashed rgba(201,163,78,0.2)',
                    minHeight: 280,
                  }}
                >
                  <div
                    className="w-10 h-10 rounded-full flex items-center justify-center"
                    style={{ background: 'rgba(201,163,78,0.1)' }}
                  >
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                      <path d="M2 8h12M9 3l5 5-5 5" stroke="#C9A34E" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </div>
                  <div className="text-xs text-[#3D4F63] leading-relaxed">
                    12 more in the archive
                  </div>
                  <Link
                    href="/deepdive"
                    className="text-xs font-semibold text-[#C9A34E] hover:underline"
                  >
                    View all →
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Drag hint */}
        <p className="text-center text-[11px] text-[#3D4F63] mt-4 font-mono">← drag to explore →</p>
      </div>
    </section>
  )
}
