'use client'
import { useState } from 'react'
import Link from 'next/link'
import type { AppUser } from '@/lib/auth'
import type { DashboardStats } from '@/lib/api'

interface Props {
  user: AppUser | null
  stats: DashboardStats | null
  onLogout: () => void
  onCancel: () => void
  cancelling: boolean
}

/* ── Plan metadata ─────────────────────────────────────────────── */
const PLAN_META = {
  free: {
    label: 'Free',
    color: '#A0AEC0',
    bg: 'rgba(160,174,192,0.10)',
    border: 'rgba(160,174,192,0.20)',
    description: '7-day trial included',
    features: ['3 digests/week (sample)', 'Public breakout watchlist', 'Sector overview', 'Basic IPO calendar'],
  },
  pro: {
    label: 'Pro',
    color: '#C9A34E',
    bg: 'rgba(201,163,78,0.10)',
    border: 'rgba(201,163,78,0.25)',
    description: 'Full market intelligence',
    features: ['Daily AI digest (full)', 'Breakout scanner (live)', 'Sector deep-dives', 'Market news feed', 'Telegram alerts'],
  },
  elite: {
    label: 'Elite',
    color: '#9F7AEA',
    bg: 'rgba(159,122,234,0.10)',
    border: 'rgba(159,122,234,0.25)',
    description: 'Everything + exclusive research',
    features: ['All Pro features', 'AI Stock Deep Dives', 'Elite Telegram channel', 'Priority support', 'Early feature access'],
  },
}

const StatBox = ({ value, label, icon }: { value: number | string; label: string; icon: React.ReactNode }) => (
  <div className="flex flex-col items-center justify-center p-4 rounded-xl text-center"
    style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
    <div className="mb-2 text-[#C9A34E]">{icon}</div>
    <div className="text-2xl font-black text-white mb-1">{value}</div>
    <p className="text-[10px] font-semibold uppercase tracking-widest text-[#4A5568]">{label}</p>
  </div>
)

const InfoRow = ({ label, value, accent }: { label: string; value: string; accent?: boolean }) => (
  <div className="flex items-center justify-between py-3 border-b last:border-0"
    style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
    <span className="text-xs font-semibold uppercase tracking-widest text-[#4A5568]">{label}</span>
    <span className={`text-sm font-medium ${accent ? 'text-[#C9A34E]' : 'text-[#D1D5DB]'}`}>{value}</span>
  </div>
)

