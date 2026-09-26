// ANTIGRAVITY — Premium Design System
// Dark-first. Intelligence-first. Bloomberg meets Linear.

export const Colors = {
  // ── Backgrounds ──────────────────────────────────────────────
  bg:           '#080A0F',
  bgSecondary:  '#0D1016',
  bgCard:       '#11151D',
  bgElevated:   '#151A23',
  bgInput:      '#0F1319',

  // ── Borders ──────────────────────────────────────────────────
  border:       '#1E2530',
  borderLight:  '#252D3A',
  borderStrong: '#2E3847',

  // ── Text ─────────────────────────────────────────────────────
  textPrimary:   '#F5F7FA',
  textSecondary: '#98A1AF',
  textMuted:     '#626B79',
  textDisabled:  '#3D4554',

  // ── Accent — restrained indigo/violet ────────────────────────
  accent:        '#7C6CFF',
  accentSoft:    '#6B5CE7',
  accentDim:     'rgba(124,108,255,0.12)',
  accentBorder:  'rgba(124,108,255,0.25)',

  // ── Positive — muted green ────────────────────────────────────
  positive:      '#22C55E',
  positiveDim:   'rgba(34,197,94,0.10)',
  positiveBorder:'rgba(34,197,94,0.20)',

  // ── Negative — muted red ──────────────────────────────────────
  negative:      '#F43F5E',
  negativeDim:   'rgba(244,63,94,0.10)',
  negativeBorder:'rgba(244,63,94,0.20)',

  // ── Warning — amber, sparingly ────────────────────────────────
  warning:       '#F59E0B',
  warningDim:    'rgba(245,158,11,0.10)',

  // ── Semantic aliases ──────────────────────────────────────────
  // Legacy aliases kept for backward compat
  green:         '#22C55E',
  greenDim:      'rgba(34,197,94,0.10)',
  red:           '#F43F5E',
  redDim:        'rgba(244,63,94,0.10)',
  yellow:        '#F59E0B',
  yellowDim:     'rgba(245,158,11,0.10)',
  blue:          '#3B82F6',
  blueDim:       'rgba(59,130,246,0.10)',
  bgCardHover:   '#151A23',
  accentBorderLegacy: 'rgba(124,108,255,0.25)',

  // ── Utility ───────────────────────────────────────────────────
  white:  '#FFFFFF',
  black:  '#000000',
  transparent: 'transparent',
} as const

export const Spacing = {
  xxs: 2,
  xs:  4,
  sm:  8,
  md:  12,
  lg:  16,
  xl:  20,
  xxl: 24,
  xxxl: 32,
  section: 40,
} as const

export const Radius = {
  xs:   4,
  sm:   8,
  md:   12,
  lg:   16,
  xl:   20,
  xxl:  24,
  full: 999,
} as const

export const FontSize = {
  // Display — big market numbers
  display: 36,
  hero:    28,
  // H1 — page titles
  h1:      24,
  // H2 — section titles
  h2:      20,
  // H3 — card titles
  h3:      17,
  // Body
  base:    15,
  // Secondary body
  sm:      13,
  // Caption / metadata
  xs:      11,
  xxs:     10,

  // Legacy aliases
  xxl: 24,
  xxxl: 30,
  xl:  20,
  lg:  17,
} as const

export const FontWeight = {
  regular:   '400' as const,
  medium:    '500' as const,
  semibold:  '600' as const,
  bold:      '700' as const,
  black:     '900' as const,
}

// Monospaced number style — numbers should align cleanly
export const MonoStyle = {
  fontVariant: ['tabular-nums'] as any,
  letterSpacing: -0.3,
} as const

// Animation durations
export const Duration = {
  fast:   150,
  normal: 200,
  slow:   300,
} as const

// Z-index stack
export const ZIndex = {
  base:    0,
  card:    10,
  header:  50,
  modal:   100,
  overlay: 200,
} as const

// Shadows (subtle in dark UI — rely on borders + surface contrast instead)
export const Shadow = {
  sm: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.3,
    shadowRadius: 4,
    elevation: 2,
  },
  md: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 4,
  },
} as const
