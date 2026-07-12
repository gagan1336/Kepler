'use client'
import { useEffect, useRef } from 'react'

/**
 * EclipseEdge — The Umbra signature motion element.
 *
 * A single sharp line of warm-gold light that sweeps across dark surfaces.
 * Rules: use ≤ 4 times sitewide. Its power is in scarcity.
 *
 * Modes:
 *   'hero'      — sweeps once across the parent on mount (hero headline)
 *   'bar'       — fills a confidence bar from left to right on trigger
 *   'card-edge' — CSS-only border trace via ::after pseudo (just add className)
 *
 * Respects prefers-reduced-motion: falls back to opacity-only or instant.
 */

interface EclipseEdgeProps {
  mode: 'hero' | 'bar'
  /** 0–100 — percentage fill (bar mode only) */
  value?: number
  /** manually trigger the animation (bar mode) */
  trigger?: boolean
  /** delay before animation starts (ms) */
  delay?: number
  className?: string
  barColor?: string
}

export function EclipseEdge({
  mode,
  value = 100,
  trigger = true,
  delay = 0,
  className = '',
  barColor,
}: EclipseEdgeProps) {
  const prefersReduced = typeof window !== 'undefined'
    ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
    : false

  if (mode === 'hero') {
    return (
      <span
        aria-hidden="true"
        className={`eclipse-sweep pointer-events-none ${prefersReduced ? 'opacity-0' : ''} ${className}`}
        style={{ animationDelay: `${delay}ms` }}
      />
    )
  }

  // Bar mode — renders a filled bar with the Eclipse Edge sweep
  return (
    <BarFill
      value={value}
      trigger={trigger}
      delay={delay}
      className={className}
      barColor={barColor}
      prefersReduced={prefersReduced}
    />
  )
}

function BarFill({
  value,
  trigger,
  delay,
  className,
  barColor,
  prefersReduced,
}: {
  value: number
  trigger: boolean
  delay: number
  className?: string
  barColor?: string
  prefersReduced: boolean
}) {
  const fillRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!trigger || !fillRef.current) return
    const el = fillRef.current
    const timeout = setTimeout(() => {
      el.style.width = `${Math.max(0, Math.min(100, value))}%`
    }, delay)
    return () => clearTimeout(timeout)
  }, [trigger, value, delay])

  const color = barColor || 'linear-gradient(90deg, #A8822E, #C9A34E, #DDB96A)'

  return (
    <div
      className={`confidence-bar-track ${className}`}
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        ref={fillRef}
        className={`confidence-bar-fill confidence-fill-eclipse ${prefersReduced ? '' : ''}`}
        style={{
          width: prefersReduced ? `${value}%` : '0%',
          background: color,
          transition: prefersReduced
            ? 'none'
            : `width ${1.0 + delay / 1000}s cubic-bezier(0.16, 1, 0.3, 1) ${delay}ms`,
        }}
      />
    </div>
  )
}

/**
 * useEclipseInView — hook that triggers the eclipse animation when
 * the target element enters the viewport. Use with bar mode.
 */
export function useEclipseInView(threshold = 0.3) {
  const ref = useRef<HTMLDivElement>(null)
  const triggered = useRef(false)
  const triggerState = useRef(false)
  const [, forceUpdate] = require('react').useReducer((x: number) => x + 1, 0)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !triggered.current) {
          triggered.current = true
          triggerState.current = true
          forceUpdate()
        }
      },
      { threshold }
    )

    observer.observe(el)
    return () => observer.disconnect()
  }, [threshold])

  return { ref, triggered: triggerState.current }
}

export default EclipseEdge
