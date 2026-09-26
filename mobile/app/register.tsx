import { useState } from 'react'
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  KeyboardAvoidingView, Platform, ActivityIndicator, Alert, ScrollView,
} from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { router } from 'expo-router'
import { useAuth } from '@/lib/auth'
import { Colors, FontSize, Radius, Spacing } from '@/constants/theme'

export default function RegisterScreen() {
  const { signUp, signInWithGoogle } = useAuth()
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm]   = useState('')
  const [loading, setLoading]   = useState(false)

  const handleRegister = async () => {
    if (!email || !password || !confirm) {
      Alert.alert('Error', 'Please fill in all fields')
      return
    }
    if (password !== confirm) {
      Alert.alert('Error', 'Passwords do not match')
      return
    }
    if (password.length < 8) {
      Alert.alert('Error', 'Password must be at least 8 characters')
      return
    }
    setLoading(true)
    try {
      await signUp(email.trim().toLowerCase(), password)
      Alert.alert('Account Created!', 'Please check your email to confirm your account.', [
        { text: 'OK', onPress: () => router.replace('/login') },
      ])
    } catch (e: any) {
      Alert.alert('Registration Failed', e.message ?? 'Please try again')
    } finally {
      setLoading(false)
    }
  }

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
          {/* Back */}
          <TouchableOpacity style={styles.back} onPress={() => router.back()}>
            <Text style={styles.backText}>← Back</Text>
          </TouchableOpacity>

          <View style={styles.brandRow}>
            <Text style={styles.brandName}>⚡ ANTIGRAVITY</Text>
          </View>

          <Text style={styles.title}>Create account</Text>
          <Text style={styles.subtitle}>Free plan • No credit card required</Text>

          {/* Google */}
          <TouchableOpacity style={styles.googleBtn} onPress={signInWithGoogle} activeOpacity={0.85}>
            <Text style={styles.googleText}>🔑  Continue with Google</Text>
          </TouchableOpacity>

          <View style={styles.dividerRow}>
            <View style={styles.dividerLine} />
            <Text style={styles.dividerText}>or sign up with email</Text>
            <View style={styles.dividerLine} />
          </View>

          <TextInput
            style={styles.input}
            placeholder="Email address"
            placeholderTextColor={Colors.textMuted}
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
          />
          <TextInput
            style={styles.input}
            placeholder="Password (min 8 characters)"
            placeholderTextColor={Colors.textMuted}
            value={password}
            onChangeText={setPassword}
            secureTextEntry
          />
          <TextInput
            style={styles.input}
            placeholder="Confirm password"
            placeholderTextColor={Colors.textMuted}
            value={confirm}
            onChangeText={setConfirm}
            secureTextEntry
          />

          <View style={styles.disclaimerBox}>
            <Text style={styles.disclaimerText}>
              By creating an account you agree that Antigravity is not SEBI registered
              and all content is for educational purposes only.
            </Text>
          </View>

          <TouchableOpacity
            style={[styles.registerBtn, loading && { opacity: 0.6 }]}
            onPress={handleRegister}
            disabled={loading}
            activeOpacity={0.85}
          >
            {loading
              ? <ActivityIndicator color={Colors.bg} />
              : <Text style={styles.registerText}>Create Account</Text>
            }
          </TouchableOpacity>

          <TouchableOpacity onPress={() => router.push('/login')} style={styles.loginRow}>
            <Text style={styles.loginText}>Already have an account? </Text>
            <Text style={styles.loginLink}>Sign in →</Text>
          </TouchableOpacity>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.bg },
  container: { padding: Spacing.xl, paddingTop: 60 },

  back: { marginBottom: Spacing.xl },
  backText: {
    color: Colors.textSecondary,
    fontFamily: 'Inter_400Regular',
    fontSize: FontSize.sm,
  },

  brandRow: { alignItems: 'center', marginBottom: Spacing.xxl },
  brandName: {
    fontSize: FontSize.xl,
    fontFamily: 'Inter_900Black',
    color: Colors.textPrimary,
    letterSpacing: 1,
  },

  title: {
    fontSize: FontSize.xxxl,
    fontFamily: 'Inter_900Black',
    color: Colors.textPrimary,
    marginBottom: Spacing.xs,
  },
  subtitle: {
    fontSize: FontSize.base,
    fontFamily: 'Inter_400Regular',
    color: Colors.textSecondary,
    marginBottom: Spacing.xl,
  },

  googleBtn: {
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.lg,
    alignItems: 'center',
    marginBottom: Spacing.xl,
  },
  googleText: {
    fontSize: FontSize.base,
    fontFamily: 'Inter_600SemiBold',
    color: Colors.textPrimary,
  },

  dividerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: Spacing.xl,
    gap: Spacing.md,
  },
  dividerLine: { flex: 1, height: 1, backgroundColor: Colors.border },
  dividerText: {
    fontSize: FontSize.xs,
    fontFamily: 'Inter_400Regular',
    color: Colors.textMuted,
  },

  input: {
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.lg,
    fontSize: FontSize.base,
    fontFamily: 'Inter_400Regular',
    color: Colors.textPrimary,
    marginBottom: Spacing.md,
  },

  disclaimerBox: {
    backgroundColor: 'rgba(201,163,78,0.06)',
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.accentBorder,
    padding: Spacing.md,
    marginBottom: Spacing.lg,
  },
  disclaimerText: {
    fontSize: FontSize.xs,
    fontFamily: 'Inter_400Regular',
    color: 'rgba(201,163,78,0.6)',
    lineHeight: 18,
    textAlign: 'center',
  },

  registerBtn: {
    backgroundColor: Colors.accent,
    borderRadius: Radius.lg,
    padding: Spacing.lg,
    alignItems: 'center',
    marginBottom: Spacing.xl,
  },
  registerText: {
    fontSize: FontSize.base,
    fontFamily: 'Inter_700Bold',
    color: Colors.bg,
  },

  loginRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
  },
  loginText: {
    fontSize: FontSize.sm,
    fontFamily: 'Inter_400Regular',
    color: Colors.textSecondary,
  },
  loginLink: {
    fontSize: FontSize.sm,
    fontFamily: 'Inter_700Bold',
    color: Colors.accent,
  },
})
