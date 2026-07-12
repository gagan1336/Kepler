import { SectorReport as SectorReportType } from '@/lib/api'

interface SectorReportProps {
  report: SectorReportType
  compact?: boolean
}

export default function SectorReport({ report, compact = false }: SectorReportProps) {
  const lines = report.content?.split('\n') || []

  // Format content with basic markdown support
  const formatLine = (line: string, idx: number) => {
    const trimmed = line.trim()
    if (!trimmed) return <div key={idx} className="h-3" />

    if (trimmed.startsWith('**') && trimmed.endsWith('**')) {
      return <h3 key={idx} className="text-white font-bold text-base mt-5 mb-2">{trimmed.slice(2, -2)}</h3>
    }
    if (trimmed.startsWith('# ')) {
      return <h2 key={idx} className="text-white font-black text-xl mt-6 mb-3">{trimmed.slice(2)}</h2>
    }
    if (trimmed.startsWith('## ')) {
      return <h3 key={idx} className="text-white font-bold text-lg mt-5 mb-2">{trimmed.slice(3)}</h3>
    }
    if (trimmed.startsWith('---')) {
      return <hr key={idx} className="border-[#1e1e1e] my-5" />
    }
    if (trimmed.startsWith('*') && trimmed.endsWith('*')) {
      return <p key={idx} className="text-xs text-[#444] italic mt-4 leading-relaxed">{trimmed.slice(1, -1)}</p>
    }

    // Bold inline
    const formatted = trimmed.replace(/\*\*(.*?)\*\*/g, '<strong class="text-white font-semibold">$1</strong>')
    return (
      <p
        key={idx}
        className="text-[#888] text-sm leading-relaxed mb-2"
        dangerouslySetInnerHTML={{ __html: formatted }}
      />
    )
  }

  return (
    <div className="glass-card p-6 md:p-8">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-6 pb-6 border-b border-[#1e1e1e]">
        <div>
          <div className="section-tag mb-2">Sector Spotlight</div>
          <h2 className="text-xl font-bold text-white">{report.sector_name}</h2>
          <p className="text-xs text-[#555] mt-1">
            {new Date(report.date).toLocaleDateString('en-IN', {
              weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
            })}
          </p>
        </div>
        <div className="shrink-0">
          <span className="badge badge-sector">🏭 Sector</span>
        </div>
      </div>

      {/* Content */}
      <div className={`prose-dark ${compact ? 'line-clamp-[12]' : ''}`}>
        {lines.map((line, idx) => formatLine(line, idx))}
      </div>

      {compact && (
        <div className="mt-4 pt-4 border-t border-[#1e1e1e]">
          <a href="/dashboard" className="text-sm text-[#00C48C] font-medium hover:underline">
            Read full report →
          </a>
        </div>
      )}
    </div>
  )
}
