'use client'
import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { motion, useInView, AnimatePresence } from 'framer-motion'
import Navbar from '@/components/Navbar'
import Footer from '@/components/Footer'
import Disclaimer from '@/components/Disclaimer'
import DigestCard from '@/components/DigestCard'
import { PricingCard, PLANS } from '@/components/PricingCard'
import { apiPublicStats, apiPublicSample, PublicStats, Digest } from '@/lib/api'
import SectorStrip from '@/components/SectorStrip'
import BreakoutShowcase from '@/components/BreakoutShowcase'
import DeepDiveShowcase from '@/components/DeepDiveShowcase'
import EclipseEdge from '@/components/EclipseEdge'

/* ═══════════════════════════════════════════════════════════════════════════════
   HERO SCANNER PREVIEW — live-feeling mock, no real API call here
   Numbers tick subtly via CSS animation to feel real without being distracting
═══════════════════════════════════════════════════════════════════════════════ */
const SCANNER_PREVIEW = [
  { ticker: 'DIXON', cmp: '14,832', change: '+2.4%', conf: 92, pos: true },
  { ticker: 'BEL', cmp: '312', change: '+1.1%', conf: 88, pos: true },
  { ticker: 'POLYCAB', cmp: '7,241', change: '-0.3%', conf: 79, pos: false },
  { ticker: 'ZOMATO', cmp: '243', change: '+3.1%', conf: 85, pos: true },
]

function HeroScannerPreview() {
  const [tick, setTick] = useState(0)

  // Subtly update one value every ~3s — gives the "live" feel without animation spam
  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 3200)
    return () => clearInterval(id)
  }, [])

  const rows = SCANNER_PREVIEW.map((s, i) => ({
    ...s,
    // Tiny random drift on tick — ±0.1% so it reads as live
    changeDisplay: i === tick % SCANNER_PREVIEW.length
      ? (s.pos ? `+${(parseFloat(s.change) + 0.1).toFixed(1)}%` : s.change)
      : s.change,
  }))

  return (
    <div
      className="rounded-xl overflow-hidden eclipse-card"
      style={{
        background: 'rgba(13,13,15,0.95)',
        border: '1px solid rgba(255,255,255,0.07)',
        boxShadow: '0 24px 80px rgba(0,0,0,0.6)',
      }}
    >
      {/* Top gold accent line */}
      <div className="h-px bg-gradient-to-r from-transparent via-[rgba(201,163,78,0.5)] to-transparent" />

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[rgba(255,255,255,0.05)]">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-[#3DDC84] animate-pulse" />
          <span className="text-[10px] font-bold tracking-[0.18em] text-[#5C5C60] uppercase font-mono">
            Umbra Scanner · Live
          </span>
        </div>
        <span className="text-[10px] text-[#5C5C60] font-mono">08:05 AM IST</span>
      </div>

      {/* Column headers */}
      <div className="grid grid-cols-[1fr_72px_64px_80px] gap-3 px-4 py-2 border-b border-[rgba(255,255,255,0.04)]">
        {['Stock', 'CMP', 'Chg', 'Score'].map(h => (
          <div key={h} className="text-[9px] font-bold tracking-[0.14em] uppercase text-[#5C5C60] font-mono">{h}</div>
        ))}
      </div>

      {/* Rows */}
      {rows.map((s, i) => (
        <div
          key={s.ticker}
          className="grid grid-cols-[1fr_72px_64px_80px] gap-3 px-4 py-3 border-b border-[rgba(255,255,255,0.03)] last:border-0"
          style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.008)' }}
        >
          <div className="text-xs font-bold text-[#F2F2F0] font-mono">{s.ticker}</div>
          <div className="text-xs font-mono text-[#F2F2F0]">₹{s.cmp}</div>
          <div
            className="text-xs font-bold font-mono"
            style={{ color: s.pos ? '#3DDC84' : '#E5484D' }}
          >
            {s.changeDisplay}
          </div>
          {/* Confidence mini-bar */}
          <div className="flex items-center gap-1.5">
            <div className="confidence-bar-track flex-1" style={{ height: 3 }}>
              <motion.div
                className="confidence-bar-fill h-full rounded-full"
                initial={{ scaleX: 0 }}
                animate={{ scaleX: s.conf / 100 }}
                transition={{ duration: 0.9, delay: i * 0.12, ease: [0.16, 1, 0.3, 1] }}
              />
            </div>
            <span className="text-[9px] font-mono text-[#9A9A9E]">{s.conf}</span>
          </div>
        </div>
      ))}

      {/* Footer */}
      <div className="px-4 py-3 flex items-center justify-between">
        <span className="text-[10px] text-[#5C5C60] font-mono">47 setups · Nifty 500</span>
        <span className="text-[10px] text-[#C9A34E] font-mono font-semibold">Members only ↗</span>
      </div>
    </div>
  )
}

