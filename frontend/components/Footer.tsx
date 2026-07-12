import Link from 'next/link'

/**
 * Umbra Footer — minimal.
 * Legal, contact, social. The brand's confidence is in what it leaves out.
 * No newsletter popup. No chat bubble.
 */
export default function Footer() {
  return (
    <footer
      className="pt-12 pb-8"
      style={{ borderTop: '1px solid rgba(255,255,255,0.06)', background: 'var(--bg-elevated)' }}
    >
      <div className="max-w-7xl mx-auto px-6">

        {/* ── Top row ─────────────────────────────────────────────────────── */}
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-10 mb-10">

          {/* Brand */}
          <div className="md:max-w-xs">
            <Link href="/" className="flex items-center gap-2.5 mb-4 w-fit group">
              {/* Eclipse mark */}
              <div className="relative w-6 h-6 shrink-0">
                <div
                  className="absolute inset-0 rounded-full opacity-25 blur-sm transition-opacity duration-300 group-hover:opacity-50"
                  style={{ background: 'radial-gradient(circle, #C9A34E 0%, transparent 70%)' }}
                />
                <div
                  className="w-6 h-6 rounded-full flex items-center justify-center relative"
                  style={{
                    background: 'radial-gradient(circle at 35% 35%, #DDB96A 0%, #C9A34E 45%, #0A0A0B 100%)',
                    boxShadow: '0 0 0 1px rgba(201,163,78,0.25)',
                  }}
                >
                  <div className="w-2 h-2 rounded-full" style={{ background: '#0A0A0B' }} />
                </div>
              </div>
              <span className="text-[15px] font-bold text-[#F2F2F0] tracking-tight">Umbra</span>
            </Link>
            <p className="text-sm text-[#5C5C60] leading-relaxed">
              Market intelligence for serious Indian traders.
              No tips. No noise.
            </p>
          </div>

          {/* Links */}
          <div className="flex gap-16">
            <div>
              <h4 className="text-[9px] font-bold tracking-[0.2em] uppercase text-[#5C5C60] mb-4 font-mono">Platform</h4>
              <div className="flex flex-col gap-2.5">
                <FooterLink href="/request-access">Request Access</FooterLink>
                <FooterLink href="/dashboard">Dashboard</FooterLink>
                <FooterLink href="/pricing">Pricing</FooterLink>
              </div>
            </div>
            <div>
              <h4 className="text-[9px] font-bold tracking-[0.2em] uppercase text-[#5C5C60] mb-4 font-mono">Legal</h4>
              <div className="flex flex-col gap-2.5">
                <FooterLink href="/privacy">Privacy</FooterLink>
                <FooterLink href="/terms">Terms</FooterLink>
                <FooterLink href="/disclaimer">Disclaimer</FooterLink>
              </div>
            </div>
          </div>
        </div>

        {/* ── Disclaimer ─────────────────────────────────────────────────── */}
        <div
          className="rounded-xl p-4 mb-8"
          style={{
            background: 'rgba(255,255,255,0.015)',
            border: '1px solid rgba(255,255,255,0.05)',
          }}
        >
          <p className="text-[11px] text-[#5C5C60] leading-relaxed font-mono">
            <span className="text-[#9A9A9E] font-semibold">DISCLAIMER: </span>
            Umbra provides market analysis and educational content only. We are not SEBI registered
            investment advisers. This is not investment advice. Past analysis does not guarantee future
            results. Please consult a SEBI registered adviser before making investment decisions.
          </p>
        </div>

        {/* ── Bottom bar ─────────────────────────────────────────────────── */}
        <div
          className="flex flex-col md:flex-row justify-between items-center gap-3 pt-5"
          style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}
        >
          <p className="text-xs text-[#5C5C60] font-mono">
            © {new Date().getFullYear()} Umbra. All rights reserved.
          </p>
          <div className="flex items-center gap-4">
            <Link
              href="mailto:hello@umbra.in"
              className="text-xs text-[#5C5C60] hover:text-[#9A9A9E] transition-colors font-mono"
            >
              hello@umbra.in
            </Link>
            <span className="text-xs text-[#5C5C60] font-mono">Built for Indian traders 🇮🇳</span>
          </div>
        </div>
      </div>
    </footer>
  )
}

function FooterLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="text-sm text-[#5C5C60] hover:text-[#C9A34E] transition-colors duration-200 w-fit"
    >
      {children}
    </Link>
  )
}
