'use client'
import { useRef, useState } from 'react'
import Link from 'next/link'
import {
  motion,
  useMotionValue,
  useTransform,
  useSpring,
  useInView,
} from 'framer-motion'
import { apiCreateSubscription } from '@/lib/api'

interface Plan {
  id: string
  name: string
  monthlyPrice: number
  annualPrice: number
  annualMonthly: number
  badge?: string
  featured?: boolean
  cta: string
  ctaLink: string
  description: string
  tagline?: string
  features: { text: string; included: boolean }[]
}

const PLANS: Plan[] = [
  {
    id: 'free',
    name: 'Free',
    monthlyPrice: 0,
    annualPrice: 0,
    annualMonthly: 0,
    cta: 'Start Free',
    ctaLink: '/register',
    description: 'Get a taste of what the platform can do.',
    tagline: 'No card required',
    features: [
      { text: 'Top 3 digest items daily', included: true },
      { text: 'Latest sector report', included: true },
      { text: 'Latest IPO brief', included: true },
      { text: 'Full morning digest (all items)', included: false },
      { text: 'Breakout watchlist', included: false },
      { text: 'Sector report history', included: false },
      { text: 'Deep dives', included: false },
    ],
  },
  {
    id: 'pro',
    name: 'Pro',
    monthlyPrice: 799,
    annualPrice: 7499,
    annualMonthly: 625,
    badge: '7-Day Free Trial',
    featured: true,
    cta: 'Start 7-Day Free Trial',
    ctaLink: '/register?plan=pro',
    description: 'Everything you need to trade with an edge every morning.',
    tagline: 'One trade pays for the year',
    features: [
      { text: 'Full morning digest — all items', included: true },
      { text: 'Breakout watchlist (Mon/Wed/Fri)', included: true },
      { text: 'Sector reports + 12-week history', included: true },
      { text: 'Full IPO briefs + archive', included: true },
      { text: 'Dashboard with all tools', included: true },
      { text: 'Deep dive list + summaries', included: true },
      { text: 'Deep dive full content', included: false },
    ],
  },
  {
    id: 'elite',
    name: 'Elite',
    monthlyPrice: 1999,
    annualPrice: 17999,
    annualMonthly: 1500,
    badge: 'Limited Seats',
    cta: 'Get Elite Access',
    ctaLink: '/register?plan=elite',
    description: 'Everything in Pro, plus our deepest analysis for high-conviction investors.',
    tagline: 'For serious money',
    features: [
      { text: 'Everything in Pro', included: true },
      { text: 'Deep dive full content', included: true },
      { text: 'Elite Telegram channel', included: true },
      { text: 'Priority access to new features', included: true },
      { text: 'Monthly market cycle report', included: true },
      { text: 'All future features included', included: true },
      { text: '30-day money back guarantee', included: true },
    ],
  },
]

// SVG checkmark draw-on
function AnimatedCheck({ included, index }: { included: boolean; index: number }) {
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true })
  const color = included ? '#C9A34E' : 'rgba(255,255,255,0.08)'

  return (
    <span ref={ref} className="shrink-0 mt-0.5">
      {included ? (
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="7" stroke={color} strokeWidth="1.4" opacity="0.5" />
          <motion.path
            d="M5 8l2.5 2.5L11 5"
            stroke="#C9A34E"
            strokeWidth="1.4"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={inView ? { pathLength: 1, opacity: 1 } : {}}
            transition={{ duration: 0.4, delay: index * 0.06 + 0.2, ease: 'easeOut' }}
          />
        </svg>
      ) : (
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="7" stroke={color} strokeWidth="1.4" />
          <path d="M5.5 10.5l5-5M10.5 10.5l-5-5" stroke={color} strokeWidth="1.4" strokeLinecap="round" />
        </svg>
      )}
    </span>
  )
}

interface PricingCardProps {
  plan: Plan
  isAnnual: boolean
  seatsRemaining?: number
  onCheckout?: (planKey: string) => void
  loading?: boolean
}

