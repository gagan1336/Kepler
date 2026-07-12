'use client'
import { useState } from 'react'
import Link from 'next/link'
import { motion, AnimatePresence } from 'framer-motion'
import Navbar from '@/components/Navbar'

/* ═══════════════════════════════════════════════════════════════════════════════
   REQUEST ACCESS
   
   Short form → confirmation screen with literal seat number.
   Tone: direct. This audience wants to feel vetted, not sold to.
   Defaults: mock storage (localStorage) — real backend POST easily added.
═══════════════════════════════════════════════════════════════════════════════ */

const TOTAL_SEATS = 1000

// In a real implementation, this reads from the /api/public-stats endpoint
function useSeatNumber() {
  if (typeof window === 'undefined') return 742
  const stored = localStorage.getItem('umbra_seat_count')
  return stored ? parseInt(stored, 10) + 1 : 743
}

type Stage = 'form' | 'confirming' | 'confirmed'

const EXPERIENCE_OPTIONS = [
  { value: 'under1', label: 'Under 1 year' },
  { value: '1to3', label: '1–3 years' },
  { value: '3to5', label: '3–5 years' },
  { value: 'over5', label: '5+ years' },
]

const TRADE_OPTIONS = [
  { value: 'cash', label: 'Cash (Delivery)' },
  { value: 'fo', label: 'F&O (Futures & Options)' },
  { value: 'both', label: 'Both Cash & F&O' },
]

