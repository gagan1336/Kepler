'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import {
  apiLiveNews, apiRefreshNews,
  type LiveNewsArticle, type LiveNewsResult, type NewsCategory,
} from '@/lib/api'
import GlobalMarketsWidget from '@/components/GlobalMarketsWidget'

// ── Category metadata (SVG icons instead of emoji) ────────────────────────────
const CATEGORIES: { id: NewsCategory; label: string; icon: React.ReactNode; color: string }[] = [
  { id: 'ALL',     label: 'All News',    color: 'var(--gain, #3DDC84)',   icon: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg> },
  { id: 'BREAKING',label: 'Breaking',    color: '#ef4444',                icon: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> },
  { id: 'MARKETS', label: 'Markets',     color: '#10b981',                icon: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg> },
  { id: 'STOCKS',  label: 'Stocks',      color: '#3b82f6',                icon: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg> },
  { id: 'RBI',     label: 'RBI / Macro', color: '#8b5cf6',                icon: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg> },
  { id: 'SEBI',    label: 'SEBI',        color: '#a78bfa',                icon: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg> },
  { id: 'GST_TAX', label: 'GST & Tax',   color: '#f59e0b',                icon: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg> },
  { id: 'IPO',     label: 'IPO',         color: '#ec4899',                icon: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14M5 12l7-7 7 7"/></svg> },
  { id: 'GLOBAL',  label: 'Global',      color: '#64748b',                icon: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg> },
]

const IMPACT_STYLE: Record<string, { label: string; dot: string; badge: string }> = {
  HIGH:   { label: 'High Impact',   dot: '#ef4444', badge: 'rgba(239,68,68,0.10)'   },
  MEDIUM: { label: 'Medium Impact', dot: '#f59e0b', badge: 'rgba(245,158,11,0.10)'  },
  LOW:    { label: 'Low Impact',    dot: '#475569', badge: 'rgba(71,85,105,0.10)'   },
}

const CAT_META: Record<string, { color: string }> = {
  BREAKING: { color: '#ef4444' },
  MARKETS:  { color: '#10b981' },
  STOCKS:   { color: '#3b82f6' },
  RBI:      { color: '#8b5cf6' },
  SEBI:     { color: '#a78bfa' },
  GST_TAX:  { color: '#f59e0b' },
  IPO:      { color: '#ec4899' },
  GLOBAL:   { color: '#64748b' },
}

// ── SVG Icons ─────────────────────────────────────────────────────────────────
const IconRefresh = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 4 23 10 17 10" /><polyline points="1 20 1 14 7 14" />
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
  </svg>
)
const IconAlertCircle = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
  </svg>
)
const IconLock = () => (
  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
  </svg>
)
const IconNewspaper = () => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/>
    <path d="M18 14h-8M15 18h-5M10 6h8v4h-8V6z"/>
  </svg>
)
const IconExternalLink = () => (
  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
    <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
  </svg>
)

// ── Breaking ticker bar ───────────────────────────────────────────────────────
function BreakingTicker({ articles }: { articles: LiveNewsArticle[] }) {
  const high = articles.filter(a => a.impact === 'HIGH').slice(0, 12)
  if (!high.length) return null
  const doubled = [...high, ...high]

  return (
    <div style={{
      background: 'rgba(239,68,68,0.07)',
      border: '1px solid rgba(239,68,68,0.18)',
      borderRadius: '10px',
      display: 'flex', alignItems: 'center',
      overflow: 'hidden', marginBottom: '18px', height: '38px',
    }}>
      <div style={{
        flexShrink: 0, background: 'rgba(239,68,68,0.85)',
        color: '#fff', fontSize: '10px', fontWeight: 800,
        letterSpacing: '1.5px', padding: '0 14px', height: '100%',
        display: 'flex', alignItems: 'center', whiteSpace: 'nowrap',
        gap: '6px',
      }}>
        {/* Animated live dot */}
        <span style={{
          width: 6, height: 6, borderRadius: '50%', background: '#fff',
          display: 'inline-block', animation: 'mn-pulse 1.2s ease-in-out infinite',
        }} />
        LIVE
      </div>
      <div style={{ overflow: 'hidden', flex: 1 }}>
        <div style={{
          display: 'flex', animation: 'mn-marquee 60s linear infinite',
          whiteSpace: 'nowrap', gap: '48px', alignItems: 'center', height: '38px',
        }}>
          {doubled.map((a, i) => (
            <a key={i} href={a.url} target="_blank" rel="noopener noreferrer"
              style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-primary)', textDecoration: 'none', whiteSpace: 'nowrap' }}
              onMouseEnter={e => (e.currentTarget.style.color = '#ef4444')}
              onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-primary)')}
            >
              {a.title}
            </a>
          ))}
        </div>
      </div>
      <style>{`
        @keyframes mn-marquee { 0%{transform:translateX(0)} 100%{transform:translateX(-50%)} }
        @keyframes mn-pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
      `}</style>
    </div>
  )
}

