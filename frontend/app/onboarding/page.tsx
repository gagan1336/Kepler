'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '@/lib/auth'

/* ═══════════════════════════════════════════════════════════════════════════════
   ONBOARDING — 3-step full-screen flow (first login only)
   
   Step 1: Sector interests (multi-select chips)
   Step 2: Notification cadence
   Step 3: Tier confirmation
   
   Transitions: horizontal slide, ~250ms, no bounce — efficient, not playful.
   Progress: 3 thin gold segments at top (not a percentage).
   Gate: stored in localStorage — no DB change required.
═══════════════════════════════════════════════════════════════════════════════ */

const SECTORS = [
  'IT', 'Banking', 'FMCG', 'Auto', 'Pharma',
  'Metal', 'Energy', 'Realty', 'Defence', 'Infra',
  'Consumer', 'Cement', 'Chemicals', 'Telecom',
]

const NOTIF_OPTIONS = [
  {
    id: 'daily',
    label: 'Daily digest + Scanner',
    desc: 'Morning digest every weekday + breakout watchlist Mon/Wed/Fri',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 4h16v2.5a2 2 0 0 1-.6 1.45L13 14v6l-2-1-2 1v-6L4.6 7.95A2 2 0 0 1 4 6.5V4Z" />
      </svg>
    ),
  },
  {
    id: 'weekly',
    label: 'Weekly summary only',
    desc: 'One consolidated weekly roundup every Sunday morning',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
        <line x1="16" y1="2" x2="16" y2="6" />
        <line x1="8" y1="2" x2="8" y2="6" />
        <line x1="3" y1="10" x2="21" y2="10" />
      </svg>
    ),
  },
  {
    id: 'both',
    label: 'Everything',
    desc: 'Daily digest, scanner, sector report, IPO briefs, deep dives',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
      </svg>
    ),
  },
]

// Slide transition — horizontal, 250ms, no bounce
const slideVariants = {
  enter: (dir: number) => ({
    x: dir > 0 ? 40 : -40,
    opacity: 0,
  }),
  center: {
    x: 0,
    opacity: 1,
    transition: { duration: 0.25, ease: [0.4, 0, 0.2, 1] as [number, number, number, number] },
  },
  exit: (dir: number) => ({
    x: dir > 0 ? -40 : 40,
    opacity: 0,
    transition: { duration: 0.2, ease: [0.4, 0, 0.2, 1] as [number, number, number, number] },
  }),
}