export default function RequestAccessPage() {
  const [stage, setStage] = useState<Stage>('form')
  const [seatNumber, setSeatNumber] = useState(743)
  const [form, setForm] = useState({
    name: '',
    email: '',
    experience: '',
    tradeType: '',
  })
  const [errors, setErrors] = useState<Partial<typeof form>>({})

  function validate() {
    const e: Partial<typeof form> = {}
    if (!form.name.trim()) e.name = 'Required'
    if (!form.email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) e.email = 'Valid email required'
    if (!form.experience) e.experience = 'Required'
    if (!form.tradeType) e.tradeType = 'Required'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!validate()) return
    setStage('confirming')

    // Simulate network delay (replace with real POST to /api/waitlist)
    await new Promise(r => setTimeout(r, 1200))

    // Assign seat number
    const stored = typeof window !== 'undefined'
      ? parseInt(localStorage.getItem('umbra_seat_count') || '742', 10)
      : 742
    const seat = stored + 1
    if (typeof window !== 'undefined') {
      localStorage.setItem('umbra_seat_count', seat.toString())
    }
    setSeatNumber(seat)
    setStage('confirmed')
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-base)' }}>
      <div className="noise-overlay" />
      <Navbar />

      <main className="flex-1 flex items-center justify-center px-6 py-24 pt-32">
        <div className="w-full max-w-[440px]">
          <AnimatePresence mode="wait">

            {/* ── FORM ──────────────────────────────────────────────────────── */}
            {stage === 'form' && (
              <motion.div
                key="form"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.22, ease: [0.4, 0, 0.2, 1] }}
              >
                {/* Header */}
                <div className="mb-8">
                  <div className="section-label mb-4">Membership</div>
                  <h1 className="text-3xl font-bold text-[#F2F2F0] mb-3 tracking-tight">
                    Request access
                  </h1>
                  <p className="text-[#9A9A9E] text-sm leading-relaxed">
                    Umbra is capped at 1,000 members. We review each application to keep the signal-to-noise ratio high.
                  </p>
                </div>

                {/* Form */}
                <form onSubmit={handleSubmit} className="space-y-5" noValidate>
                  {/* Name */}
                  <div>
                    <label className="block text-xs font-semibold text-[#9A9A9E] mb-1.5 tracking-wide uppercase font-mono">
                      Name
                    </label>
                    <input
                      id="request-name"
                      type="text"
                      autoComplete="name"
                      className="input-dark"
                      placeholder="Your full name"
                      value={form.name}
                      onChange={e => { setForm({ ...form, name: e.target.value }); setErrors({ ...errors, name: undefined }) }}
                    />
                    {errors.name && <p className="text-[#E5484D] text-xs mt-1.5 font-mono">{errors.name}</p>}
                  </div>

                  {/* Email */}
                  <div>
                    <label className="block text-xs font-semibold text-[#9A9A9E] mb-1.5 tracking-wide uppercase font-mono">
                      Email
                    </label>
                    <input
                      id="request-email"
                      type="email"
                      autoComplete="email"
                      className="input-dark"
                      placeholder="you@example.com"
                      value={form.email}
                      onChange={e => { setForm({ ...form, email: e.target.value }); setErrors({ ...errors, email: undefined }) }}
                    />
                    {errors.email && <p className="text-[#E5484D] text-xs mt-1.5 font-mono">{errors.email}</p>}
                  </div>

                  {/* Trading experience */}
                  <div>
                    <label className="block text-xs font-semibold text-[#9A9A9E] mb-1.5 tracking-wide uppercase font-mono">
                      Trading Experience
                    </label>
                    <select
                      id="request-experience"
                      className="input-dark appearance-none"
                      value={form.experience}
                      onChange={e => { setForm({ ...form, experience: e.target.value }); setErrors({ ...errors, experience: undefined }) }}
                      style={{ cursor: 'pointer' }}
                    >
                      <option value="">Select experience</option>
                      {EXPERIENCE_OPTIONS.map(o => (
                        <option key={o.value} value={o.value} style={{ background: '#1C1C1F' }}>{o.label}</option>
                      ))}
                    </select>
                    {errors.experience && <p className="text-[#E5484D] text-xs mt-1.5 font-mono">{errors.experience}</p>}
                  </div>

                  {/* What you trade */}
                  <div>
                    <label className="block text-xs font-semibold text-[#9A9A9E] mb-1.5 tracking-wide uppercase font-mono">
                      What do you trade?
                    </label>
                    <div className="grid grid-cols-3 gap-2">
                      {TRADE_OPTIONS.map(o => (
                        <button
                          key={o.value}
                          type="button"
                          id={`request-trade-${o.value}`}
                          onClick={() => { setForm({ ...form, tradeType: o.value }); setErrors({ ...errors, tradeType: undefined }) }}
                          className={`py-2.5 px-3 rounded-lg text-xs font-semibold text-center transition-all duration-200 border ${
                            form.tradeType === o.value
                              ? 'bg-[rgba(201,163,78,0.12)] border-[rgba(201,163,78,0.35)] text-[#C9A34E]'
                              : 'bg-transparent border-[rgba(255,255,255,0.07)] text-[#5C5C60] hover:border-[rgba(255,255,255,0.14)] hover:text-[#9A9A9E]'
                          }`}
                        >
                          {o.label}
                        </button>
                      ))}
                    </div>
                    {errors.tradeType && <p className="text-[#E5484D] text-xs mt-1.5 font-mono">{errors.tradeType}</p>}
                  </div>

                  {/* Submit */}
                  <button
                    type="submit"
                    id="request-submit-btn"
                    className="btn-brand w-full py-3.5 mt-2"
                    style={{ boxShadow: '0 6px 28px rgba(201,163,78,0.22)' }}
                  >
                    Request a Seat
                  </button>
                </form>

                <p className="text-center text-xs text-[#5C5C60] mt-5 font-mono">
                  Already a member?{' '}
                  <Link href="/login" className="text-[#9A9A9E] hover:text-[#C9A34E] transition-colors">
                    Sign in
                  </Link>
                </p>
              </motion.div>
            )}

            {/* ── CONFIRMING (loading state) ────────────────────────────────── */}
            {stage === 'confirming' && (
              <motion.div
                key="confirming"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.18 }}
                className="text-center py-12"
              >
                <div className="relative w-16 h-16 mx-auto mb-6">
                  <div
                    className="absolute inset-0 rounded-full animate-spin"
                    style={{
                      background: 'conic-gradient(from 0deg, #C9A34E, transparent)',
                      animationDuration: '1s',
                    }}
                  />
                  <div
                    className="absolute inset-1 rounded-full"
                    style={{ background: 'var(--bg-base)' }}
                  />
                  <div
                    className="absolute inset-0 rounded-full"
                    style={{
                      background: 'radial-gradient(circle at 35% 35%, #DDB96A 0%, #C9A34E 45%, #0A0A0B 100%)',
                      boxShadow: '0 0 0 1px rgba(201,163,78,0.3)',
                      inset: '4px',
                      position: 'absolute',
                    }}
                  />
                </div>
                <p className="text-[#9A9A9E] text-sm font-mono">Processing your request…</p>
              </motion.div>
            )}

            {/* ── CONFIRMED ────────────────────────────────────────────────────── */}
            {stage === 'confirmed' && (
              <motion.div
                key="confirmed"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                className="text-center"
              >
                {/* Eclipse mark large */}
                <div className="relative w-20 h-20 mx-auto mb-8">
                  <div
                    className="absolute inset-0 rounded-full opacity-30 blur-lg"
                    style={{ background: 'radial-gradient(circle, #C9A34E 0%, transparent 70%)' }}
                  />
                  <div
                    className="w-20 h-20 rounded-full flex items-center justify-center relative"
                    style={{
                      background: 'radial-gradient(circle at 35% 35%, #DDB96A 0%, #C9A34E 50%, #0A0A0B 100%)',
                      boxShadow: '0 0 0 1.5px rgba(201,163,78,0.35), 0 0 40px rgba(201,163,78,0.2)',
                    }}
                  >
                    <div
                      className="w-9 h-9 rounded-full"
                      style={{ background: '#0A0A0B' }}
                    />
                  </div>
                </div>

                {/* Seat number — the honest scarcity signal */}
                <div className="mb-2">
                  <span
                    className="text-[68px] font-bold font-mono leading-none"
                    style={{ color: '#C9A34E' }}
                  >
                    #{seatNumber}
                  </span>
                </div>
                <p className="text-[#9A9A9E] text-sm mb-8 font-mono">
                  of {TOTAL_SEATS} seats · {TOTAL_SEATS - seatNumber} remaining
                </p>

                <h2 className="text-2xl font-bold text-[#F2F2F0] mb-3 tracking-tight">
                  You're on the list.
                </h2>
                <p className="text-[#9A9A9E] text-sm leading-relaxed mb-8 max-w-xs mx-auto">
                  We'll review your application and send you a magic link when your seat is confirmed. Usually within 24–48 hours.
                </p>

                <div
                  className="rounded-xl px-5 py-4 mb-8 text-left"
                  style={{
                    background: 'rgba(201,163,78,0.05)',
                    border: '1px solid rgba(201,163,78,0.15)',
                  }}
                >
                  <p className="text-xs text-[#5C5C60] font-mono mb-1 uppercase tracking-widest">What happens next</p>
                  <ul className="space-y-2 mt-3">
                    {[
                      'Email confirmation sent to your inbox',
                      'Application reviewed within 24h',
                      'Magic link to activate your seat',
                    ].map((step, i) => (
                      <li key={i} className="flex items-center gap-2.5 text-sm text-[#9A9A9E]">
                        <span className="w-4 h-4 rounded-full bg-[rgba(201,163,78,0.15)] flex items-center justify-center shrink-0">
                          <span className="text-[9px] font-bold text-[#C9A34E] font-mono">{i + 1}</span>
                        </span>
                        {step}
                      </li>
                    ))}
                  </ul>
                </div>

                <Link href="/" className="text-sm text-[#5C5C60] hover:text-[#9A9A9E] transition-colors font-mono">
                  ← Back to homepage
                </Link>
              </motion.div>
            )}

          </AnimatePresence>
        </div>
      </main>
    </div>
  )
}
