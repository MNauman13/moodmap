'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import { useRouter, usePathname, useSearchParams } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import type { Session } from '@supabase/supabase-js'

// Routes safe for unauthenticated users. Anything else requires a session.
const PUBLIC_ROUTES = ['/login', '/signup', '/']

// Only allow same-origin paths from the ?next= param to prevent open-redirect.
function safeRedirectTarget(raw: string | null): string {
    if (!raw) return '/dashboard'
    if (!raw.startsWith('/') || raw.startsWith('//')) return '/dashboard'
    return raw
}

interface AuthContextType {
    session: Session | null
    isLoading: boolean
}

const AuthContext = createContext<AuthContextType>({ session: null, isLoading: true })

export default function AuthProvider({ children }: { children: React.ReactNode }) {
    const [session, setSession] = useState<Session | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const router = useRouter()
    const pathname = usePathname()
    const searchParams = useSearchParams()

    useEffect(() => {
        let mounted = true

        const handleRouting = (currentSession: Session | null, currentPath: string) => {
            const isPublicRoute = PUBLIC_ROUTES.includes(currentPath)

            if (!currentSession && !isPublicRoute) {
                // Not logged in trying to access a private page — preserve where they wanted to go
                const next = encodeURIComponent(currentPath)
                router.replace(`/login?next=${next}`)
            } else if (currentSession && isPublicRoute && currentPath !== '/') {
                // Logged in on /login or /signup — bounce them onward
                const target = safeRedirectTarget(searchParams.get('next'))
                router.replace(target)
            }
        }

        const applyPendingConsent = async (session: Session) => {
            const pending = localStorage.getItem("moodmap_pending_consent")
            if (pending !== "true") return
            try {
                await fetch("/api/v1/account/consent", {
                    method: "POST",
                    headers: {
                        Authorization: `Bearer ${session.access_token}`,
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({ consent_given: true }),
                })
                localStorage.removeItem("moodmap_pending_consent")
            } catch {
                // Non-fatal — user can re-enable consent in Account Settings
            }
        }

        const initializeAuth = async () => {
            const { data: { session } } = await supabase.auth.getSession()
            if (mounted) {
                setSession(session)
                setIsLoading(false)
                if (session) await applyPendingConsent(session)
                handleRouting(session, pathname)
            }
        }

        initializeAuth()

        const { data: { subscription } } = supabase.auth.onAuthStateChange(async (_event, session) => {
            if (mounted) {
                setSession(session)
                if (session) await applyPendingConsent(session)
                handleRouting(session, pathname)
            }
        })

        return () => {
            mounted = false
            subscription.unsubscribe()
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [pathname])

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
