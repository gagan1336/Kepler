'use client'
import { useState, useEffect, useCallback, useRef } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import {
  apiCreateCryptoPayment,
  apiGetCryptoStatus,
  type CryptoPaymentResponse,
  type CryptoPaymentStatus,
} from '@/lib/api'

/* ── Types ─────────────────────────────────────────────────────────────────── */
type Plan = 'pro' | 'elite'
type Billing = 'monthly' | 'yearly'
type Coin = 'usdttrc20' | 'btc' | 'eth'

interface CryptoPaymentModalProps {
  plan: Plan
  billing: Billing
  onClose: () => void
  onSuccess: () => void
}

/* ── Coin metadata ──────────────────────────────────────────────────────────── */
const COINS: { id: Coin; label: string; symbol: string; network?: string; color: string; icon: string }[] = [
  { id: 'usdttrc20', label: 'USDT', symbol: 'USDT', network: 'TRC-20', color: '#26A17B', icon: '₮' },
  { id: 'btc',       label: 'Bitcoin', symbol: 'BTC', color: '#F7931A', icon: '₿' },
  { id: 'eth',       label: 'Ethereum', symbol: 'ETH', color: '#627EEA', icon: 'Ξ' },
]

/* ── Price table ────────────────────────────────────────────────────────────── */
const PRICES: Record<Plan, Record<Billing, number>> = {
  pro:   { monthly: 799,   yearly: 7990  },
  elite: { monthly: 1999,  yearly: 19990 },
}

/* ── Status badge ───────────────────────────────────────────────────────────── */
const STATUS_LABELS: Record<string, { label: string; color: string; pulse?: boolean }> = {
  waiting:    { label: 'Awaiting Payment', color: '#F7B731', pulse: true },
  confirming: { label: 'Confirming on chain…', color: '#7EC8E3', pulse: true },
  confirmed:  { label: '✓ Payment Confirmed!', color: '#00C48C' },
  failed:     { label: 'Payment Failed', color: '#ef4444' },
  expired:    { label: 'Invoice Expired', color: '#ef4444' },
  refunded:   { label: 'Refunded', color: '#A0AEC0' },
}

/* ── Copy-to-clipboard button ───────────────────────────────────────────────── */
function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback for browsers that don't support clipboard API
      const el = document.createElement('textarea')
      el.value = text
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      document.body.removeChild(el)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <button
      onClick={copy}
      className="flex items-center gap-1.5 text-xs font-semibold transition-all duration-200 py-1.5 px-3 rounded-lg"
      style={{
        background: copied ? 'rgba(0,196,140,0.15)' : 'rgba(255,255,255,0.06)',
        color: copied ? '#00C48C' : '#A0AEC0',
        border: `1px solid ${copied ? 'rgba(0,196,140,0.3)' : 'rgba(255,255,255,0.08)'}`,
      }}
      title={`Copy ${label}`}
    >
      {copied ? (
        <>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          Copied!
        </>
      ) : (
        <>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
          </svg>
          Copy
        </>
      )}
    </button>
  )
}

