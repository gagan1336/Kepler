import { useState } from 'react'
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ScrollView, Platform, ActivityIndicator, Alert, KeyboardAvoidingView,
} from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { router } from 'expo-router'
import * as WebBrowser from 'expo-web-browser'
import { useAuth } from '@/lib/auth.tsx'
import { Colors, FontSize, Radius, Spacing } from '@/constants/theme'

// Required for OAuth redirect to close the browser automatically
WebBrowser.maybeCompleteAuthSession()

export default function LoginScreen() {
  const { signIn, signInWithGoogle } = useAuth()
  const [email, setEmail]           = useState('')
  const [password, setPassword]     = useState('')
  const [loading, setLoading]       = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)
  const [errorMsg, setErrorMsg]     = useState('')

  const handleLogin = async () => {
    if (!email.trim() || !password) {
      setErrorMsg('Please enter your email and password')
      return
    }
    setLoading(true)
    setErrorMsg('')
    try {
      await signIn(email.trim().toLowerCase(), password)
      router.replace('/(tabs)')
    } catch (e: any) {
      console.log('LOGIN ERROR:', JSON.stringify(e))
      const msg = e?.message ?? e?.error_description ?? JSON.stringify(e)
      setErrorMsg(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleGoogleLogin = async () => {
    setGoogleLoading(true)
    setErrorMsg('')
    try {
      await signInWithGoogle()
      // Supabase opens a browser tab — when the user returns the auth state
      // listener in auth.tsx fires automatically and routes them in
    } catch (e: any) {
      const msg = e?.message ?? 'Google sign-in failed'
      setErrorMsg(msg)
    } finally {
      setGoogleLoading(false)
    }
  }

  return (
    <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* Back */}
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Text style={styles.backText}>← Back</Text>
          </TouchableOpacity>

          {/* Brand */}
          <Text style={styles.brand}>KEPLER</Text>
          <Text style={styles.subtitle}>AI Stock Research · Indian Markets</Text>

          <Text style={styles.title}>Welcome back</Text>

          {/* Email */}
          <Text style={styles.label}>Email</Text>
          <TextInput
            style={styles.input}
            placeholder="you@example.com"
            placeholderTextColor={Colors.textMuted}
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
            editable={!loading}
          />

          {/* Password */}
          <Text style={styles.label}>Password</Text>
          <TextInput
            style={styles.input}
            placeholder="Your password"
            placeholderTextColor={Colors.textMuted}
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            editable={!loading}
          />

          {/* Sign In Button */}
          <TouchableOpacity
            style={[styles.btn, loading && styles.btnDisabled]}
            onPress={handleLogin}
            disabled={loading}
          >
            {loading
              ? <ActivityIndicator color={Colors.bg} />
              : <Text style={styles.btnText}>Sign In</Text>
            }
          </TouchableOpacity>

          {/* Divider */}
          <View style={styles.divider}>
            <View style={styles.dividerLine} />
            <Text style={styles.dividerText}>or</Text>
            <View style={styles.dividerLine} />
          </View>

          {/* Google Sign-In */}
          <TouchableOpacity
            style={[styles.googleBtn, googleLoading && styles.btnDisabled]}
            onPress={handleGoogleLogin}
            disabled={googleLoading || loading}
          >
            {googleLoading
              ? <ActivityIndicator color={Colors.textPrimary} />
              : <>
                  <Text style={styles.googleIcon}>G</Text>
                  <Text style={styles.googleBtnText}>Continue with Google</Text>
                </>
            }
          </TouchableOpacity>

          {/* Error message */}
          {errorMsg ? (
            <View style={styles.errorBox}>
              <Text style={styles.errorText}>❌ {errorMsg}</Text>
            </View>
          ) : null}

          {/* Register link */}
          <View style={styles.row}>
            <Text style={styles.rowText}>Don't have an account? </Text>
            <TouchableOpacity onPress={() => router.push('/register')}>
              <Text style={styles.link}>Create one →</Text>
            </TouchableOpacity>
          </View>

          {/* Disclaimer */}
          <Text style={styles.disclaimer}>
            Not SEBI registered. All content is for educational purposes only.
          </Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.bg },
  scroll: {
    flexGrow: 1,
    padding: Spacing.xl,
    paddingTop: Spacing.md,
  },
  backBtn: {
    paddingVertical: Spacing.sm,
    marginBottom: Spacing.xl,
    alignSelf: 'flex-start',
  },
  backText: { color: Colors.textSecondary, fontSize: FontSize.sm },

  brand: {
    fontSize: FontSize.xxl,
    fontWeight: '900',
    color: Colors.textPrimary,
    letterSpacing: 1,
    marginBottom: 4,
  },
  subtitle: {
    fontSize: FontSize.sm,
    color: Colors.textMuted,
    marginBottom: Spacing.xxxl,
  },
  title: {
    fontSize: FontSize.xxxl,
    fontWeight: '900',
    color: Colors.textPrimary,
    marginBottom: Spacing.xl,
  },

  label: {
    fontSize: FontSize.sm,
    color: Colors.textSecondary,
    marginBottom: Spacing.xs,
    fontWeight: '600',
  },
  input: {
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.lg,
    fontSize: FontSize.base,
    color: Colors.textPrimary,
    marginBottom: Spacing.lg,
  },

  btn: {
    backgroundColor: Colors.accent,
    borderRadius: Radius.lg,
    padding: Spacing.lg,
    alignItems: 'center',
    marginTop: Spacing.sm,
    marginBottom: Spacing.xl,
  },
  btnDisabled: { opacity: 0.6 },
  btnText: {
    fontSize: FontSize.base,
    fontWeight: '700',
    color: Colors.bg,
  },

  row: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: Spacing.xl,
  },
  rowText: { fontSize: FontSize.sm, color: Colors.textSecondary },
  link: { fontSize: FontSize.sm, fontWeight: '700', color: Colors.accent },

  divider: { flexDirection: 'row', alignItems: 'center', gap: Spacing.md, marginVertical: Spacing.lg },
  dividerLine: { flex: 1, height: 1, backgroundColor: Colors.border },
  dividerText: { fontSize: FontSize.xs, color: Colors.textMuted },

  googleBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: Spacing.md, borderRadius: Radius.lg,
    borderWidth: 1, borderColor: Colors.border,
    backgroundColor: Colors.bgCard,
    padding: Spacing.lg, marginBottom: Spacing.xl,
  },
  googleIcon: {
    fontSize: FontSize.lg, fontWeight: '900', color: '#4285F4',
    width: 24, textAlign: 'center',
  },
  googleBtnText: { fontSize: FontSize.base, fontWeight: '700', color: Colors.textPrimary },

  disclaimer: {
    fontSize: FontSize.xs,
    color: Colors.textMuted,
    textAlign: 'center',
    fontStyle: 'italic',
  },

  errorBox: {
    backgroundColor: 'rgba(229,72,77,0.1)',
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: 'rgba(229,72,77,0.3)',
    padding: Spacing.md,
    marginBottom: Spacing.md,
  },
  errorText: {
    color: Colors.red,
    fontSize: FontSize.sm,
    textAlign: 'center',
  },
})
