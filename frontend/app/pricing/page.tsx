'use client'
import { useState, useEffect, useCallback, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import Navbar from '@/components/Navbar'
import Footer from '@/components/Footer'
import Disclaimer from '@/components/Disclaimer'
import { PricingCard, PLANS } from '@/components/PricingCard'
import { apiPublicStats, apiCreateSubscription, PublicStats } from '@/lib/api'
import { useAuth } from '@/lib/auth'

const FAQ = [
  {
    q: 'Is there really no credit card required for the free trial?',
    a: 'Correct. Register with email only. No payment information needed. The 7-day trial gives you full Pro access.',
  },
  {
    q: 'What happens after the 7-day trial?',
    a: 'Your account stays active on the Free plan. You keep access to the top 3 digest items per day, the latest sector report, and the latest IPO brief. Nothing is deleted.',
  },
  {
    q: 'How does the 30-day refund work?',
    a: 'If you subscribe and decide it\'s not for you within 30 days, email us and we\'ll process a full refund. No questions. The refund takes 5-7 business days.',
  },
  {
    q: 'What exactly is the morning digest?',
    a: 'Every weekday morning, Gemini 1.5 Pro reads news from 4 RSS feeds, NewsAPI, and GNews — scores each article 1-10 for market importance — and delivers only the articles scoring 7 or above with plain-English summaries. It lands at 8 AM IST.',
  },
  {
    q: 'How is the breakout scanner different from regular screeners?',
    a: 'It scans the full Nifty 500 every morning for specific setups: stocks within 5% of their 52-week high, with above-average volume, RSI between 45-72, and trading above their 20-day EMA. It finds pre-breakout setups, not stocks that have already moved.',
  },
  {
    q: 'Is this SEBI registered investment advice?',
    a: 'No. We are not SEBI registered advisers. Everything on Antigravity is educational and informational content. We help you do better research — what you decide to do with that research is entirely your decision.',
  },
  {
    q: 'Can I get a GST invoice?',
    a: 'Yes. A GST invoice (18% GST included) is automatically generated for every payment and available to download from your account dashboard.',
  },
  {
    q: 'How does the Telegram delivery work?',
    a: 'When you subscribe, you\'ll receive an invite link to our private Telegram channel. The morning digest is published there every weekday at 8 AM IST. Elite members also get the sector report on Tuesday.',
  },
  {
    q: 'Can I switch between monthly and annual billing?',
    a: 'Yes. You can switch to annual billing anytime from your account settings. The annual savings are applied from the next billing cycle.',
  },
  {
    q: 'What is the Elite plan\'s seat limit?',
    a: 'Elite is capped at 100 members to maintain the quality of the analysis and keep the community manageable. Once seats fill, new members go on a waitlist.',
  },
  {
    q: 'How do I cancel?',
    a: 'Go to your account dashboard and click "Cancel subscription." One click. No friction. You keep access until the end of the billing period. No cancellation fee.',
  },
  {
    q: 'What are the payment methods?',
    a: 'We accept all major Indian payment methods via Razorpay: UPI, credit card, debit card, net banking, and EMI.',
  },
]

const COMPARISON = [
  { feature: 'Morning digest (top 3 items)', free: true, pro: true, elite: true },
  { feature: 'Full morning digest (all items)', free: false, pro: true, elite: true },
  { feature: 'Digest history (last 30 days)', free: false, pro: true, elite: true },
  { feature: 'Breakout watchlist (daily)', free: false, pro: true, elite: true },
  { feature: 'Latest sector report', free: true, pro: true, elite: true },
  { feature: 'Sector report history (12 weeks)', free: false, pro: true, elite: true },
  { feature: 'Latest IPO brief', free: true, pro: true, elite: true },
  { feature: 'IPO brief archive', free: false, pro: true, elite: true },
  { feature: 'Deep dive list + summaries', free: false, pro: true, elite: true },
  { feature: 'Deep dive full content', free: false, pro: false, elite: true },
  { feature: 'Telegram channel access', free: false, pro: true, elite: true },
  { feature: 'Elite Telegram (sector reports)', free: false, pro: false, elite: true },
  { feature: 'GST invoices', free: false, pro: true, elite: true },
  { feature: '30-day money back guarantee', free: false, pro: true, elite: true },
]

function PricingPageInner() {
  const [isAnnual, setIsAnnual] = useState(false)
  const [openFaq, setOpenFaq] = useState<number | null>(null)
  const [stats, setStats] = useState<PublicStats | null>(null)
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null) // tracks which plan is loading
  const searchParams = useSearchParams()
  const { isAuthenticated: isLoggedIn } = useAuth()

  useEffect(() => {
    apiPublicStats().then(setStats).catch(console.error)
  }, [])

  // Auto-trigger checkout when returning from /register?plan=xxx
  useEffect(() => {
    const plan = searchParams.get('plan')
    if (plan && isLoggedIn) {
      // slight delay to let Razorpay script load
      const timer = setTimeout(() => handleCheckout(plan), 800)
      return () => clearTimeout(timer)
    }
  }, [isLoggedIn])
  const handleCheckout = async (planKey: string) => {
    if (!isLoggedIn) {
      window.location.href = `/register?plan=${planKey}`
      return
    }

    setCheckoutLoading(planKey)
    try {
      const data = await apiCreateSubscription(planKey)
      const Razorpay = (window as any).Razorpay
      if (!Razorpay) {
        alert('Payment system loading. Please try again in a moment.')
        return
      }
      const rzp = new Razorpay({
        key: data.razorpay_key,
        subscription_id: data.subscription_id,
        name: 'Antigravity',
        description: planKey.replace(/_/g, ' ').toUpperCase(),
        image: 'https://antigravity.in/logo.png',
        theme: { color: '#00C48C' },
        prefill: {},
        handler: () => {
          window.location.href = '/dashboard?subscribed=1'
        },
        modal: {
          ondismiss: () => setCheckoutLoading(null),
        },
      })
      rzp.open()
    } catch (e: any) {
      alert(e.message || 'Could not initiate payment. Please try again.')
      setCheckoutLoading(null)
    }
  }

  const tick = <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="#00C48C" strokeWidth="1.5" /><path d="M5 8l2.5 2.5L11 5" stroke="#00C48C" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
  const cross = <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="#2a2a2a" strokeWidth="1.5" /><path d="M5.5 10.5l5-5M10.5 10.5l-5-5" stroke="#333" strokeWidth="1.5" strokeLinecap="round" /></svg>

  return (
    <div className="min-h-screen bg-[#090909]">
      <Navbar />
      {/* Load Razorpay */}
      <script src="https://checkout.razorpay.com/v1/checkout.js" async />

      <section className="pt-32 pb-20 max-w-7xl mx-auto px-6">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="section-tag justify-center mb-3">Pricing</div>
          <h1 className="text-4xl md:text-5xl font-black text-white mb-4">
            Simple, honest pricing
          </h1>
          <p className="text-[#555] text-lg max-w-xl mx-auto">
            Start free. Upgrade when you're ready. Cancel anytime.
          </p>
          {/* Toggle */}
          <div className="inline-flex items-center gap-4 mt-6">
            <button onClick={() => setIsAnnual(false)} className={`text-sm font-medium transition-colors ${!isAnnual ? 'text-white' : 'text-[#555]'}`}>Monthly</button>
            <button onClick={() => setIsAnnual(!isAnnual)} className={`relative w-12 h-6 rounded-full transition-colors ${isAnnual ? 'bg-[#00C48C]' : 'bg-[#2a2a2a]'}`}>
              <span className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-white transition-transform ${isAnnual ? 'translate-x-6' : ''}`} />
            </button>
            <button onClick={() => setIsAnnual(true)} className={`text-sm font-medium transition-colors ${isAnnual ? 'text-white' : 'text-[#555]'}`}>
              Annual <span className="text-[#00C48C] text-xs font-bold">~22% off</span>
            </button>
          </div>
        </div>

        {/* Plans */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-20">
          {PLANS.map((plan) => (
            <PricingCard
              key={plan.id}
              plan={plan}
              isAnnual={isAnnual}
              seatsRemaining={plan.id === 'elite' ? stats?.elite_seats_remaining : undefined}
              onCheckout={isLoggedIn ? handleCheckout : undefined}
              loading={checkoutLoading !== null}
            />
          ))}
        </div>

        {/* Comparison table */}
        <div className="mb-20">
          <h2 className="text-2xl font-black text-white mb-8 text-center">Full feature comparison</h2>
          <div className="glass-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[#1e1e1e]">
                    <th className="text-left p-4 text-xs font-bold uppercase tracking-widest text-[#555]">Feature</th>
                    <th className="p-4 text-center text-xs font-bold uppercase tracking-widest text-[#555]">Free</th>
                    <th className="p-4 text-center text-xs font-bold uppercase tracking-widest text-[#00C48C]">Pro</th>
                    <th className="p-4 text-center text-xs font-bold uppercase tracking-widest text-[#fbbf24]">Elite</th>
                  </tr>
                </thead>
                <tbody>
                  {COMPARISON.map((row, i) => (
                    <tr key={i} className="border-b border-[#1a1a1a] hover:bg-[#0f0f0f] transition-colors">
                      <td className="p-4 text-sm text-[#888]">{row.feature}</td>
                      <td className="p-4 text-center">{row.free ? tick : cross}</td>
                      <td className="p-4 text-center">{row.pro ? tick : cross}</td>
                      <td className="p-4 text-center">{row.elite ? tick : cross}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Trust badges */}
        <div className="flex flex-wrap justify-center gap-6 mb-20">
          {[
            { label: 'Razorpay Secure', icon: '🔒' },
            { label: 'GST Invoice Included', icon: '📄' },
            { label: 'SSL Encrypted', icon: '🛡️' },
            { label: '30-Day Money Back', icon: '💰' },
          ].map((b) => (
            <div key={b.label} className="flex items-center gap-2 text-sm text-[#555]">
              <span>{b.icon}</span>
              <span>{b.label}</span>
            </div>
          ))}
        </div>

        {/* FAQ */}
        <div className="max-w-3xl mx-auto">
          <h2 className="text-2xl font-black text-white mb-8 text-center">Frequently asked questions</h2>
          <div className="space-y-3">
            {FAQ.map((item, i) => (
              <div key={i} className="glass-card overflow-hidden">
                <button
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  className="w-full flex items-start justify-between gap-4 p-5 text-left"
                >
                  <span className="text-sm font-semibold text-white">{item.q}</span>
                  <svg
                    width="16" height="16" viewBox="0 0 16 16" fill="none"
                    className={`shrink-0 mt-0.5 transition-transform text-[#555] ${openFaq === i ? 'rotate-180' : ''}`}
                  >
                    <path d="M3 6l5 5 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  </svg>
                </button>
                {openFaq === i && (
                  <div className="px-5 pb-5">
                    <p className="text-sm text-[#666] leading-relaxed">{item.a}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* CTA */}
        <div className="mt-20 text-center glass-card p-12">
          <h2 className="text-3xl font-black text-white mb-4">Ready to start?</h2>
          <p className="text-[#555] mb-8">7 days free. No card. No strings.</p>
          <Link href="/register" className="btn-brand text-lg py-4 px-10">
            Start Free Trial →
          </Link>
        </div>

        <div className="mt-12">
          <Disclaimer />
        </div>
      </section>

      <Footer />
    </div>
  )
}

export default function PricingPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#080C10]" />}>
      <PricingPageInner />
    </Suspense>
  )
}
