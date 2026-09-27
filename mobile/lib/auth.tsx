// KEPLER — Supabase Auth for React Native
import { createClient } from '@supabase/supabase-js'
import * as SecureStore from 'expo-secure-store'
import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'

const SUPABASE_URL = process.env.EXPO_PUBLIC_SUPABASE_URL ?? ''
const SUPABASE_ANON = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? ''

// Custom SecureStore adapter for Supabase session persistence
const ExpoSecureStoreAdapter = {
  getItem: (key: string) => SecureStore.getItemAsync(key),
  setItem: (key: string, value: string) => SecureStore.setItemAsync(key, value),
  removeItem: (key: string) => SecureStore.deleteItemAsync(key),
}

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON, {
  auth: {
    storage: ExpoSecureStoreAdapter,
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
})

// ── Auth Context ──────────────────────────────────────────────────────────────

interface AuthState {
  user: { id: string; email: string } | null
  accessToken: string | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  signInWithGoogle: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<{ id: string; email: string } | null>(null)
  const [accessToken, setAccessToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const syncSession = useCallback(async () => {
    const { data: { session } } = await supabase.auth.getSession()
    if (session) {
      setUser({ id: session.user.id, email: session.user.email ?? '' })
      setAccessToken(session.access_token)
      await SecureStore.setItemAsync('access_token', session.access_token)
    } else {
      setUser(null)
      setAccessToken(null)
      await SecureStore.deleteItemAsync('access_token')
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    syncSession()
    const { data: { subscription } } = supabase.auth.onAuthStateChange(() => {
      syncSession()
    })
    return () => subscription.unsubscribe()
  }, [syncSession])

  const signIn = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error
  }

  const signUp = async (email: string, password: string) => {
    const { error } = await supabase.auth.signUp({ email, password })
    if (error) throw error
  }

  const signOut = async () => {
    await supabase.auth.signOut()
  }

  const signInWithGoogle = async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: 'kepler://auth/callback' },
    })
    if (error) throw error
  }

  return (
    <AuthContext.Provider value={{ user, accessToken, loading, signIn, signUp, signOut, signInWithGoogle }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