/* ── Main Modal Component ───────────────────────────────────────────────────── */
export default function CryptoPaymentModal({ plan, billing, onClose, onSuccess }: CryptoPaymentModalProps) {
  const [step, setStep] = useState<'select-coin' | 'payment' | 'success'>('select-coin')
  const [selectedCoin, setSelectedCoin] = useState<Coin>('usdttrc20')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [paymentData, setPaymentData] = useState<CryptoPaymentResponse | null>(null)
  const [statusData, setStatusData] = useState<CryptoPaymentStatus | null>(null)
  const [timeLeft, setTimeLeft] = useState(7200) // 2 hours in seconds
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const priceINR = PRICES[plan][billing]
  const coinMeta = COINS.find(c => c.id === selectedCoin)!

  /* ── Cleanup on unmount ─────────────────────────────────────────────────── */
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [])

  /* ── Countdown timer ────────────────────────────────────────────────────── */
  const startTimer = useCallback(() => {
    timerRef.current = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) {
          clearInterval(timerRef.current!)
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }, [])

  /* ── Status poller ──────────────────────────────────────────────────────── */
  const startPolling = useCallback((paymentId: string) => {
    pollRef.current = setInterval(async () => {
      try {
        const status = await apiGetCryptoStatus(paymentId)
        setStatusData(status)

        if (status.status === 'confirmed') {
          clearInterval(pollRef.current!)
          clearInterval(timerRef.current!)
          setStep('success')
          setTimeout(onSuccess, 3000) // auto-close and refresh after 3s
        } else if (['failed', 'expired', 'refunded'].includes(status.status)) {
          clearInterval(pollRef.current!)
        }
      } catch (e) {
        // Silently ignore polling errors
      }
    }, 5000)
  }, [onSuccess])

  /* ── Create payment ─────────────────────────────────────────────────────── */
  const handleCreatePayment = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await apiCreateCryptoPayment({
        plan,
        billing_period: billing,
        coin: selectedCoin,
      })
      setPaymentData(data)
      setStep('payment')
      startTimer()
      startPolling(data.payment_id)
    } catch (e: any) {
      setError(e.message || 'Failed to create payment. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  /* ── Format countdown ───────────────────────────────────────────────────── */
  const formatTime = (secs: number) => {
    const h = Math.floor(secs / 3600)
    const m = Math.floor((secs % 3600) / 60)
    const s = secs % 60
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }

  const currentStatus = statusData?.status ?? paymentData?.status ?? 'waiting'
  const statusMeta = STATUS_LABELS[currentStatus] ?? STATUS_LABELS.waiting

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(12px)' }}
      onClick={(e) => e.target === e.currentTarget && step !== 'payment' && onClose()}
    >
      <div
        className="relative w-full max-w-md rounded-2xl overflow-hidden"
        style={{
          background: 'linear-gradient(135deg, #0d1117 0%, #111827 100%)',
          border: '1px solid rgba(255,255,255,0.08)',
          boxShadow: '0 25px 60px rgba(0,0,0,0.7)',
        }}
      >
        {/* ── Gradient header strip ── */}
        <div
          className="h-1 w-full"
          style={{ background: 'linear-gradient(90deg, #F7931A, #627EEA, #26A17B)' }}
        />

        {/* ── Header ── */}
        <div className="flex items-center justify-between px-6 pt-5 pb-4">
          <div>
            <h2 className="text-white font-black text-lg">Pay with Crypto</h2>
            <p className="text-[#4A5568] text-xs mt-0.5 capitalize">
              Kepler {plan} — {billing} · ₹{priceINR.toLocaleString('en-IN')}
            </p>
          </div>
          {step !== 'payment' && (
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-full flex items-center justify-center transition-colors hover:bg-white/10 text-[#4A5568] hover:text-white"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          )}
        </div>

        {/* ══════════════ STEP 1: COIN SELECTOR ══════════════ */}
        {step === 'select-coin' && (
          <div className="px-6 pb-6">
            <p className="text-[#4A5568] text-xs mb-4 font-medium">Select your preferred cryptocurrency</p>

            <div className="space-y-3 mb-6">
              {COINS.map((coin) => (
                <button
                  key={coin.id}
                  onClick={() => setSelectedCoin(coin.id)}
                  className="w-full flex items-center gap-4 p-4 rounded-xl transition-all duration-200 text-left"
                  style={{
                    background: selectedCoin === coin.id ? `${coin.color}15` : 'rgba(255,255,255,0.03)',
                    border: `1px solid ${selectedCoin === coin.id ? coin.color + '50' : 'rgba(255,255,255,0.06)'}`,
                    transform: selectedCoin === coin.id ? 'scale(1.01)' : 'scale(1)',
                  }}
                >
                  {/* Coin icon */}
                  <div
                    className="w-11 h-11 rounded-full flex items-center justify-center text-xl font-black flex-shrink-0"
                    style={{ background: `${coin.color}20`, color: coin.color }}
                  >
                    {coin.icon}
                  </div>

                  {/* Label */}
                  <div className="flex-1 min-w-0">
                    <p className="text-white font-bold text-sm">{coin.label}</p>
                    {coin.network && (
                      <p className="text-[#4A5568] text-xs">{coin.network} Network</p>
                    )}
                  </div>

                  {/* Radio */}
                  <div
                    className="w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0"
                    style={{
                      borderColor: selectedCoin === coin.id ? coin.color : 'rgba(255,255,255,0.2)',
                      background: selectedCoin === coin.id ? coin.color : 'transparent',
                    }}
                  >
                    {selectedCoin === coin.id && (
                      <div className="w-2 h-2 rounded-full bg-white" />
                    )}
                  </div>
                </button>
              ))}
            </div>

            {/* Info notice */}
            <div
              className="flex items-start gap-3 p-3 rounded-lg mb-6 text-xs text-[#4A5568]"
              style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.05)' }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#F7B731" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mt-0.5 flex-shrink-0">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <span>
                Amount auto-converted from ₹{priceINR.toLocaleString('en-IN')} INR by NOWPayments.
                Payment window: 2 hours. No auto-renewal — you'll be prompted before expiry.
              </span>
            </div>

            {error && (
              <div className="mb-4 p-3 rounded-lg text-xs text-[#ef4444]"
                style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' }}>
                {error}
              </div>
            )}

            <button
              onClick={handleCreatePayment}
              disabled={loading}
              className="w-full py-3.5 rounded-xl font-bold text-sm transition-all duration-200 flex items-center justify-center gap-2"
              style={{
                background: loading ? 'rgba(255,255,255,0.05)' : `linear-gradient(135deg, ${coinMeta.color}, ${coinMeta.color}bb)`,
                color: loading ? '#4A5568' : '#000',
                cursor: loading ? 'not-allowed' : 'pointer',
              }}
            >
              {loading ? (
                <>
                  <svg className="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                  </svg>
                  Generating Invoice…
                </>
              ) : (
                <>
                  Generate Payment Address →
                </>
              )}
            </button>
          </div>
        )}

        {/* ══════════════ STEP 2: PAYMENT (QR + Details) ══════════════ */}
        {step === 'payment' && paymentData && (
          <div className="px-6 pb-6">
            {/* Status bar */}
            <div
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg mb-5"
              style={{
                background: `${statusMeta.color}12`,
                border: `1px solid ${statusMeta.color}30`,
              }}
            >
              {statusMeta.pulse && (
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75" style={{ background: statusMeta.color }} />
                  <span className="relative inline-flex rounded-full h-2 w-2" style={{ background: statusMeta.color }} />
                </span>
              )}
              <span className="text-xs font-semibold" style={{ color: statusMeta.color }}>
                {statusMeta.label}
              </span>
              <span className="ml-auto text-xs font-mono" style={{ color: '#4A5568' }}>
                ⏱ {formatTime(timeLeft)}
              </span>
            </div>

            {/* QR Code */}
            <div className="flex justify-center mb-5">
              <div className="p-3 rounded-2xl" style={{ background: '#fff' }}>
                <QRCodeSVG
                  value={paymentData.pay_address}
                  size={180}
                  fgColor="#000000"
                  bgColor="#ffffff"
                  level="M"
                />
              </div>
            </div>

            {/* Amount */}
            <div
              className="text-center p-4 rounded-xl mb-4"
              style={{ background: `${coinMeta.color}0f`, border: `1px solid ${coinMeta.color}25` }}
            >
              <p className="text-[#4A5568] text-xs mb-1 uppercase tracking-widest">Amount to send</p>
              <p className="text-3xl font-black" style={{ color: coinMeta.color }}>
                {paymentData.pay_amount}
              </p>
              <p className="text-white font-bold text-sm">{paymentData.coin_display}</p>
              <p className="text-[#4A5568] text-xs mt-1">≈ ₹{paymentData.amount_inr.toLocaleString('en-IN')} INR</p>
            </div>

            {/* Send EXACT amount warning */}
            <div className="flex items-center gap-2 mb-4 px-3 py-2 rounded-lg text-xs text-[#F7B731]"
              style={{ background: 'rgba(247,183,49,0.07)', border: '1px solid rgba(247,183,49,0.15)' }}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="flex-shrink-0">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                <line x1="12" y1="9" x2="12" y2="13" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
              Send the <strong>exact amount</strong> shown above. Partial payments require extra confirmation time.
            </div>

            {/* Address */}
            <div
              className="rounded-xl p-4 mb-4"
              style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-bold uppercase tracking-widest text-[#4A5568]">
                  {paymentData.coin_display} Address
                </span>
                <CopyButton text={paymentData.pay_address} label="address" />
              </div>
              <p className="text-white text-xs font-mono break-all leading-relaxed">
                {paymentData.pay_address}
              </p>
            </div>

            {/* Instructions */}
            <div className="space-y-2 text-xs text-[#4A5568]">
              <div className="flex items-start gap-2">
                <span className="w-5 h-5 rounded-full bg-white/05 flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0 mt-0.5">1</span>
                <span>Open your crypto wallet and send <strong className="text-white">{paymentData.pay_amount} {paymentData.coin_display.split(' ')[0]}</strong> to the address above</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="w-5 h-5 rounded-full bg-white/05 flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0 mt-0.5">2</span>
                <span>We monitor the blockchain and confirm your payment automatically</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="w-5 h-5 rounded-full bg-white/05 flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0 mt-0.5">3</span>
                <span>Your plan activates instantly once confirmed — no action needed from you</span>
              </div>
            </div>

            {/* Close note */}
            <p className="text-center text-[10px] text-[#333] mt-5">
              You can safely close this window. Your payment will be tracked automatically.
            </p>
            <button
              onClick={onClose}
              className="w-full mt-3 py-2.5 rounded-xl text-sm font-medium text-[#4A5568] hover:text-white transition-colors"
              style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}
            >
              Close & Wait for Confirmation
            </button>
          </div>
        )}

        {/* ══════════════ STEP 3: SUCCESS ══════════════ */}
        {step === 'success' && (
          <div className="px-6 pb-8 text-center">
            {/* Animated checkmark */}
            <div
              className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6 mt-2"
              style={{
                background: 'radial-gradient(circle, rgba(0,196,140,0.2), rgba(0,196,140,0.05))',
                border: '2px solid rgba(0,196,140,0.4)',
                animation: 'pulse 2s infinite',
              }}
            >
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#00C48C" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>

            <h3 className="text-white font-black text-xl mb-2">Payment Confirmed!</h3>
            <p className="text-[#4A5568] text-sm mb-6 leading-relaxed">
              Your <span className="text-white font-semibold capitalize">{paymentData?.plan} {paymentData?.billing_period}</span> subscription
              is now active. Redirecting to your dashboard…
            </p>

            {statusData?.subscription_end && (
              <div
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-full text-xs font-semibold mb-6"
                style={{ background: 'rgba(0,196,140,0.12)', color: '#00C48C', border: '1px solid rgba(0,196,140,0.25)' }}
              >
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                  <line x1="16" y1="2" x2="16" y2="6" />
                  <line x1="8" y1="2" x2="8" y2="6" />
                  <line x1="3" y1="10" x2="21" y2="10" />
                </svg>
                Active until {new Date(statusData.subscription_end).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
              </div>
            )}

            <button
              onClick={onSuccess}
              className="w-full py-3 rounded-xl font-bold text-sm text-black"
              style={{ background: 'linear-gradient(135deg, #00C48C, #00a876)' }}
            >
              Go to Dashboard →
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
