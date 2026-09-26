import type { Metadata } from 'next'
import SwingStrategiesHub from '@/components/SwingStrategiesHub'

export const metadata: Metadata = {
  title: 'Swing Strategy Intelligence | Kepler',
  description: 'Backtested swing trading strategies with ML win probability, news sentiment fusion, and Hermes self-learning — pick only the highest win-rate setups.',
}

export default function SwingStrategiesPage() {
  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #020617 0%, #0f172a 50%, #0a0f1e 100%)',
      padding: '24px 20px',
    }}>
      <SwingStrategiesHub />
    </div>
  )
}