export default function AccountTab({ user, stats, onLogout, onCancel, cancelling }: Props) {
  const [showCancelConfirm, setShowCancelConfirm] = useState(false)
  const plan = (user?.plan ?? 'free') as keyof typeof PLAN_META
  const meta = PLAN_META[plan]
  const isPro = plan === 'pro' || plan === 'elite'
  const isElite = plan === 'elite'

  const formatDate = (d: string | null | undefined) => {
    if (!d) return '—'
    try { return new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) }
    catch { return d }
  }

  const handleCancelClick = () => {
    if (showCancelConfirm) {
      onCancel()
      setShowCancelConfirm(false)
    } else {
      setShowCancelConfirm(true)
      setTimeout(() => setShowCancelConfirm(false), 5000)
    }
  }

  return (
    <div className="animate-fade-in max-w-2xl">
      {/* ── Header ── */}
      <div className="mb-8">
        <h1 className="text-2xl font-black text-white">My Account</h1>
        <p className="text-[#4A5568] text-sm mt-1">Manage your profile, plan, and billing</p>
      </div>

      <div className="grid gap-5">

        {/* ── Profile Card ── */}
        <div className="glass-card p-6">
          <h3 className="text-[10px] font-bold tracking-[0.15em] uppercase text-[#4A5568] mb-5">Profile</h3>
          <div className="flex items-center gap-4 mb-5">
            {/* Avatar */}
            <div className="w-14 h-14 rounded-full flex items-center justify-center text-xl font-black text-white flex-shrink-0"
              style={{ background: `linear-gradient(135deg, ${meta.color}33, ${meta.color}11)`, border: `2px solid ${meta.border}` }}>
              {user?.email?.[0]?.toUpperCase() ?? '?'}
            </div>
            <div className="min-w-0">
              <p className="text-white font-bold truncate">{user?.email ?? '—'}</p>
              <div className="flex items-center gap-2 mt-1">
                <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full"
                  style={{ background: meta.bg, color: meta.color, border: `1px solid ${meta.border}` }}>
                  {meta.label}
                </span>
                <span className="text-[11px] text-[#4A5568]">{meta.description}</span>
              </div>
            </div>
          </div>

          <div className="space-y-0">
            <InfoRow label="Email" value={user?.email ?? '—'} />
            <InfoRow label="Member since" value={formatDate(user?.created_at)} />
            <InfoRow label="Current plan" value={`${meta.label} Plan`} accent />
            {stats?.trial_ends && <InfoRow label="Trial ends" value={formatDate(stats.trial_ends)} />}
            {stats?.next_billing && <InfoRow label="Next billing" value={formatDate(stats.next_billing)} />}
          </div>
        </div>

        {/* ── Usage This Month ── */}
        {stats && (
          <div className="glass-card p-6">
            <h3 className="text-[10px] font-bold tracking-[0.15em] uppercase text-[#4A5568] mb-5">Activity This Month</h3>
            <div className="grid grid-cols-3 gap-3">
              <StatBox
                value={stats.digests_this_month}
                label="Digests"
                icon={
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M4 4h16v2.5a2 2 0 0 1-.6 1.45L13 14v6l-2-1-2 1v-6L4.6 7.95A2 2 0 0 1 4 6.5V4Z" />
                  </svg>
                }
              />
              <StatBox
                value={stats.chart_analyses_this_month}
                label="Analyses"
                icon={
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
                    <polyline points="16 7 22 7 22 13" />
                  </svg>
                }
              />
              <StatBox
                value={stats.sector_reports_this_month}
                label="Reports"
                icon={
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <path d="M12 2a14.5 14.5 0 0 1 0 20" />
                    <path d="M2 12h20" />
                  </svg>
                }
              />
            </div>
          </div>
        )}

        {/* ── Plan & Upgrade ── */}
        <div className="glass-card p-6">
          <h3 className="text-[10px] font-bold tracking-[0.15em] uppercase text-[#4A5568] mb-5">Your Plan</h3>

          {/* Features list */}
          <div className="mb-5 space-y-2">
            {meta.features.map((f, i) => (
              <div key={i} className="flex items-center gap-2">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke={meta.color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                <span className="text-sm text-[#D1D5DB]">{f}</span>
              </div>
            ))}
          </div>

          {/* CTA buttons */}
          <div className="flex flex-wrap gap-3 pt-3 border-t" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
            {!isPro && (
              <Link href="/pricing" className="btn-brand text-sm py-2 px-5">
                ✦ Upgrade to Pro
              </Link>
            )}
            {isPro && !isElite && (
              <Link href="/pricing?plan=elite" className="btn-brand text-sm py-2 px-5">
                ✦ Upgrade to Elite
              </Link>
            )}
            {isElite && (
              <div className="flex items-center gap-2 text-sm" style={{ color: meta.color }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                </svg>
                You're on the highest tier
              </div>
            )}
            {isPro && (
              <button
                onClick={handleCancelClick}
                disabled={cancelling}
                className="text-sm transition-colors py-2 px-3 rounded-lg"
                style={{
                  color: showCancelConfirm ? '#ef4444' : '#4A5568',
                  background: showCancelConfirm ? 'rgba(239,68,68,0.08)' : 'transparent',
                  border: showCancelConfirm ? '1px solid rgba(239,68,68,0.2)' : '1px solid transparent',
                }}
              >
                {cancelling ? 'Cancelling…' : showCancelConfirm ? '⚠ Tap again to confirm' : 'Cancel subscription'}
              </button>
            )}
          </div>
        </div>

        {/* ── Invoices ── */}
        {stats?.invoices && stats.invoices.length > 0 && (
          <div className="glass-card p-6">
            <h3 className="text-[10px] font-bold tracking-[0.15em] uppercase text-[#4A5568] mb-4">Billing History</h3>
            <div className="space-y-0">
              {stats.invoices.map((inv, i) => (
                <div key={i} className="flex items-center justify-between py-3 border-b last:border-0"
                  style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
                  <div>
                    <p className="text-sm text-white font-medium capitalize">{inv.plan} Plan</p>
                    <p className="text-xs text-[#4A5568]">{formatDate(inv.date)}</p>
                  </div>
                  <a href={inv.url} target="_blank" rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-xs font-medium transition-colors hover:text-[#C9A34E]"
                    style={{ color: '#00D4A3' }}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="7 10 12 15 17 10" />
                      <line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                    Download PDF
                  </a>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Danger Zone: Logout ── */}
        <div className="glass-card p-6">
          <h3 className="text-[10px] font-bold tracking-[0.15em] uppercase text-[#4A5568] mb-4">Session</h3>
          <button
            onClick={onLogout}
            className="flex items-center gap-2.5 text-sm text-[#4A5568] hover:text-[#ef4444] transition-colors group"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"
              className="group-hover:stroke-[#ef4444] transition-colors">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            Sign out of all devices
          </button>
          <p className="text-[11px] text-[#333] mt-2">You'll be asked to log in again next time.</p>
        </div>

      </div>
    </div>
  )
}
