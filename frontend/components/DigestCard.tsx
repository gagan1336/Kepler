import { DigestItem } from '@/lib/api'

type Category = 'MACRO' | 'SECTOR' | 'STOCK' | 'RESULT' | 'GLOBAL' | 'POLICY' | 'GST' | 'RBI_SEBI' | string

const CATEGORY_COLORS: Record<string, string> = {
  MACRO:    'bg-[rgba(96,165,250,0.1)] text-[#60a5fa] border-[rgba(96,165,250,0.2)]',
  SECTOR:   'bg-[rgba(129,140,248,0.1)] text-[#818CF8] border-[rgba(129,140,248,0.2)]',
  STOCK:    'bg-[rgba(99,102,241,0.1)] text-[#6366F1] border-[rgba(99,102,241,0.2)]',
  RESULT:   'bg-[rgba(16,185,129,0.1)] text-[#10B981] border-[rgba(16,185,129,0.2)]',
  GLOBAL:   'bg-[rgba(251,191,36,0.1)] text-[#fbbf24] border-[rgba(251,191,36,0.2)]',
  POLICY:   'bg-[rgba(248,113,113,0.1)] text-[#f87171] border-[rgba(248,113,113,0.2)]',
  GST:      'bg-[rgba(245,158,11,0.1)] text-[#f59e0b] border-[rgba(245,158,11,0.2)]',
  RBI_SEBI: 'bg-[rgba(129,140,248,0.1)] text-[#818CF8] border-[rgba(129,140,248,0.2)]',
}

const CATEGORY_LABEL: Record<string, string> = {
  MACRO:    'Macro',
  SECTOR:   'Sector',
  STOCK:    'Stock',
  RESULT:   'Result',
  GLOBAL:   'Global',
  POLICY:   'Policy',
  GST:      'GST',
  RBI_SEBI: 'RBI/SEBI',
}

const SENTIMENT_CONFIG = {
  BULLISH: { label: 'Bullish', color: 'text-[#10B981]', dot: 'bg-[#10B981]' },
  BEARISH: { label: 'Bearish', color: 'text-[#ef4444]', dot: 'bg-[#ef4444]' },
  NEUTRAL: { label: 'Neutral', color: 'text-[#f59e0b]', dot: 'bg-[#f59e0b]' },
}

const TIME_SENSITIVITY: Record<string, { label: string; color: string }> = {
  TODAY:       { label: 'Act Today',    color: 'text-[#ef4444]' },
  SHORT_TERM:  { label: 'Short Term',  color: 'text-[#f59e0b]' },
  MEDIUM_TERM: { label: 'Medium Term', color: 'text-[#60a5fa]' },
  LONG_TERM:   { label: 'Long Term',   color: 'text-[#9ca3af]' },
}

interface DigestCardProps {
  item: DigestItem & {
    catalyst_type?: string
    time_sensitivity?: string
    importance_score?: number
    category?: Category
  }
  index: number
  blurred?: boolean
}

export default function DigestCard({ item, index, blurred = false }: DigestCardProps) {
  const sentiment = SENTIMENT_CONFIG[(item.sentiment as keyof typeof SENTIMENT_CONFIG)] || SENTIMENT_CONFIG.NEUTRAL
  const catKey = item.category as string
  const catColor = CATEGORY_COLORS[catKey] || 'bg-[rgba(255,255,255,0.05)] text-[#8A9BB0] border-[rgba(255,255,255,0.08)]'
  const catLabel = CATEGORY_LABEL[catKey] || catKey
  const timeSens = item.time_sensitivity ? TIME_SENSITIVITY[item.time_sensitivity] : null
  const score = item.importance_score || 0

  return (
    <div
      className={`glass-card p-5 md:p-6 transition-all duration-300 ${
        blurred ? 'blur-overlay select-none' : 'hover:border-[rgba(99,102,241,0.25)]'
      }`}
    >
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          {/* Category badge */}
          <span className={`inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full border font-semibold ${catColor}`}>
            {catLabel}
          </span>

          {/* Sentiment */}
          <div className="flex items-center gap-1.5">
            <div className={`w-1.5 h-1.5 rounded-full ${sentiment.dot}`} />
            <span className={`text-xs font-medium ${sentiment.color}`}>{sentiment.label}</span>
          </div>

          {/* Time sensitivity */}
          {timeSens && (
            <span className={`text-xs font-medium ${timeSens.color}`}>
              {timeSens.label}
            </span>
          )}
        </div>

        {/* Importance score */}
        {score >= 7 && (
          <div className="flex items-center gap-1 shrink-0">
            <div
              className={`text-xs font-black px-2 py-0.5 rounded font-mono ${
                score >= 9
                  ? 'bg-[rgba(239,68,68,0.12)] text-[#ef4444]'
                  : score >= 8
                  ? 'bg-[rgba(245,158,11,0.12)] text-[#f59e0b]'
                  : 'bg-[rgba(99,102,241,0.1)] text-[#818CF8]'
              }`}
            >
              {score}/10
            </div>
          </div>
        )}
      </div>

      <h3 className="text-sm font-semibold text-white mb-2 leading-snug">
        {item.title}
      </h3>

      <p className="text-sm text-[#8A9BB0] leading-relaxed mb-4">
        {item.summary}
      </p>

      {/* Affected sectors */}
      {item.affected_sectors?.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {item.affected_sectors.slice(0, 4).map((sector) => (
            <span
              key={sector}
              className="text-xs px-2 py-0.5 rounded-full bg-[rgba(255,255,255,0.04)] text-[#4A5568] border border-[rgba(255,255,255,0.06)]"
            >
              {sector}
            </span>
          ))}
        </div>
      )}

      {/* Affected stocks */}
      {item.affected_stocks?.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {item.affected_stocks.slice(0, 5).map((stock) => (
            <span
              key={stock}
              className="text-xs px-2 py-0.5 rounded bg-[rgba(99,102,241,0.07)] text-[#818CF8] border border-[rgba(99,102,241,0.15)] font-mono font-medium"
            >
              {stock}
            </span>
          ))}
        </div>
      )}

      {/* Source link */}
      {item.source_url && !blurred && (
        <div className="mt-4 pt-3 border-t border-[rgba(255,255,255,0.05)]">
          <a
            href={item.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-[#3D4F63] hover:text-[#818CF8] transition-colors"
          >
            Read source →
          </a>
        </div>
      )}
    </div>
  )
}
