'use client'
import { useState } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import Disclaimer from '@/components/Disclaimer'
import { useAuth } from '@/lib/auth'
import { Suspense, useEffect } from 'react'

function LoginPageInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { login, loginWithGoogle } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const err = searchParams.get('error')
    if (err) setError(decodeURIComponent(err))
  }, [searchParams])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      router.push('/dashboard')
    } catch (err: any) {
      setError(err.message || 'Login failed. Please check your credentials.')
    } finally {
      setLoading(false)
    }
  }

  const handleGoogleLogin = async () => {
    setError('')
    setGoogleLoading(true)
    try {
      await loginWithGoogle()
      // Browser redirects to Supabase then back to /auth/callback
    } catch (err: any) {
      setError(err.message || 'Google sign-in failed. Please try again.')
      setGoogleLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ background: 'var(--bg-base)' }}>
      {/* Background */}
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
          <p className="text-[#5C5C60] text-sm mt-3">Welcome back</p>
        </div>

        {/* Card */}
        <div className="glass-card p-8">
          {error && (
            <div className="mb-5 p-3 rounded-lg bg-[rgba(239,68,68,0.08)] border border-[rgba(239,68,68,0.2)] text-sm text-[#ef4444]">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-[#666] uppercase tracking-widest mb-2" htmlFor="login-email">
                Email
              </label>
              <input
                id="login-email"
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
              <label className="block text-xs font-semibold text-[#666] uppercase tracking-widest mb-2" htmlFor="login-password">
                Password
              </label>
              <input
                id="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-dark"
                placeholder="••••••••"
                required
                autoComplete="current-password"
              />
            </div>

            <button
              type="submit"
              id="login-submit"
              disabled={loading}
              className="btn-brand w-full py-3 disabled:opacity-60 disabled:cursor-not-allowed mt-2"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <div className="w-4 h-4 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                  Logging in...
                </span>
              ) : 'Log In'}
            </button>
          </form>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-[#1e1e1e]" />
            </div>
            <div className="relative flex justify-center">
              <span className="px-4 text-xs text-[#444] bg-[#141414]">or continue with</span>
            </div>
          </div>

          <button
            id="login-google"
            onClick={handleGoogleLogin}
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
            Continue with Google
          </button>

          <p className="text-center text-sm text-[#555] mt-6">
            Don&apos;t have an account?{' '}
            <Link href="/register" className="text-[#C9A34E] font-medium hover:underline">
              Start free trial
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

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg-base)' }}>
        <div className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin"
          style={{ borderColor: 'rgba(201,163,78,0.2)', borderTopColor: '#C9A34E' }} />
      </div>
    }>
      <LoginPageInner />
    </Suspense>
  )
}
