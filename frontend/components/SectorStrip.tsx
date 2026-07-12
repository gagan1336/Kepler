'use client'
import { useEffect, useRef } from 'react'
import useEmblaCarousel from 'embla-carousel-react'
import Autoplay from 'embla-carousel-autoplay'
import { motion, AnimatePresence } from 'framer-motion'

interface Sector {
  name: string
  code: string
  change: number
  sparkline: number[] // 7 data points
}

const SECTORS: Sector[] = [
  { name: 'IT', code: 'IT', change: +1.24, sparkline: [45, 47, 44, 49, 52, 50, 55] },
  { name: 'Banking', code: 'BANK', change: -0.83, sparkline: [60, 58, 62, 57, 55, 58, 54] },
  { name: 'FMCG', code: 'FMCG', change: +0.41, sparkline: [38, 40, 39, 41, 40, 42, 43] },
  { name: 'Auto', code: 'AUTO', change: +2.17, sparkline: [42, 44, 43, 46, 48, 50, 53] },
  { name: 'Pharma', code: 'PHARMA', change: -0.34, sparkline: [55, 53, 56, 54, 52, 55, 53] },
  { name: 'Metal', code: 'METAL', change: +1.89, sparkline: [30, 33, 31, 35, 36, 38, 40] },
  { name: 'Energy', code: 'ENERGY', change: -1.12, sparkline: [65, 63, 60, 62, 59, 61, 58] },
  { name: 'Realty', code: 'REALTY', change: +3.44, sparkline: [25, 27, 29, 28, 32, 35, 38] },
  { name: 'Media', code: 'MEDIA', change: -0.67, sparkline: [48, 46, 49, 47, 45, 47, 44] },
  { name: 'Infra', code: 'INFRA', change: +0.92, sparkline: [50, 52, 51, 53, 54, 55, 57] },
]

function Sparkline({ data, positive }: { data: number[]; positive: boolean }) {
  const W = 48
  const H = 22
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const step = W / (data.length - 1)

  const points = data
    .map((v, i) => `${i * step},${H - ((v - min) / range) * H}`)
    .join(' ')

  const color = positive ? '#3DDC84' : '#E5484D'
  const gradId = `spark-${positive ? 'g' : 'r'}-${data[0]}`

  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="overflow-visible">
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline
        points={points + ` ${W},${H} 0,${H}`}
        fill={`url(#${gradId})`}
        stroke="none"
      />
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function SectorCard({ sector }: { sector: Sector }) {
  const isPos = sector.change >= 0
  const color = isPos ? '#10B981' : '#EF4444'
  const sign = isPos ? '+' : ''

  return (
    <motion.div
      whileHover={{ y: -4, transition: { type: 'spring', stiffness: 300, damping: 20 } }}
      className="embla__slide px-1.5"
      style={{ flex: '0 0 140px' }}
    >
      <div
        className="rounded-xl px-4 py-3.5 cursor-pointer select-none h-full"
        style={{
          background: 'rgba(19,19,21,0.9)',
          border: `1px solid rgba(255,255,255,0.07)`,
          backdropFilter: 'blur(8px)',
          transition: 'border-color 0.2s, box-shadow 0.2s',
        }}
        onMouseEnter={e => {
          const el = e.currentTarget as HTMLDivElement
          el.style.borderColor = 'rgba(201,163,78,0.28)'
          el.style.boxShadow = '0 4px 20px rgba(201,163,78,0.12)'
        }}
        onMouseLeave={e => {
          const el = e.currentTarget as HTMLDivElement
          el.style.borderColor = 'rgba(255,255,255,0.07)'
          el.style.boxShadow = 'none'
        }}
      >
        <div className="flex items-start justify-between mb-2">
          <div>
            <div className="text-[9px] font-bold tracking-[0.15em] text-[#5C5C60] mb-0.5 font-mono">
              {sector.code}
            </div>
            <div className="text-xs font-semibold text-[#F2F2F0] leading-none">
              {sector.name}
            </div>
          </div>
          <div
            className="text-xs font-bold font-mono"
            style={{ color }}
          >
            {sign}{sector.change.toFixed(2)}%
          </div>
        </div>
        <Sparkline data={sector.sparkline} positive={isPos} />
      </div>
    </motion.div>
  )
}

export default function SectorStrip() {
  const autoplay = useRef(Autoplay({ delay: 2200, stopOnInteraction: false, stopOnMouseEnter: true }))
  const [emblaRef] = useEmblaCarousel(
    { loop: true, dragFree: true, align: 'start', skipSnaps: true },
    [autoplay.current]
  )

  return (
    <div className="relative py-4 overflow-hidden" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
      {/* Left fade */}
      <div className="absolute left-0 top-0 bottom-0 w-16 z-10 pointer-events-none"
        style={{ background: 'linear-gradient(to right, #0A0A0B, transparent)' }}
      />
      {/* Right fade */}
      <div className="absolute right-0 top-0 bottom-0 w-16 z-10 pointer-events-none"
        style={{ background: 'linear-gradient(to left, #0A0A0B, transparent)' }}
      />

      {/* Label */}
      <div className="absolute top-1/2 -translate-y-1/2 left-4 z-20 hidden md:flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-[#3DDC84] animate-pulse" />
        <span className="text-[9px] font-bold tracking-[0.2em] text-[#5C5C60] uppercase font-mono">Sectors</span>
      </div>

      <div className="embla pl-20" ref={emblaRef}>
        <div className="embla__container">
          {/* Double the array for seamless loop feel */}
          {[...SECTORS, ...SECTORS].map((sector, i) => (
            <SectorCard key={`${sector.code}-${i}`} sector={sector} />
          ))}
        </div>
      </div>
    </div>
  )
}
