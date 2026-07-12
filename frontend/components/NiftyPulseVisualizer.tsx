'use client'
import { useRef, useEffect, useState } from 'react'
import { motion, useMotionValue, useTransform, useSpring } from 'framer-motion'

// Representative Nifty 500 candlestick data — 40 candles
// Format: [open, high, low, close] — normalized to 0-100 range
const CANDLES = [
  [42, 45, 40, 44], [44, 46, 43, 45], [45, 47, 44, 43], [43, 44, 41, 42],
  [42, 43, 39, 40], [40, 42, 38, 41], [41, 44, 40, 43], [43, 45, 42, 44],
  [44, 46, 43, 45], [45, 47, 44, 46], [46, 48, 45, 47], [47, 50, 46, 49],
  [49, 51, 47, 48], [48, 49, 46, 47], [47, 48, 45, 46], [46, 47, 44, 45],
  [45, 47, 44, 46], [46, 48, 45, 47], [47, 50, 46, 49], [49, 51, 48, 50],
  [50, 53, 49, 52], [52, 54, 50, 51], [51, 52, 49, 50], [50, 51, 48, 49],
  [49, 51, 48, 50], [50, 52, 49, 51], [51, 54, 50, 53], [53, 56, 52, 55],
  [55, 58, 54, 57], [57, 59, 55, 56], [56, 57, 54, 55], [55, 58, 54, 57],
  [57, 61, 56, 60], [60, 64, 59, 63], [63, 67, 62, 66], [66, 70, 65, 69],
  [69, 73, 68, 72], [72, 76, 71, 75], [75, 79, 74, 78], [78, 82, 77, 81],
]

// The "breakout" candle index
const BREAKOUT_IDX = 33

interface NiftyPulseVisualizerProps {
  mouseX?: number
  mouseY?: number
}

