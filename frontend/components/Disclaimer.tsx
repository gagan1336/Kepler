export default function Disclaimer({ compact = false }: { compact?: boolean }) {
  if (compact) {
    return (
      <p className="text-xs text-[#5C5C60] leading-relaxed font-mono">
        For educational and informational purposes only. Not SEBI registered investment advisers.
        Not investment advice. Please do your own research.
      </p>
    )
  }

  return (
    <div
      className="rounded-xl p-5 md:p-6"
      style={{ border: '1px solid rgba(255,255,255,0.06)', background: 'rgba(255,255,255,0.015)' }}
    >
      <div className="flex items-start gap-3">
        <div className="shrink-0 mt-0.5">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="7" stroke="rgba(255,255,255,0.18)" strokeWidth="1.5" />
            <path d="M8 5v4M8 11v.5" stroke="rgba(255,255,255,0.18)" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </div>
        <p className="text-xs text-[#5C5C60] leading-relaxed font-mono">
          <span className="text-[#9A9A9E] font-semibold">Important Disclaimer: </span>
          Umbra provides market analysis and educational content only. We are not SEBI registered
          investment advisers. Nothing on this platform is investment advice. Past analysis accuracy
          does not guarantee future results. Please consult a SEBI registered investment adviser
          before making any investment decisions. All content is for educational and informational
          purposes only.
        </p>
      </div>
    </div>
  )
}
