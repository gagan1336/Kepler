/**
 * ANTIGRAVITY — Affiliate API Client
 * All affiliate-related API calls with proper TypeScript types.
 */
import { getAccessToken } from './api'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ── Generic fetch helper ──────────────────────────────────────────────────────
async function affiliateFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = await getAccessToken()
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface AffiliateProfile {
  id: string
  status: 'pending' | 'active' | 'suspended' | 'banned' | 'rejected'
  display_name: string | null
  bio: string | null
  photo_url: string | null
  creator_type: string | null
  commission_pct: number
  commission_is_custom: boolean
  social: {
    youtube: string | null
    twitter: string | null
    telegram: string | null
    linkedin: string | null
    instagram: string | null
    website: string | null
  }
  preferred_currency: string
  preferred_payout_method: string | null
  tax_id: string | null
  tax_country: string | null
  is_flagged: boolean
  applied_at: string | null
  approved_at: string | null
  links: AffiliateLink[]
  payout_methods: PayoutMethodPreview[]
}

export interface AffiliateLink {
  id: string
  ref_code: string
  label: string
  is_primary: boolean
  referral_url: string
  total_clicks: number
  unique_clicks: number
  total_signups: number
  total_paid: number
}

export interface PayoutMethodPreview {
  id: string
  method_type: 'bank' | 'upi' | 'paypal' | 'wise' | 'stripe'
  label: string
  is_primary: boolean
  is_verified: boolean
  currency: string
  details_preview: Record<string, string>
}

export interface DashboardStats {
  status: string
  commission_pct: number
  stats: {
    total_clicks: number
    unique_clicks: number
    total_signups: number
    paid_customers: number
    active_subscribers: number
    cancelled_subscribers: number
    mrr: number
    lifetime_earnings: number
    pending_earnings: number
    paid_earnings: number
    available_balance: number
    conversion_rate: number
    avg_revenue_per_referral: number
    projected_next_month: number
  }
  min_payout_inr: number
  min_payout_usd: number
}

export interface ReferralItem {
  referral_id: string
  customer_email: string
  signup_date: string
  status: string
  plan: string
  subscription_status: string | null
  commission_pct: number | null
  commission_amount: number
  last_payment: string | null
  next_renewal: string | null
  lifetime_revenue: number
  affiliate_earnings: number
  lifetime_payments: number
}

export interface CommissionItem {
  id: string
  invoice_id: string
  customer_email: string
  plan: string | null
  billing_period: string | null
  gross_amount: number
  currency: string
  commission_pct: number
  commission_amount: number
  status: 'pending' | 'approved' | 'paid' | 'rejected' | 'chargeback' | 'refunded'
  payment_date: string
  hold_until: string | null
  admin_notes: string | null
}

export interface PayoutItem {
  id: string
  amount: number
  currency: string
  status: 'pending' | 'approved' | 'paid' | 'rejected'
  payout_method: string | null
  transaction_ref: string | null
  admin_notes: string | null
  requested_at: string
  approved_at: string | null
  paid_at: string | null
}

export interface PayoutsResponse {
  available_balance: number
  pending_balance: number
  min_payout_inr: number
  min_payout_usd: number
  preferred_currency: string
  payouts: PayoutItem[]
}

export interface AnalyticsData {
  clicks_by_day: Array<{ day: string; clicks: number; unique_clicks: number }>
  signups_by_day: Array<{ day: string; count: number }>
  commissions_by_day: Array<{ day: string; amount: number; count: number }>
  countries: Array<{ country: string; count: number }>
  devices: Array<{ device: string; count: number }>
}

export interface MarketingData {
  ref_code: string | null
  referral_url: string | null
  qr_code_url: string | null
  assets: Array<{
    id: string
    asset_type: string
    title: string
    description: string | null
    content_url: string | null
    content_text: string | null
    width: number | null
    height: number | null
    platform: string | null
  }>
  templates: {
    twitter: string
    telegram: string
    email_subject: string
    email_body: string
  }
}

