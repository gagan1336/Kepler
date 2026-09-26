import { View, Text, StyleSheet, TouchableOpacity } from 'react-native'
import { router } from 'expo-router'
import { Ionicons } from '@expo/vector-icons'
import { Colors, FontSize, Radius, Spacing } from '@/constants/theme'

interface Props {
  message?: string
}

export function SignInPrompt({ message = 'Sign in to access this feature' }: Props) {
  return (
    <View style={styles.container}>
      <View style={styles.iconCircle}>
        <Ionicons name="lock-closed-outline" size={32} color={Colors.accent} />
      </View>
      <Text style={styles.title}>Sign In Required</Text>
      <Text style={styles.message}>{message}</Text>
      <TouchableOpacity
        style={styles.btn}
        onPress={() => router.push('/login')}
        activeOpacity={0.85}
      >
        <Text style={styles.btnText}>Sign In</Text>
      </TouchableOpacity>
      <TouchableOpacity onPress={() => router.push('/register')}>
        <Text style={styles.registerText}>New here? Create free account →</Text>
      </TouchableOpacity>
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: Spacing.xxxl,
    gap: Spacing.md,
    backgroundColor: Colors.bg,
  },
  iconCircle: {
    width: 72, height: 72,
    borderRadius: Radius.full,
    backgroundColor: Colors.accentDim,
    borderWidth: 1,
    borderColor: Colors.accentBorder,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.sm,
  },
  title: {
    fontSize: FontSize.xl,
    fontFamily: 'Inter_900Black',
    color: Colors.textPrimary,
    textAlign: 'center',
  },
  message: {
    fontSize: FontSize.sm,
    color: Colors.textSecondary,
    textAlign: 'center',
    lineHeight: 20,
    maxWidth: 260,
  },
  btn: {
    marginTop: Spacing.lg,
    backgroundColor: Colors.accent,
    paddingHorizontal: Spacing.xxxl,
    paddingVertical: Spacing.md,
    borderRadius: Radius.full,
  },
  btnText: {
    color: Colors.bg,
    fontSize: FontSize.base,
    fontWeight: '700',
  },
  registerText: {
    color: Colors.accent,
    fontSize: FontSize.sm,
    marginTop: Spacing.sm,
  },
})