export function PricingCard({ plan, isAnnual, seatsRemaining, onCheckout, loading }: PricingCardProps) {
  const price = isAnnual ? plan.annualMonthly : plan.monthlyPrice
  const totalAnnual = plan.annualPrice

  // Cursor tilt — max 7° (spec: 6-8°)
  const cardRef = useRef<HTMLDivElement>(null)
  const mouseX = useMotionValue(0)
  const mouseY = useMotionValue(0)
  const rotateX = useTransform(mouseY, [-0.5, 0.5], [7, -7])
  const rotateY = useTransform(mouseX, [-0.5, 0.5], [-7, 7])
  const springRotX = useSpring(rotateX, { stiffness: 150, damping: 22 })
  const springRotY = useSpring(rotateY, { stiffness: 150, damping: 22 })

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current) return
    const rect = cardRef.current.getBoundingClientRect()
    mouseX.set((e.clientX - rect.left) / rect.width - 0.5)
    mouseY.set((e.clientY - rect.top) / rect.height - 0.5)
  }

  const handleMouseLeave = () => {
    mouseX.set(0)
    mouseY.set(0)
  }

  // All tiers use gold accent in Umbra
  const accentColor = plan.id === 'elite' ? '#DDB96A' : plan.featured ? '#C9A34E' : 'rgba(255,255,255,0.2)'
  const accentDim = plan.id === 'elite' ? 'rgba(201,163,78,0.10)' : plan.featured ? 'rgba(201,163,78,0.08)' : 'transparent'

  return (
    <motion.div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{
        rotateX: springRotX,
        rotateY: springRotY,
        transformStyle: 'preserve-3d',
        perspective: 800,
      }}
      className="relative flex flex-col h-full rounded-2xl"
    >
      {/* Card body */}
      <div
        className={`relative flex flex-col h-full rounded-2xl transition-all duration-300 ${
          plan.featured ? 'p-8' : 'p-7'
        }`}
        style={{
          background: plan.featured
            ? 'linear-gradient(135deg, rgba(19,19,21,0.98) 0%, rgba(10,10,11,0.99) 100%)'
            : 'rgba(19,19,21,0.9)',
          border: `1px solid ${plan.featured
            ? 'rgba(201,163,78,0.30)'
            : plan.id === 'elite'
            ? 'rgba(201,163,78,0.18)'
            : 'rgba(255,255,255,0.07)'}`,
          boxShadow: plan.featured
            ? '0 0 50px rgba(201,163,78,0.08), 0 0 0 1px rgba(201,163,78,0.12), inset 0 0 50px rgba(201,163,78,0.025)'
            : plan.id === 'elite'
            ? '0 0 36px rgba(201,163,78,0.05)'
            : '0 4px 20px rgba(0,0,0,0.4)',
        }}
      >
        {/* Top accent line */}
        {(plan.featured || plan.id === 'elite') && (
          <div
            className="absolute top-0 left-6 right-6 h-px"
            style={{
              background: `linear-gradient(90deg, transparent, ${accentColor}88, transparent)`,
            }}
          />
        )}

        {/* Badge */}
        {plan.badge && (
          <div className="mb-5">
            <span
              className="text-[10px] font-bold tracking-[0.12em] uppercase px-3 py-1 rounded-full font-mono"
              style={{
                color: accentColor,
                background: accentDim,
                border: `1px solid ${accentColor}35`,
              }}
            >
              {plan.badge}
            </span>
          </div>
        )}

        {/* Plan name */}
        <div className="mb-5">
          <h3 className="text-xl font-black text-white mb-1">{plan.name}</h3>
          {plan.tagline && (
            <p className="text-xs font-semibold tracking-wide" style={{ color: accentColor }}>
              {plan.tagline}
            </p>
          )}
          <p className="text-sm text-[#3D4F63] mt-2 leading-relaxed">{plan.description}</p>
        </div>

        {/* Price */}
        <div className="mb-7 pb-7 border-b border-[rgba(255,255,255,0.05)]">
          {plan.monthlyPrice === 0 ? (
            <div>
              <span className="text-5xl font-black text-white">Free</span>
              <span className="text-[#3D4F63] ml-2 text-sm font-mono">forever</span>
            </div>
          ) : (
            <div>
              <div className="flex items-baseline gap-1">
                <span className="text-[#7A8FA6] text-xl font-mono">₹</span>
                <motion.span
                  key={`${price}-${isAnnual}`}
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25, type: 'spring', stiffness: 200 }}
                  className="text-5xl font-black text-white font-mono"
                >
                  {price.toLocaleString('en-IN')}
                </motion.span>
                <span className="text-[#3D4F63] text-sm font-mono">/mo</span>
              </div>
              {isAnnual && (
                <motion.p
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  className="text-xs mt-2 font-semibold font-mono"
                  style={{ color: accentColor }}
                >
                  ₹{totalAnnual.toLocaleString('en-IN')} billed annually
                  {' · '}
                  Save ₹{((plan.monthlyPrice * 12) - totalAnnual).toLocaleString('en-IN')}
                </motion.p>
              )}
            </div>
          )}
        </div>

        {/* Features */}
        <ul className="space-y-3 flex-1 mb-7">
          {plan.features.map((f, i) => (
            <li key={i} className="flex items-start gap-3">
              <AnimatedCheck included={f.included} index={i} />
              <span
                className={`text-sm leading-snug ${
                  f.included ? 'text-[#C4D0DC]' : 'text-[#2A3440] line-through'
                }`}
              >
                {f.text}
              </span>
            </li>
          ))}
        </ul>

        {/* Seat counter for Elite */}
        {plan.id === 'elite' && seatsRemaining !== undefined && (
          <div className="mb-5 text-center">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full"
              style={{ background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.2)' }}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-[#F59E0B] animate-pulse" />
              <span className="text-xs text-[#F59E0B] font-semibold font-mono">{seatsRemaining} seats remaining</span>
            </div>
          </div>
        )}

        {/* CTA */}
        {onCheckout && plan.id !== 'free' ? (
          <button
            onClick={() => {
              const planKey = isAnnual ? `${plan.id}_annual` : `${plan.id}_monthly`
              onCheckout(planKey)
            }}
            disabled={loading}
            className={`w-full block text-center font-bold py-3.5 px-6 rounded-xl transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed ${
              plan.featured
                ? 'btn-brand'
                : 'bg-[rgba(255,255,255,0.04)] text-white border border-[rgba(255,255,255,0.1)] hover:border-[#F59E0B] hover:text-[#F59E0B] hover:bg-[rgba(245,158,11,0.04)]'
            }`}
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-4 h-4 border-2 border-current/30 border-t-current rounded-full animate-spin" />
                Opening checkout...
              </span>
            ) : plan.cta}
          </button>
        ) : (
          <Link
            href={plan.ctaLink}
            className={`block text-center font-bold py-3.5 px-6 rounded-xl transition-all duration-200 ${
              plan.featured
                ? 'btn-brand'
                : plan.id === 'free'
                ? 'btn-outline'
                : 'bg-[rgba(255,255,255,0.04)] text-white border border-[rgba(255,255,255,0.1)] hover:border-[#F59E0B] hover:text-[#F59E0B] hover:bg-[rgba(245,158,11,0.04)]'
            }`}
          >
            {plan.cta}
          </Link>
        )}
      </div>
    </motion.div>
  )
}

// Export plans for use in pages
export { PLANS }
