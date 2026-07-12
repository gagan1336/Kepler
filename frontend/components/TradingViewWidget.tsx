'use client'
import { useEffect, useRef } from 'react'

// ── TickerTape ──────────────────────────────────────────────────────────
export function TickerTape() {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    container.innerHTML = ''

    const wrapper = document.createElement('div')
    wrapper.className = 'tradingview-widget-container'
    wrapper.style.width = '100%'
    wrapper.style.height = '46px'

    const widgetDiv = document.createElement('div')
    widgetDiv.className = 'tradingview-widget-container__widget'
    wrapper.appendChild(widgetDiv)

    const script = document.createElement('script')
    script.type = 'text/javascript'
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js'
    script.async = true
    script.innerHTML = JSON.stringify({
      symbols: [
        { proName: 'BSE:SENSEX',    title: 'Sensex' },
        { proName: 'NSE:NIFTY',     title: 'Nifty 50' },
        { proName: 'NSE:BANKNIFTY', title: 'Bank Nifty' },
        { proName: 'NSE:RELIANCE',  title: 'Reliance' },
        { proName: 'NSE:TCS',       title: 'TCS' },
        { proName: 'NSE:HDFCBANK',  title: 'HDFC Bank' },
        { proName: 'NSE:INFY',      title: 'Infosys' },
        { proName: 'NSE:ICICIBANK', title: 'ICICI Bank' },
        { proName: 'FX_IDC:USDINR', title: 'USD/INR' },
        { proName: 'TVC:GOLD',      title: 'Gold' },
      ],
      showSymbolLogo: true,
      colorTheme: 'dark',
      isTransparent: true,
      displayMode: 'adaptive',
      locale: 'en',
    })

    wrapper.appendChild(script)
    container.appendChild(wrapper)

    return () => {
      container.innerHTML = ''
    }
  }, [])

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height: '46px' }}
    />
  )
}

// ── AdvancedChart ─────────────────────────────────────────────────────────────
interface AdvancedChartProps {
  symbol: string
  height?: number
}

export function AdvancedChart({ symbol, height = 500 }: AdvancedChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    container.innerHTML = ''

    const wrapper = document.createElement('div')
    wrapper.className = 'tradingview-widget-container'
    wrapper.style.width = '100%'
    wrapper.style.height = '100%'

    const widgetDiv = document.createElement('div')
    widgetDiv.className = 'tradingview-widget-container__widget'
    widgetDiv.style.height = 'calc(100% - 32px)'
    widgetDiv.style.width = '100%'
    wrapper.appendChild(widgetDiv)

    const script = document.createElement('script')
    script.type = 'text/javascript'
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js'
    script.async = true
    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol: `NSE:${symbol}`,
      interval: 'D',
      timezone: 'Asia/Kolkata',
      theme: 'dark',
      style: '1',
      locale: 'en',
      backgroundColor: 'rgba(9,9,9,1)',
      gridColor: 'rgba(30,30,30,1)',
      hide_top_toolbar: false,
      hide_legend: false,
      save_image: false,
      calendar: false,
      hide_volume: false,
    })

    wrapper.appendChild(script)
    container.appendChild(wrapper)

    return () => {
      container.innerHTML = ''
    }
  }, [symbol])

  return (
    <div
      className="rounded-xl overflow-hidden border border-[#1e1e1e]"
      style={{ height }}
      ref={containerRef}
    />
  )
}

// ── MiniChart ─────────────────────────────────────────────────────────────────
interface MiniChartProps {
  symbol: string
}

export function MiniChart({ symbol }: MiniChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    container.innerHTML = ''

    const wrapper = document.createElement('div')
    wrapper.className = 'tradingview-widget-container'
    wrapper.style.width = '100%'

    const widgetDiv = document.createElement('div')
    widgetDiv.className = 'tradingview-widget-container__widget'
    wrapper.appendChild(widgetDiv)

    const script = document.createElement('script')
    script.type = 'text/javascript'
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js'
    script.async = true
    script.innerHTML = JSON.stringify({
      symbol: `NSE:${symbol}`,
      width: '100%',
      height: '200',
      locale: 'en',
      dateRange: '1M',
      colorTheme: 'dark',
      isTransparent: true,
      autosize: false,
    })

    wrapper.appendChild(script)
    container.appendChild(wrapper)

    return () => {
      container.innerHTML = ''
    }
  }, [symbol])

  return (
    <div
      className="rounded-lg overflow-hidden"
      ref={containerRef}
      style={{ minHeight: '200px' }}
    />
  )
}
