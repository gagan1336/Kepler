import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { AuthProvider } from '@/lib/auth'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
  weight: ['300', '400', '500', '600', '700', '800', '900'],
})

export const metadata: Metadata = {
  title: 'Umbra — See the Setup Before the Crowd Does',
  description:
    'Umbra is invite-only market intelligence for serious Indian traders. Breakout scanner, sector analysis, morning digest, and deep-dive research. No tips. No noise.',
  keywords: [
    'Indian stock market', 'NSE', 'Nifty', 'market intelligence',
    'breakout scanner', 'sector analysis', 'Umbra', 'equity research India',
    'swing trading', 'market research India',
  ],
  authors: [{ name: 'Umbra' }],
  creator: 'Umbra',
  openGraph: {
    type: 'website',
    locale: 'en_IN',
    url: 'https://umbra.in',
    siteName: 'Umbra',
    title: 'Umbra — See the Setup Before the Crowd Does',
    description:
      'Invite-only market intelligence for serious Indian traders. No tips. No noise. Just research.',
    images: [{ url: 'https://umbra.in/og-image.png', width: 1200, height: 630, alt: 'Umbra' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Umbra — See the Setup Before the Crowd Does',
    description: 'Invite-only market intelligence. Breakout scanner, sector analysis, morning digest.',
    images: ['https://umbra.in/og-image.png'],
  },
  robots: { index: true, follow: true },
  metadataBase: new URL('https://umbra.in'),
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={inter.variable}>
      <head>
        <link rel="icon" href="/favicon.ico" />
        <meta name="theme-color" content="#C9A34E" />
        {/* JetBrains Mono — non-blocking */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
      </head>
      <body className="antialiased">
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  )
}

