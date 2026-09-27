'use client'
import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from './supabase'
import type { Session, User as SupabaseUser } from '@supabase/supabase-js'
import { apiGetMe } from './api'

// ── App-level User shape (matches backend /auth/me response) ──────────────────
export interface AppUser {
  id: string
  email: string
  plan: 'free' | 'pro' | 'elite'
  trial_end_date: string | null
  created_at: string
}

interface AuthContextType {
  user: AppUser | null
  supabaseUser: SupabaseUser | null
  session: Session | null
  loading: boolean          // true while Supabase session is being resolved
  backendLoading: boolean   // true while backend user profile is being fetched
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<{ needsConfirmation: boolean }>
  loginWithGoogle: () => Promise<void>
  logout: () => Promise<void>
  isAuthenticated: boolean  // true as soon as Supabase session exists
  isPro: boolean
  isElite: boolean
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AppUser | null>(null)
  const [supabaseUser, setSupabaseUser] = useState<SupabaseUser | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)          // Supabase session check
  const [backendLoading, setBackendLoading] = useState(false)  // Backend profile fetch

  // Fetch backend user profile — does NOT affect `loading` or `isAuthenticated`
  const fetchBackendUser = useCallback(async (accessToken: string) => {
    setBackendLoading(true)
    try {
      const appUser = await apiGetMe()
      setUser(appUser)
    } catch (err) {
      console.error('[Auth] Backend user fetch failed:', err)
      // Non-fatal — session is still valid, user just won't have plan info yet
      setUser(null)
    } finally {
      setBackendLoading(false)
    }
  }, [])

  useEffect(() => {
    // 1. Hydrate session on mount — this is the ONLY thing that controls `loading`
    supabase.auth.getSession().then(({ data: { session: initialSession } }) => {
      if (initialSession) {
        setSession(initialSession)
        setSupabaseUser(initialSession.user)
        fetchBackendUser(initialSession.access_token)
      }
      // Always stop loading after session check, regardless of backend
      setLoading(false)
    })

    // 2. Listen for auth state changes (login, logout, token refresh, OAuth callback)
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, newSession) => {
      console.log('[Auth] State change:', event)
      if (newSession) {
        setSession(newSession)
        setSupabaseUser(newSession.user)
        fetchBackendUser(newSession.access_token)
      } else {
        // Signed out
        setSession(null)
        setSupabaseUser(null)
        setUser(null)
      }
    })

    return () => subscription.unsubscribe()
  }, [fetchBackendUser])

  // ── Login with email + password ───────────────────────────────────────────────
  const login = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw new Error(error.message)
    // onAuthStateChange fires automatically and sets session/user
  }

  // ── Register with email + password ────────────────────────────────────────────
  const register = async (email: string, password: string) => {
    const { data, error } = await supabase.auth.signUp({ email, password })
    if (error) throw new Error(error.message)
    const needsConfirmation = !data.session
    return { needsConfirmation }
  }

  // ── Google OAuth (Supabase-managed) ───────────────────────────────────────────
  const loginWithGoogle = async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    })
    if (error) throw new Error(error.message)
  }

  // ── Logout ────────────────────────────────────────────────────────────────────
  const logout = async () => {
    await supabase.auth.signOut()
    setUser(null)
    setSupabaseUser(null)
    setSession(null)
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        supabaseUser,
        session,
        loading,
        backendLoading,
        login,
        register,
        loginWithGoogle,
        logout,
        // isAuthenticated is based on Supabase session, NOT backend user
        isAuthenticated: !!session,
        isPro: user?.plan === 'pro' || user?.plan === 'elite',
        isElite: user?.plan === 'elite',
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

export function withAuth(Component: React.ComponentType<any>) {
  return function ProtectedComponent(props: any) {
    const router = useRouter()
    const { isAuthenticated, loading } = useAuth()

    useEffect(() => {
      if (!loading && !isAuthenticated) {
        router.push('/login')
      }
    }, [loading, isAuthenticated, router])

    if (loading) return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg-base)' }}>
        <div
          className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin"
          style={{ borderColor: 'rgba(201,163,78,0.3)', borderTopColor: '#C9A34E' }}
        />
      </div>
    )

    if (!isAuthenticated) return null
    return <Component {...props} />
  }
}
