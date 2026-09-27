// KEPLER — Profile Screen
// Clean account management. No payment UI in V1.

import { useState, useCallback } from 'react'
import {
  View, Text, ScrollView, StyleSheet, TouchableOpacity,
  Switch, Alert, Linking,
} from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { router } from 'expo-router'
import { useAuth } from '@/lib/auth'
import { Colors, Spacing, Radius, FontSize, FontWeight } from '@/constants/theme'
import { Divider } from '@/components/ui'

// ── Section group ─────────────────────────────────────────────────────────────

function SettingsSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={s.section}>
      <Text style={s.sectionLabel}>{title}</Text>
      <View style={s.sectionCard}>
        {children}
      </View>
    </View>
  )
}

// ── Settings Row ──────────────────────────────────────────────────────────────

function SettingsRow({
  label, subtitle, icon, onPress, rightElement, last = false,
}: {
  label: string; subtitle?: string; icon?: string; onPress?: () => void;
  rightElement?: React.ReactNode; last?: boolean;
}) {
  const Row = onPress ? TouchableOpacity : View
  return (
    <Row
      style={[s.row, !last && s.rowBorder]}
      onPress={onPress}
      activeOpacity={0.7}
    >
      {icon && (
        <View style={s.rowIcon}>
          <Text style={s.rowIconText}>{icon}</Text>
        </View>
      )}
      <View style={s.rowContent}>
        <Text style={s.rowLabel}>{label}</Text>
        {subtitle && <Text style={s.rowSubtitle}>{subtitle}</Text>}
      </View>
      {rightElement ?? (onPress && <Text style={s.rowChevron}>›</Text>)}
    </Row>
  )
}

// ── Toggle Row ────────────────────────────────────────────────────────────────

function ToggleRow({ label, subtitle, value, onChange, last = false }: {
  label: string; subtitle?: string; value: boolean; onChange: (v: boolean) => void; last?: boolean;
}) {
  return (
    <View style={[s.row, !last && s.rowBorder]}>
      <View style={s.rowContent}>
        <Text style={s.rowLabel}>{label}</Text>
        {subtitle && <Text style={s.rowSubtitle}>{subtitle}</Text>}
      </View>
      <Switch
        value={value}
        onValueChange={onChange}
        trackColor={{ false: Colors.bgElevated, true: Colors.accentDim }}
        thumbColor={value ? Colors.accent : Colors.textMuted}
        ios_backgroundColor={Colors.bgElevated}
      />
    </View>
  )
}

// ── Main Screen ───────────────────────────────────────────────────────────────