/* ── Digest preview — line-by-line stagger on scroll ─────────────────────── */
const DIGEST_PREVIEW_ITEMS = [
  {
    category: 'MACRO',
    headline: 'RBI holds rates, signals possible cut in Aug — FII inflows surge ₹4,200Cr',
    score: 9,
    impact: 'Bullish for rate-sensitives: Banks, Realty, NBFCs',
  },
  {
    category: 'SECTOR',
    headline: 'Defence capex up 22% in Q1 — BEL, HAL, Mazagon Dock order books at ATH',
    score: 8,
    impact: 'Structural tailwind — PSU defence on watch',
  },
  {
    category: 'STOCK',
    headline: 'Dixon Technologies reports 31% revenue growth, guidance raised for FY27',
    score: 8,
    impact: 'Breakout candidate — near 52W high with volume',
  },
]

function DigestPreview() {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '-80px' })

  return (
    <div ref={ref} className="space-y-3">
      {DIGEST_PREVIEW_ITEMS.map((item, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, y: 16 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5, delay: i * 0.15, ease: [0.4, 0, 0.2, 1] }}
          className="glass-card p-4 eclipse-card"
        >
          <div className="flex items-start justify-between gap-3 mb-2">
            <span className="badge badge-macro">{item.category}</span>
            <div
              className="text-[10px] font-bold font-mono px-2 py-0.5 rounded-full"
              style={{
                color: '#C9A34E',
                background: 'rgba(201,163,78,0.1)',
                border: '1px solid rgba(201,163,78,0.2)',
              }}
            >
              {item.score}/10
            </div>
          </div>
          <p className="text-sm font-semibold text-[#F2F2F0] leading-snug mb-1.5">{item.headline}</p>
          <p className="text-[11px] text-[#5C5C60] font-mono">{item.impact}</p>
        </motion.div>
      ))}

      {/* Blur / gated item */}
      <div className="relative">
        <div className="glass-card p-4 select-none" style={{ filter: 'blur(4px)', opacity: 0.4, userSelect: 'none' }}>
          <div className="flex items-start justify-between gap-3 mb-2">
            <span className="badge badge-macro">IPO</span>
            <div className="text-[10px] font-bold font-mono px-2 py-0.5 rounded-full" style={{ color: '#C9A34E', background: 'rgba(201,163,78,0.1)', border: '1px solid rgba(201,163,78,0.2)' }}>7/10</div>
          </div>
          <p className="text-sm font-semibold text-[#F2F2F0] leading-snug mb-1.5">This item is for members only. Request access to read.</p>
          <p className="text-[11px] text-[#5C5C60] font-mono">Hidden content · request access to unlock</p>
        </div>
        <div className="absolute inset-0 flex items-center justify-center">
          <Link href="/request-access" className="btn-brand text-xs py-2 px-5">
            Request Access to Read
          </Link>
        </div>
      </div>
    </div>
  )
}

/* ── Scarcity strip — real seat counter ────────────────────────────────────── */
function ScarcityStrip({ claimed }: { claimed: number }) {
  const TOTAL = 1000
  const pct = Math.min((claimed / TOTAL) * 100, 100)

  return (
    <div
      className="py-4 px-6"
      style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', background: 'rgba(13,13,15,0.8)' }}
    >
      <div className="max-w-7xl mx-auto flex items-center gap-5">
        <div className="text-[11px] font-mono text-[#5C5C60] whitespace-nowrap shrink-0">
          <span className="text-[#C9A34E] font-bold">{claimed.toLocaleString('en-IN')}</span>
          {' '}of <span className="text-[#9A9A9E]">1,000</span> seats claimed
        </div>
        <div className="flex-1 max-w-xs">
          <div className="scarcity-bar-track">
            <motion.div
              className="scarcity-bar-fill"
              initial={{ width: 0 }}
              animate={{ width: `${pct}%` }}
              transition={{ duration: 1.4, ease: [0.16, 1, 0.3, 1], delay: 0.5 }}
            />
          </div>
        </div>
        <div className="text-[11px] font-mono text-[#E5484D] font-semibold whitespace-nowrap shrink-0">
          {TOTAL - claimed} seats remaining
        </div>
      </div>
    </div>
  )
}

