'use client'

import Link from "next/link"
import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { supabase } from "@/lib/supabase"

export default function VerifiedPage() {
    const router = useRouter()
    const [countdown, setCountdown] = useState(4)

    useEffect(() => {
        // Check if they have a session (email confirmed = session issued by Supabase)
        supabase.auth.getSession().then(({ data: { session } }) => {
            if (!session) return // No session — just show the page, let them log in manually

            // Apply any pending consent that was captured during signup.
            // We do this here (rather than relying solely on the AuthProvider
            // SIGNED_IN event) because this page is the guaranteed landing point
            // after email confirmation, so timing is deterministic.
            if (localStorage.getItem('moodmap_pending_consent') === 'true') {
                fetch('/api/v1/account/consent', {
                    method: 'POST',
                    headers: {
                        Authorization: `Bearer ${session.access_token}`,
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ consent_given: true }),
                }).then(res => {
                    if (res.ok) localStorage.removeItem('moodmap_pending_consent')
                }).catch(() => { /* retried by AuthProvider on next sign-in */ })
            }

            // Countdown then redirect to dashboard
            const interval = setInterval(() => {
                setCountdown(prev => {
                    if (prev <= 1) {
                        clearInterval(interval)
                        router.replace("/dashboard")
                    }
                    return prev - 1
                })
            }, 1000)

            return () => clearInterval(interval)
        })
    }, [router])

    return (
        <div className="flex min-h-screen items-center justify-center bg-[#0e0d0b] px-4 font-sans">
            <div className="w-full max-w-md rounded-2xl border border-[#1a1815] bg-[#0c0b09] p-8 shadow-2xl text-center">

                <div className="w-16 h-16 rounded-full border border-[#c8a96e] flex items-center justify-center mx-auto mb-6 text-[#c8a96e] text-3xl">
                    ✓
                </div>

                <h2 className="font-['Lora'] text-2xl text-[#c8bfb0] mb-3">
                    Email verified
                </h2>
                <p className="text-[13px] text-[#6b6357] leading-relaxed mb-8">
                    Your account is confirmed. You&apos;re all set.
                </p>

                {countdown > 0 ? (
                    <p className="text-[12px] text-[#4a4438]">
                        Redirecting to your dashboard in {countdown}…
                    </p>
                ) : null}

                <div className="mt-6">
                    <Link
                        href="/dashboard"
                        className="inline-flex items-center gap-2 px-6 py-2.5 rounded-full bg-[#c8a96e] text-[#0e0d0b] text-[13px] font-medium no-underline transition-all duration-200 hover:bg-[#dbb97e]"
                    >
                        Go to dashboard →
                    </Link>
                </div>

            </div>
        </div>
    )
}
