'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import {
  apiIpoHub,
  type IpoHubResult,
  type IpoDetail,
  type IpoGmp,
  type IpoSubscription,
  type IpoAiVerdict,
} from '@/lib/api'

// ── Config ────────────────────────────────────────────────────────────────────

const STATUS_CFG = {
  OPEN:      { label: 'Open Now',   color: '#10b981', bg: 'rgba(16,185,129,0.10)',  border: 'rgba(16,185,129,0.25)' },
  UPCOMING:  { label: 'Upcoming',   color: '#3b82f6', bg: 'rgba(59,130,246,0.10)',  border: 'rgba(59,130,246,0.25)' },
  ALLOTMENT: { label: 'Allotment',  color: '#f59e0b', bg: 'rgba(245,158,11,0.10)',  border: 'rgba(245,158,11,0.25)' },
  LISTED:    { label: 'Listed',     color: '#64748b', bg: 'rgba(100,116,139,0.08)', border: 'rgba(100,116,139,0.18)' },
  UNKNOWN:   { label: 'Unknown',    color: '#475569', bg: 'rgba(71,85,105,0.06)',   border: 'rgba(71,85,105,0.16)' },
}

const VERDICT_CFG = {
  APPLY:    { label: 'APPLY',    color: '#10b981', bg: 'rgba(16,185,129,0.10)',  border: 'rgba(16,185,129,0.28)' },
  CAUTIOUS: { label: 'CAUTIOUS', color: '#f59e0b', bg: 'rgba(245,158,11,0.10)',  border: 'rgba(245,158,11,0.28)' },
  AVOID:    { label: 'AVOID',    color: '#ef4444', bg: 'rgba(239,68,68,0.10)',   border: 'rgba(239,68,68,0.28)' },
}

const OUTLOOK_CFG = {
  POSITIVE: { label: '↗ Positive Listing', color: '#10b981' },
  NEUTRAL:  { label: '→ Neutral Listing',  color: '#64748b' },
  NEGATIVE: { label: '↘ Weak Listing',     color: '#ef4444' },
}

type TabId = 'open' | 'upcoming' | 'allotment' | 'listed' | 'all'

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtCr(n: number | null | undefined): string {
  if (n == null) return '—'
  if (n >= 10000) return `₹${(n / 1000).toFixed(1)}K Cr`
  return `₹${Math.round(n)} Cr`
}

function fmtDate(s: string | null | undefined): string {
  if (!s) return '—'
  try {
    return new Date(s).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
  } catch { return s }
}

function fmtInvestment(n: number | null | undefined): string {
  if (n == null) return '—'
  return `₹${n.toLocaleString('en-IN')}`
}

function daysLabel(n: number | null | undefined, suffix: string): string {
  if (n == null) return ''
  if (n < 0) return 'Closed'
  if (n === 0) return 'Today'
  return `${n}d ${suffix}`
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.07)',
      borderRadius: '16px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px',
      animation: 'pulse 1.5s ease-in-out infinite',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ width: 180, height: 18, background: 'rgba(255,255,255,0.06)', borderRadius: 6 }} />
          <div style={{ width: 100, height: 12, background: 'rgba(255,255,255,0.04)', borderRadius: 6 }} />
        </div>
        <div style={{ width: 90, height: 28, background: 'rgba(255,255,255,0.04)', borderRadius: 8 }} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
        {[1,2,3,4].map(i => <div key={i} style={{ height: 52, background: 'rgba(255,255,255,0.03)', borderRadius: 8 }} />)}
      </div>
    </div>
  )
}

// ── GMP Strip ─────────────────────────────────────────────────────────────────

