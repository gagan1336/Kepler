/**
 * Supabase browser client — singleton for client-side usage.
 * Used in all auth operations (sign in, sign up, sign out, Google OAuth).
 */
import { createBrowserClient } from '@supabase/ssr'

export const supabase = createBrowserClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)
