'use client'
import { useState, useEffect } from 'react'
import Link from 'next/link'
import Navbar from '@/components/Navbar'
import Footer from '@/components/Footer'
import DigestCard from '@/components/DigestCard'
import SectorReport from '@/components/SectorReport'
import Disclaimer from '@/components/Disclaimer'
import { apiPublicSample, Digest, SectorReport as SectorReportType } from '@/lib/api'

export default function SamplePage() {
  const [digests, setDigests] = useState<Digest[]>([])
  const [sector, setSector] = useState<SectorReportType | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiPublicSample()
      .then((data) => {
        setDigests(data.digests || [])
        setSector(data.sector_report)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="min-h-screen bg-[#090909]">
      <Navbar />

      <section className="pt-32 pb-20 max-w-5xl mx-auto px-6">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="section-tag justify-center mb-3">Sample Content</div>
          <h1 className="text-4xl md:text-5xl font-black text-white mb-4">
            This is what Pro members receive every day
          </h1>
          <p className="text-[#555] text-lg max-w-xl mx-auto">
            Three complete morning digests and one sector report — fully unlocked, no login required.
          </p>
        </div>

        {/* Digests */}
        {loading ? (
          <div className="space-y-12">
            {[1, 2, 3].map((i) => (
              <div key={i} className="space-y-4">
                <div className="skeleton h-8 w-48 mb-4" />
                {[1, 2, 3].map((j) => (
                  <div key={j} className="glass-card p-6 h-36">
                    <div className="skeleton h-4 w-20 mb-4" />
                    <div className="skeleton h-5 w-3/4 mb-3" />
                    <div className="skeleton h-4 w-full" />
                  </div>
                ))}
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-16">
            {digests.map((digest, di) => (
              <div key={digest.id}>
                <div className="flex items-center gap-3 mb-6">
                  <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-semibold ${
                    digest.market_mood === 'BULLISH'
                      ? 'bg-[rgba(0,196,140,0.15)] text-[#00C48C] border-[rgba(0,196,140,0.3)]'
                      : digest.market_mood === 'BEARISH'
                      ? 'bg-[rgba(239,68,68,0.15)] text-[#ef4444] border-[rgba(239,68,68,0.3)]'
                      : 'bg-[rgba(245,158,11,0.15)] text-[#f59e0b] border-[rgba(245,158,11,0.3)]'
                  }`}>
                    <div className={`w-1.5 h-1.5 rounded-full ${
                      digest.market_mood === 'BULLISH' ? 'bg-[#00C48C]' :
                      digest.market_mood === 'BEARISH' ? 'bg-[#ef4444]' : 'bg-[#f59e0b]'
                    }`} />
                    {digest.market_mood}
                  </div>
                  <h2 className="text-lg font-bold text-white">
                    Morning Digest — {new Date(digest.date).toLocaleDateString('en-IN', {
                      weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
                    })}
                  </h2>
                </div>
                <div className="space-y-4">
                  {digest.items.map((item, i) => (
                    <DigestCard key={i} item={item} index={i} />
                  ))}
                </div>
                {di < digests.length - 1 && <div className="divider mt-8" />}
              </div>
            ))}
          </div>
        )}

        {/* Sector Report */}
        {sector && (
          <div className="mt-16">
            <div className="flex items-center gap-3 mb-6">
              <span className="section-tag">Sector Report</span>
            </div>
            <SectorReport report={sector} />
          </div>
        )}

        {/* CTA */}
        <div className="mt-16 glass-card p-10 md:p-12 text-center pricing-card-featured">
          <h2 className="text-3xl font-black text-white mb-3">
            This is what Pro members get every morning.
          </h2>
          <p className="text-[#555] mb-8 max-w-lg mx-auto">
            7 days free. No credit card. Full access to the digest, breakout watchlist, and sector reports.
          </p>
          <Link href="/register" className="btn-brand text-base py-4 px-8">
            Start Free Trial →
          </Link>
          <p className="text-xs text-[#444] mt-4">No card required · Cancel anytime</p>
        </div>

        <div className="mt-12">
          <Disclaimer />
        </div>
      </section>

      <Footer />
    </div>
  )
}