function GmpStrip({ ipos }: { ipos: IpoDetail[] }) {
  const withGmp = ipos.filter(i => i.gmp && ['OPEN', 'UPCOMING'].includes(i.status))
  if (!withGmp.length) return null

  return (
    <div style={{
      background: 'rgba(255,255,255,0.015)', border: '1px solid rgba(255,255,255,0.07)',
      borderRadius: '12px', padding: '10px 16px', marginBottom: '20px', overflowX: 'auto',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
        <span style={{ fontSize: '10px', color: '#475569', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#f59e0b', display: 'inline-block' }} />
          Live GMP (Grey Market Premium)
        </span>
        <span style={{ fontSize: '9px', background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', color: '#f59e0b', padding: '1px 6px', borderRadius: 4, fontWeight: 600 }}>
          Unofficial · Not SEBI Verified
        </span>
      </div>
      <div style={{ display: 'flex', gap: '10px', minWidth: 'max-content' }}>
        {withGmp.map(ipo => {
          const gmp = ipo.gmp!
          const isPos = gmp.gmp_price >= 0
          return (
            <div key={ipo.id} style={{
              display: 'flex', flexDirection: 'column', gap: '3px',
              background: isPos ? 'rgba(16,185,129,0.06)' : 'rgba(239,68,68,0.06)',
              border: `1px solid ${isPos ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'}`,
              borderRadius: '8px', padding: '8px 12px', minWidth: 130,
            }}>
              <span style={{ fontSize: '11px', color: '#94a3b8', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 120 }}>{ipo.company_name}</span>
              <span style={{ fontSize: '14px', fontWeight: 800, color: isPos ? '#10b981' : '#ef4444' }}>
                {isPos ? '+' : ''}₹{gmp.gmp_price}
              </span>
              {gmp.premium_pct != null && (
                <span style={{ fontSize: '10px', color: isPos ? '#10b981' : '#ef4444', fontWeight: 600 }}>
                  {isPos ? '+' : ''}{gmp.premium_pct.toFixed(1)}% premium
                </span>
              )}
              {gmp.est_listing != null && (
                <span style={{ fontSize: '10px', color: '#64748b' }}>Est. ₹{gmp.est_listing}</span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Subscription Table ─────────────────────────────────────────────────────────

function SubscriptionTable({ sub }: { sub: IpoSubscription }) {
  const rows = [
    { label: 'QIB (Institutions)', value: sub.qib, color: '#3b82f6' },
    { label: 'NII (HNI ≥₹2L)',    value: sub.nii, color: '#8b5cf6' },
    { label: 'RII (Retail ≤₹2L)', value: sub.rii, color: '#10b981' },
    { label: 'Total',              value: sub.total, color: '#00C48C', bold: true },
  ]

  return (
    <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ padding: '8px 12px', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: '11px', color: '#475569', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Subscription Status</span>
        <span style={{ fontSize: '9px', color: '#334155' }}>as of {sub.updated_at}</span>
      </div>
      {rows.map(row => {
        const pct = Math.min((row.value / Math.max(sub.total * 1.5, 10)) * 100, 100)
        return (
          <div key={row.label} style={{ padding: '8px 12px', borderBottom: '1px solid rgba(255,255,255,0.04)', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '11px', color: '#64748b', minWidth: 140, fontWeight: (row as any).bold ? 700 : 400 }}>{row.label}</span>
            <div style={{ flex: 1, height: 5, background: 'rgba(255,255,255,0.05)', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${pct}%`, background: row.color, borderRadius: 3, transition: 'width 0.6s ease' }} />
            </div>
            <span style={{ fontSize: '13px', fontWeight: 800, color: row.color, minWidth: 50, textAlign: 'right' }}>
              {row.value.toFixed(2)}×
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ── AI Verdict Panel ──────────────────────────────────────────────────────────

function VerdictPanel({ verdict }: { verdict: IpoAiVerdict }) {
  const cfg = VERDICT_CFG[verdict.verdict] || VERDICT_CFG.CAUTIOUS
  const outlook = OUTLOOK_CFG[verdict.listing_outlook] || OUTLOOK_CFG.NEUTRAL
  const conf_colors = { HIGH: '#10b981', MEDIUM: '#f59e0b', LOW: '#ef4444' }
  const confColor = conf_colors[verdict.confidence] || '#64748b'

  return (
    <div style={{ background: cfg.bg, border: `1px solid ${cfg.border}`, borderRadius: 12, padding: '14px 16px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: '15px', fontWeight: 900, color: cfg.color }}>{cfg.label}</span>
          <span style={{ fontSize: '9px', fontWeight: 700, padding: '2px 6px', borderRadius: 4, background: `${confColor}18`, color: confColor, border: `1px solid ${confColor}30`, letterSpacing: '0.5px' }}>
            {verdict.confidence} CONFIDENCE
          </span>
        </div>
        <span style={{ fontSize: '11px', fontWeight: 700, color: outlook.color }}>{outlook.label}</span>
      </div>

      {/* Summary */}
      <p style={{ fontSize: '12px', color: '#cbd5e1', lineHeight: 1.5, marginBottom: 12, fontStyle: 'italic' }}>
        "{verdict.summary}"
      </p>

      {/* Reasons */}
      <div style={{ marginBottom: 10 }}>
        <p style={{ fontSize: '10px', color: cfg.color, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>
          {verdict.verdict === 'AVOID' ? 'Concerns:' : 'Positives:'}
        </p>
        <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 4 }}>
          {verdict.reasons.map((r, i) => (
            <li key={i} style={{ display: 'flex', gap: 6, fontSize: '11px', color: '#94a3b8', lineHeight: 1.4 }}>
              <span style={{ color: cfg.color, flexShrink: 0 }}>{verdict.verdict === 'AVOID' ? '✗' : '✓'}</span>
              {r}
            </li>
          ))}
        </ul>
      </div>

      {/* Risks */}
      {verdict.risks.length > 0 && (
        <div>
          <p style={{ fontSize: '10px', color: '#ef4444', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>⚠ Key Risks:</p>
          <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 4 }}>
            {verdict.risks.map((r, i) => (
              <li key={i} style={{ display: 'flex', gap: 6, fontSize: '11px', color: '#94a3b8', lineHeight: 1.4 }}>
                <span style={{ color: '#ef4444', flexShrink: 0 }}>•</span>
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* SEBI note */}
      <p style={{ fontSize: '9px', color: '#334155', marginTop: 10, lineHeight: 1.4 }}>
        🤖 AI-generated verdict. Not SEBI-registered advice. Always read the RHP before applying.
      </p>
    </div>
  )
}

// ── IPO Timeline ──────────────────────────────────────────────────────────────

function IpoTimeline({ ipo }: { ipo: IpoDetail }) {
  const today = new Date().toISOString().split('T')[0]
  const steps = [
    { label: 'Open Date',  date: ipo.open_date      },
    { label: 'Close Date', date: ipo.close_date     },
    { label: 'Allotment',  date: ipo.allotment_date },
    { label: 'Listing',    date: ipo.listing_date   },
  ]
  return (
    <div style={{ display: 'flex', gap: '0', position: 'relative', marginBottom: 4 }}>
      {steps.map((step, i) => {
        const isPast = step.date && step.date < today
        const isToday = step.date === today
        const isFuture = step.date && step.date > today
        const color = isPast ? '#10b981' : isToday ? '#00C48C' : '#334155'
        return (
          <div key={i} style={{ flex: 1, position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
            {/* connector line */}
            {i < steps.length - 1 && (
              <div style={{
                position: 'absolute', top: 13, left: '50%', width: '100%', height: 2,
                background: isPast ? '#10b981' : 'rgba(255,255,255,0.08)', zIndex: 0,
              }} />
            )}
            {/* dot */}
            <div style={{
              width: 26, height: 26, borderRadius: '50%', zIndex: 1,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: isPast ? 'rgba(16,185,129,0.15)' : isToday ? 'rgba(0,196,140,0.15)' : 'rgba(255,255,255,0.04)',
              border: `2px solid ${isPast ? '#10b981' : isToday ? '#00C48C' : 'rgba(255,255,255,0.1)'}`,
            }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: isPast ? '#10b981' : isToday ? '#00C48C' : 'rgba(255,255,255,0.2)', display: 'inline-block' }} />
            </div>
            <span style={{ fontSize: '9px', color, fontWeight: 600, textAlign: 'center', lineHeight: 1.2 }}>{step.label}</span>
            <span style={{ fontSize: '9px', color: isPast ? '#10b981' : '#475569', textAlign: 'center' }}>
              {fmtDate(step.date)}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ── IPO Card ──────────────────────────────────────────────────────────────────

function IpoCard({ ipo }: { ipo: IpoDetail }) {
  const [expanded, setExpanded] = useState(false)
  const statusCfg = STATUS_CFG[ipo.status] || STATUS_CFG.UNKNOWN
  const verdict = ipo.ai_verdict
  const verdictCfg = verdict ? (VERDICT_CFG[verdict.verdict] || VERDICT_CFG.CAUTIOUS) : null

  // Countdown for OPEN IPOs
  const daysLeft = ipo.days_to_close

  return (
    <div style={{
      background: 'rgba(255,255,255,0.02)',
      border: '1px solid rgba(255,255,255,0.07)',
      borderRadius: '16px', overflow: 'hidden',
      transition: 'border-color 0.2s, box-shadow 0.2s',
    }}
      onMouseEnter={e => {
        ;(e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(255,255,255,0.14)'
        ;(e.currentTarget as HTMLDivElement).style.boxShadow = '0 4px 24px rgba(0,0,0,0.3)'
      }}
      onMouseLeave={e => {
        ;(e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(255,255,255,0.07)'
        ;(e.currentTarget as HTMLDivElement).style.boxShadow = 'none'
      }}
    >
      {/* Status accent bar */}
      <div style={{ height: 3, background: `linear-gradient(90deg, ${statusCfg.color}, ${statusCfg.color}44)` }} />

      <div style={{ padding: '16px 18px' }}>

        {/* ── Header row ── */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10, marginBottom: 12 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            {/* Company initial badge */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10, flexShrink: 0, fontSize: 14, fontWeight: 900,
                background: `linear-gradient(135deg, ${statusCfg.color}20, ${statusCfg.color}08)`,
                border: `1px solid ${statusCfg.color}30`,
                display: 'flex', alignItems: 'center', justifyContent: 'center', color: statusCfg.color,
              }}>
                {ipo.company_name[0]}
              </div>
              <div style={{ minWidth: 0 }}>
                <p style={{ fontSize: 14, fontWeight: 800, color: '#f1f5f9', margin: 0, lineHeight: 1.2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {ipo.company_name}
                </p>
                <p style={{ fontSize: 11, color: '#475569', margin: 0, marginTop: 2 }}>
                  {ipo.industry || 'Unlisted'}{ipo.symbol ? ` · ${ipo.symbol}` : ''}
                </p>
              </div>
            </div>
          </div>

          {/* Right column: status + verdict */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6, flexShrink: 0 }}>
            <span style={{
              fontSize: 10, fontWeight: 700, padding: '3px 9px', borderRadius: 99, letterSpacing: '0.3px',
              background: statusCfg.bg, border: `1px solid ${statusCfg.border}`, color: statusCfg.color,
            }}>
              {statusCfg.label}
            </span>
            {verdictCfg && (
              <span style={{
                fontSize: 10, fontWeight: 800, padding: '3px 9px', borderRadius: 99, letterSpacing: '0.3px',
                background: verdictCfg.bg, border: `1px solid ${verdictCfg.border}`, color: verdictCfg.color,
              }}>
                {verdictCfg.label}
              </span>
            )}
          </div>
        </div>

        {/* ── Key metrics grid ── */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6, marginBottom: 12 }}>
          {[
            { label: 'Price Band', value: ipo.price_band || '—' },
            { label: 'Lot Size', value: ipo.lot_size ? `${ipo.lot_size} shares` : '—' },
            { label: 'Min. Invest', value: fmtInvestment(ipo.min_investment) },
            { label: 'Issue Size', value: fmtCr(ipo.issue_size_cr) },
          ].map(m => (
            <div key={m.label} style={{
              background: 'rgba(255,255,255,0.025)', borderRadius: 8, padding: '8px 10px',
              display: 'flex', flexDirection: 'column', gap: 3,
            }}>
              <span style={{ fontSize: 9, color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.3px' }}>{m.label}</span>
              <span style={{ fontSize: 11, fontWeight: 700, color: '#e2e8f0' }}>{m.value}</span>
            </div>
          ))}
        </div>

        {/* ── GMP bar ── */}
        {ipo.gmp && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12,
            background: ipo.gmp.gmp_price >= 0 ? 'rgba(16,185,129,0.06)' : 'rgba(239,68,68,0.06)',
            border: `1px solid ${ipo.gmp.gmp_price >= 0 ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'}`,
            borderRadius: 8, padding: '8px 12px', flexWrap: 'wrap',
          }}>
            <span style={{ fontSize: 10, color: '#64748b', fontWeight: 600 }}>GMP</span>
            <span style={{ fontSize: 14, fontWeight: 800, color: ipo.gmp.gmp_price >= 0 ? '#10b981' : '#ef4444' }}>
              {ipo.gmp.gmp_price >= 0 ? '+' : ''}₹{ipo.gmp.gmp_price}
            </span>
            {ipo.gmp.premium_pct != null && (
              <span style={{ fontSize: 11, fontWeight: 700, color: ipo.gmp.gmp_price >= 0 ? '#10b981' : '#ef4444' }}>
                ({ipo.gmp.gmp_price >= 0 ? '+' : ''}{ipo.gmp.premium_pct.toFixed(1)}%)
              </span>
            )}
            {ipo.gmp.est_listing != null && (
              <>
                <span style={{ color: '#334155', fontSize: 10 }}>·</span>
                <span style={{ fontSize: 10, color: '#64748b' }}>Est. Listing: <strong style={{ color: '#94a3b8' }}>₹{ipo.gmp.est_listing}</strong></span>
              </>
            )}
            <span style={{ marginLeft: 'auto', fontSize: 9, color: '#334155', fontStyle: 'italic' }}>Unofficial</span>
          </div>
        )}

        {/* ── Open COUNTDOWN ── */}
        {ipo.status === 'OPEN' && daysLeft != null && daysLeft >= 0 && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12,
            background: 'rgba(16,185,129,0.06)', border: '1px solid rgba(16,185,129,0.2)',
            borderRadius: 8, padding: '6px 12px',
          }}>
            <span style={{ fontSize: 11, color: '#10b981', fontWeight: 700 }}>Closes in</span>
            <span style={{ fontSize: 13, fontWeight: 800, color: daysLeft <= 1 ? '#ef4444' : '#10b981' }}>
              {daysLeft === 0 ? 'Today' : `${daysLeft} day${daysLeft > 1 ? 's' : ''}`}
            </span>
            <span style={{ fontSize: 10, color: '#475569', marginLeft: 'auto' }}>{fmtDate(ipo.close_date)}</span>
          </div>
        )}

        {/* ── Subscription quick stat ── */}
        {ipo.subscription && ipo.subscription.total > 0 && (
          <div style={{
            display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap',
          }}>
            {[
              { label: 'QIB', val: ipo.subscription.qib, color: '#3b82f6' },
              { label: 'NII', val: ipo.subscription.nii, color: '#8b5cf6' },
              { label: 'RII', val: ipo.subscription.rii, color: '#10b981' },
              { label: 'Total', val: ipo.subscription.total, color: '#00C48C' },
            ].map(s => (
              <div key={s.label} style={{
                flex: 1, minWidth: 60, background: `${s.color}10`,
                border: `1px solid ${s.color}25`, borderRadius: 7, padding: '5px 8px', textAlign: 'center',
              }}>
                <div style={{ fontSize: 9, color: '#475569', fontWeight: 600 }}>{s.label}</div>
                <div style={{ fontSize: 12, fontWeight: 800, color: s.color }}>{s.val.toFixed(2)}×</div>
              </div>
            ))}
          </div>
        )}

        {/* ── Expand button ── */}
        <button
          onClick={() => setExpanded(e => !e)}
          style={{
            width: '100%', background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.07)', borderRadius: 8,
            color: '#475569', fontSize: 11, fontWeight: 600, padding: '7px',
            cursor: 'pointer', transition: 'all 0.15s',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
          }}
          onMouseEnter={e => {
            ;(e.currentTarget as HTMLButtonElement).style.background = 'rgba(0,196,140,0.08)'
            ;(e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(0,196,140,0.25)'
            ;(e.currentTarget as HTMLButtonElement).style.color = '#00C48C'
          }}
          onMouseLeave={e => {
            ;(e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.03)'
            ;(e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,255,255,0.07)'
            ;(e.currentTarget as HTMLButtonElement).style.color = '#475569'
          }}
        >
          {expanded ? 'Hide Details ↑' : 'Full Analysis ↓'}
        </button>

        {/* ════════════════ EXPANDED PANEL ════════════════ */}
        {expanded && (
          <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid rgba(255,255,255,0.06)', display: 'flex', flexDirection: 'column', gap: 16 }}>

            {/* Timeline */}
            <div>
              <p style={{ fontSize: 10, color: '#475569', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 10 }}>IPO Timeline</p>
              <IpoTimeline ipo={ipo} />
            </div>

            {/* AI Verdict */}
            <div>
              <p style={{ fontSize: 10, color: '#475569', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>AI Analysis & Verdict</p>
              <VerdictPanel verdict={verdict} />
            </div>

            {/* Full subscription table */}
            {ipo.subscription && (
              <SubscriptionTable sub={ipo.subscription} />
            )}

            {/* GMP detail */}
            {ipo.gmp && (
              <div style={{ background: 'rgba(245,158,11,0.04)', border: '1px solid rgba(245,158,11,0.15)', borderRadius: 10, padding: '12px 14px' }}>
                <p style={{ fontSize: 10, color: '#f59e0b', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>Grey Market Premium (GMP)</p>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8 }}>
                  {[
                    { label: 'GMP Price', value: `${ipo.gmp.gmp_price >= 0 ? '+' : ''}₹${ipo.gmp.gmp_price}` },
                    { label: 'Premium %', value: ipo.gmp.premium_pct != null ? `${ipo.gmp.premium_pct >= 0 ? '+' : ''}${ipo.gmp.premium_pct.toFixed(1)}%` : '—' },
                    { label: 'Est. Listing', value: ipo.gmp.est_listing ? `₹${ipo.gmp.est_listing}` : '—' },
                  ].map(m => (
                    <div key={m.label} style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 9, color: '#64748b', fontWeight: 600 }}>{m.label}</div>
                      <div style={{ fontSize: 14, fontWeight: 800, color: '#f59e0b', marginTop: 2 }}>{m.value}</div>
                    </div>
                  ))}
                </div>
                <p style={{ fontSize: 9, color: '#475569', marginTop: 8, lineHeight: 1.4 }}>
                  GMP is sourced from unofficial grey markets and is speculative. It is not verified by SEBI or the exchanges.
                  GMP can change rapidly and does not guarantee listing gains. Source: {ipo.gmp.source}
                </p>
              </div>
            )}

            {/* Details */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              {[
                { label: 'Exchange', value: ipo.exchange || '—' },
                { label: 'Issue Type', value: ipo.issue_type || '—' },
                { label: 'Registrar', value: ipo.registrar || '—' },
                { label: 'Industry', value: ipo.industry || '—' },
              ].map(m => (
                <div key={m.label} style={{ background: 'rgba(255,255,255,0.02)', borderRadius: 8, padding: '8px 10px' }}>
                  <div style={{ fontSize: 9, color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.3px' }}>{m.label}</div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: '#94a3b8', marginTop: 2 }}>{m.value}</div>
                </div>
              ))}
            </div>

            {/* Links */}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {ipo.rhp_url && (
                <a href={ipo.rhp_url} target="_blank" rel="noopener noreferrer" style={{
                  fontSize: 11, fontWeight: 700, padding: '7px 14px', borderRadius: 8,
                  background: 'rgba(0,196,140,0.08)', border: '1px solid rgba(0,196,140,0.25)',
                  color: '#00C48C', textDecoration: 'none', transition: 'all 0.15s',
                }}>
                  RHP / Prospectus ↗
                </a>
              )}
              {ipo.drhp_url && (
                <a href={ipo.drhp_url} target="_blank" rel="noopener noreferrer" style={{
                  fontSize: 11, fontWeight: 700, padding: '7px 14px', borderRadius: 8,
                  background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.25)',
                  color: '#3b82f6', textDecoration: 'none',
                }}>
                  DRHP ↗
                </a>
              )}
              <a
                href={`https://www.nseindia.com/market-data/all-upcoming-issues-ipo`}
                target="_blank" rel="noopener noreferrer"
                style={{
                  fontSize: 11, fontWeight: 700, padding: '7px 14px', borderRadius: 8,
                  background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
                  color: '#64748b', textDecoration: 'none',
                }}
              >
                NSE IPO Page ↗
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Tab filter ────────────────────────────────────────────────────────────────

const TAB_FILTERS: Record<TabId, (ipo: IpoDetail) => boolean> = {
  all:       () => true,
  open:      ipo => ipo.status === 'OPEN',
  upcoming:  ipo => ipo.status === 'UPCOMING',
  allotment: ipo => ipo.status === 'ALLOTMENT',
  listed:    ipo => ipo.status === 'LISTED',
}

// ── Main Component ─────────────────────────────────────────────────────────────

export default function IpoHub({ data: externalData }: { data: IpoHubResult | null }) {
  const [data, setData]       = useState<IpoHubResult | null>(externalData)
  const [loading, setLoading] = useState(!externalData)
  const [error, setError]     = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<TabId>('open')
  const [countdown, setCountdown] = useState(externalData?.next_refresh_in ?? 1800)
  const countdownRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    if (externalData) {
      setData(externalData)
      setLoading(false)
      setCountdown(externalData.next_refresh_in)
    }
  }, [externalData])

  const load = useCallback(async (force = false) => {
    setLoading(true)
    setError(null)
    try {
      const result = await apiIpoHub(force)
      setData(result)
      setCountdown(result.next_refresh_in)
      // Default to 'open' tab if there are open IPOs, else 'upcoming'
      if (result.stats.open > 0) setActiveTab('open')
      else if (result.stats.upcoming > 0) setActiveTab('upcoming')
      else setActiveTab('all')
    } catch (e: any) {
      setError(e.message || 'Failed to load IPO data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!externalData) load()
  }, [externalData, load])

  // Countdown
  useEffect(() => {
    countdownRef.current = setInterval(() => {
      setCountdown(c => {
        if (c <= 1) { load(true); return 1800 }
        return c - 1
      })
    }, 1000)
    return () => { if (countdownRef.current) clearInterval(countdownRef.current) }
  }, [load])

  const mins = Math.floor(countdown / 60)
  const secs = countdown % 60

  const stats = data?.stats
  const TAB_COLORS: Record<string, string> = { open: '#10b981', upcoming: '#3b82f6', allotment: '#f59e0b', listed: '#64748b', all: 'var(--gain, #3DDC84)' }
  const TABS: { id: TabId; label: string; count: number }[] = [
    { id: 'open',      label: 'Open Now',  count: stats?.open      ?? 0 },
    { id: 'upcoming',  label: 'Upcoming',  count: stats?.upcoming  ?? 0 },
    { id: 'allotment', label: 'Allotment', count: stats?.allotment ?? 0 },
    { id: 'listed',    label: 'Listed',    count: stats?.listed    ?? 0 },
    { id: 'all',       label: 'All',       count: stats?.total     ?? 0 },
  ]

  const filtered = data?.ipos.filter(TAB_FILTERS[activeTab]) ?? []

  return (
    <div style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>
      <style>{`@keyframes pulse { 0%,100%{opacity:.4} 50%{opacity:.8} }`}</style>

      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-primary, #F2F2F0)', margin: 0, letterSpacing: '-0.4px', fontFamily: 'var(--font-primary)' }}>
            IPO Intelligence Hub
          </h2>
          <p style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 4, fontFamily: 'var(--font-primary)' }}>
            Live IPO data · GMP · Subscription · AI Verdict ·{' '}
            {!loading && <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>Refreshes in {mins}:{secs.toString().padStart(2,'0')}</span>}
            {loading && <span style={{ color: 'var(--gain)' }}> Fetching…</span>}
            {data?.stale && <span style={{ color: '#f59e0b' }}> (stale)</span>}
          </p>
        </div>
        <button
          onClick={() => load(true)} disabled={loading}
          style={{
            background: 'rgba(0,196,140,0.08)', border: '1px solid rgba(0,196,140,0.2)',
            color: '#00C48C', fontSize: 11, fontWeight: 700, padding: '6px 14px',
            borderRadius: 8, cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.6 : 1, transition: 'all 0.15s',
          }}
        >
          Refresh
        </button>
      </div>

      {/* ── Error ── */}
      {error && !loading && (
        <div style={{
          padding: '14px 18px', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
          borderRadius: 12, color: '#fca5a5', fontSize: 13,
          display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20,
        }}>
          {error}
          <button onClick={() => load()} style={{ marginLeft: 'auto', background: 'rgba(239,68,68,0.15)', border: 'none', color: '#fca5a5', padding: '5px 12px', borderRadius: 6, cursor: 'pointer', fontSize: 11, fontWeight: 700 }}>
            Retry
          </button>
        </div>
      )}

      {/* ── Skeleton ── */}
      {loading && !data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px,1fr))', gap: 16 }}>
          {[...Array(4)].map((_, i) => <SkeletonCard key={i} />)}
        </div>
      )}

      {/* ── Data ── */}
      {data && (
        <>
          {/* GMP Strip */}
          <GmpStrip ipos={data.ipos} />

          {/* Tabs */}
          <div style={{ display: 'flex', gap: 6, marginBottom: 20, flexWrap: 'wrap' }}>
            {TABS.map(tab => {
              const col = TAB_COLORS[tab.id] || 'var(--gain)'
              const active = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    fontSize: 12, fontWeight: 700, padding: '7px 14px', borderRadius: 10,
                    cursor: 'pointer', transition: 'all 0.15s',
                    background: active ? col + '14' : 'rgba(255,255,255,0.02)',
                    border: `1px solid ${active ? col + '40' : 'var(--border)'}`,
                    color: active ? col : 'var(--text-tertiary)',
                    fontFamily: 'var(--font-primary)',
                  }}
                >
                  <span style={{ width: 7, height: 7, borderRadius: '50%', background: active ? col : 'rgba(255,255,255,0.2)', display: 'inline-block', flexShrink: 0 }} />
                  <span>{tab.label}</span>
                  {tab.count > 0 && (
                    <span style={{
                      fontSize: 10, fontWeight: 800, padding: '1px 6px', borderRadius: 99,
                      background: active ? col + '22' : 'rgba(255,255,255,0.05)',
                      color: active ? col : 'var(--text-muted)',
                      fontFamily: 'var(--font-mono)',
                    }}>
                      {tab.count}
                    </span>
                  )}
                </button>
              )
            })}
          </div>

          {/* Empty tab */}
          {filtered.length === 0 && !loading && (
            <div style={{
              textAlign: 'center', padding: '60px 20px',
              background: 'rgba(255,255,255,0.015)', border: '1px solid rgba(255,255,255,0.07)',
              borderRadius: 16,
            }}>
              <div style={{ fontSize: 28, marginBottom: 16, color: 'var(--text-muted)' }}>
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
              </div>
              <p style={{ fontSize: 16, fontWeight: 700, color: '#475569', marginBottom: 8 }}>
                No {activeTab === 'all' ? '' : activeTab} IPOs right now
              </p>
              <p style={{ fontSize: 13, color: '#334155' }}>
                Check back soon or view a different tab
              </p>
            </div>
          )}

          {/* IPO Cards */}
          {filtered.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px,1fr))', gap: 16 }}>
              {filtered.map(ipo => <IpoCard key={ipo.id} ipo={ipo} />)}
            </div>
          )}

          {/* Footer */}
          <div style={{
            marginTop: 24, paddingTop: 14, borderTop: '1px solid rgba(255,255,255,0.05)',
            display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8,
          }}>
            <span style={{ fontSize: 10, color: '#1e293b' }}>
              Data via NSE · GMP from grey market sources ({data.gmp_count} GMP entries) · AI verdicts by Gemini
            </span>
            <span style={{ fontSize: 10, color: '#1e293b' }}>
              Last updated: {new Date(data.fetched_at * 1000).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })} IST
            </span>
          </div>

          {/* Master disclaimer */}
          <div style={{
            marginTop: 12, padding: '12px 16px',
            background: 'rgba(245,158,11,0.04)', border: '1px solid rgba(245,158,11,0.12)',
            borderRadius: 10, fontSize: 10, color: '#475569', lineHeight: 1.6,
          }}>
            <strong style={{ color: '#f59e0b' }}>Important Disclaimers:</strong>{' '}
            (1) IPO data is sourced from NSE/BSE and may have delays.
            (2) GMP (Grey Market Premium) is sourced from unofficial channels, is speculative, unregulated, and NOT verified by SEBI or the exchanges.
            (3) AI verdicts are generated by an AI model and are <strong>NOT investment advice</strong> from a SEBI-registered advisor.
            (4) Past GMP or subscription trends do NOT guarantee listing gains or profits.
            Always read the Red Herring Prospectus (RHP) and consult a qualified financial advisor before applying to any IPO.
          </div>
        </>
      )}
    </div>
  )
}
