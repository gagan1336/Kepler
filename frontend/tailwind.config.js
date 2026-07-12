/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Eclipse Edge accent — warm gold (CTAs, active states, signature sweep)
        accent: {
          DEFAULT: '#C9A34E',
          dark:    '#A8822E',
          light:   '#DDB96A',
          dim:     'rgba(201,163,78,0.10)',
          border:  'rgba(201,163,78,0.25)',
          glow:    'rgba(201,163,78,0.18)',
        },
        // Semantic: real market direction ONLY
        gain: '#3DDC84',
        loss: '#E5484D',
        // Gold alias (same as accent in Umbra)
        gold: {
          DEFAULT: '#C9A34E',
          dim:    'rgba(201,163,78,0.10)',
          border: 'rgba(201,163,78,0.25)',
        },
        // Umbra surfaces — dark-mode only
        surface: {
          base:     '#0A0A0B',
          elevated: '#131315',
          overlay:  '#1C1C1F',
          1: '#131315',
          2: '#1C1C1F',
          3: '#222226',
        },
        // Umbra text scale
        ink: {
          1: '#F2F2F0',
          2: '#9A9A9E',
          3: '#5C5C60',
        },
        // Legacy compat — maps to gold
        brand: {
          DEFAULT: '#C9A34E',
          dark:    '#A8822E',
          light:   '#DDB96A',
          glow:    'rgba(201,163,78,0.15)',
        },
      },
      fontFamily: {
        sans:    ['Inter', 'var(--font-inter)', 'system-ui', 'sans-serif'],
        mono:    ['"JetBrains Mono"', 'var(--font-mono)', 'ui-monospace', 'monospace'],
        display: ['Inter', 'var(--font-inter)', 'system-ui', 'sans-serif'],
      },
      animation: {
        'fade-in':        'fadeIn 0.45s ease-out',
        'slide-up':       'slideUp 0.5s cubic-bezier(0.4,0,0.2,1)',
        'pulse-slow':     'pulse 3s ease-in-out infinite',
        'pulse-accent':   'glow-pulse 2.5s ease-in-out infinite',
        'glow':           'shimmer-gold 3s ease-in-out infinite alternate',
        'shimmer':        'shimmer 1.8s infinite',
        'candleTick':     'candleTick 0.4s ease-out',
        'scanLine':       'scanLine 4s linear infinite',
        'eclipse-sweep':  'eclipse-sweep-ltr 1.2s cubic-bezier(0.16,1,0.3,1) forwards',
        'conf-sweep':     'conf-bar-sweep 1.0s cubic-bezier(0.16,1,0.3,1) forwards',
        'aurora-drift-1': 'aurora-drift-1 24s ease-in-out infinite',
        'aurora-drift-2': 'aurora-drift-2 30s ease-in-out infinite',
        'float':          'float 6s ease-in-out infinite',
        'page':           'pageSlide 0.22s ease-out',
        'breathe':        'breathe 4s ease-in-out infinite',
        'flash-gain':     'value-flash-gain 0.6s ease-out',
        'flash-loss':     'value-flash-loss 0.6s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%':   { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pageSlide: {
          '0%':   { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        candleTick: {
          '0%':   { transform: 'scaleY(0)', opacity: '0' },
          '100%': { transform: 'scaleY(1)', opacity: '1' },
        },
        scanLine: {
          '0%':   { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(400%)' },
        },
        'eclipse-sweep-ltr': {
          '0%':   { left: '-60%', opacity: '0' },
          '5%':   { opacity: '1' },
          '95%':  { opacity: '1' },
          '100%': { left: '160%', opacity: '0' },
        },
        'conf-bar-sweep': {
          '0%':   { left: '-40%' },
          '100%': { left: '110%' },
        },
        'shimmer-gold': {
          '0%, 100%': { boxShadow: '0 0 20px rgba(201,163,78,0)' },
          '50%': { boxShadow: '0 0 40px rgba(201,163,78,0.22)' },
        },
        'glow-pulse': {
          '0%, 100%': { opacity: '0.5' },
          '50%': { opacity: '1' },
        },
        'aurora-drift-1': {
          '0%, 100%': { transform: 'translate(0,0) scale(1)' },
          '33%': { transform: 'translate(60px,40px) scale(1.08)' },
          '66%': { transform: 'translate(-40px,60px) scale(0.96)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-7px)' },
        },
        breathe: {
          '0%, 100%': { opacity: '0.4', transform: 'scale(1)' },
          '50%': { opacity: '0.8', transform: 'scale(1.02)' },
        },
        'value-flash-gain': {
          '0%, 100%': { color: 'inherit' },
          '30%': { color: '#3DDC84' },
        },
        'value-flash-loss': {
          '0%, 100%': { color: 'inherit' },
          '30%': { color: '#E5484D' },
        },
      },
      backgroundImage: {
        'grid-pattern':   "linear-gradient(rgba(255,255,255,0.018) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.018) 1px, transparent 1px)",
        'hero-gradient':  'radial-gradient(ellipse 80% 50% at 50% -20%, rgba(201,163,78,0.06), transparent)',
        'accent-gradient':'linear-gradient(135deg, #C9A34E 0%, #DDB96A 100%)',
      },
      backgroundSize: {
        'grid': '48px 48px',
      },
      boxShadow: {
        'accent':     '0 0 40px rgba(201,163,78,0.16), 0 8px 32px rgba(0,0,0,0.5)',
        'accent-sm':  '0 0 18px rgba(201,163,78,0.12)',
        'card':       '0 4px 24px rgba(0,0,0,0.4)',
        'gain':       '0 0 18px rgba(61,220,132,0.2)',
        'gold':       '0 0 28px rgba(201,163,78,0.18)',
      },
    },
  },
  plugins: [],
}
