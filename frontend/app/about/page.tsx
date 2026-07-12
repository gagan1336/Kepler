import Link from 'next/link'
import Navbar from '@/components/Navbar'
import Footer from '@/components/Footer'
import Disclaimer from '@/components/Disclaimer'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'About Antigravity — AI Market Intelligence for Indian Traders',
  description: 'Learn about Antigravity: what it is, what it is not, how the AI pipeline works, and our commitment to education over tips.',
}

const WHAT_IT_IS = [
  'An AI-powered morning digest that filters and summarises market news',
  'A technical scanner that identifies pre-breakout setups in the Nifty 500',
  'A weekly sector rotation tracker backed by real performance data',
  'A neutral IPO analysis service that helps you research before subscribing',
  'An educational platform that teaches you to research, not what to buy',
]

const WHAT_IT_IS_NOT = [
  'Not a SEBI registered investment adviser',
  'Not a stock recommendation service',
  'Not a tip service of any kind',
  'Not a "guarantee" of any returns or performance',
  'Not a substitute for your own research and due diligence',
]

const HOW_IT_WORKS = [
  {
    step: '01',
    title: 'News Collection (6 AM IST)',
    desc: 'Four RSS feeds, NewsAPI, and GNews are scraped for all market-relevant news published in the last 24 hours. Articles are deduplicated using similarity matching.',
  },
  {
    step: '02',
    title: 'AI Classification (6:15 AM IST)',
    desc: 'All articles are sent to Gemini 1.5 Pro in a single API call. It classifies each article (MACRO, SECTOR, STOCK, etc.), scores it 1-10 for market importance, and filters out anything below 7.',
  },
  {
    step: '03',
    title: 'Plain-English Summaries',
    desc: 'Each remaining article is summarised in 2-3 sentences. No jargon. If a technical term is unavoidable, it\'s explained in the same sentence. Affected sectors and NSE stock symbols are extracted.',
  },
  {
    step: '04',
    title: 'Breakout Scanner (7 AM IST)',
    desc: 'yfinance pulls 1 year of OHLCV data for all Nifty 500 stocks. RSI, EMA20/50, 52W high, and volume ratios are calculated. Stocks passing all four criteria are passed to Gemini 1.5 Flash for setup descriptions.',
  },
  {
    step: '05',
    title: 'Telegram Delivery (8 AM IST)',
    desc: 'The formatted digest is published to the Pro and Elite Telegram channels. Elite members also receive the Tuesday sector report. The dashboard is updated simultaneously.',
  },
]

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-[#090909]">
      <Navbar />

      {/* Hero */}
      <section className="pt-32 pb-16 max-w-4xl mx-auto px-6">
        <div className="section-tag mb-4">About</div>
        <h1 className="text-4xl md:text-5xl font-black text-white mb-6 leading-tight">
          Built for traders who are tired of noise.
        </h1>
        <p className="text-[#666] text-lg leading-relaxed max-w-2xl">
          Antigravity was built because the Indian financial media is broken. Too many headlines, too little
          signal. Too many "tips", too little research. Too much noise, not enough thinking.
        </p>
      </section>

      {/* What it is / is not */}
      <section className="py-16 bg-[#0a0a0a]">
        <div className="max-w-4xl mx-auto px-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div>
              <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
                <span className="text-[#00C48C]">✓</span> What Antigravity is
              </h2>
              <ul className="space-y-3">
                {WHAT_IT_IS.map((item) => (
                  <li key={item} className="flex items-start gap-3 text-sm text-[#888]">
                    <span className="text-[#00C48C] mt-0.5 shrink-0">→</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
                <span className="text-[#ef4444]">✗</span> What Antigravity is not
              </h2>
              <ul className="space-y-3">
                {WHAT_IT_IS_NOT.map((item) => (
                  <li key={item} className="flex items-start gap-3 text-sm text-[#888]">
                    <span className="text-[#ef4444] mt-0.5 shrink-0">✗</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* How the AI pipeline works */}
      <section className="py-16 max-w-4xl mx-auto px-6">
        <div className="section-tag mb-4">The Pipeline</div>
        <h2 className="text-3xl font-black text-white mb-10">
          How the AI pipeline works
        </h2>
        <div className="space-y-6">
          {HOW_IT_WORKS.map((step) => (
            <div key={step.step} className="glass-card p-6 flex gap-5">
              <div className="text-3xl font-black text-[rgba(0,196,140,0.3)] font-mono shrink-0 leading-tight">
                {step.step}
              </div>
              <div>
                <h3 className="text-white font-bold mb-2">{step.title}</h3>
                <p className="text-sm text-[#666] leading-relaxed">{step.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Full disclaimer */}
      <section className="py-16 bg-[#0a0a0a]">
        <div className="max-w-4xl mx-auto px-6">
          <div className="section-tag mb-4">Disclosure</div>
          <h2 className="text-2xl font-black text-white mb-6">Legal Disclaimer</h2>
          <div className="glass-card p-6 md:p-8 prose-dark">
            <p>
              Antigravity is a market intelligence and educational content platform. We provide AI-curated
              news summaries, technical analysis observations, and sector commentary for informational
              and educational purposes only.
            </p>
            <br />
            <p>
              <strong>We are not a SEBI registered investment adviser</strong> under the SEBI
              (Investment Advisers) Regulations, 2013. Nothing published on this platform — including
              the morning digest, breakout watchlist, sector reports, IPO briefs, or deep dives —
              constitutes investment advice, a recommendation to buy or sell any security, or a
              solicitation of any investment.
            </p>
            <br />
            <p>
              All content is based on publicly available information and AI analysis of that information.
              The AI systems used may make errors in classification, analysis, or interpretation.
              Historical accuracy of any analysis does not guarantee future accuracy or results.
            </p>
            <br />
            <p>
              Indian securities markets are subject to market risk. Investments in equities are subject
              to high risk. Past performance is not indicative of future results. You should conduct
              your own research and consult a SEBI registered investment adviser before making any
              investment decisions.
            </p>
            <br />
            <p>
              By using this platform, you acknowledge and agree that all content is for educational
              purposes only and that you will not hold Antigravity liable for any investment decisions
              made based on content published on this platform.
            </p>
          </div>
        </div>
      </section>

      {/* Contact */}
      <section id="contact" className="py-16 max-w-4xl mx-auto px-6">
        <div className="section-tag mb-4">Contact</div>
        <h2 className="text-2xl font-black text-white mb-6">Get in touch</h2>
        <div className="glass-card p-6 md:p-8">
          <p className="text-[#666] text-sm mb-4">
            For questions about the platform, your subscription, or feedback on the analysis:
          </p>
          <a
            href="mailto:hello@antigravity.in"
            className="text-[#00C48C] font-medium hover:underline text-sm"
          >
            hello@antigravity.in
          </a>
          <p className="text-[#444] text-xs mt-4">
            We respond to all emails personally within 24 hours on business days.
          </p>
        </div>
      </section>

      <Disclaimer />
      <Footer />
    </div>
  )
}
