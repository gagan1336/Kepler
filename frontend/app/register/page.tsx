'use client'
import { useState, Suspense } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import Disclaimer from '@/components/Disclaimer'
import { useAuth } from '@/lib/auth'

function RegisterPageInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const plan = searchParams.get('plan') || 'free'
  const { register, loginWithGoogle } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)
  const [error, setError] = useState('')
  const [confirmationSent, setConfirmationSent] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (password !== confirm) {
      setError('Passwords do not match')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    setLoading(true)
    try {
      const { needsConfirmation } = await register(email, password)
      if (needsConfirmation) {
        // Supabase email confirmation is enabled — show confirmation message
        setConfirmationSent(true)
      } else {
        // Auto-confirmed (e.g. email confirmation disabled in Supabase)
        if (plan !== 'free') {
          router.push(`/pricing?plan=${plan}`)
        } else {
          router.push('/dashboard')
        }
      }
    } catch (err: any) {
      setError(err.message || 'Registration failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleGoogleSignup = async () => {
    setError('')
    setGoogleLoading(true)
    try {
      await loginWithGoogle()
      // Browser is redirected to Supabase then back to /auth/callback
    } catch (err: any) {
      setError(err.message || 'Google sign-up failed. Please try again.')
      setGoogleLoading(false)
    }
  }

  const planLabels: Record<string, string> = {
    free: 'Free Plan',
    pro: 'Pro Plan (₹799/mo)',
    elite: 'Elite Plan (₹1,999/mo)',
  }

  // ── Email confirmation sent state ─────────────────────────────────────────
  if (confirmationSent) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4" style={{ background: 'var(--bg-base)' }}>
        <div className="absolute inset-0 bg-hero-gradient pointer-events-none" />
        <div className="relative w-full max-w-sm text-center">
          <div className="glass-card p-10">
            <div className="text-5xl mb-4">📬</div>
            <h1 className="text-xl font-bold text-[#F2F2F0] mb-3">Check your email</h1>
            <p className="text-[#777] text-sm leading-relaxed mb-6">
              We sent a confirmation link to <span className="text-[#C9A34E] font-medium">{email}</span>.
              Click it to activate your account.
            </p>
            <Link href="/login" className="btn-brand inline-block px-6 py-2 text-sm">
              Back to Login
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ background: 'var(--bg-base)' }}>
      <div className="absolute inset-0 bg-hero-gradient pointer-events-none" />
      <div className="absolute inset-0 bg-grid-pattern bg-grid opacity-50 pointer-events-none" />

      <div className="relative w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2.5 group justify-center">
            <div className="relative w-7 h-7 shrink-0">
              <div
                className="absolute inset-0 rounded-full opacity-30 blur-sm"
                style={{ background: 'radial-gradient(circle, #C9A34E 0%, transparent 70%)' }}
              />
              <div
                className="w-7 h-7 rounded-full flex items-center justify-center relative"
                style={{
                  background: 'radial-gradient(circle at 35% 35%, #DDB96A 0%, #C9A34E 45%, #0A0A0B 100%)',
                  boxShadow: '0 0 0 1px rgba(201,163,78,0.3)',
                }}
              >
                <div className="w-2.5 h-2.5 rounded-full" style={{ background: '#0A0A0B' }} />
              </div>
            </div>
            <span className="font-bold text-[17px] tracking-[-0.02em] text-[#F2F2F0]">Umbra</span>
          </Link>
          <p className="text-[#5C5C60] text-sm mt-3">
            {plan !== 'free'
              ? `Start your 7-day free trial — ${planLabels[plan]}`
              : 'Create your free account'}
          </p>
        </div>

        {/* Plan badge */}
        {plan !== 'free' && (
          <div className="mb-4 text-center">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[rgba(201,163,78,0.08)] border border-[rgba(201,163,78,0.2)]">
              <span className="text-sm text-[#C9A34E] font-semibold">7 days free · No card required</span>
            </div>
          </div>
        )}

        {/* Card */}
        <div className="glass-card p-8">
          {error && (
            <div className="mb-5 p-3 rounded-lg bg-[rgba(239,68,68,0.08)] border border-[rgba(239,68,68,0.2)] text-sm text-[#ef4444]">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-[#666] uppercase tracking-widest mb-2" htmlFor="reg-email">
                Email
              </label>
              <input
                id="reg-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input-dark"
                placeholder="you@example.com"
                required
                autoComplete="email"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#666] uppercase tracking-widest mb-2" htmlFor="reg-password">
                Password
              </label>
              <input
                id="reg-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-dark"
                placeholder="Minimum 8 characters"
                required
                minLength={8}
                autoComplete="new-password"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#666] uppercase tracking-widest mb-2" htmlFor="reg-confirm">
                Confirm Password
              </label>
              <input
                id="reg-confirm"
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className="input-dark"
                placeholder="••••••••"
                required
                autoComplete="new-password"
              />
            </div>

            <button
              type="submit"
              id="register-submit"
              disabled={loading}
              className="btn-brand w-full py-3 disabled:opacity-60 mt-2"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <div className="w-4 h-4 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                  Creating account...
                </span>
              ) : 'Start Free Trial →'}
            </button>
          </form>

          {/* Perks */}
          <div className="mt-6 space-y-2">
            {['No credit card required', 'Cancel anytime', '7 days full access'].map((perk) => (
              <div key={perk} className="flex items-center gap-2 text-xs text-[#555]">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M2 6l3 3 5-5" stroke="#C9A34E" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                {perk}
              </div>
            ))}
          </div>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-[#1e1e1e]" />
            </div>
            <div className="relative flex justify-center">
              <span className="px-4 text-xs text-[#444] bg-[#141414]">or</span>
            </div>
          </div>

          <button
            id="register-google"
            onClick={handleGoogleSignup}
            disabled={googleLoading}
            className="w-full flex items-center justify-center gap-3 py-3 px-4 rounded-xl bg-[#1a1a1a] border border-[#2a2a2a] text-sm font-medium text-[#ccc] hover:bg-[#222] hover:border-[#333] transition-all disabled:opacity-60"
          >
            {googleLoading ? (
              <div className="w-4 h-4 border-2 border-[#666]/30 border-t-[#666] rounded-full animate-spin" />
            ) : (
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615Z" fill="#4285F4" />
                <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18Z" fill="#34A853" />
                <path d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332Z" fill="#FBBC05" />
                <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58Z" fill="#EA4335" />
              </svg>
            )}
            Sign up with Google
          </button>

          <p className="text-center text-sm text-[#555] mt-6">
            Already have an account?{' '}
            <Link href="/login" className="text-[#C9A34E] font-medium hover:underline">
              Log in
            </Link>
          </p>
        </div>

        <div className="mt-6">
          <Disclaimer compact />
        </div>
      </div>
    </div>
  )
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#080C10]" />}>
      <RegisterPageInner />
    </Suspense>
  )
}