// ── Single news card ──────────────────────────────────────────────────────────
function NewsCard({ article }: { article: LiveNewsArticle }) {
  const imp  = IMPACT_STYLE[article.impact] || IMPACT_STYLE.LOW
  const cat  = CAT_META[article.category] || { color: '#64748b' }
  const catDef = CATEGORIES.find(c => c.id === article.category)
  const isHigh = article.impact === 'HIGH'

  return (
    <a href={article.url} target="_blank" rel="noopener noreferrer"
      style={{
        display: 'block',
        background: isHigh
          ? 'linear-gradient(135deg, rgba(239,68,68,0.05) 0%, var(--bg-surface, #0F0F11) 100%)'
          : 'var(--bg-surface, #0F0F11)',
        border: `1px solid ${isHigh ? 'rgba(239,68,68,0.18)' : 'var(--border)'}`,
        borderLeft: `3px solid ${isHigh ? '#ef4444' : cat.color}`,
        borderRadius: '12px', padding: '15px 18px',
        cursor: 'pointer', transition: 'all 0.18s',
        textDecoration: 'none', color: 'inherit',
      }}
      onMouseEnter={e => {
        const el = e.currentTarget as HTMLAnchorElement
        el.style.borderColor = cat.color + '45'
        el.style.transform = 'translateY(-1px)'
      }}
      onMouseLeave={e => {
        const el = e.currentTarget as HTMLAnchorElement
        el.style.borderColor = isHigh ? 'rgba(239,68,68,0.18)' : 'var(--border)'
        el.style.transform = 'none'
      }}
    >
      {/* Top row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px', flexWrap: 'wrap' }}>
        <span style={{
          background: cat.color + '14', color: cat.color,
          fontSize: '10px', fontWeight: 700, padding: '3px 8px',
          borderRadius: '6px', letterSpacing: '0.4px',
          border: `1px solid ${cat.color}25`,
          display: 'flex', alignItems: 'center', gap: '4px',
          fontFamily: 'var(--font-primary)',
        }}>
          {catDef?.icon}
          {article.category.replace('_', ' & ')}
        </span>

        <span style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-primary)' }}>
          <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: imp.dot, display: 'inline-block', flexShrink: 0 }} />
          {imp.label}
        </span>

        <span style={{ marginLeft: 'auto', fontSize: '11px', color: 'var(--text-muted)', whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)' }}>
          {article.time_ago}
        </span>
      </div>

      {/* Headline */}
      <h3 style={{ margin: '0 0 8px', fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.45, letterSpacing: '-0.1px', fontFamily: 'var(--font-primary)' }}>
        {article.title}
      </h3>

      {/* Description */}
      {article.description && (
        <p style={{
          margin: '0 0 10px', fontSize: '12px',
          color: 'var(--text-tertiary)', lineHeight: 1.55,
          display: '-webkit-box', WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical', overflow: 'hidden',
          fontFamily: 'var(--font-primary)',
        }}>
          {article.description}
        </p>
      )}

      {/* Source + link */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600, fontFamily: 'var(--font-primary)' }}>
          {article.source}
        </span>
        <span style={{ fontSize: '11px', color: cat.color, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4, fontFamily: 'var(--font-primary)' }}>
          Read <IconExternalLink />
        </span>
      </div>
    </a>
  )
}

