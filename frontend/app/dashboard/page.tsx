'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import Navbar from '@/components/Navbar'
import DigestCard from '@/components/DigestCard'
import BreakoutWatchlist from '@/components/BreakoutWatchlist'
import SectorReport from '@/components/SectorReport'
import SectorHub from '@/components/SectorHub'
import IpoHub from '@/components/IpoHub'
import Disclaimer from '@/components/Disclaimer'
import StockSearchTab from '@/components/StockSearchTab'
import StockScreener from '@/components/StockScreener'
import NewListingsTab from '@/components/NewListingsTab'
import MarketNewsTab from '@/components/MarketNewsTab'
import DeepDiveCard from '@/components/DeepDiveCard'
import AccountTab from '@/components/AccountTab'
import SignalsFeedTab from '@/components/SignalsFeedTab'
import {
  apiDigestToday, apiBreakoutToday, apiSectorLatest, apiSectorHistory,
  apiIPOLatest, apiDeepDiveList, apiDashboardStats, apiCancelSubscription,
  apiMarketUpdates, apiSectorsLive, apiIpoHub,
  Digest, Breakout, SectorReport as SectorReportType, IPOBrief, DashboardStats, MarketUpdate,
  SectorHubResult, IpoHubResult,
} from '@/lib/api'
import { useAuth } from '@/lib/auth'

/* ── Tab definitions with SVG icons ──────────────────────────────────────────── */
interface TabDef {
  id: string
  label: string
  shortLabel: string
  group: 'intelligence' | 'screening' | 'analysis' | 'account'
  icon: React.ReactNode
}

const TABS: TabDef[] = [
  // Intelligence group
  {
    id: 'digest',
    label: "Today's Digest",
    shortLabel: 'Digest',
    group: 'intelligence',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 4h16v2.5a2 2 0 0 1-.6 1.45L13 14v6l-2-1-2 1v-6L4.6 7.95A2 2 0 0 1 4 6.5V4Z" />
      </svg>
    ),
  },
  {
    id: 'updates',
    label: 'Market News',
    shortLabel: 'News',
    group: 'intelligence',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 11a9 9 0 0 1 9 9" />
        <path d="M4 4a16 16 0 0 1 16 16" />
        <circle cx="5" cy="19" r="1" fill="currentColor" />
      </svg>
    ),
  },
  {
    id: 'deepdive',
    label: 'Deep Dives',
    shortLabel: 'Research',
    group: 'intelligence',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
        <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
      </svg>
    ),
  },
  // Screening group
  {
    id: 'stocksearch',
    label: 'Stock Search',
    shortLabel: 'Search',
    group: 'screening',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="11" cy="11" r="8" />
        <path d="m21 21-4.35-4.35" />
      </svg>
    ),
  },
  {
    id: 'screener',
    label: 'Stock Screener',
    shortLabel: 'Screener',
    group: 'screening',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
      </svg>
    ),
  },
  {
    id: 'breakout',
    label: 'Breakout Watchlist',
    shortLabel: 'Breakouts',
    group: 'screening',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
        <polyline points="16 7 22 7 22 13" />
      </svg>
    ),
  },
  {
    id: 'signals',
    label: 'Stock Signals',
    shortLabel: 'Signals',
    group: 'screening',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        <path d="M2 20h20"/>
        <path d="m6 16 4-8 4 6 3-4 3 6"/>
      </svg>
    ),
  },
  // Analysis group
  {
    id: 'sector',
    label: 'Sector Reports',
    shortLabel: 'Sectors',
    group: 'analysis',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 2a14.5 14.5 0 0 1 0 20" />
        <path d="M2 12h20" />
      </svg>
    ),
  },
  {
    id: 'ipo',
    label: 'IPO Briefs',
    shortLabel: 'IPOs',
    group: 'analysis',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
      </svg>
    ),
  },
  {
    id: 'newlistings',
    label: 'New Listings',
    shortLabel: 'Listings',
    group: 'analysis',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 5v14M5 12l7-7 7 7" />
      </svg>
    ),
  },
  // Account group
  {
    id: 'account',
    label: 'Account',
    shortLabel: 'Account',
    group: 'account',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
    ),
  },
]

const GROUP_LABELS: Record<string, string> = {
  intelligence: 'Intelligence',
  screening: 'Screening',
  analysis: 'Analysis',
  account: 'Account',
}

