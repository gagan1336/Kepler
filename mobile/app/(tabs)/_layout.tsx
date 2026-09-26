// ANTIGRAVITY — Premium Tab Navigation
import { Tabs } from 'expo-router'
import { View, Text, StyleSheet, Platform } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { Colors, FontSize, FontWeight, Spacing, Radius } from '@/constants/theme'

type TabName = 'index' | 'markets' | 'news' | 'ipo' | 'account'

const TAB_CFG: Record<TabName, {
  label: string
  icon: keyof typeof Ionicons.glyphMap
  iconActive: keyof typeof Ionicons.glyphMap
}> = {
  index:   { label: 'Intelligence', icon: 'flash-outline',      iconActive: 'flash' },
  markets: { label: 'Markets',      icon: 'bar-chart-outline',  iconActive: 'bar-chart' },
  news:    { label: 'Discover',     icon: 'compass-outline',    iconActive: 'compass' },
  ipo:     { label: 'IPO',          icon: 'rocket-outline',     iconActive: 'rocket' },
  account: { label: 'Profile',      icon: 'person-outline',     iconActive: 'person' },
}

function TabIcon({ name, focused }: { name: TabName; focused: boolean }) {
  const cfg = TAB_CFG[name]
  const color = focused ? Colors.accent : Colors.textMuted
  return (
    <View style={s.tabItem}>
      <View style={[s.iconWrap, focused && s.iconWrapActive]}>
        <Ionicons
          name={focused ? cfg.iconActive : cfg.icon}
          size={22}
          color={color}
        />
      </View>
      <Text style={[s.label, focused && s.labelActive]} numberOfLines={1}>
        {cfg.label}
      </Text>
    </View>
  )
}

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: s.tabBar,
        tabBarShowLabel: false,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{ tabBarIcon: ({ focused }) => <TabIcon name="index" focused={focused} /> }}
      />
      <Tabs.Screen
        name="markets"
        options={{ tabBarIcon: ({ focused }) => <TabIcon name="markets" focused={focused} /> }}
      />
      <Tabs.Screen
        name="news"
        options={{ tabBarIcon: ({ focused }) => <TabIcon name="news" focused={focused} /> }}
      />
      <Tabs.Screen
        name="ipo"
        options={{ tabBarIcon: ({ focused }) => <TabIcon name="ipo" focused={focused} /> }}
      />
      <Tabs.Screen
        name="account"
        options={{ tabBarIcon: ({ focused }) => <TabIcon name="account" focused={focused} /> }}
      />

      {/* Hidden — accessible via sub-tabs within screens */}
      <Tabs.Screen name="research"  options={{ href: null }} />
      <Tabs.Screen name="sectors"   options={{ href: null }} />
      <Tabs.Screen name="screener"  options={{ href: null }} />
    </Tabs>
  )
}

const s = StyleSheet.create({
  tabBar: {
    backgroundColor: Colors.bgCard,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
    height: Platform.OS === 'android' ? 60 : 72,
    paddingBottom: Platform.OS === 'android' ? 6 : 16,
    paddingTop: 4,
  },
  tabItem: {
    alignItems: 'center',
    justifyContent: 'center',
    gap: 3,
  },
  iconWrap: {
    width: 36,
    height: 30,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: Radius.sm,
  },
  iconWrapActive: {
    backgroundColor: Colors.accentDim,
  },
  label: {
    fontSize: 10,
    fontWeight: FontWeight.semibold,
    color: Colors.textMuted,
    letterSpacing: 0.1,
  },
  labelActive: {
    color: Colors.accent,
  },
})
