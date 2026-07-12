'use client'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

/**
 * Legacy Google OAuth Callback — now redirects to the Supabase callback.
 * Supabase OAuth goes to /auth/callback, not /auth/google/callback.
 * This page handles any lingering old-style redirects.
 */
export default function LegacyGoogleCallbackPage() {
  const router = useRouter()

  useEffect(() => {
    // Redirect to the new Supabase callback handler
    // The hash/params will be preserved in the URL
    router.replace('/auth/callback' + window.location.search + window.location.hash)
  }, [router])

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4" style={{ background: 'var(--bg-base)' }}>
      <div
        className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin"
        style={{ borderColor: 'rgba(201,163,78,0.2)', borderTopColor: '#C9A34E' }}
      />
      <p className="text-[#555] text-sm">Redirecting...</p>
    </div>
  )
}
