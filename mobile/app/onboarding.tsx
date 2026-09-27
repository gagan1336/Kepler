// KEPLER -- Onboarding Screen
// Shown once on first launch. 4 slides + CTA.

import { useState, useRef } from 'react'
import {
  View, Text, StyleSheet, TouchableOpacity, FlatList,
  Dimensions, Animated, Platform,
} from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { router } from 'expo-router'
import * as SecureStore from 'expo-secure-store'
import { Colors, Spacing, Radius, FontSize, FontWeight } from '@/constants/theme'

const { width: SW } = Dimensions.get('window')

const ONBOARDING_KEY = 'kepler_onboarding_done'

const SLIDES = [
  {
    id: '1',
    icon: '◎',
    title: 'Meet KEPLER',
    subtitle: 'AI-powered market intelligence\nfor the Indian market.',
    accent: Colors.accent,
  },
  {
    id: '2',
    icon: '◈',
    title: 'Know What Matters',
    subtitle: 'Get curated market news and intelligence\nwithout information overload.',
    accent: Colors.accent,
  },
  {
    id: '3',
    icon: '◇',
    title: 'Understand Why',
    subtitle: 'See market, sector and stock context\nin one place.',
    accent: Colors.accent,
  },
  {
    id: '4',
    icon: '○',
    title: 'Go Deeper',
    subtitle: 'Explore AI Deep Dives, screeners,\nbreakouts and IPO intelligence.',
    accent: Colors.accent,
  },
]

export default function OnboardingScreen() {
  const [activeIndex, setActiveIndex] = useState(0)
  const listRef = useRef<FlatList>(null)
  const progressAnim = useRef(new Animated.Value(0)).current

  const goNext = () => {
    if (activeIndex < SLIDES.length - 1) {
      const next = activeIndex + 1
      listRef.current?.scrollToIndex({ index: next, animated: true })
      setActiveIndex(next)
      Animated.timing(progressAnim, {
        toValue: next,
        duration: 250,
        useNativeDriver: false,
      }).start()
    }
  }

  const finish = async () => {
    await SecureStore.setItemAsync(ONBOARDING_KEY, 'true')
    router.replace('/(tabs)')
  }

  const isLast = activeIndex === SLIDES.length - 1

  return (
    <SafeAreaView style={s.safe} edges={['top', 'bottom']}>
      {/* Skip */}
      {!isLast && (
        <TouchableOpacity style={s.skip} onPress={finish}>
          <Text style={s.skipText}>Skip</Text>
        </TouchableOpacity>
      )}

      {/* Slides */}
      <FlatList
        ref={listRef}
        data={SLIDES}
        keyExtractor={(item) => item.id}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        scrollEnabled={false}
        renderItem={({ item }) => (
          <View style={[s.slide, { width: SW }]}>
            <View style={s.iconWrap}>
              <Text style={[s.icon, { color: item.accent }]}>{item.icon}</Text>
            </View>
            <Text style={s.slideTitle}>{item.title}</Text>
            <Text style={s.slideSubtitle}>{item.subtitle}</Text>
          </View>
        )}
      />

      {/* Dots */}
      <View style={s.dots}>
        {SLIDES.map((_, i) => (
          <View
            key={i}
            style={[
              s.dot,
              i === activeIndex && s.dotActive,
            ]}
          />
        ))}
      </View>

      {/* CTA */}
      <View style={s.footer}>
        {isLast ? (
          <TouchableOpacity style={s.ctaBtn} onPress={finish} activeOpacity={0.88}>
            <Text style={s.ctaText}>Explore KEPLER</Text>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity style={s.nextBtn} onPress={goNext} activeOpacity={0.88}>
            <Text style={s.nextText}>Continue →</Text>
          </TouchableOpacity>
        )}

        {/* Tagline */}
        <Text style={s.tagline}>Understand the market. Go deeper.</Text>
      </View>
    </SafeAreaView>
  )
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.bg },

  skip: {
    position: 'absolute', top: Platform.OS === 'ios' ? 54 : 16,
    right: Spacing.xl, zIndex: 10,
  },
  skipText: {
    fontSize: FontSize.sm, color: Colors.textMuted, fontWeight: FontWeight.medium,
  },

  slide: {
    flex: 1, alignItems: 'center', justifyContent: 'center',
    paddingHorizontal: Spacing.xxl,
    paddingTop: 60,
  },
  iconWrap: {
    width: 88, height: 88, borderRadius: 44,
    backgroundColor: Colors.accentDim,
    borderWidth: 1, borderColor: Colors.accentBorder,
    alignItems: 'center', justifyContent: 'center',
    marginBottom: Spacing.xxxl,
  },
  icon: {
    fontSize: 36, fontWeight: FontWeight.black,
  },
  slideTitle: {
    fontSize: FontSize.xxxl, fontWeight: FontWeight.black,
    color: Colors.textPrimary, textAlign: 'center',
    letterSpacing: -0.5, marginBottom: Spacing.lg,
  },
  slideSubtitle: {
    fontSize: FontSize.base, color: Colors.textSecondary,
    textAlign: 'center', lineHeight: 26,
  },

  dots: {
    flexDirection: 'row', justifyContent: 'center',
    gap: Spacing.sm, paddingBottom: Spacing.xl,
  },
  dot: {
    width: 6, height: 6, borderRadius: 3,
    backgroundColor: Colors.bgElevated,
  },
  dotActive: {
    width: 20, backgroundColor: Colors.accent,
  },

  footer: {
    paddingHorizontal: Spacing.xl, paddingBottom: Spacing.xl, gap: Spacing.lg,
  },
  ctaBtn: {
    backgroundColor: Colors.accent, borderRadius: Radius.lg,
    paddingVertical: Spacing.lg, alignItems: 'center',
  },
  ctaText: {
    fontSize: FontSize.base, fontWeight: FontWeight.black,
    color: Colors.bg, letterSpacing: 0.3,
  },
  nextBtn: {
    borderWidth: 1, borderColor: Colors.border,
    borderRadius: Radius.lg, paddingVertical: Spacing.lg,
    alignItems: 'center', backgroundColor: Colors.bgCard,
  },
  nextText: {
    fontSize: FontSize.base, fontWeight: FontWeight.semibold,
    color: Colors.textPrimary,
  },
  tagline: {
    fontSize: FontSize.xs, color: Colors.textDisabled,
    textAlign: 'center', letterSpacing: 0.3,
  },
})

export { ONBOARDING_KEY }
