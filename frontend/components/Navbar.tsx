'use client'
import { useState, useEffect } from 'react'
import Link from 'next/link'
import { motion, AnimatePresence } from 'framer-motion'
import { usePathname } from 'next/navigation'
import { getAccessToken } from '@/lib/api'

/**
 * Umbra Navbar
 * 
 * Public state: Logo left / "Request Access" CTA right — nothing else above the fold.
 * Authenticated state: Logo left / Dashboard link + account menu right.
 * 
 * The logo is the one quiet constant — no animation on the mark itself.
 * Scroll adds backdrop-blur. Mobile gets a simplified drawer.
 */
export default function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [isAuth, setIsAuth] = useState(false)
  const pathname = usePathname()

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 16)
    window.addEventListener('scroll', handler, { passive: true })
    return () => window.removeEventListener('scroll', handler)
  }, [])

  useEffect(() => {
    setMenuOpen(false)
  }, [pathname])

  useEffect(() => {
    setIsAuth(!!getAccessToken())
  }, [pathname])

  const isDashboard = pathname?.startsWith('/dashboard')

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
        scrolled || menuOpen
          ? 'bg-[rgba(10,10,11,0.92)] backdrop-blur-2xl border-b border-[rgba(255,255,255,0.06)]'
          : 'bg-transparent'
      }`}
    >
      <div className="max-w-7xl mx-auto px-6 h-[60px] flex items-center justify-between">

        {/* ── Logo wordmark — static, the one quiet constant ───────────── */}
        <Link
          href={isAuth ? '/dashboard' : '/'}
          className="flex items-center gap-3 group"
          aria-label="Umbra home"
        >
          {/* The eclipse mark — a simple circle with a shadow core */}
          <div className="relative w-7 h-7 shrink-0">
            <div
              className="absolute inset-0 rounded-full opacity-40 blur-sm transition-opacity duration-400 group-hover:opacity-70"
              style={{ background: 'radial-gradient(circle, #C9A34E 0%, transparent 70%)' }}
            />
            <div
              className="relative w-7 h-7 rounded-full flex items-center justify-center"
              style={{
                background: 'radial-gradient(circle at 35% 35%, #DDB96A 0%, #C9A34E 45%, #0A0A0B 100%)',
                boxShadow: '0 0 0 1px rgba(201,163,78,0.3)',
              }}
            >
              {/* Shadow core — the umbra */}
              <div
                className="w-2.5 h-2.5 rounded-full"
                style={{ background: '#0A0A0B' }}
              />
            </div>
          </div>

          {/* Wordmark — no animation, just clean type */}
          <span
            className="text-[17px] font-bold tracking-[-0.02em] text-[#F2F2F0]"
            style={{ letterSpacing: '-0.02em' }}
          >
            Umbra
          </span>
        </Link>

        {/* ── Desktop: right side ──────────────────────────────────────── */}
        <div className="hidden md:flex items-center gap-3">
          {isAuth ? (
            <>
              {!isDashboard && (
                <Link
                  href="/dashboard"
                  className="text-sm font-medium text-[#9A9A9E] hover:text-[#F2F2F0] transition-colors duration-200 px-3 py-2"
                >
                  Dashboard
                </Link>
              )}
              <Link
                href="/dashboard"
                className="btn-brand text-sm py-2 px-5"
                style={{ fontSize: '13px' }}
              >
                Open Dashboard
              </Link>
            </>
          ) : (
            <>
              <Link
                href="/login"
                className="text-sm font-medium text-[#5C5C60] hover:text-[#9A9A9E] transition-colors duration-200 px-3 py-2"
              >
                Sign in
              </Link>
              <Link
                href="/request-access"
                className="btn-brand text-sm py-2 px-5"
                style={{ fontSize: '13px' }}
              >
                Request Access
              </Link>
            </>
          )}
        </div>

        {/* ── Mobile menu toggle ───────────────────────────────────────── */}
        <button
          onClick={() => setMenuOpen(!menuOpen)}
          className="md:hidden p-2 rounded-lg text-[#5C5C60] hover:text-[#9A9A9E] hover:bg-white/[0.04] transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#C9A34E] focus-visible:ring-offset-1"
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={menuOpen}
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            {menuOpen ? (
              <path d="M3 3L15 15M15 3L3 15" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            ) : (
              <path d="M2 5H16M2 9H16M2 13H16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            )}
          </svg>
        </button>
      </div>

      {/* ── Mobile drawer ─────────────────────────────────────────────── */}
      <AnimatePresence>
        {menuOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
            className="md:hidden bg-[rgba(10,10,11,0.98)] backdrop-blur-2xl border-t border-[rgba(255,255,255,0.06)] overflow-hidden"
          >
            <div className="px-6 py-6 flex flex-col gap-4">
              {isAuth ? (
                <>
                  <Link
                    href="/dashboard"
                    onClick={() => setMenuOpen(false)}
                    className="text-base font-medium text-[#9A9A9E] hover:text-[#F2F2F0] transition-colors py-2"
                  >
                    Dashboard
                  </Link>
                  <Link
                    href="/login"
                    onClick={() => setMenuOpen(false)}
                    className="text-sm text-[#5C5C60] hover:text-[#9A9A9E] transition-colors py-1"
                  >
                    Sign out
                  </Link>
                </>
              ) : (
                <>
                  <Link
                    href="/request-access"
                    onClick={() => setMenuOpen(false)}
                    className="btn-brand text-center w-full"
                  >
                    Request Access
                  </Link>
                  <Link
                    href="/login"
                    onClick={() => setMenuOpen(false)}
                    className="text-center text-sm text-[#5C5C60] hover:text-[#9A9A9E] transition-colors py-2"
                  >
                    Already a member? Sign in
                  </Link>
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  )
}
