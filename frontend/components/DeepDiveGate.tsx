'use client'
import React from 'react'
import Link from 'next/link'
import { motion } from 'framer-motion'

interface DeepDiveGateProps {
  /** 'free' | 'pro' | 'elite' */
  requiredTier: 'pro' | 'elite'
  userTier: 'free' | 'pro' | 'elite'
  children: React.ReactNode
  /** How many lines to show before blurring (default 8) */
  previewLines?: number
}

const TIER_RANK: Record<string, number> = { free: 0, pro: 1, elite: 2 }
const TIER_LABELS: Record<string, string> = { pro: 'Pro', elite: 'Elite' }
const TIER_PRICES: Record<string, string> = { pro: '₹799/mo', elite: '₹1,499/mo' }

/**
 * DeepDiveGate — Wraps long-form content with a blur overlay when
 * the user's tier doesn't meet the required tier.
 *
 * - Shows the beginning of the content clearly
 * - Blurs the lower half with a fade gradient + upgrade card overlay
 * - Honest about what's gated — not a dark-pattern teaser
 * - No animation inside the overlay (respects reading focus)
 */
export default function DeepDiveGate({
  requiredTier,
  userTier,
  children,
  previewLines = 8,
}: DeepDiveGateProps) {
  const userRank = TIER_RANK[userTier] ?? 0
  const requiredRank = TIER_RANK[requiredTier] ?? 1
  const isGated = userRank < requiredRank

  if (!isGated) return <>{children}</>

  return (
    <div className="relative">
      {/* Visible content */}
      <div
        className="relative overflow-hidden"
        style={{
          maxHeight: `${previewLines * 1.85 * 16}px`, // approx N lines
        }}
      >
        {children}
        {/* Gradient fade to blur */}
        <div
          className="absolute bottom-0 left-0 right-0"
          style={{
            height: '60%',
            background: `linear-gradient(to bottom, transparent 0%, rgba(10,10,11,0.75) 45%, rgba(10,10,11,0.98) 100%)`,
            backdropFilter: 'blur(6px)',
            WebkitBackdropFilter: 'blur(6px)',
          }}
        />
      </div>

      {/* Upgrade overlay — honest, not dark-pattern */}
      <div
        className="relative rounded-2xl mt-0 overflow-hidden"
        style={{
          background: 'rgba(13,13,15,0.98)',
          border: '1px solid rgba(201,163,78,0.2)',
        }}
      >
        {/* Top accent line */}
        <div className="h-px bg-gradient-to-r from-transparent via-[rgba(201,163,78,0.45)] to-transparent" />

        <div className="px-8 py-10 text-center">
          {/* Lock icon */}
          <div
            className="w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-5"
            style={{
              background: 'rgba(201,163,78,0.1)',
              border: '1px solid rgba(201,163,78,0.2)',
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#C9A34E" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
          </div>

          <div
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full mb-4 text-xs font-bold font-mono"
            style={{
              background: 'rgba(201,163,78,0.1)',
              border: '1px solid rgba(201,163,78,0.25)',
              color: '#C9A34E',
              letterSpacing: '0.12em',
            }}
          >
            {TIER_LABELS[requiredTier]} Only
          </div>

          <h3 className="text-xl font-bold text-[#F2F2F0] mb-2 tracking-tight">
            This Deep Dive is for {TIER_LABELS[requiredTier]} members
          </h3>
          <p className="text-[#9A9A9E] text-sm leading-relaxed mb-8 max-w-sm mx-auto">
            Upgrade to {TIER_LABELS[requiredTier]} to read this report and all Deep Dives in the archive.
            {TIER_PRICES[requiredTier] && ` Starts at ${TIER_PRICES[requiredTier]}.`}
          </p>

          {/* What you get */}
          <div
            className="rounded-xl px-5 py-4 mb-8 text-left"
            style={{
              background: 'rgba(255,255,255,0.02)',
              border: '1px solid rgba(255,255,255,0.06)',
            }}
          >
            <p className="text-[9px] font-bold text-[#5C5C60] font-mono uppercase tracking-[0.2em] mb-3">
              {TIER_LABELS[requiredTier]} includes
            </p>
            <ul className="space-y-2">
              {(requiredTier === 'elite'
                ? [
                    'All Deep Dive reports (12+ in archive)',
                    'Sector deep dives + macro themes',
                    'Priority access to new reports',
                    'Full Breakout Scanner + watchlist',
                    'Morning Digest — all items',
                  ]
                : [
                    'Full Breakout Scanner access',
                    'Complete morning digest',
                    'Sector reports + IPO briefs',
                    'Pro Deep Dives',
                  ]
              ).map((item, i) => (
                <li key={i} className="flex items-center gap-2.5 text-sm text-[#9A9A9E]">
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                    <circle cx="6" cy="6" r="5" stroke="#C9A34E" strokeWidth="1.2" />
                    <path d="M3.5 6l2 2L8.5 4" stroke="#C9A34E" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <Link
            href={`/pricing#${requiredTier}`}
            className="btn-brand w-full py-3.5 text-sm"
            style={{ boxShadow: '0 6px 28px rgba(201,163,78,0.2)' }}
          >
            Upgrade to {TIER_LABELS[requiredTier]}
          </Link>
          <p className="text-xs text-[#5C5C60] mt-3 font-mono">
            Cancel anytime · Full refund within 30 days
          </p>
        </div>
      </div>
    </div>
  )
}
