'use client'

import { supabase } from "@/lib/supabase"
import Link from "next/link"
import { useState } from "react"

export default function SignUp() {
    const [email, setEmail]         = useState('')
    const [password, setPassword]   = useState('')
    const [consent, setConsent]     = useState(false)
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError]         = useState<string | null>(null)
    const [confirmed, setConfirmed] = useState(false)

    const handleSignUp = async (e: React.FormEvent) => {
        e.preventDefault()
        setError(null)

        if (!consent) {
            setError("You must accept the data processing terms to create an account.")
            return
        }

        setIsLoading(true)

        const { data, error: signUpError } = await supabase.auth.signUp({
            email,
            password,
            options: {
                emailRedirectTo: `${window.location.origin}/verified`,
            },
        })

        if (signUpError) {
            setError(signUpError.message)
            setIsLoading(false)
            return
        }

        // Record explicit consent immediately after account creation.
        // The session may not be fully established yet (email confirmation pending),
        // so we store the intent in localStorage and apply it on first login via AuthProvider.
        if (data?.user) {
            localStorage.setItem("moodmap_pending_consent", "true")
        }

        setIsLoading(false)
        setConfirmed(true)
    }

    if (confirmed) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-[#0e0d0b] px-4 font-sans">
                <div className="w-full max-w-md rounded-2xl border border-[#1a1815] bg-[#0c0b09] p-8 shadow-2xl text-center">
                    <div className="w-14 h-14 rounded-full border border-[#c8a96e] flex items-center justify-center mx-auto mb-6 text-[#c8a96e] text-2xl">
                        ✉
                    </div>
                    <h2 className="font-['Lora'] text-2xl text-[#c8bfb0] mb-3">Check your inbox</h2>
                    <p className="text-[13px] text-[#6b6357] leading-relaxed mb-6">
                        We&apos;ve sent a confirmation link to <span className="text-[#a09080]">{email}</span>.
                        Click it to verify your account — you&apos;ll be signed in automatically and taken to your dashboard.
                    </p>
                    <Link href="/login" className="text-[13px] text-[#c8a96e] hover:underline underline-offset-4 no-underline">
                        Back to login →
                    </Link>
                </div>
            </div>
        )
    }

    return (
        <div className="flex min-h-screen items-center justify-center bg-[#0e0d0b] px-4 font-sans">
            <div className="w-full max-w-md rounded-2xl border border-[#1a1815] bg-[#0c0b09] p-8 shadow-2xl">

                <div className="mb-8 text-center">
                    <h2 className="font-['Lora'] text-3xl text-[#c8bfb0] mb-2">
                        Join MoodMap
                    </h2>
                    <p className="text-[13px] font-light text-[#6b6357]">
                        Start understanding your emotional landscape.
                    </p>
                </div>

                {error && (
                    <div className="mb-6 rounded-lg border border-[#8a2a2a]/30 bg-[#8a2a2a]/10 p-3 text-center text-[13px] text-[#e8a4a4]">
                        {error}
                    </div>
                )}

                <form onSubmit={handleSignUp} className="space-y-4">
                    <input
                        type="email"
                        placeholder="Email address"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className="w-full rounded-lg border border-[#2a2720] bg-[#141210] p-3.5 text-[14px] text-[#e8e4dc] placeholder-[#4a4438] transition-all focus:border-[#c8a96e] focus:outline-none focus:ring-1 focus:ring-[#c8a96e]"
                        required
                    />
                    <input
                        type="password"
                        placeholder="Create a password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className="w-full rounded-lg border border-[#2a2720] bg-[#141210] p-3.5 text-[14px] text-[#e8e4dc] placeholder-[#4a4438] transition-all focus:border-[#c8a96e] focus:outline-none focus:ring-1 focus:ring-[#c8a96e]"
                        required
                    />

                    {/* GDPR Art. 9 — explicit consent for special-category data */}
                    <label className="flex items-start gap-3 cursor-pointer group">
                        <div className="relative mt-0.5 shrink-0">
                            <input
                                type="checkbox"
                                checked={consent}
                                onChange={(e) => setConsent(e.target.checked)}
                                className="sr-only peer"
                            />
                            <div className={`w-4 h-4 rounded border transition-all ${
                                consent
                                    ? "bg-[#c8a96e] border-[#c8a96e]"
                                    : "bg-[#141210] border-[#2a2720] group-hover:border-[#4a4438]"
                            }`}>
                                {consent && (
                                    <svg className="w-4 h-4 text-[#0e0d0b]" viewBox="0 0 16 16" fill="none">
                                        <path d="M3 8l3.5 3.5 6.5-7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                                    </svg>
                                )}
                            </div>
                        </div>
                        <span className="text-[12px] text-[#6b6357] leading-relaxed">
                            I consent to MoodMap processing my mood, journal, and voice data
                            to provide emotional insights. This data is classified as{" "}
                            <span className="text-[#8a8070]">special-category health data</span>{" "}
                            under GDPR Art. 9. I can withdraw this consent at any time in Account
                            Settings.{" "}
                            <Link href="/account" className="text-[#c8a96e] hover:underline underline-offset-2">
                                Privacy policy
                            </Link>
                        </span>
                    </label>

                    <button
                        type="submit"
                        disabled={isLoading || !consent}
                        className="mt-2 w-full rounded-lg bg-[#c8a96e] p-3.5 text-[14px] font-medium text-[#0e0d0b] transition-all hover:bg-[#b89b60] active:scale-[0.98] disabled:opacity-50 disabled:active:scale-100 disabled:cursor-not-allowed"
                    >
                        {isLoading ? "Creating account…" : "Sign Up"}
                    </button>
                </form>

                <p className="mt-8 text-center text-[13px] text-[#6b6357]">
                    Already have an account?{' '}
                    <Link href="/login" className="text-[#c8a96e] transition-colors hover:text-[#e8e4dc] hover:underline underline-offset-4">
                        Log in
                    </Link>
                </p>
            </div>
        </div>
    )
}