// ── Stats bar ─────────────────────────────────────────────────────────────────
function StatsBar({ result, onRefresh, refreshing, isPro }: {
  result: LiveNewsResult; onRefresh: () => void; refreshing: boolean; isPro: boolean
}) {
  const [countdown, setCountdown] = useState(result.next_refresh_in)
  const lastServerVal = useRef(result.next_refresh_in)

  useEffect(() => {
    const diff = Math.abs(result.next_refresh_in - lastServerVal.current)
    if (diff > 30) {
      setCountdown(result.next_refresh_in)
      lastServerVal.current = result.next_refresh_in
    }
    const t = setInterval(() => setCountdown(c => Math.max(0, c - 1)), 1000)
    return () => clearInterval(t)
  }, [result.next_refresh_in])

  const mins = Math.floor(countdown / 60)
  const secs = countdown % 60

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '12px',
      marginBottom: '18px', padding: '10px 16px',
      background: 'var(--bg-surface, #0F0F11)',
      border: '1px solid var(--border)', borderRadius: '10px', flexWrap: 'wrap',
    }}>
      <div style={{ display: 'flex', gap: '16px', flex: 1 }}>
        <span style={{ fontSize: '12px', color: '#ef4444', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '5px', fontFamily: 'var(--font-primary)' }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#ef4444', display: 'inline-block', animation: 'mn-pulse 1.2s ease-in-out infinite' }} />
          {result.stats.high_impact} Breaking
        </span>
        <span style={{ fontSize: '12px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{result.stats.total} total</span>
        <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{result.count} showing</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          Refresh in {mins}:{secs.toString().padStart(2, '0')}
        </span>
        {isPro ? (
          <button onClick={onRefresh} disabled={refreshing} style={{
            background: refreshing ? 'rgba(255,255,255,0.03)' : 'var(--gain-dim, rgba(61,220,132,0.08))',
            border: `1px solid ${refreshing ? 'var(--border)' : 'var(--gain-border, rgba(61,220,132,0.2))'}`,
            color: refreshing ? 'var(--text-muted)' : 'var(--gain)',
            fontSize: '11px', fontWeight: 700, padding: '4px 12px', borderRadius: '6px',
            cursor: refreshing ? 'not-allowed' : 'pointer', transition: 'all 0.15s',
            display: 'flex', alignItems: 'center', gap: '5px',
            fontFamily: 'var(--font-primary)',
          }}>
            <IconRefresh /> {refreshing ? 'Refreshing…' : 'Refresh Now'}
          </button>
        ) : (
          <button disabled title="Upgrade to Pro to refresh news on demand" style={{
            background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)',
            color: 'var(--text-muted)', fontSize: '11px', fontWeight: 700,
            padding: '4px 12px', borderRadius: '6px', cursor: 'not-allowed', opacity: 0.5,
            display: 'flex', alignItems: 'center', gap: '5px',
            fontFamily: 'var(--font-primary)',
          }}>
            <IconRefresh /> Refresh Now <IconLock />
          </button>
        )}
      </div>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function MarketNewsTab({ userPlan = 'free' }: { userPlan?: string }) {
  const [category, setCategory]   = useState<NewsCategory>('ALL')
  const [result, setResult]       = useState<LiveNewsResult | null>(null)
  const [loading, setLoading]     = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError]         = useState<string | null>(null)
  const autoRefreshRef            = useRef<NodeJS.Timeout | null>(null)

  const isPro = userPlan === 'pro' || userPlan === 'elite'

  const load = useCallback(async (cat: NewsCategory, force = false) => {
    if (force) setRefreshing(true)
    else setLoading(true)
    setError(null)
    try {
      let data: LiveNewsResult
      if (force && isPro) {
        data = await apiRefreshNews()
      } else {
        data = await apiLiveNews(cat === 'ALL' ? undefined : cat, undefined, 60)
      }
      setResult(data)
    } catch (e: any) {
      setError(e.message || 'Failed to load news')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [isPro])

  useEffect(() => { load(category) }, [category, load])

  useEffect(() => {
    autoRefreshRef.current = setInterval(() => load(category), 10 * 60 * 1000)
    return () => { if (autoRefreshRef.current) clearInterval(autoRefreshRef.current) }
  }, [category, load])

  const articles = result?.articles ?? []
  const filtered = category === 'ALL'
    ? articles
    : category === 'BREAKING'
    ? articles.filter(a => a.impact === 'HIGH')
    : articles.filter(a => a.category === category)

  const counts: Record<string, number> = {}
  if (result) {
    counts['ALL']      = result.stats.total
    counts['BREAKING'] = result.stats.high_impact
    Object.entries(result.stats.categories || {}).forEach(([k, v]) => { counts[k] = v })
  }

  return (
    <div style={{ fontFamily: "var(--font-primary, 'Inter', system-ui, sans-serif)" }}>

      {/* Header */}
      <div style={{ marginBottom: '20px' }}>
        <h2 style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-primary)', margin: '0 0 5px', letterSpacing: '-0.4px' }}>
          Market News
        </h2>
        <p style={{ fontSize: '12px', color: 'var(--text-tertiary)', margin: 0, fontFamily: 'var(--font-primary)' }}>
          Live from 14 Indian financial feeds · Smart impact scoring · Auto-refresh every 10 min
        </p>
      </div>

      {/* Global Markets Widget */}
      <GlobalMarketsWidget />

      {/* Breaking ticker */}
      {result && !loading && <BreakingTicker articles={result.articles} />}

      {/* Category filter tabs */}
      <div style={{ display: 'flex', gap: '6px', marginBottom: '16px', flexWrap: 'wrap' }}>
        {CATEGORIES.map(cat => {
          const count = counts[cat.id] ?? 0
          const active = category === cat.id
          return (
            <button key={cat.id} onClick={() => setCategory(cat.id)} style={{
              background: active ? cat.color + '14' : 'rgba(255,255,255,0.025)',
              border: `1px solid ${active ? cat.color + '45' : 'var(--border)'}`,
              borderRadius: '99px', padding: '6px 14px',
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px',
              transition: 'all 0.15s', fontSize: '12px',
              fontWeight: active ? 700 : 500,
              color: active ? cat.color : 'var(--text-tertiary)',
              whiteSpace: 'nowrap', fontFamily: 'var(--font-primary)',
            }}>
              {cat.icon} {cat.label}
              {count > 0 && (
                <span style={{
                  background: active ? cat.color + '25' : 'rgba(255,255,255,0.05)',
                  color: active ? cat.color : 'var(--text-muted)',
                  fontSize: '10px', fontWeight: 700, padding: '1px 6px',
                  borderRadius: '99px', minWidth: '20px', textAlign: 'center',
                  fontFamily: 'var(--font-mono)',
                }}>
                  {count}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Stats bar */}
      {result && !loading && (
        <StatsBar
          result={result}
          onRefresh={() => load(category, true)}
          refreshing={refreshing}
          isPro={isPro}
        />
      )}

      {/* Loading */}
      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '60px 20px', gap: '16px' }}>
          <div style={{
            width: '36px', height: '36px', borderRadius: '50%',
            border: '2.5px solid rgba(255,255,255,0.07)',
            borderTopColor: 'var(--gain, #3DDC84)',
            animation: 'mn-spin 0.75s linear infinite',
          }} />
          <div style={{ textAlign: 'center' }}>
            <div style={{ color: 'var(--text-secondary)', fontSize: '14px', fontWeight: 600, marginBottom: '4px', fontFamily: 'var(--font-primary)' }}>
              Fetching live news from 14 sources…
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: '12px', fontFamily: 'var(--font-primary)' }}>
              Scoring market impact and categorizing articles
            </div>
          </div>
          <style>{`
            @keyframes mn-spin { to { transform: rotate(360deg); } }
          `}</style>
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div style={{
          padding: '16px', background: 'rgba(229,72,77,0.07)',
          border: '1px solid rgba(229,72,77,0.18)', borderRadius: '12px',
          color: '#fca5a5', fontSize: '13px',
          display: 'flex', alignItems: 'center', gap: '10px',
          fontFamily: 'var(--font-primary)',
        }}>
          <IconAlertCircle />
          {error}
          <button onClick={() => load(category)} style={{
            marginLeft: 'auto', background: 'rgba(229,72,77,0.12)',
            border: 'none', color: '#fca5a5',
            padding: '6px 14px', borderRadius: '7px',
            cursor: 'pointer', fontSize: '12px', fontWeight: 600,
          }}>Retry</button>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && filtered.length === 0 && (() => {
        const catMeta = CATEGORIES.find(c => c.id === category)
        return (
          <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
            <div style={{ color: 'var(--text-muted)', marginBottom: '14px', display: 'flex', justifyContent: 'center' }}>
              <IconNewspaper />
            </div>
            <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '8px', fontFamily: 'var(--font-primary)' }}>
              {category === 'ALL' ? 'No live articles available' : `No ${catMeta?.label ?? category} articles right now`}
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', maxWidth: '280px', margin: '0 auto', lineHeight: 1.6, fontFamily: 'var(--font-primary)' }}>
              {category === 'ALL'
                ? 'News feeds are being fetched. Please wait a moment and try refreshing.'
                : `No articles categorized under "${catMeta?.label ?? category}". Try All News or check back in a few minutes.`}
            </div>
            <button onClick={() => setCategory('ALL')} style={{
              marginTop: '16px',
              background: 'var(--gain-dim, rgba(61,220,132,0.08))',
              border: '1px solid var(--gain-border, rgba(61,220,132,0.2))',
              color: 'var(--gain)', fontSize: '12px', fontWeight: 700,
              padding: '7px 16px', borderRadius: '8px', cursor: 'pointer',
              fontFamily: 'var(--font-primary)',
            }}>
              View All News
            </button>
          </div>
        )
      })()}

      {/* News grid */}
      {!loading && !error && filtered.length > 0 && (() => {
        const high   = filtered.filter(a => a.impact === 'HIGH')
        const others = filtered.filter(a => a.impact !== 'HIGH')
        return (
          <div>
            {high.length > 0 && (
              <div style={{ marginBottom: '20px' }}>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '8px',
                  marginBottom: '12px', paddingBottom: '8px',
                  borderBottom: '1px solid rgba(239,68,68,0.12)',
                }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#ef4444', display: 'inline-block', animation: 'mn-pulse 1.2s ease-in-out infinite' }} />
                  <span style={{ fontSize: '11px', fontWeight: 800, color: '#ef4444', letterSpacing: '0.8px', fontFamily: 'var(--font-primary)', textTransform: 'uppercase' }}>
                    High Impact
                  </span>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{high.length} articles</span>
                </div>
                <div style={{ display: 'grid', gap: '10px' }}>
                  {high.map(a => <NewsCard key={a.id} article={a} />)}
                </div>
              </div>
            )}
            {others.length > 0 && (
              <div>
                {high.length > 0 && (
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: '8px',
                    marginBottom: '12px', paddingBottom: '8px',
                    borderBottom: '1px solid var(--border-subtle)',
                  }}>
                    <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '0.8px', fontFamily: 'var(--font-primary)', textTransform: 'uppercase' }}>
                      Other News
                    </span>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{others.length} articles</span>
                  </div>
                )}
                <div style={{ display: 'grid', gap: '10px' }}>
                  {others.map(a => <NewsCard key={a.id} article={a} />)}
                </div>
              </div>
            )}

            {/* Footer */}
            <div style={{ marginTop: '24px', padding: '12px 0', borderTop: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-primary)' }}>
                Sourced from: Economic Times, Moneycontrol, LiveMint, Business Standard, SEBI, RBI + more
              </span>
              {result?.fetched_at && (
                <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  Updated: {new Date(result.fetched_at + 'Z').toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                </span>
              )}
            </div>
          </div>
        )
      })()}
    </div>
  )
}
