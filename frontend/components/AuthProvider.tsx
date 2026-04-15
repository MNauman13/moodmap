'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import type { Session } from '@supabase/supabase-js'

// The routes that do NOT require authentication
const PUBLIC_ROUTES = ['/login', '/signup', '/']

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

    useEffect(() => {
        let mounted = true

        // 1. Check initial session
        const initializeAuth = async () => {
            const { data: { session } } = await supabase.auth.getSession()
            if (mounted) {
                setSession(session)
                setIsLoading(false)
                handleRouting(session, pathname)
            }
        }

        initializeAuth()

        // 2. Listen for auth changes (e.g., logging in, logging out, token refresh)
        const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
            if (mounted) {
                setSession(session)
                handleRouting(session, pathname)
            }
        })

        return () => {
            mounted = false
            subscription.unsubscribe()
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [pathname])

    // 3. The Routing Logic
    const handleRouting = (currentSession: Session | null, currentPath: string) => {
        const isPublicRoute = PUBLIC_ROUTES.includes(currentPath)

        if (!currentSession && !isPublicRoute) {
            // Not logged in, trying to access a private page -> send to login
            router.replace('/login')
        } else if (currentSession && isPublicRoute && currentPath !== '/') {
            // Logged in, trying to access login/signup -> send to dashboard
            // (We allow '/' if you have a marketing landing page, otherwise remove `&& currentPath !== '/'`)
            router.replace('/dashboard')
        }
    }

    // 4. The Loading Screen
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