export default function NiftyPulseVisualizer({ mouseX = 0, mouseY = 0 }: NiftyPulseVisualizerProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [revealProgress, setRevealProgress] = useState(0)
  const [breakoutGlow, setBreakoutGlow] = useState(0)
  const springX = useSpring(mouseX * 12, { stiffness: 80, damping: 20 })
  const springY = useSpring(mouseY * 8, { stiffness: 80, damping: 20 })

  // Stagger candle reveal on mount
  useEffect(() => {
    let frame = 0
    const total = CANDLES.length
    const interval = setInterval(() => {
      frame++
      setRevealProgress(Math.min(frame / total, 1))
      if (frame >= total) clearInterval(interval)
    }, 40)
    return () => clearInterval(interval)
  }, [])

  // Breathing breakout glow
  useEffect(() => {
    let t = 0
    const anim = setInterval(() => {
      t += 0.04
      setBreakoutGlow(Math.sin(t) * 0.5 + 0.5)
    }, 30)
    return () => clearInterval(anim)
  }, [])

  const W = 340
  const H = 200
  const PAD = { left: 10, right: 10, top: 12, bottom: 12 }
  const chartW = W - PAD.left - PAD.right
  const chartH = H - PAD.top - PAD.bottom
  const n = CANDLES.length
  const candleW = chartW / n
  const bodyW = Math.max(3, candleW * 0.55)

  // Map value (0–100) to SVG y coordinate
  const toY = (v: number) => PAD.top + chartH - (v / 100) * chartH
  const toX = (i: number) => PAD.left + i * candleW + candleW / 2

  // Build the closing-price line path
  const linePath = CANDLES.slice(0, Math.ceil(revealProgress * n))
    .map((c, i) => `${i === 0 ? 'M' : 'L'} ${toX(i)} ${toY(c[3])}`)
    .join(' ')

  const visibleCount = Math.ceil(revealProgress * n)

  const confidenceScore = 87

  return (
    <motion.div
      style={{ x: springX, y: springY }}
      className="relative select-none"
    >
      {/* Outer glow container */}
      <div className="relative rounded-2xl overflow-hidden"
        style={{
          background: 'linear-gradient(135deg, rgba(17,24,32,0.95) 0%, rgba(11,16,22,0.98) 100%)',
          border: '1px solid rgba(99,102,241,0.2)',
          boxShadow: '0 0 60px rgba(99,102,241,0.08), 0 24px 60px rgba(0,0,0,0.5)',
        }}
      >
        {/* Top accent line */}
        <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[#6366F1] to-transparent opacity-60" />

        {/* Header bar */}
        <div className="flex items-center justify-between px-4 pt-3.5 pb-2">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-[#10B981] animate-pulse" />
            <span className="text-[10px] font-bold text-[#7A8FA6] tracking-[0.18em] uppercase font-mono">
              NIFTY 500 · BREAKOUT SCANNER
            </span>
          </div>
          <span className="text-[10px] font-mono text-[#3D4F63]">
            {new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}
          </span>
        </div>

        {/* Scan line overlay */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none" style={{ zIndex: 5 }}>
          <div className="scan-line" style={{ height: '100%' }} />
        </div>

        {/* SVG Chart */}
        <div className="px-3 pb-3">
          <svg ref={svgRef} width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="overflow-visible" style={{ maxWidth: '100%' }}>
            <defs>
              {/* Grid */}
              <pattern id="chartGrid" width="34" height="40" patternUnits="userSpaceOnUse">
                <path d="M 34 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="0.5" />
              </pattern>
              {/* Breakout glow */}
              <filter id="breakoutGlow" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur in="SourceGraphic" stdDeviation="4" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
              {/* Line gradient */}
              <linearGradient id="lineGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#3D4F63" stopOpacity="0.4" />
                <stop offset="70%" stopColor="#6366F1" stopOpacity="0.8" />
                <stop offset="100%" stopColor="#818CF8" stopOpacity="1" />
              </linearGradient>
              {/* Area gradient */}
              <linearGradient id="areaGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#6366F1" stopOpacity="0.12" />
                <stop offset="100%" stopColor="#6366F1" stopOpacity="0" />
              </linearGradient>
            </defs>

            {/* Background grid */}
            <rect x={PAD.left} y={PAD.top} width={chartW} height={chartH} fill="url(#chartGrid)" />

            {/* Horizontal reference lines */}
            {[25, 50, 75].map(v => (
              <line
                key={v}
                x1={PAD.left} y1={toY(v)}
                x2={PAD.left + chartW} y2={toY(v)}
                stroke="rgba(255,255,255,0.04)"
                strokeWidth="0.5"
                strokeDasharray="4,4"
              />
            ))}

            {/* Area fill under trend line */}
            {visibleCount > 1 && (
              <motion.path
                d={`${linePath} L ${toX(visibleCount - 1)} ${toY(0)} L ${toX(0)} ${toY(0)} Z`}
                fill="url(#areaGrad)"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.5 }}
              />
            )}

            {/* Candlesticks */}
            {CANDLES.slice(0, visibleCount).map((c, i) => {
              const [o, h, l, cl] = c
              const x = toX(i)
              const isBreakout = i === BREAKOUT_IDX
              const isUp = cl >= o
              const color = isBreakout ? '#818CF8' : isUp ? '#10B981' : '#EF4444'
              const bodyTop = toY(Math.max(o, cl))
              const bodyBot = toY(Math.min(o, cl))
              const bodyHeight = Math.max(1.5, bodyBot - bodyTop)

              return (
                <g key={i} filter={isBreakout ? 'url(#breakoutGlow)' : undefined}>
                  {/* Wick */}
                  <line
                    x1={x} y1={toY(h)}
                    x2={x} y2={toY(l)}
                    stroke={color}
                    strokeWidth={isBreakout ? 1.5 : 0.8}
                    opacity={isBreakout ? 0.9 : 0.6}
                  />
                  {/* Body */}
                  <rect
                    x={x - bodyW / 2}
                    y={bodyTop}
                    width={bodyW}
                    height={bodyHeight}
                    rx="1"
                    fill={isBreakout ? `rgba(129,140,248,${0.7 + breakoutGlow * 0.3})` : color}
                    fillOpacity={isBreakout ? 1 : 0.75}
                    stroke={isBreakout ? '#818CF8' : 'none'}
                    strokeWidth={isBreakout ? 0.5 : 0}
                  />
                  {/* Breakout annotation */}
                  {isBreakout && (
                    <>
                      {/* Glow circle */}
                      <circle
                        cx={x}
                        cy={toY(h) - 8}
                        r={3 + breakoutGlow * 2}
                        fill="rgba(129,140,248,0.3)"
                      />
                      <circle
                        cx={x}
                        cy={toY(h) - 8}
                        r={1.5}
                        fill="#818CF8"
                      />
                      {/* Label */}
                      <text
                        x={x + 6}
                        y={toY(h) - 5}
                        fontSize="7"
                        fill="#818CF8"
                        fontFamily="JetBrains Mono, monospace"
                        fontWeight="600"
                      >
                        BREAKOUT
                      </text>
                    </>
                  )}
                </g>
              )
            })}

            {/* Trend line */}
            {visibleCount > 1 && (
              <motion.path
                d={linePath}
                fill="none"
                stroke="url(#lineGrad)"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 1.2, ease: 'easeOut' }}
              />
            )}

            {/* Current price label */}
            {visibleCount > 0 && (() => {
              const lastC = CANDLES[visibleCount - 1]
              const ly = toY(lastC[3])
              return (
                <g>
                  <line
                    x1={PAD.left}
                    y1={ly}
                    x2={PAD.left + chartW}
                    y2={ly}
                    stroke="rgba(129,140,248,0.3)"
                    strokeWidth="0.5"
                    strokeDasharray="3,3"
                  />
                  <rect x={PAD.left + chartW - 2} y={ly - 7} width={32} height={14} rx="3" fill="rgba(99,102,241,0.85)" />
                  <text
                    x={PAD.left + chartW + 14}
                    y={ly + 3.5}
                    fontSize="7"
                    fill="#fff"
                    fontFamily="JetBrains Mono, monospace"
                    fontWeight="600"
                    textAnchor="middle"
                  >
                    24.8K
                  </text>
                </g>
              )
            })()}
          </svg>
        </div>

        {/* Bottom stats row */}
        <div className="border-t border-[rgba(255,255,255,0.05)] mx-3 mb-3 pt-3 grid grid-cols-3 gap-2">
          {[
            { label: 'Confidence', value: `${confidenceScore}%`, accent: '#6366F1' },
            { label: '52W High', value: '24,853', accent: '#10B981' },
            { label: 'Vol Surge', value: '2.4×', accent: '#F59E0B' },
          ].map((stat) => (
            <div key={stat.label} className="text-center">
              <div
                className="text-xs font-bold font-mono"
                style={{ color: stat.accent }}
              >
                {stat.value}
              </div>
              <div className="text-[9px] text-[#3D4F63] mt-0.5 tracking-wide">{stat.label}</div>
            </div>
          ))}
        </div>

        {/* Confidence bar */}
        <div className="mx-3 mb-3">
          <div className="confidence-bar-track">
            <motion.div
              className="confidence-bar-fill"
              initial={{ scaleX: 0 }}
              animate={{ scaleX: confidenceScore / 100 }}
              transition={{ duration: 1.2, delay: 0.8, type: 'spring', stiffness: 60, damping: 15 }}
            />
          </div>
        </div>

        {/* Floating badge: 3 setups today */}
        <div className="absolute -top-3 -right-3">
          <motion.div
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 1.4, type: 'spring', stiffness: 200, damping: 15 }}
            className="px-2.5 py-1 rounded-full text-[10px] font-bold font-mono text-white"
            style={{ background: 'linear-gradient(135deg, #6366F1, #818CF8)', boxShadow: '0 4px 16px rgba(99,102,241,0.5)' }}
          >
            3 setups today
          </motion.div>
        </div>
      </div>
    </motion.div>
  )
}