const GROUPS = ['intelligence', 'screening', 'analysis', 'account'] as const

/* ═══════════════════════════════════════════════════════════════════════════════
   DASHBOARD PAGE
═══════════════════════════════════════════════════════════════════════════════ */
export default function DashboardPage() {
  const router = useRouter()
  const { user: authUser, loading: authLoading, logout, isAuthenticated } = useAuth()
  const [activeTab, setActiveTab] = useState('digest')
  const [sidebarExpanded, setSidebarExpanded] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  // Data states
  const [digest, setDigest] = useState<Digest | null>(null)
  const [breakouts, setBreakouts] = useState<Breakout[]>([])
  const [sectorHub, setSectorHub] = useState<SectorHubResult | null>(null)
  const [ipoHub, setIpoHub] = useState<IpoHubResult | null>(null)
  const [deepDives, setDeepDives] = useState<any[]>([])
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [cancelling, setCancelling] = useState(false)

  useEffect(() => {
    // Only redirect if Supabase session check is complete AND there's no session
    // Do NOT redirect if still loading — that would cause a race condition
    if (!authLoading && !isAuthenticated) {
      router.push('/login')
      return
    }
    if (!authLoading && isAuthenticated) {
      loadTabData('digest')
      apiDashboardStats().then(setStats).catch(console.error)
    }
  }, [authLoading, isAuthenticated])

  const loadTabData = async (tab: string) => {
    setLoading(true)
    try {
      switch (tab) {
        case 'digest':
          if (!digest) setDigest(await apiDigestToday().catch(() => null)); break
        case 'updates': break // handled by MarketNewsTab internally
        case 'breakout':
          if (!breakouts.length) setBreakouts(await apiBreakoutToday().catch(() => [])); break
        case 'sector':
          setSectorHub(await apiSectorsLive().catch(() => null)); break
        case 'ipo':
          setIpoHub(await apiIpoHub().catch(() => null)); break
        case 'deepdive':
          if (!deepDives.length) setDeepDives(await apiDeepDiveList().catch(() => [])); break
      }
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  const handleTabChange = (tab: string) => {
    setActiveTab(tab)
    setMobileOpen(false)
    loadTabData(tab)
  }

  const handleCancel = async () => {
    if (!confirm('Cancel your subscription? You keep access until the billing period ends.')) return
    setCancelling(true)
    try {
      const result = await apiCancelSubscription()
      alert(`Cancelled. Your access continues until ${result.access_until}.`)
    } catch (e: any) { alert(e.message || 'Could not cancel subscription') }
    finally { setCancelling(false) }
  }

  const handleLogout = async () => { await logout(); router.push('/') }

  const user = authUser
  const isPro = user?.plan === 'pro' || user?.plan === 'elite'
  const isElite = user?.plan === 'elite'
  const planBadgeClass = isElite ? 'badge-elite' : isPro ? 'badge-pro' : 'badge-free'
  const activeTabDef = TABS.find(t => t.id === activeTab)

  const moodConfig = {
    BULLISH: { color: 'bg-[rgba(61,220,132,0.10)] text-[#3DDC84] border-[rgba(61,220,132,0.22)]', dot: 'bg-[#3DDC84]' },
    BEARISH: { color: 'bg-[rgba(229,72,77,0.10)] text-[#E5484D] border-[rgba(229,72,77,0.22)]', dot: 'bg-[#E5484D]' },
    NEUTRAL: { color: 'bg-[rgba(201,163,78,0.10)] text-[#C9A34E] border-[rgba(201,163,78,0.22)]', dot: 'bg-[#C9A34E]' },
  }

  // Wait for Supabase session check before rendering or redirecting
  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg-base)' }}>
        <div
          className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin"
          style={{ borderColor: 'rgba(201,163,78,0.2)', borderTopColor: '#C9A34E' }}
        />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-base)' }}>
      <Navbar />

      <div className="flex flex-1 pt-16">
        {/* ── Mobile FAB ──────────────────────────────────────────────────────── */}
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="md:hidden fixed bottom-6 right-6 z-50 w-13 h-13 bg-[#C9A34E] rounded-2xl flex items-center justify-center shadow-[0_8px_30px_rgba(201,163,78,0.3)] transition-transform active:scale-95"
          style={{ width: 52, height: 52 }}
        >
          {mobileOpen ? (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#000" strokeWidth="2.2" strokeLinecap="round">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#000" strokeWidth="2.2" strokeLinecap="round">
              <path d="M3 12h18M3 6h18M3 18h18" />
            </svg>
          )}
        </button>

        {/* Mobile overlay */}
        {mobileOpen && (
          <div
            className="md:hidden fixed inset-0 z-30 bg-black/60 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
          />
        )}

        {/* ── SIDEBAR ─────────────────────────────────────────────────────────── */}
        <aside
          onMouseEnter={() => setSidebarExpanded(true)}
          onMouseLeave={() => setSidebarExpanded(false)}
          className={`
            fixed md:sticky top-[60px] left-0 h-[calc(100vh-60px)] z-40
            border-r border-[rgba(255,255,255,0.06)]
            flex flex-col
            transition-all duration-300 ease-in-out
            ${mobileOpen ? 'translate-x-0 w-64' : '-translate-x-full'}
            md:translate-x-0
            ${sidebarExpanded ? 'md:w-60' : 'md:w-16'}
          `}
          style={{ background: 'var(--bg-elevated)' }}
        >
          {/* User info (expanded only) */}
          <div className={`border-b border-[rgba(255,255,255,0.06)] overflow-hidden transition-all duration-300 ${sidebarExpanded || mobileOpen ? 'p-4 opacity-100' : 'p-3 opacity-0 md:opacity-100'}`}>
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl flex items-center justify-center border shrink-0" style={{ background: 'rgba(201,163,78,0.1)', borderColor: 'rgba(201,163,78,0.2)' }}>
                <span className="font-bold text-sm uppercase" style={{ color: '#C9A34E' }}>
                  {user?.email?.[0] || 'U'}
                </span>
              </div>
              {(sidebarExpanded || mobileOpen) && (
                <div className="min-w-0 animate-fade-in">
                  <p className="text-xs text-white font-semibold truncate max-w-[140px]">{user?.email}</p>
                  <span className={`badge mt-1 ${planBadgeClass}`}>
                    {user?.plan?.toUpperCase() || 'FREE'}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Navigation groups */}
          <nav className="flex-1 overflow-y-auto py-3 space-y-1">
            {GROUPS.map(group => {
              const groupTabs = TABS.filter(t => t.group === group)
              if (group === 'account') return null // handled separately at bottom
              return (
                <div key={group} className="px-2">
                  {/* Group label */}
                  {(sidebarExpanded || mobileOpen) && (
                    <p className="text-[9px] font-bold tracking-[0.18em] uppercase text-[#5C5C60] px-2 py-2 animate-fade-in font-mono">
                      {GROUP_LABELS[group]}
                    </p>
                  )}
                  {!sidebarExpanded && !mobileOpen && <div className="h-2" />}
                  {/* Tabs */}
                  {groupTabs.map(tab => (
                    <button
                      key={tab.id}
                      onClick={() => handleTabChange(tab.id)}
                      title={!sidebarExpanded && !mobileOpen ? tab.label : undefined}
                      className={`
                        w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium
                        transition-all duration-200 mb-0.5 group relative
                        ${activeTab === tab.id
                          ? 'text-[#C9A34E] border border-[rgba(201,163,78,0.2)]' + (sidebarExpanded || mobileOpen ? ' bg-[rgba(201,163,78,0.08)]' : '')
                          : 'text-[#5C5C60] hover:text-[#9A9A9E] hover:bg-[rgba(255,255,255,0.035)] border border-transparent'
                        }
                      `}
                    >
                      {/* Active indicator */}
                      {activeTab === tab.id && (
                        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-r-full" style={{ background: '#C9A34E' }} />
                      )}
                      <span className="shrink-0">{tab.icon}</span>
                      {(sidebarExpanded || mobileOpen) && (
                        <span className="truncate animate-fade-in">{tab.label}</span>
                      )}
                    </button>
                  ))}
                  <div className="h-1" />
                </div>
              )
            })}
          </nav>

          {/* Bottom: Account + Upgrade + Logout */}
          <div className="border-t border-[rgba(255,255,255,0.06)] p-2 space-y-1">
            {/* Account tab */}
            <button
              onClick={() => handleTabChange('account')}
              title={!sidebarExpanded && !mobileOpen ? 'Account' : undefined}
              className={`
                w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium
                transition-all duration-200 group border
                ${activeTab === 'account'
                  ? 'text-[#C9A34E] border-[rgba(201,163,78,0.2)]'
                  : 'text-[#5C5C60] hover:text-[#9A9A9E] hover:bg-[rgba(255,255,255,0.035)] border-transparent'
                }
              `}
            >
              {TABS.find(t => t.id === 'account')?.icon}
              {(sidebarExpanded || mobileOpen) && (
                <span className="animate-fade-in">Account</span>
              )}
            </button>

            {/* Upgrade CTA (expanded only) */}
            {!isPro && (sidebarExpanded || mobileOpen) && (
              <Link
                href="/pricing"
                className="w-full btn-brand text-xs py-2.5 text-center block rounded-xl animate-fade-in"
              >
                Upgrade to Pro
              </Link>
            )}
            {/* Compact upgrade (collapsed) */}
            {!isPro && !sidebarExpanded && !mobileOpen && (
              <button
                onClick={() => router.push('/pricing')}
                title="Upgrade to Pro"
                className="w-full flex items-center justify-center px-3 py-2.5 rounded-xl hover:bg-[rgba(201,163,78,0.08)] transition-all"
                style={{ color: '#C9A34E' }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                </svg>
              </button>
            )}

            {/* Logout */}
            <button
              onClick={handleLogout}
              title={!sidebarExpanded && !mobileOpen ? 'Log out' : undefined}
              className="w-full flex items-center gap-3 px-3 py-2 rounded-xl text-[#4A5568] hover:text-[#8A9BB0] hover:bg-[rgba(255,255,255,0.04)] transition-all text-xs"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              {(sidebarExpanded || mobileOpen) && <span className="animate-fade-in">Log out</span>}
            </button>
          </div>
        </aside>

        {/* ── MAIN CONTENT ────────────────────────────────────────────────────── */}
        <main className="flex-1 min-w-0 p-6 md:p-8 overflow-auto" style={{ background: 'var(--bg-base)' }}>

          {/* ── DIGEST TAB ────────────────────────────────────────────────────── */}
          {activeTab === 'digest' && (
            <div className="animate-fade-in">
              <div className="flex items-center justify-between mb-7">
                <div>
                  <h1 className="text-2xl font-black text-white">Today's Digest</h1>
                  <p className="text-[#4A5568] text-sm mt-1">
                    {new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' })}
                  </p>
                </div>
                {digest?.market_mood && (() => {
                  const mc = moodConfig[digest.market_mood as keyof typeof moodConfig] || moodConfig.NEUTRAL
                  return (
                    <div className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-semibold ${mc.color}`}>
                      <div className={`w-1.5 h-1.5 rounded-full ${mc.dot}`} />
                      {digest.market_mood}
                    </div>
                  )
                })()}
              </div>

              {loading && <LoadingSkeleton />}

              {!loading && !digest && (
                <div className="glass-card p-12 text-center">
                  <p className="text-[#4A5568]">No digest available yet. Check back after 8 AM IST on weekdays.</p>
                </div>
              )}

              {digest && (
                <div className="space-y-4">
                  {digest.items.map((item, i) => <DigestCard key={i} item={item} index={i} />)}
                  {digest.is_restricted && digest.blurred_count > 0 && (
                    <div className="glass-card p-8 text-center border-dashed border-[rgba(0,212,163,0.15)]">
                      <p className="text-white font-bold mb-2">{digest.blurred_count} more items in today's digest</p>
                      <p className="text-[#4A5568] text-sm mb-5">Upgrade to Pro to unlock the full morning digest every day.</p>
                      <Link href="/pricing" className="btn-brand">Upgrade to Pro</Link>
                    </div>
                  )}
                  <div className="pt-4"><Disclaimer compact /></div>
                </div>
              )}
            </div>
          )}

          {/* ── STOCK SEARCH TAB ──────────────────────────────────────────────── */}
          {activeTab === 'stocksearch' && <StockSearchTab />}

          {/* ── SCREENER TAB ──────────────────────────────────────────────────── */}
          {activeTab === 'screener' && <StockScreener userPlan={user?.plan ?? 'free'} />}

          {/* ── MARKET NEWS TAB ───────────────────────────────────────────────── */}
          {activeTab === 'updates' && <MarketNewsTab userPlan={user?.plan ?? 'free'} />}

          {/* ── BREAKOUT TAB ──────────────────────────────────────────────────────── */}
          {activeTab === 'breakout' && (
            <div className="animate-fade-in">
              <div className="mb-7">
                <h1 className="text-2xl font-black text-white">Breakout Watchlist</h1>
                <p className="text-[#4A5568] text-sm mt-1">NSE stocks showing technical breakout signals</p>
              </div>
              {loading && <LoadingSkeleton />}
              {!loading && breakouts.length === 0 && (
                <div className="glass-card p-12 text-center">
                  <p className="text-[#4A5568]">No breakout signals detected today. Check back after market hours.</p>
                </div>
              )}
              {breakouts.length > 0 && (
                <div className="space-y-4">
                  {breakouts.map((b, i) => <BreakoutWatchlist key={i} breakouts={[b]} />)}
                </div>
              )}
            </div>
          )}

          {/* ── SECTOR TAB ────────────────────────────────────────────────────────── */}
          {activeTab === 'sector' && (
            <div className="animate-fade-in">
              <div className="mb-7">
                <h1 className="text-2xl font-black text-white">Sector Hub</h1>
                <p className="text-[#4A5568] text-sm mt-1">Live sector performance across NSE</p>
              </div>
              {loading && <LoadingSkeleton />}
              {!loading && !sectorHub && (
                <div className="glass-card p-12 text-center">
                  <p className="text-[#4A5568]">Sector data unavailable. Try again in a moment.</p>
                </div>
              )}
              {sectorHub && <SectorHub data={sectorHub} isPro={isPro} />}
            </div>
          )}

          {/* ── IPO TAB ───────────────────────────────────────────────────────────── */}
          {activeTab === 'ipo' && (
            <div className="animate-fade-in">
              <div className="mb-7">
                <h1 className="text-2xl font-black text-white">IPO Hub</h1>
                <p className="text-[#4A5568] text-sm mt-1">Upcoming, open and recently listed IPOs</p>
              </div>
              {loading && <LoadingSkeleton />}
              {!loading && !ipoHub && (
                <div className="glass-card p-12 text-center">
                  <p className="text-[#4A5568]">IPO data unavailable. Try again in a moment.</p>
                </div>
              )}
              {ipoHub && <IpoHub data={ipoHub} />}
            </div>
          )}

          {/* ── DEEP DIVE TAB ─────────────────────────────────────────────────────── */}
          {activeTab === 'deepdive' && (
            <div className="animate-fade-in">
              <div className="mb-7">
                <h1 className="text-2xl font-black text-white">AI Deep Dives</h1>
                <p className="text-[#4A5568] text-sm mt-1">In-depth AI analysis on individual stocks</p>
              </div>
              {loading && <LoadingSkeleton />}
              {!loading && deepDives.length === 0 && (
                <div className="glass-card p-12 text-center">
                  <p className="text-[#4A5568]">No deep dives published yet.</p>
                </div>
              )}
              {deepDives.length > 0 && (
                <div className="space-y-4">
                  {deepDives.map((d, i) => <DeepDiveCard key={i} dive={d} />)}
                </div>
              )}
            </div>
          )}

          {/* ── NEW LISTINGS TAB ──────────────────────────────────────────────────── */}
          {activeTab === 'newlistings' && <NewListingsTab />}

          {/* ── SIGNALS TAB ───────────────────────────────────────────────────────── */}
          {activeTab === 'signals' && <SignalsFeedTab userPlan={user?.plan ?? 'free'} />}

          {/* ── ACCOUNT TAB ──────────────────────────────────────────────── */}
          {activeTab === 'account' && (
            <AccountTab
              user={user}
              stats={stats}
              onLogout={handleLogout}
              onCancel={handleCancel}
              cancelling={cancelling}
            />
          )}
        </main>
      </div>
    </div>
  )
}

/* ── Skeleton ─────────────────────────────────────────────────────────────────── */
function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map((i) => (
        <div key={i} className="glass-card p-6">
          <div className="skeleton h-3 w-16 mb-4" />
          <div className="skeleton h-5 w-3/4 mb-3" />
          <div className="skeleton h-4 w-full mb-2" />
          <div className="skeleton h-4 w-2/3" />
        </div>
      ))}
    </div>
  )
}

/* ── Deep Dive Tab ────────────────────────────────────────────────────────────── */
function DeepDiveTab({ dives, loading, isPro, isElite }: {
  dives: any[]; loading: boolean; isPro: boolean; isElite: boolean
}) {
  const [verdictFilter, setVerdictFilter] = useState<string | null>(null)
  const VERDICTS = ['BUY', 'HOLD', 'AVOID']
  const filtered = verdictFilter ? dives.filter(d => d.verdict === verdictFilter) : dives

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-7 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-black text-white">Deep Dives</h1>
          <p className="text-[#4A5568] text-sm mt-1">Institutional-grade research, AI-powered</p>
        </div>
        {isElite && (
          <Link href="/admin" className="btn-outline text-xs py-2 px-4">
            + Generate New
          </Link>
        )}
      </div>

      {!isPro ? (
        <div className="glass-card p-12 text-center">
          <div className="w-16 h-16 rounded-2xl bg-[rgba(0,212,163,0.08)] flex items-center justify-center mx-auto mb-5 text-[#00D4A3]">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" /><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
            </svg>
          </div>
          <h3 className="text-white font-bold text-xl mb-3">Pro Feature</h3>
          <p className="text-[#4A5568] text-sm mb-6 max-w-xs mx-auto">Deep dives are available on Pro and Elite plans.</p>
          <Link href="/pricing" className="btn-brand">Upgrade to Pro</Link>
        </div>
      ) : loading ? (
        <LoadingSkeleton />
      ) : (
        <>
          {dives.some(d => d.verdict) && (
            <div className="flex gap-2 mb-6 flex-wrap">
              <button
                onClick={() => setVerdictFilter(null)}
                className={`text-xs px-3 py-1.5 rounded-full border transition-all ${
                  !verdictFilter ? 'bg-[#00D4A3] text-black border-[#00D4A3] font-bold' : 'text-[#4A5568] border-[rgba(255,255,255,0.08)] hover:border-[rgba(255,255,255,0.15)]'
                }`}
              >All</button>
              {VERDICTS.map(v => (
                <button key={v} onClick={() => setVerdictFilter(verdictFilter === v ? null : v)}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-all ${
                    verdictFilter === v
                      ? v === 'BUY' ? 'bg-[#00D4A3] text-black border-[#00D4A3] font-bold'
                      : v === 'HOLD' ? 'bg-[#F0B429] text-black border-[#F0B429] font-bold'
                                    : 'bg-[#ef4444] text-white border-[#ef4444] font-bold'
                      : 'text-[#4A5568] border-[rgba(255,255,255,0.08)] hover:border-[rgba(255,255,255,0.15)]'
                  }`}
                >{v}</button>
              ))}
            </div>
          )}

          {filtered.length === 0 && dives.length === 0 && (
            <div className="glass-card p-12 text-center">
              <div className="w-14 h-14 rounded-2xl bg-[rgba(255,255,255,0.04)] flex items-center justify-center mx-auto mb-4 text-[#4A5568]">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
                </svg>
              </div>
              <h3 className="text-white font-bold mb-2">No Deep Dives Yet</h3>
              <p className="text-[#4A5568] text-sm mb-6">Published monthly. {isElite ? 'Generate one from the admin panel.' : 'Check back soon.'}</p>
              {isElite && <Link href="/admin" className="btn-brand">Generate Deep Dive</Link>}
            </div>
          )}

          <div className="grid md:grid-cols-2 gap-4">
            {filtered.map(d => <DeepDiveCard key={d.id} dive={d} isElite={isElite} />)}
          </div>

          {!isElite && dives.length > 0 && (
            <div className="mt-6 glass-card p-8 text-center border-[rgba(0,212,163,0.12)]">
              <div className="w-12 h-12 rounded-xl bg-[rgba(0,212,163,0.08)] flex items-center justify-center mx-auto mb-4 text-[#00D4A3]">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
              </div>
              <p className="text-white font-bold mb-1">Full content requires Elite plan</p>
              <p className="text-[#4A5568] text-sm mb-5">Upgrade to read the complete structured research reports</p>
              <Link href="/pricing?plan=elite" className="btn-brand">Upgrade to Elite</Link>
            </div>
          )}
        </>
      )}
    </div>
  )
}