export default function OnboardingPage() {
  const router = useRouter()
  const [step, setStep] = useState(0)
  const [direction, setDirection] = useState(1)
  const [sectors, setSectors] = useState<string[]>([])
  const [notif, setNotif] = useState('')
  const [loading, setLoading] = useState(false)

  // Guard: only show if not already onboarded and user is logged in
  const { isAuthenticated, loading: authLoading } = useAuth()
  useEffect(() => {
    const onboarded = localStorage.getItem('umbra_onboarded')
    if (onboarded === 'true') {
      router.replace('/dashboard')
    }
    if (!authLoading && !isAuthenticated) {
      router.replace('/login')
    }
  }, [router, authLoading, isAuthenticated])

  function goNext() {
    setDirection(1)
    setStep(s => s + 1)
  }

  function goBack() {
    setDirection(-1)
    setStep(s => s - 1)
  }

  async function complete() {
    setLoading(true)
    // Save preferences — replace with real API call if desired
    localStorage.setItem('umbra_onboarded', 'true')
    localStorage.setItem('umbra_sectors', JSON.stringify(sectors))
    localStorage.setItem('umbra_notif', notif)
    await new Promise(r => setTimeout(r, 600))
    router.push('/dashboard')
  }

  function toggleSector(s: string) {
    setSectors(prev =>
      prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]
    )
  }

  const STEPS = ['Sectors', 'Notifications', 'Confirm']

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ background: 'var(--bg-base)' }}
    >
      <div className="noise-overlay" />

      {/* ── Top progress — 3 thin gold segments ───────────────────────────── */}
      <div className="fixed top-0 left-0 right-0 z-50 flex gap-1 px-4 pt-3">
        {STEPS.map((_, i) => (
          <div key={i} className="onboarding-segment">
            <motion.div
              className="onboarding-segment-fill"
              animate={{ width: i <= step ? '100%' : '0%' }}
              transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            />
          </div>
        ))}
      </div>

      {/* ── Logo ───────────────────────────────────────────────────────────── */}
      <div className="pt-10 px-6 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div
            className="w-6 h-6 rounded-full"
            style={{
              background: 'radial-gradient(circle at 35% 35%, #DDB96A 0%, #C9A34E 45%, #0A0A0B 100%)',
              boxShadow: '0 0 0 1px rgba(201,163,78,0.3)',
            }}
          >
            <div className="w-full h-full rounded-full flex items-center justify-center">
              <div className="w-2 h-2 rounded-full" style={{ background: '#0A0A0B' }} />
            </div>
          </div>
          <span className="text-[15px] font-bold text-[#F2F2F0] tracking-tight">Umbra</span>
        </div>
        <span className="text-xs text-[#5C5C60] font-mono">
          Step {step + 1} of {STEPS.length}
        </span>
      </div>

      {/* ── Step content ────────────────────────────────────────────────────── */}
      <main className="flex-1 flex items-center justify-center px-6 py-12 overflow-hidden">
        <div className="w-full max-w-[500px]">
          <AnimatePresence mode="wait" custom={direction}>
            {/* ── STEP 0: Sector interests ─────────────────────────────── */}
            {step === 0 && (
              <motion.div
                key="step0"
                custom={direction}
                variants={slideVariants}
                initial="enter"
                animate="center"
                exit="exit"
              >
                <div className="mb-8">
                  <div className="section-label mb-4">Step 1</div>
                  <h1 className="text-3xl font-bold text-[#F2F2F0] mb-3 tracking-tight">
                    What sectors do you follow?
                  </h1>
                  <p className="text-[#9A9A9E] text-sm">
                    Select all that apply. We'll prioritize these in your morning digest.
                  </p>
                </div>

                <div className="flex flex-wrap gap-2 mb-10">
                  {SECTORS.map(s => {
                    const active = sectors.includes(s)
                    return (
                      <button
                        key={s}
                        type="button"
                        id={`sector-chip-${s.toLowerCase()}`}
                        onClick={() => toggleSector(s)}
                        className={`px-4 py-2 rounded-full text-sm font-semibold transition-all duration-200 border font-mono ${
                          active
                            ? 'bg-[rgba(201,163,78,0.14)] border-[rgba(201,163,78,0.4)] text-[#C9A34E]'
                            : 'bg-transparent border-[rgba(255,255,255,0.08)] text-[#5C5C60] hover:border-[rgba(255,255,255,0.16)] hover:text-[#9A9A9E]'
                        }`}
                      >
                        {s}
                      </button>
                    )
                  })}
                </div>

                <button
                  onClick={goNext}
                  id="onboard-next-0"
                  className="btn-brand w-full py-3.5"
                  disabled={sectors.length === 0}
                  style={{
                    opacity: sectors.length === 0 ? 0.5 : 1,
                    cursor: sectors.length === 0 ? 'not-allowed' : 'pointer',
                  }}
                >
                  Continue
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M2 7h10M7.5 3l4 4-4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              </motion.div>
            )}

            {/* ── STEP 1: Notification cadence ─────────────────────────── */}
            {step === 1 && (
              <motion.div
                key="step1"
                custom={direction}
                variants={slideVariants}
                initial="enter"
                animate="center"
                exit="exit"
              >
                <div className="mb-8">
                  <div className="section-label mb-4">Step 2</div>
                  <h1 className="text-3xl font-bold text-[#F2F2F0] mb-3 tracking-tight">
                    How often should we send updates?
                  </h1>
                  <p className="text-[#9A9A9E] text-sm">
                    You can change this anytime from your account settings.
                  </p>
                </div>

                <div className="space-y-3 mb-10">
                  {NOTIF_OPTIONS.map(opt => {
                    const active = notif === opt.id
                    return (
                      <button
                        key={opt.id}
                        type="button"
                        id={`notif-${opt.id}`}
                        onClick={() => setNotif(opt.id)}
                        className={`w-full rounded-xl p-4 text-left transition-all duration-200 border flex items-start gap-4 ${
                          active
                            ? 'bg-[rgba(201,163,78,0.08)] border-[rgba(201,163,78,0.32)] text-[#F2F2F0]'
                            : 'bg-transparent border-[rgba(255,255,255,0.07)] text-[#9A9A9E] hover:border-[rgba(255,255,255,0.14)]'
                        }`}
                      >
                        <div
                          className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
                          style={{
                            background: active ? 'rgba(201,163,78,0.14)' : 'rgba(255,255,255,0.04)',
                            color: active ? '#C9A34E' : '#5C5C60',
                          }}
                        >
                          {opt.icon}
                        </div>
                        <div>
                          <div className={`text-sm font-semibold mb-0.5 ${active ? 'text-[#F2F2F0]' : 'text-[#9A9A9E]'}`}>
                            {opt.label}
                          </div>
                          <div className="text-xs text-[#5C5C60]">{opt.desc}</div>
                        </div>
                        {active && (
                          <div className="ml-auto shrink-0 w-4 h-4 rounded-full flex items-center justify-center" style={{ background: '#C9A34E' }}>
                            <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                              <path d="M1.5 4l2 2L6.5 2" stroke="#0A0A0B" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                          </div>
                        )}
                      </button>
                    )
                  })}
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={goBack}
                    className="btn-outline flex-1 py-3.5"
                    id="onboard-back-1"
                  >
                    Back
                  </button>
                  <button
                    onClick={goNext}
                    className="btn-brand flex-1 py-3.5"
                    disabled={!notif}
                    style={{ opacity: !notif ? 0.5 : 1, cursor: !notif ? 'not-allowed' : 'pointer' }}
                    id="onboard-next-1"
                  >
                    Continue
                  </button>
                </div>
              </motion.div>
            )}

            {/* ── STEP 2: Tier confirmation ─────────────────────────────── */}
            {step === 2 && (
              <motion.div
                key="step2"
                custom={direction}
                variants={slideVariants}
                initial="enter"
                animate="center"
                exit="exit"
              >
                <div className="mb-8">
                  <div className="section-label mb-4">Step 3</div>
                  <h1 className="text-3xl font-bold text-[#F2F2F0] mb-3 tracking-tight">
                    You're all set.
                  </h1>
                  <p className="text-[#9A9A9E] text-sm">
                    Review your setup before entering the dashboard.
                  </p>
                </div>

                {/* Summary */}
                <div
                  className="rounded-xl overflow-hidden mb-8"
                  style={{
                    border: '1px solid rgba(201,163,78,0.2)',
                    background: 'rgba(201,163,78,0.04)',
                  }}
                >
                  {/* Top gold line */}
                  <div className="h-px bg-gradient-to-r from-transparent via-[rgba(201,163,78,0.5)] to-transparent" />

                  <div className="divide-y divide-[rgba(255,255,255,0.05)]">
                    <div className="flex items-center justify-between px-5 py-3.5">
                      <span className="text-xs text-[#5C5C60] font-mono uppercase tracking-widest">Sectors</span>
                      <span className="text-sm text-[#F2F2F0] font-semibold text-right max-w-[240px] truncate">
                        {sectors.slice(0, 4).join(', ')}{sectors.length > 4 ? ` +${sectors.length - 4} more` : ''}
                      </span>
                    </div>
                    <div className="flex items-center justify-between px-5 py-3.5">
                      <span className="text-xs text-[#5C5C60] font-mono uppercase tracking-widest">Updates</span>
                      <span className="text-sm text-[#F2F2F0] font-semibold">
                        {NOTIF_OPTIONS.find(o => o.id === notif)?.label}
                      </span>
                    </div>
                    <div className="flex items-center justify-between px-5 py-3.5">
                      <span className="text-xs text-[#5C5C60] font-mono uppercase tracking-widest">Delivery</span>
                      <span className="text-sm text-[#F2F2F0] font-semibold">8:00 AM IST</span>
                    </div>
                  </div>
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={goBack}
                    className="btn-outline py-3.5"
                    style={{ minWidth: 80 }}
                    id="onboard-back-2"
                  >
                    Back
                  </button>
                  <button
                    onClick={complete}
                    className="btn-brand flex-1 py-3.5"
                    disabled={loading}
                    id="onboard-finish"
                    style={{ boxShadow: '0 6px 28px rgba(201,163,78,0.22)' }}
                  >
                    {loading ? (
                      <span className="flex items-center gap-2">
                        <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Entering Umbra…
                      </span>
                    ) : (
                      'Enter Dashboard'
                    )}
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>
    </div>
  )
}