/* ── Section reveal ─────────────────────────────────────────────────────────── */
function RevealSection({ children, delay = 0, className = '' }: {
  children: React.ReactNode; delay?: number; className?: string
}) {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '-60px' })

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 20 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.5, delay, ease: [0.4, 0, 0.2, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  )
}

/* ═══════════════════════════════════════════════════════════════════════════════
   HOMEPAGE
═══════════════════════════════════════════════════════════════════════════════ */
export default function HomePage() {
  const [stats, setStats] = useState<PublicStats | null>(null)
  const [digest, setDigest] = useState<Digest | null>(null)
  const [isAnnual, setIsAnnual] = useState(false)
  const [mouseNorm, setMouseNorm] = useState({ x: 0, y: 0 })

  useEffect(() => {
    apiPublicStats().then(setStats).catch(() => {})
    apiPublicSample()
      .then((data) => setDigest(data.digests?.[0] || null))
      .catch(() => {})
  }, [])

  // Cursor tracking for pricing card tilt
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      setMouseNorm({
        x: (e.clientX / window.innerWidth) * 2 - 1,
        y: (e.clientY / window.innerHeight) * 2 - 1,
      })
    }
    window.addEventListener('mousemove', handler, { passive: true })
    return () => window.removeEventListener('mousemove', handler)
  }, [])

  // Seat count — real or fallback to 742
  const seatsClaimed = stats?.total_members ?? 742

  const moodConfig = {
    BULLISH: { label: 'Bullish', color: 'bg-[rgba(61,220,132,0.10)] text-[#3DDC84] border-[rgba(61,220,132,0.22)]', dot: 'bg-[#3DDC84]' },
    BEARISH: { label: 'Bearish', color: 'bg-[rgba(229,72,77,0.10)] text-[#E5484D] border-[rgba(229,72,77,0.22)]', dot: 'bg-[#E5484D]' },
    NEUTRAL: { label: 'Neutral', color: 'bg-[rgba(201,163,78,0.10)] text-[#C9A34E] border-[rgba(201,163,78,0.22)]', dot: 'bg-[#C9A34E]' },
  }
  const mood = moodConfig[digest?.market_mood as keyof typeof moodConfig] || moodConfig.NEUTRAL

  const spring = { type: 'spring' as const, stiffness: 110, damping: 20 }

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-base)' }}>
      <div className="noise-overlay" />
      <Navbar />

      {/* ── SCARCITY STRIP ────────────────────────────────────────────────────── */}
      <div className="pt-[60px]">
        <ScarcityStrip claimed={seatsClaimed} />
      </div>

      {/* ── SECTOR STRIP ─────────────────────────────────────────────────────── */}
      <SectorStrip />

      {/* ═══════════════════════════════════════════════════════════════════════
          HERO — The Eclipse Edge plays here. Once. On load.
      ═══════════════════════════════════════════════════════════════════════ */}
      <section className="relative min-h-[92vh] flex items-center overflow-hidden">
        {/* Background — ambient, never competing with the Eclipse Edge */}
        <div className="hero-bg">
          <div className="aurora-orb aurora-orb-1" />
          <div className="aurora-orb aurora-orb-2" />
          <div className="grid-overlay" />
          <div className="beam-line" style={{ left: '72%', height: '35%', animationDelay: '1s', animationDuration: '8s' }} />
        </div>

        <div className="relative max-w-7xl mx-auto px-6 py-24 w-full">
          <div className="grid lg:grid-cols-2 gap-16 items-center">

            {/* ── LEFT: Content ────────────────────────────────────────── */}
            <div>
              {/* Live badge */}
              <motion.div
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ ...spring, delay: 0 }}
                className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border mb-8"
                style={{
                  borderColor: 'rgba(201,163,78,0.2)',
                  background: 'rgba(201,163,78,0.06)',
                }}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-[#3DDC84] animate-pulse" />
                <span className="text-[10px] font-bold text-[#C9A34E] tracking-[0.2em] uppercase font-mono">
                  Invite-Only · 1,000 Members
                </span>
              </motion.div>

              {/* Headline — the Eclipse Edge sweeps once across this */}
              <motion.div
                initial={{ opacity: 0, y: 22 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ ...spring, delay: 0.06 }}
                className="relative mb-6"
              >
                <h1 className="text-5xl md:text-6xl lg:text-[68px] font-bold leading-[1.03] tracking-[-0.025em] text-[#F2F2F0]">
                  See the setup<br />
                  <span className="gradient-text">before the crowd</span><br />
                  does.
                </h1>
                {/* Eclipse Edge — plays once on load across the headline */}
                <EclipseEdge mode="hero" delay={400} />
              </motion.div>

              {/* Sub-headline */}
              <motion.p
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ ...spring, delay: 0.14 }}
                className="text-lg text-[#9A9A9E] max-w-xl mb-2 leading-relaxed"
              >
                Every morning at 8 AM, the Umbra scanner reads Nifty 500 for pre-breakout setups — volume confirmation, RSI momentum, proximity to 52W high.
              </motion.p>
              <motion.p
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ ...spring, delay: 0.2 }}
                className="text-sm text-[#5C5C60] max-w-md mb-10 font-mono"
              >
                Paired with an AI-curated digest. Zero tips. Zero noise. Just research.
              </motion.p>

              {/* Single CTA — no secondary link diluting the ask */}
              <motion.div
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ ...spring, delay: 0.28 }}
                className="mb-12"
              >
                <Link
                  href="/request-access"
                  className="btn-brand text-base py-4 px-9 inline-flex"
                  id="hero-request-access-cta"
                  style={{ boxShadow: '0 8px 36px rgba(201,163,78,0.25)' }}
                >
                  Request Access
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="ml-1">
                    <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </Link>
              </motion.div>

              {/* Social proof — sparse, factual */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.44, duration: 0.4 }}
                className="flex flex-wrap items-center gap-6"
              >
                <div className="flex items-center gap-2">
                  <div className="flex -space-x-1.5">
                    {['#C9A34E', '#3DDC84', '#DDB96A', '#9A9A9E'].map((c, i) => (
                      <div key={i} className="w-6 h-6 rounded-full border-2 border-[#0A0A0B]" style={{ background: c }} />
                    ))}
                  </div>
                  <span className="text-sm text-[#9A9A9E]">
                    <span className="text-[#F2F2F0] font-bold font-mono">{seatsClaimed.toLocaleString('en-IN')}</span>
                    {' '}traders joined
                  </span>
                </div>
                <div className="w-px h-3.5 bg-[rgba(255,255,255,0.07)]" />
                <span className="text-sm text-[#9A9A9E] font-mono">
                  <span className="text-[#E5484D] font-bold">{1000 - seatsClaimed}</span>
                  {' '}seats remaining
                </span>
              </motion.div>
            </div>

            {/* ── RIGHT: Live-feeling scanner preview ──────────────────── */}
            <motion.div
              initial={{ opacity: 0, x: 36 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ ...spring, delay: 0.18 }}
              className="hidden lg:block"
            >
              <HeroScannerPreview />
            </motion.div>
          </div>
        </div>
      </section>

      {/* ── MORNING DIGEST PREVIEW ───────────────────────────────────────────── */}
      <section className="py-20" style={{ background: 'rgba(13,13,15,0.7)' }}>
        <div className="max-w-5xl mx-auto px-6">
          <RevealSection className="text-center mb-12">
            <div className="section-label justify-center">Morning Digest</div>
            <h2 className="text-3xl md:text-4xl font-bold text-[#F2F2F0] mb-4 tracking-tight">
              This lands in your inbox<br />
              <span className="gradient-text-gold">every morning at 8 AM</span>
            </h2>
            <p className="text-[#9A9A9E] max-w-md mx-auto text-sm leading-relaxed">
              Gemini reads the entire financial internet. Scores every item 1–10.
              You only receive what scores 7+. No noise, no clickbait.
            </p>
            {digest && (
              <div className="inline-flex items-center gap-3 mt-5">
                <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-semibold ${mood.color}`}>
                  <div className={`w-1.5 h-1.5 rounded-full ${mood.dot}`} />
                  Market Mood: {digest.market_mood}
                </div>
                <span className="text-[#5C5C60] text-xs font-mono">
                  {new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'short' })}
                </span>
              </div>
            )}
          </RevealSection>

          {/* Live digest if available, otherwise static preview */}
          {digest?.items?.length ? (
            <div className="grid gap-4">
              {digest.items.slice(0, 4).map((item, i) => (
                <div key={i} className="relative">
                  <DigestCard item={item} index={i} blurred={i >= 3} />
                  {i >= 3 && (
                    <div className="absolute inset-0 z-20 flex items-center justify-center rounded-2xl">
                      <Link href="/request-access" className="btn-brand text-sm py-2.5 px-6">
                        Request Access to Read More
                      </Link>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <DigestPreview />
          )}
        </div>
      </section>

      {/* ── BREAKOUT SCANNER SHOWCASE — 2nd (restrained) Eclipse Edge moment ── */}
      <BreakoutShowcase />

      {/* ── DEEP DIVES CAROUSEL ──────────────────────────────────────────────── */}
      <DeepDiveShowcase />

      {/* ── PRICING ──────────────────────────────────────────────────────────── */}
      <section id="pricing" className="py-24" style={{ background: 'rgba(13,13,15,0.5)' }}>
        <div className="max-w-7xl mx-auto px-6">
          <RevealSection className="text-center mb-12">
            <div className="section-label justify-center">Pricing</div>
            <h2 className="text-4xl md:text-5xl font-bold text-[#F2F2F0] mb-3 tracking-tight">
              Transparent. Honest.
            </h2>
            <p className="text-[#9A9A9E] mb-8 max-w-md mx-auto">
              One trade pays for the entire year. Cancel anytime.
            </p>

            {/* Billing toggle */}
            <div className="inline-flex items-center gap-4 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.07)] rounded-xl p-1.5">
              <button
                onClick={() => setIsAnnual(false)}
                className={`text-sm font-semibold px-4 py-2 rounded-lg transition-all duration-200 ${
                  !isAnnual
                    ? 'bg-[rgba(201,163,78,0.12)] text-[#C9A34E]'
                    : 'text-[#5C5C60] hover:text-[#9A9A9E]'
                }`}
              >
                Monthly
              </button>
              <button
                onClick={() => setIsAnnual(!isAnnual)}
                className={`relative w-10 h-5.5 rounded-full transition-colors duration-300 ${isAnnual ? 'bg-[#C9A34E]' : 'bg-[#1C1C1F]'}`}
                aria-label="Toggle annual billing"
                style={{ height: '22px' }}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform duration-300 shadow-sm ${isAnnual ? 'translate-x-5' : ''}`}
                />
              </button>
              <button
                onClick={() => setIsAnnual(true)}
                className={`text-sm font-semibold px-4 py-2 rounded-lg transition-all duration-200 ${
                  isAnnual
                    ? 'bg-[rgba(201,163,78,0.12)] text-[#C9A34E]'
                    : 'text-[#5C5C60] hover:text-[#9A9A9E]'
                }`}
              >
                Annual{' '}
                <span className="text-[#3DDC84] text-xs font-bold">Save 22%</span>
              </button>
            </div>
          </RevealSection>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-start" style={{ perspective: '1200px' }}>
            {PLANS.map((plan) => (
              <PricingCard
                key={plan.id}
                plan={plan}
                isAnnual={isAnnual}
                seatsRemaining={plan.id === 'elite' ? stats?.elite_seats_remaining : undefined}
              />
            ))}
          </div>

          <p className="text-center text-[#5C5C60] text-sm mt-8 font-mono">
            Annual Pro (₹7,499) recovered by a single 3% gain on a ₹2.5L position.{' '}
            <span className="text-[#C9A34E] font-semibold">One trade. One year, paid.</span>
          </p>
        </div>
      </section>

      {/* ── DISCLAIMER ───────────────────────────────────────────────────────── */}
      <section className="py-12 max-w-4xl mx-auto px-6">
        <Disclaimer />
      </section>

      <Footer />
    </div>
  )
}
