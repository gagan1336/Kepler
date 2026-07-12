'use client'
import { useState, useEffect, useRef, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import Navbar from '@/components/Navbar'
import { apiDashboardStats, apiDeepDiveGenerate, apiUploadSignal, apiGetSignals, apiDeleteSignal, type StockSignal } from '@/lib/api'
import { supabase } from '@/lib/supabase'
import { useAuth } from '@/lib/auth'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const ADMIN_EMAIL = 'gagansolanki293@gmail.com'

async function adminRequest(path: string, body?: any) {
  const { data: { session } } = await supabase.auth.getSession()
  const token = session?.access_token
  const res = await fetch(`${API_BASE}${path}`, {
    method: body ? 'POST' : 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

type StatusMsg = { type: 'success' | 'error' | 'info'; text: string } | null

export default function AdminPage() {
  const router = useRouter()
  const { user: authUser, isAuthenticated, loading: authLoading, backendLoading } = useAuth()
  const [stats, setStats] = useState<any>(null)
  const [status, setStatus] = useState<StatusMsg>(null)

  // IPO form state
  const [ipoForm, setIpoForm] = useState({
    company_name: '', open_date: '', close_date: '', price_band: '', industry: '',
  })
  const [ipoLoading, setIpoLoading] = useState(false)

  // AI Deep Dive generate state
  const [aiSymbol, setAiSymbol] = useState('')
  const [aiTier, setAiTier] = useState('elite')
  const [aiLoading, setAiLoading] = useState(false)
  const [aiResult, setAiResult] = useState<{ id: string; symbol: string; message: string } | null>(null)

  // Manual Deep Dive form state
  const [diveForm, setDiveForm] = useState({ title: '', summary: '', content: '', tier: 'elite' })
  const [diveLoading, setDiveLoading] = useState(false)

  // Scanner state
  const [scanLoading, setScanLoading]         = useState(false)
  const [newsLoading, setNewsLoading]         = useState(false)
  const [telegramLoading, setTelegramLoading] = useState(false)

  // Signal upload state
  const [sigForm, setSigForm] = useState({
    symbol: '', title: '', description: '', timeframe: 'Daily',
    signal_type: 'BULLISH', support: '', resistance: '', target: '', stoploss: '',
    plan_required: 'pro',
  })
  const [sigImage, setSigImage]       = useState<File | null>(null)
  const [sigPreview, setSigPreview]   = useState<string | null>(null)
  const [sigLoading, setSigLoading]   = useState(false)
  const [existingSigs, setExistingSigs] = useState<StockSignal[]>([])
  const [sigsLoaded, setSigsLoaded]   = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const loadSigs = useCallback(async () => {
    try {
      const data = await apiGetSignals(1, 50)
      setExistingSigs(data.signals)
      setSigsLoaded(true)
    } catch {}
  }, [])

  useEffect(() => {
    // Wait for BOTH Supabase session AND backend profile before checking access
    if (authLoading || backendLoading) return
    if (!isAuthenticated) { router.push('/login'); return }
    if (authUser?.email?.toLowerCase() !== ADMIN_EMAIL.toLowerCase()) {
      router.push('/dashboard'); return
    }
    apiDashboardStats().then(setStats).catch(console.error)
    loadSigs()
  }, [authLoading, backendLoading, isAuthenticated, authUser, loadSigs])

  const user = authUser

  // Show spinner while session + backend profile are loading
  if (authLoading || backendLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#090909' }}>
        <div
          className="w-10 h-10 border-2 rounded-full animate-spin"
          style={{ borderColor: 'rgba(201,163,78,0.2)', borderTopColor: '#C9A34E' }}
        />
      </div>
    )
  }

  const notify = (type: 'success' | 'error' | 'info', text: string) => {
    setStatus({ type, text })
    setTimeout(() => setStatus(null), 5000)
  }

  const handleIPOSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIpoLoading(true)
    try {
      await adminRequest('/ipo/create', {
        ...ipoForm,
        open_date: ipoForm.open_date,
        close_date: ipoForm.close_date,
      })
      notify('success', `IPO analysis queued for ${ipoForm.company_name}. Check back in a few minutes.`)
      setIpoForm({ company_name: '', open_date: '', close_date: '', price_band: '', industry: '' })
    } catch (err: any) {
      notify('error', err.message)
    } finally {
      setIpoLoading(false)
    }
  }

  const handleAIGenerate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!aiSymbol.trim()) { notify('error', 'Enter a stock symbol'); return }
    setAiLoading(true)
    setAiResult(null)
    try {
      const result = await apiDeepDiveGenerate(aiSymbol.trim().toUpperCase(), aiTier)
      setAiResult(result)
      notify('success', result.message)
      setAiSymbol('')
    } catch (err: any) {
      notify('error', err.message || 'AI generation failed')
    } finally {
      setAiLoading(false)
    }
  }

  const handleDiveSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!diveForm.content.trim()) { notify('error', 'Content is required'); return }
    setDiveLoading(true)
    try {
      await adminRequest('/admin/deepdive', diveForm)
      notify('success', `Deep Dive "${diveForm.title}" published successfully.`)
      setDiveForm({ title: '', summary: '', content: '', tier: 'elite' })
    } catch (err: any) {
      notify('error', err.message || 'Could not publish deep dive.')
    } finally {
      setDiveLoading(false)
    }
  }

  const runScan = async () => {
    setScanLoading(true)
    try {
      await adminRequest('/admin/trigger/breakout-scan', {})
      notify('success', 'Breakout scan triggered — results will appear in the watchlist shortly.')
    } catch (err: any) {
      notify('error', err.message)
    } finally {
      setScanLoading(false)
    }
  }

  const runNewsPipeline = async () => {
    setNewsLoading(true)
    try {
      await adminRequest('/admin/trigger/news-pipeline', {})
      notify('success', 'News + AI pipeline triggered — digest will be ready shortly.')
    } catch (err: any) {
      notify('error', err.message)
    } finally {
      setNewsLoading(false)
    }
  }

  const sendTelegramDigest = async () => {
    setTelegramLoading(true)
    try {
      await adminRequest('/admin/trigger/telegram', {})
      notify('success', 'Telegram morning digest sent to all channels.')
    } catch (err: any) {
      notify('error', err.message)
    } finally {
      setTelegramLoading(false)
    }
  }

  const inputCls = "w-full bg-[#0f0f0f] border border-[#2a2a2a] rounded-lg px-4 py-2.5 text-sm text-white placeholder:text-[#444] focus:outline-none focus:border-[#00C48C]/50 transition-colors"
  const labelCls = "block text-xs font-bold uppercase tracking-widest text-[#555] mb-2"

  return (
    <div className="min-h-screen bg-[#090909]">
      <Navbar />
      <div className="max-w-5xl mx-auto px-6 pt-28 pb-20">

        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="badge badge-elite">Admin Panel</span>
              <span className="text-xs text-[#444]">Elite Access Only</span>
            </div>
            <h1 className="text-3xl font-black text-white">Antigravity Control Centre</h1>
          </div>
          <Link href="/dashboard" className="btn-outline text-sm py-2">← Dashboard</Link>
        </div>

        {/* Status notification */}
        {status && (
          <div className={`mb-6 p-4 rounded-xl border text-sm font-medium ${
            status.type === 'success'
              ? 'bg-[rgba(0,196,140,0.08)] border-[rgba(0,196,140,0.2)] text-[#00C48C]'
              : status.type === 'error'
              ? 'bg-[rgba(239,68,68,0.08)] border-[rgba(239,68,68,0.2)] text-[#ef4444]'
              : 'bg-[rgba(245,158,11,0.08)] border-[rgba(245,158,11,0.2)] text-[#f59e0b]'
          }`}>
            {status.text}
          </div>
        )}

        {/* Stats overview */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            {[
              { label: 'Digests This Month', value: stats.digests_this_month },
              { label: 'Chart Analyses', value: stats.chart_analyses_this_month },
              { label: 'Sector Reports', value: stats.sector_reports_this_month },
              { label: 'Your Plan', value: stats.plan?.toUpperCase() },
            ].map((s) => (
              <div key={s.label} className="glass-card p-5 text-center">
                <div className="text-2xl font-black text-[#00C48C]">{s.value}</div>
                <div className="text-xs text-[#555] mt-1">{s.label}</div>
              </div>
            ))}
          </div>
        )}

        <div className="grid md:grid-cols-2 gap-6">

          {/* Pipeline Triggers */}
          <div className="glass-card p-6">
            <h2 className="text-sm font-bold uppercase tracking-widest text-[#555] mb-5">Manual Pipeline Triggers</h2>
            <div className="space-y-3">
              <div className="flex items-center justify-between p-4 bg-[#0f0f0f] rounded-xl border border-[#1e1e1e]">
                <div>
                  <p className="text-sm font-semibold text-white">News + AI Pipeline</p>
                  <p className="text-xs text-[#444] mt-0.5">Collect news → Gemini Pro → Save digest</p>
                </div>
                <button
                  onClick={runNewsPipeline}
                  disabled={newsLoading}
                  className="btn-brand text-xs py-2 px-4 shrink-0"
                >
                  {newsLoading ? <Spinner /> : '▶ Run'}
                </button>
              </div>

              <div className="flex items-center justify-between p-4 bg-[#0f0f0f] rounded-xl border border-[#1e1e1e]">
                <div>
                  <p className="text-sm font-semibold text-white">Breakout Scanner</p>
                  <p className="text-xs text-[#444] mt-0.5">Scan Nifty 500 → Save watchlist</p>
                </div>
                <button
                  onClick={runScan}
                  disabled={scanLoading}
                  className="btn-brand text-xs py-2 px-4 shrink-0"
                >
                  {scanLoading ? <Spinner /> : '▶ Run'}
                </button>
              </div>

              <div className="flex items-center justify-between p-4 bg-[#0f0f0f] rounded-xl border border-[#1e1e1e]">
                <div>
                  <p className="text-sm font-semibold text-white">Telegram Digest</p>
                  <p className="text-xs text-[#444] mt-0.5">Publish today's digest to Pro + Elite channels</p>
                </div>
                <button
                  onClick={sendTelegramDigest}
                  disabled={telegramLoading}
                  className="btn-brand text-xs py-2 px-4 shrink-0"
                >
                  {telegramLoading ? <Spinner /> : '📤 Send'}
                </button>
              </div>
            </div>
          </div>

          {/* IPO Analysis Trigger */}
          <div className="glass-card p-6">
            <h2 className="text-sm font-bold uppercase tracking-widest text-[#555] mb-5">Trigger IPO Analysis</h2>
            <form onSubmit={handleIPOSubmit} className="space-y-3">
              <div>
                <label className={labelCls}>Company Name</label>
                <input
                  className={inputCls}
                  placeholder="e.g. Hyundai India"
                  value={ipoForm.company_name}
                  onChange={(e) => setIpoForm({ ...ipoForm, company_name: e.target.value })}
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={labelCls}>Open Date</label>
                  <input type="date" className={inputCls} value={ipoForm.open_date}
                    onChange={(e) => setIpoForm({ ...ipoForm, open_date: e.target.value })} required />
                </div>
                <div>
                  <label className={labelCls}>Close Date</label>
                  <input type="date" className={inputCls} value={ipoForm.close_date}
                    onChange={(e) => setIpoForm({ ...ipoForm, close_date: e.target.value })} required />
                </div>
              </div>
              <div>
                <label className={labelCls}>Price Band</label>
                <input className={inputCls} placeholder="e.g. ₹1,865 - ₹1,960"
                  value={ipoForm.price_band}
                  onChange={(e) => setIpoForm({ ...ipoForm, price_band: e.target.value })} required />
              </div>
              <div>
                <label className={labelCls}>Industry</label>
                <input className={inputCls} placeholder="e.g. Automobiles"
                  value={ipoForm.industry}
                  onChange={(e) => setIpoForm({ ...ipoForm, industry: e.target.value })} required />
              </div>
              <button type="submit" disabled={ipoLoading} className="btn-brand w-full py-2.5 mt-2">
                {ipoLoading ? 'Generating analysis...' : '🚀 Generate IPO Analysis'}
              </button>
            </form>
          </div>

          {/* AI Deep Dive Generator */}
          <div className="glass-card p-6 md:col-span-2">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-8 h-8 rounded-lg bg-[rgba(0,196,140,0.1)] border border-[rgba(0,196,140,0.2)] flex items-center justify-center text-[#00C48C] text-sm">🤖</div>
              <div>
                <h2 className="text-sm font-bold uppercase tracking-widest text-[#555]">AI Deep Dive Generator</h2>
                <p className="text-xs text-[#333] mt-0.5">Gemini 2.0 Flash — fetches live data + generates structured research report</p>
              </div>
            </div>
            <form onSubmit={handleAIGenerate} className="flex gap-3 flex-wrap items-end">
              <div className="flex-1 min-w-48">
                <label className={labelCls}>NSE Symbol</label>
                <input
                  className={inputCls}
                  placeholder="e.g. RELIANCE, TCS, HDFCBANK"
                  value={aiSymbol}
                  onChange={e => setAiSymbol(e.target.value.toUpperCase())}
                  required
                />
              </div>
              <div>
                <label className={labelCls}>Tier</label>
                <select className={inputCls + ' cursor-pointer w-36'} value={aiTier} onChange={e => setAiTier(e.target.value)}>
                  <option value="elite">Elite Only</option>
                  <option value="pro">Pro + Elite</option>
                </select>
              </div>
              <button
                type="submit"
                disabled={aiLoading}
                className="btn-brand py-2.5 px-6 shrink-0"
              >
                {aiLoading ? <span className="flex items-center gap-2"><span className="w-3 h-3 border-2 border-black/30 border-t-black rounded-full animate-spin" />Generating...</span> : '⚡ Generate'}
              </button>
            </form>
            {aiResult && (
              <div className="mt-4 p-4 bg-[rgba(0,196,140,0.05)] border border-[rgba(0,196,140,0.2)] rounded-xl">
                <p className="text-sm text-[#00C48C] font-bold mb-1">✓ Generation started for {aiResult.symbol}</p>
                <p className="text-xs text-[#555] mb-2">{aiResult.message}</p>
                <Link href={`/deepdive/${aiResult.id}`} className="text-xs text-[#00C48C] hover:underline">
                  Preview when ready → /deepdive/{aiResult.id}
                </Link>
              </div>
            )}
          </div>

          {/* Manual Publish Deep Dive */}
          <div className="glass-card p-6 md:col-span-2">
            <h2 className="text-sm font-bold uppercase tracking-widest text-[#555] mb-5">Publish Deep Dive</h2>
            <form onSubmit={handleDiveSubmit} className="space-y-4">
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <label className={labelCls}>Title</label>
                  <input className={inputCls} placeholder="e.g. Banking Sector — Cycle Analysis May 2026"
                    value={diveForm.title}
                    onChange={(e) => setDiveForm({ ...diveForm, title: e.target.value })} required />
                </div>
                <div>
                  <label className={labelCls}>Access Tier</label>
                  <select className={inputCls + ' cursor-pointer'}
                    value={diveForm.tier}
                    onChange={(e) => setDiveForm({ ...diveForm, tier: e.target.value })}>
                    <option value="elite">Elite Only</option>
                    <option value="pro">Pro + Elite</option>
                  </select>
                </div>
              </div>
              <div>
                <label className={labelCls}>Short Summary (preview for Pro users)</label>
                <input className={inputCls} placeholder="2-3 sentence teaser..."
                  value={diveForm.summary}
                  onChange={(e) => setDiveForm({ ...diveForm, summary: e.target.value })} />
              </div>
              <div>
                <label className={labelCls}>Full Content (Markdown supported)</label>
                <textarea
                  className={inputCls + ' resize-none h-48 font-mono text-xs leading-relaxed'}
                  placeholder={'# Banking Sector — Deep Dive\n\n## The Headline\n...\n\n## Key Metrics\n- ROE trend...\n\n---\n*SEBI disclaimer here*'}
                  value={diveForm.content}
                  onChange={(e) => setDiveForm({ ...diveForm, content: e.target.value })}
                  required
                />
              </div>
              <button type="submit" disabled={diveLoading} className="btn-brand py-2.5 px-8">
                {diveLoading ? 'Publishing...' : '📚 Publish Deep Dive'}
              </button>
            </form>
          </div>
            <div className="glass-card p-6 md:col-span-2">
              <div className="flex items-center gap-3 mb-5">
                <div className="w-8 h-8 rounded-lg bg-[rgba(201,163,78,0.1)] border border-[rgba(201,163,78,0.2)] flex items-center justify-center text-sm">📊</div>
                <div>
                  <h2 className="text-sm font-bold uppercase tracking-widest text-[#555]">Upload Stock Signal</h2>
                  <p className="text-xs text-[#333] mt-0.5">Chart image + technical levels — visible to subscribers</p>
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-6">
                {/* Left: image drop zone */}
                <div>
                  <label className={labelCls}>Chart Image (JPEG/PNG/WebP, max 15 MB)</label>
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    className="relative w-full aspect-video rounded-xl border-2 border-dashed border-[#222] hover:border-[rgba(201,163,78,0.4)] transition-colors cursor-pointer overflow-hidden bg-[#0a0a0a] flex items-center justify-center"
                  >
                    {sigPreview ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={sigPreview} alt="preview" className="w-full h-full object-contain" />
                    ) : (
                      <div className="text-center px-4">
                        <p className="text-3xl mb-2">🖼️</p>
                        <p className="text-sm text-[#444]">Click to select chart image</p>
                        <p className="text-xs text-[#333] mt-1">or drag & drop here</p>
                      </div>
                    )}
                  </div>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/gif"
                    className="hidden"
                    onChange={e => {
                      const f = e.target.files?.[0] ?? null
                      setSigImage(f)
                      setSigPreview(f ? URL.createObjectURL(f) : null)
                    }}
                  />
                  {sigPreview && (
                    <button
                      onClick={() => { setSigImage(null); setSigPreview(null); if (fileInputRef.current) fileInputRef.current.value = '' }}
                      className="mt-2 text-xs text-[#555] hover:text-[#ef4444] transition-colors"
                    >✕ Remove image</button>
                  )}
                </div>

                {/* Right: metadata fields */}
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className={labelCls}>NSE Symbol *</label>
                      <input className={inputCls} placeholder="RELIANCE" value={sigForm.symbol}
                        onChange={e => setSigForm({ ...sigForm, symbol: e.target.value.toUpperCase() })} />
                    </div>
                    <div>
                      <label className={labelCls}>Timeframe</label>
                      <select className={inputCls + ' cursor-pointer'} value={sigForm.timeframe}
                        onChange={e => setSigForm({ ...sigForm, timeframe: e.target.value })}>
                        {['1m','5m','15m','30m','1H','4H','Daily','Weekly','Monthly'].map(tf => (
                          <option key={tf} value={tf}>{tf}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className={labelCls}>Title *</label>
                    <input className={inputCls} placeholder="Bullish Cup & Handle breakout above 2850" value={sigForm.title}
                      onChange={e => setSigForm({ ...sigForm, title: e.target.value })} />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className={labelCls}>Signal Type</label>
                      <select className={inputCls + ' cursor-pointer'} value={sigForm.signal_type}
                        onChange={e => setSigForm({ ...sigForm, signal_type: e.target.value })}>
                        <option value="BULLISH">▲ Bullish</option>
                        <option value="BEARISH">▼ Bearish</option>
                        <option value="NEUTRAL">◆ Neutral</option>
                      </select>
                    </div>
                    <div>
                      <label className={labelCls}>Access Plan</label>
                      <select className={inputCls + ' cursor-pointer'} value={sigForm.plan_required}
                        onChange={e => setSigForm({ ...sigForm, plan_required: e.target.value })}>
                        <option value="free">Free (all users)</option>
                        <option value="pro">Pro + Elite</option>
                        <option value="elite">Elite only</option>
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className={labelCls}>Support ₹</label>
                      <input type="number" className={inputCls} placeholder="2750" value={sigForm.support}
                        onChange={e => setSigForm({ ...sigForm, support: e.target.value })} />
                    </div>
                    <div>
                      <label className={labelCls}>Resistance ₹</label>
                      <input type="number" className={inputCls} placeholder="3100" value={sigForm.resistance}
                        onChange={e => setSigForm({ ...sigForm, resistance: e.target.value })} />
                    </div>
                    <div>
                      <label className={labelCls}>Target ₹</label>
                      <input type="number" className={inputCls} placeholder="3400" value={sigForm.target}
                        onChange={e => setSigForm({ ...sigForm, target: e.target.value })} />
                    </div>
                    <div>
                      <label className={labelCls}>Stop Loss ₹</label>
                      <input type="number" className={inputCls} placeholder="2680" value={sigForm.stoploss}
                        onChange={e => setSigForm({ ...sigForm, stoploss: e.target.value })} />
                    </div>
                  </div>

                  <div>
                    <label className={labelCls}>Analysis Notes</label>
                    <textarea
                      className={inputCls + ' resize-none h-24 text-xs leading-relaxed'}
                      placeholder="Describe the setup, key levels, expected move..."
                      value={sigForm.description}
                      onChange={e => setSigForm({ ...sigForm, description: e.target.value })}
                    />
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-4 mt-5 pt-4 border-t border-[#1a1a1a]">
                <button
                  disabled={sigLoading || !sigImage || !sigForm.symbol || !sigForm.title}
                  onClick={async () => {
                    if (!sigImage || !sigForm.symbol || !sigForm.title) return
                    setSigLoading(true)
                    try {
                      const fd = new FormData()
                      fd.append('image', sigImage)
                      Object.entries(sigForm).forEach(([k, v]) => { if (v !== '') fd.append(k, v) })
                      await apiUploadSignal(fd)
                      notify('success', `Signal for ${sigForm.symbol} published!`)
                      setSigForm({ symbol: '', title: '', description: '', timeframe: 'Daily', signal_type: 'BULLISH', support: '', resistance: '', target: '', stoploss: '', plan_required: 'pro' })
                      setSigImage(null); setSigPreview(null)
                      if (fileInputRef.current) fileInputRef.current.value = ''
                      loadSigs()
                    } catch (err: any) {
                      notify('error', err.message || 'Upload failed')
                    } finally {
                      setSigLoading(false)
                    }
                  }}
                  className="btn-brand py-2.5 px-8"
                >
                  {sigLoading ? '⏳ Uploading…' : '📤 Publish Signal'}
                </button>
                <p className="text-xs text-[#444]">Symbol + Title + Image are required</p>
              </div>
            </div>

            {/* Existing signals list */}
            {sigsLoaded && existingSigs.length > 0 && (
              <div className="glass-card p-6 md:col-span-2">
                <h2 className="text-sm font-bold uppercase tracking-widest text-[#555] mb-4">Published Signals ({existingSigs.length})</h2>
                <div className="space-y-2">
                  {existingSigs.map(s => (
                    <div key={s.id} className="flex items-center justify-between p-3 bg-[#0f0f0f] rounded-xl border border-[#1a1a1a]">
                      <div className="flex items-center gap-3">
                        <span className="text-xs font-black text-[#9A9A9E] px-2 py-0.5 bg-[#1a1a1a] rounded">{s.symbol}</span>
                        <span className={`text-xs font-bold ${ s.signal_type === 'BULLISH' ? 'text-[#3DDC84]' : s.signal_type === 'BEARISH' ? 'text-[#E5484D]' : 'text-[#C9A34E]' }`}>
                          {s.signal_type === 'BULLISH' ? '▲' : s.signal_type === 'BEARISH' ? '▼' : '◆'} {s.signal_type}
                        </span>
                        <span className="text-sm text-white truncate max-w-xs">{s.title}</span>
                      </div>
                      <button
                        onClick={async () => {
                          if (!confirm(`Delete signal "${s.title}"?`)) return
                          try {
                            await apiDeleteSignal(s.id)
                            notify('success', 'Signal deleted')
                            loadSigs()
                          } catch (err: any) {
                            notify('error', err.message)
                          }
                        }}
                        className="text-xs text-[#555] hover:text-[#ef4444] transition-colors px-3 py-1.5 border border-[#1e1e1e] rounded-lg hover:border-[rgba(239,68,68,0.3)]"
                      >Delete</button>
                    </div>
                  ))}
                </div>
              </div>
            )}

        </div>
      </div>
    </div>
  )
}

function Spinner() {
  return (
    <span className="flex items-center gap-1.5">
      <span className="w-3 h-3 border-2 border-black/30 border-t-black rounded-full animate-spin" />
      Running...
    </span>
  )
}