export interface AffiliateApplyPayload {
  display_name: string
  bio?: string
  creator_type?: string
  youtube_url?: string
  twitter_url?: string
  telegram_url?: string
  linkedin_url?: string
  instagram_url?: string
  website_url?: string
}

export interface AdminAffiliate {
  id: string
  email: string
  display_name: string | null
  status: string
  creator_type: string | null
  commission_pct: number
  commission_is_custom: boolean
  fraud_score: number
  is_flagged: boolean
  referral_count: number
  total_earned: number
  applied_at: string | null
  approved_at: string | null
}

export interface AffiliateSettings {
  id: string
  default_commission_pct: number
  min_payout_usd: number
  min_payout_inr: number
  attribution_window_days: number
  cookie_name: string
  program_name: string
  program_description: string | null
  is_program_open: boolean
  require_approval: boolean
  refund_hold_days: number
  updated_at: string | null
  updated_by: string | null
}

export interface AdminSummary {
  affiliates: {
    total: number
    active: number
    pending: number
    flagged: number
  }
  referrals: number
  commissions_approved: number
  commissions_pending: number
  payouts_pending: number
}

// ── Affiliate API Calls ───────────────────────────────────────────────────────

export async function apiAffiliateApply(payload: AffiliateApplyPayload) {
  return affiliateFetch('/affiliate/apply', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function apiGetAffiliateProfile(): Promise<AffiliateProfile> {
  return affiliateFetch('/affiliate/me')
}

export async function apiUpdateAffiliateProfile(payload: Partial<AffiliateProfile>) {
  return affiliateFetch('/affiliate/me', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function apiGetAffiliateDashboard(): Promise<DashboardStats> {
  return affiliateFetch('/affiliate/dashboard')
}

export async function apiGetReferrals(params: {
  page?: number
  per_page?: number
  status?: string
  search?: string
  sort?: string
  order?: string
}): Promise<{ items: ReferralItem[]; total: number; page: number; per_page: number; pages: number }> {
  const q = new URLSearchParams()
  if (params.page) q.set('page', String(params.page))
  if (params.per_page) q.set('per_page', String(params.per_page))
  if (params.status) q.set('status', params.status)
  if (params.search) q.set('search', params.search)
  if (params.sort) q.set('sort', params.sort)
  if (params.order) q.set('order', params.order)
  return affiliateFetch(`/affiliate/referrals?${q}`)
}

export async function apiGetPayments(params: {
  page?: number
  per_page?: number
  status?: string
}): Promise<{ items: CommissionItem[]; total: number; page: number; per_page: number; pages: number }> {
  const q = new URLSearchParams()
  if (params.page) q.set('page', String(params.page))
  if (params.per_page) q.set('per_page', String(params.per_page))
  if (params.status) q.set('status', params.status)
  return affiliateFetch(`/affiliate/payments?${q}`)
}

export async function apiGetPayouts(): Promise<PayoutsResponse> {
  return affiliateFetch('/affiliate/payouts')
}

export async function apiRequestPayout(amount: number, payout_method_id?: string) {
  return affiliateFetch('/affiliate/payouts/request', {
    method: 'POST',
    body: JSON.stringify({ amount, payout_method_id }),
  })
}

export async function apiAddPayoutMethod(payload: {
  method_type: string
  label?: string
  is_primary: boolean
  details: Record<string, string>
  currency: string
}) {
  return affiliateFetch('/affiliate/payout-methods', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function apiGetAnalytics(days: number = 30): Promise<AnalyticsData> {
  return affiliateFetch(`/affiliate/analytics?days=${days}`)
}

export async function apiGetMarketing(): Promise<MarketingData> {
  return affiliateFetch('/affiliate/marketing')
}

// ── Admin API Calls ───────────────────────────────────────────────────────────

export async function apiAdminGetSettings(): Promise<AffiliateSettings> {
  return affiliateFetch('/admin/affiliate/settings')
}

export async function apiAdminUpdateSettings(payload: Partial<AffiliateSettings>) {
  return affiliateFetch('/admin/affiliate/settings', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function apiAdminGetSummary(): Promise<AdminSummary> {
  return affiliateFetch('/admin/affiliate/summary')
}

export async function apiAdminListAffiliates(params: {
  page?: number
  per_page?: number
  status?: string
  search?: string
  flagged?: boolean
}): Promise<{ items: AdminAffiliate[]; total: number; page: number; per_page: number; pages: number }> {
  const q = new URLSearchParams()
  if (params.page) q.set('page', String(params.page))
  if (params.per_page) q.set('per_page', String(params.per_page))
  if (params.status) q.set('status', params.status)
  if (params.search) q.set('search', params.search)
  if (params.flagged !== undefined) q.set('flagged', String(params.flagged))
  return affiliateFetch(`/admin/affiliate/affiliates?${q}`)
}

export async function apiAdminGetAffiliate(id: string) {
  return affiliateFetch(`/admin/affiliate/affiliates/${id}`)
}

export async function apiAdminUpdateAffiliateStatus(
  id: string,
  status: string,
  reason?: string,
  notes?: string,
) {
  return affiliateFetch(`/admin/affiliate/affiliates/${id}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status, reason, notes }),
  })
}

export async function apiAdminSetCommission(id: string, commission_pct: number | null) {
  return affiliateFetch(`/admin/affiliate/affiliates/${id}/commission`, {
    method: 'PUT',
    body: JSON.stringify({ commission_pct }),
  })
}

export async function apiAdminListPayouts(params: {
  page?: number
  status?: string
}) {
  const q = new URLSearchParams()
  if (params.page) q.set('page', String(params.page))
  if (params.status) q.set('status', params.status)
  return affiliateFetch(`/admin/affiliate/payouts?${q}`)
}

export async function apiAdminActionPayout(
  id: string,
  action: 'approve' | 'reject' | 'mark_paid',
  transaction_ref?: string,
  notes?: string,
) {
  return affiliateFetch(`/admin/affiliate/payouts/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ action, transaction_ref, notes }),
  })
}

export async function apiAdminListCommissions(params: {
  page?: number
  status?: string
  affiliate_id?: string
}) {
  const q = new URLSearchParams()
  if (params.page) q.set('page', String(params.page))
  if (params.status) q.set('status', params.status)
  if (params.affiliate_id) q.set('affiliate_id', params.affiliate_id)
  return affiliateFetch(`/admin/affiliate/commissions?${q}`)
}

export async function apiAdminListFraudFlags(is_resolved?: boolean) {
  const q = is_resolved !== undefined ? `?is_resolved=${is_resolved}` : ''
  return affiliateFetch(`/admin/affiliate/fraud-flags${q}`)
}

export async function apiAdminGetAuditLogs(page: number = 1) {
  return affiliateFetch(`/admin/affiliate/audit-logs?page=${page}`)
}

// ── Cookie helper for frontend referral capture ───────────────────────────────

export function captureRefCode(): string | null {
  if (typeof window === 'undefined') return null
  const params = new URLSearchParams(window.location.search)
  const ref = params.get('ref')
  if (ref) {
    // Store in cookie for 90 days
    const expires = new Date(Date.now() + 90 * 86400 * 1000).toUTCString()
    if (!document.cookie.includes('ag_ref=')) {
      document.cookie = `ag_ref=${ref}; expires=${expires}; path=/; SameSite=Lax`
    }
    document.cookie = `ag_ref_last=${ref}; expires=${expires}; path=/; SameSite=Lax`
  }
  // Read from cookie
  const match = document.cookie.match(/(?:^|;\s*)ag_ref=([^;]+)/)
  return match ? match[1] : null
}

export function getRefCodeFromCookie(): string | null {
  if (typeof window === 'undefined') return null
  const match = document.cookie.match(/(?:^|;\s*)ag_ref=([^;]+)/)
  return match ? match[1] : null
}

export function getSessionIdFromCookie(): string | null {
  if (typeof window === 'undefined') return null
  const match = document.cookie.match(/(?:^|;\s*)ag_sid=([^;]+)/)
  return match ? match[1] : null
}
