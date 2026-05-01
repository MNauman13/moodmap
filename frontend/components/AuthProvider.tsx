'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import type { Session } from '@supabase/supabase-js'

interface AuthContextType {
    session: Session | null
    isLoading: boolean
}

const AuthContext = createContext<AuthContextType>({ session: null, isLoading: true })

/**
 * Provides the Supabase session to the component tree.
 *
 * Routing is handled entirely by proxy.ts (server-side). This component
 * does NOT redirect — doing so would race with the proxy and create redirect
 * loops. Its only job is to keep `session` in sync and to flush any
 * pending consent that was stored in localStorage during signup.
 */
export default function AuthProvider({ children }: { children: React.ReactNode }) {
    const [session, setSession] = useState<Session | null>(null)
    const [isLoading, setIsLoading] = useState(true)

    useEffect(() => {
        // Seed state from the current cookie-backed session, then flush any
        // pending consent recorded during signup (before email was confirmed).
        supabase.auth.getSession().then(({ data: { session } }) => {
            setSession(session)
            setIsLoading(false)
            if (session) applyPendingConsent(session)
        })

        // Keep state in sync across tab focus, token refreshes, sign-out, etc.
        // Also flush pending consent on the SIGNED_IN event so new accounts
        // get their consent recorded on the very first login.
        const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
            setSession(session)
            if (session && event === 'SIGNED_IN') applyPendingConsent(session)
        })

        return () => subscription.unsubscribe()
    }, [])

    if (isLoading) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-[#0e0d0b]">
                <div className="flex flex-col items-center gap-4">
                    <div className="h-6 w-6 animate-spin rounded-full border-2 border-[#1a1815] border-t-[#c8a96e]"></div>
                    <p className="font-['Lora'] text-[13px] text-[#6b6357] animate-pulse">
                        Authenticating...
                    </p>
                </div>
            </div>
        )
    }

    return (
        <AuthContext.Provider value={{ session, isLoading }}>
            {children}
        </AuthContext.Provider>
    )
}

export const useAuth = () => useContext(AuthContext)

/**
 * If the user granted consent during signup (before their email was
 * confirmed and a session existed), we stored the intent in localStorage.
 * This function picks that up and POSTs it to the backend on first login.
 * Non-fatal: if it fails, the user can enable consent in Account Settings.
 */
async function applyPendingConsent(session: Session): Promise<void> {
    if (localStorage.getItem('moodmap_pending_consent') !== 'true') return
    try {
        await fetch('/api/v1/account/consent', {
            method: 'POST',
            headers: {
                Authorization: `Bearer ${session.access_token}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ consent_given: true }),
        })
        localStorage.removeItem('moodmap_pending_consent')
    } catch {
        // Non-fatal — user can re-enable consent in Account Settings
    }
}