export default function ProfileScreen() {
  const { user, signOut } = useAuth()
  const [notifDigest,   setNotifDigest]   = useState(true)
  const [notifBreakout, setNotifBreakout] = useState(false)
  const [notifIPO,      setNotifIPO]      = useState(true)
  const [notifNews,     setNotifNews]     = useState(false)

  const handleSignOut = useCallback(() => {
    Alert.alert(
      'Sign Out',
      'Are you sure you want to sign out?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Sign Out',
          style: 'destructive',
          onPress: async () => {
            await signOut()
            router.replace('/login' as any)
          },
        },
      ]
    )
  }, [signOut])

  const displayName = user?.email?.split('@')[0] ?? 'User'
  const plan = (user as any)?.plan ?? 'free'
  const planLabel = plan === 'elite' ? 'Elite Member' : plan === 'pro' ? 'Pro Member' : 'Free Member'
  const planColor = plan === 'elite' ? Colors.accent : plan === 'pro' ? Colors.positive : Colors.textMuted

  return (
    <SafeAreaView style={s.safe} edges={['top']}>
      <ScrollView style={s.scroll} showsVerticalScrollIndicator={false}>
        {/* ── Header ───────────────────────────────────────────── */}
        <View style={s.header}>
          <Text style={s.headerTitle}>PROFILE</Text>
        </View>

        {/* ── User Card ─────────────────────────────────────────── */}
        <View style={s.userCard}>
          {user ? (
            <>
              <View style={s.avatar}>
                <Text style={s.avatarText}>{displayName[0].toUpperCase()}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={s.userName}>{displayName.toUpperCase()}</Text>
                <Text style={s.userEmail}>{user.email}</Text>
                <View style={[s.planBadge, { borderColor: planColor + '40', backgroundColor: planColor + '12' }]}>
                  <Text style={[s.planText, { color: planColor }]}>{planLabel.toUpperCase()}</Text>
                </View>
              </View>
            </>
          ) : (
            <View style={{ flex: 1 }}>
              <Text style={s.notSignedIn}>Not signed in</Text>
              <TouchableOpacity
                style={s.signInBtn}
                onPress={() => router.push('/login' as any)}
              >
                <Text style={s.signInText}>SIGN IN →</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>

        {/* ── Notifications ──────────────────────────────────────── */}
        <SettingsSection title="NOTIFICATIONS">
          <ToggleRow
            label="Daily Intelligence"
            subtitle="Morning market brief at 9:30 AM IST"
            value={notifDigest}
            onChange={setNotifDigest}
          />
          <ToggleRow
            label="Breakout Alerts"
            subtitle="Technical setup notifications at 1:20 PM IST"
            value={notifBreakout}
            onChange={setNotifBreakout}
          />
          <ToggleRow
            label="IPO Updates"
            subtitle="Opening, closing and allotment alerts"
            value={notifIPO}
            onChange={setNotifIPO}
          />
          <ToggleRow
            label="Breaking News"
            subtitle="High-impact market news only"
            value={notifNews}
            onChange={setNotifNews}
            last
          />
        </SettingsSection>

        {/* ── Account ────────────────────────────────────────────── */}
        <SettingsSection title="ACCOUNT">
          <SettingsRow
            label="Edit Profile"
            icon="◇"
            onPress={() => Alert.alert('Coming Soon', 'Profile editing coming in the next update.')}
          />
          <SettingsRow
            label="Watchlist"
            subtitle="Saved stocks"
            icon="○"
            onPress={() => Alert.alert('Coming Soon', 'Watchlist coming in the next update.')}
          />
          <SettingsRow
            label="Saved Research"
            subtitle="Bookmarked deep dives"
            icon="□"
            last
            onPress={() => Alert.alert('Coming Soon', 'Saved research coming in the next update.')}
          />
        </SettingsSection>

        {/* ── Appearance ─────────────────────────────────────────── */}
        <SettingsSection title="PREFERENCES">
          <SettingsRow
            label="Appearance"
            subtitle="Dark mode (default)"
            icon="◈"
            last
            onPress={() => Alert.alert('Appearance', 'Dark mode is the only theme in V1.')}
          />
        </SettingsSection>

        {/* ── Support ────────────────────────────────────────────── */}
        <SettingsSection title="SUPPORT">
          <SettingsRow
            label="Help"
            icon="?"
            onPress={() => Alert.alert('Help', 'Support available at support@kepler.in')}
          />
          <SettingsRow
            label="Send Feedback"
            icon="✉"
            onPress={() => Linking.openURL('mailto:support@kepler.in?subject=Feedback').catch(() => {})}
          />
          <SettingsRow
            label="Privacy Policy"
            icon="◻"
            onPress={() => Alert.alert('Privacy Policy', 'Your data is handled per our privacy policy.')}
          />
          <SettingsRow
            label="Terms of Service"
            icon="◻"
            onPress={() => Alert.alert('Terms', 'Educational platform. Not SEBI registered.')}
            last
          />
        </SettingsSection>

        {/* ── Disclaimer ─────────────────────────────────────────── */}
        <View style={s.disclaimerBox}>
          <Text style={s.disclaimerTitle}>DISCLAIMER</Text>
          <Text style={s.disclaimerText}>
            KEPLER is not SEBI registered. All content is for educational and informational
            purposes only. Nothing on this platform constitutes investment advice, a solicitation,
            or a recommendation to buy or sell any security. Always consult a qualified financial
            advisor before making investment decisions.
          </Text>
        </View>

        {/* ── Sign Out ───────────────────────────────────────────── */}
        {user && (
          <TouchableOpacity style={s.signOutBtn} onPress={handleSignOut} activeOpacity={0.8}>
            <Text style={s.signOutText}>SIGN OUT</Text>
          </TouchableOpacity>
        )}

        {/* ── Version ────────────────────────────────────────────── */}
        <View style={s.footer}>
          <Text style={s.brand}>KEPLER</Text>
          <Text style={s.version}>v1.0.0 · AI Stock Research</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  )
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.bg },
  scroll: { flex: 1 },

  header: {
    paddingHorizontal: Spacing.xl, paddingTop: Spacing.xl, paddingBottom: Spacing.lg,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  headerTitle: {
    fontSize: FontSize.h1, fontWeight: FontWeight.black,
    color: Colors.textPrimary, letterSpacing: -0.5,
  },

  // User card
  userCard: {
    flexDirection: 'row', alignItems: 'center', gap: Spacing.lg,
    margin: Spacing.xl,
    backgroundColor: Colors.bgCard, borderRadius: Radius.xl,
    borderWidth: 1, borderColor: Colors.border,
    padding: Spacing.xl,
  },
  avatar: {
    width: 52, height: 52, borderRadius: 26,
    backgroundColor: Colors.accentDim, borderWidth: 1, borderColor: Colors.accentBorder,
    alignItems: 'center', justifyContent: 'center',
  },
  avatarText: { fontSize: FontSize.h2, fontWeight: FontWeight.black, color: Colors.accent },
  userName: {
    fontSize: FontSize.base, fontWeight: FontWeight.black,
    color: Colors.textPrimary, letterSpacing: 0.5, marginBottom: 2,
  },
  userEmail: { fontSize: FontSize.xs, color: Colors.textMuted, marginBottom: Spacing.sm },
  planBadge: {
    alignSelf: 'flex-start', paddingHorizontal: Spacing.sm, paddingVertical: 3,
    borderRadius: Radius.xs, borderWidth: 1,
  },
  planText: { fontSize: FontSize.xxs, fontWeight: FontWeight.black, letterSpacing: 0.8 },

  notSignedIn: { fontSize: FontSize.sm, color: Colors.textMuted, marginBottom: Spacing.md },
  signInBtn: {
    paddingHorizontal: Spacing.lg, paddingVertical: Spacing.sm,
    backgroundColor: Colors.accent, borderRadius: Radius.md, alignSelf: 'flex-start',
  },
  signInText: { fontSize: FontSize.xs, fontWeight: FontWeight.black, color: Colors.white, letterSpacing: 0.5 },

  // Sections
  section: { paddingHorizontal: Spacing.xl, marginBottom: Spacing.lg },
  sectionLabel: {
    fontSize: FontSize.xxs, fontWeight: FontWeight.bold, color: Colors.textMuted,
    letterSpacing: 1.5, marginBottom: Spacing.sm,
  },
  sectionCard: {
    backgroundColor: Colors.bgCard, borderRadius: Radius.lg,
    borderWidth: 1, borderColor: Colors.border, overflow: 'hidden',
  },

  // Rows
  row: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: Spacing.lg, paddingVertical: Spacing.md + 2,
    gap: Spacing.md, minHeight: 52,
  },
  rowBorder: { borderBottomWidth: 1, borderBottomColor: Colors.border },
  rowIcon: {
    width: 28, height: 28, borderRadius: Radius.sm,
    backgroundColor: Colors.bgElevated,
    alignItems: 'center', justifyContent: 'center',
  },
  rowIconText: { fontSize: 12, color: Colors.textSecondary },
  rowContent: { flex: 1 },
  rowLabel: { fontSize: FontSize.sm, fontWeight: FontWeight.semibold, color: Colors.textPrimary },
  rowSubtitle: { fontSize: FontSize.xs, color: Colors.textMuted, marginTop: 1 },
  rowChevron: { fontSize: 18, color: Colors.textMuted },

  // Disclaimer
  disclaimerBox: {
    margin: Spacing.xl,
    backgroundColor: Colors.bgCard, borderRadius: Radius.lg,
    borderWidth: 1, borderColor: Colors.border,
    padding: Spacing.lg,
  },
  disclaimerTitle: {
    fontSize: FontSize.xxs, fontWeight: FontWeight.black,
    color: Colors.textMuted, letterSpacing: 1.5, marginBottom: Spacing.sm,
  },
  disclaimerText: {
    fontSize: FontSize.xxs, color: Colors.textDisabled,
    lineHeight: 18,
  },

  // Sign out
  signOutBtn: {
    marginHorizontal: Spacing.xl, marginBottom: Spacing.lg,
    paddingVertical: Spacing.md, alignItems: 'center',
    borderWidth: 1, borderColor: Colors.negativeBorder,
    borderRadius: Radius.md, backgroundColor: Colors.negativeDim,
  },
  signOutText: {
    fontSize: FontSize.xs, fontWeight: FontWeight.black,
    color: Colors.negative, letterSpacing: 1,
  },

  // Footer
  footer: { alignItems: 'center', paddingBottom: 40, gap: 4 },
  brand: {
    fontSize: FontSize.xs, fontWeight: FontWeight.black,
    color: Colors.textDisabled, letterSpacing: 2,
  },
  version: { fontSize: FontSize.xxs, color: Colors.textDisabled },
})
