'use client'

import { supabase } from "@/lib/supabase"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useState } from "react"

export default function Login() {
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const router = useRouter()

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault()
        setError(null)
        setIsLoading(true)

        const { error } = await supabase.auth.signInWithPassword({
            email,
            password
        })

        setIsLoading(false)

        if (error) {
            setError(error.message)
            return
        }

        router.push('/dashboard')
    }

    return (
        <div className="flex min-h-screen items-center justify-center bg-[#0e0d0b] px-4 font-sans">
            <div className="w-full max-w-md rounded-2xl border border-[#1a1815] bg-[#0c0b09] p-8 shadow-2xl">
                
                <div className="mb-8 text-center">
                    <h2 className="font-['Lora'] text-3xl text-[#c8bfb0] mb-2">
                        Welcome Back
                    </h2>
                    <p className="text-[13px] font-light text-[#6b6357]">
                        Enter your details to access your journal.
                    </p>
                </div>

                {error && (
                    <div className="mb-6 rounded-lg border border-[#8a2a2a]/30 bg-[#8a2a2a]/10 p-3 text-center text-[13px] text-[#e8a4a4]">
                        {error}
                    </div>
                )}

                <form onSubmit={handleLogin} className="space-y-4">
                    <div>
                        <input 
                            type="email"
                            placeholder="Email address"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="w-full rounded-lg border border-[#2a2720] bg-[#141210] p-3.5 text-[14px] text-[#e8e4dc] placeholder-[#4a4438] transition-all focus:border-[#c8a96e] focus:outline-none focus:ring-1 focus:ring-[#c8a96e]"
                            required
                        />
                    </div>
                    <div>
                        <input
                            type="password"
                            placeholder="Password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="w-full rounded-lg border border-[#2a2720] bg-[#141210] p-3.5 text-[14px] text-[#e8e4dc] placeholder-[#4a4438] transition-all focus:border-[#c8a96e] focus:outline-none focus:ring-1 focus:ring-[#c8a96e]"
                            required
                        />
                    </div>
                    <button
                        type="submit"
                        disabled={isLoading}
                        className="mt-2 w-full rounded-lg bg-[#c8a96e] p-3.5 text-[14px] font-medium text-[#0e0d0b] transition-all hover:bg-[#b89b60] active:scale-[0.98] disabled:opacity-50 disabled:active:scale-100"
                    >
                        {isLoading ? "Signing in..." : "Log In"}
                    </button>
                </form>

                <p className="mt-8 text-center text-[13px] text-[#6b6357]">
                    Don&apos;t have an account?{' '}
                    <Link href="/signup" className="text-[#c8a96e] transition-colors hover:text-[#e8e4dc] hover:underline underline-offset-4">
                        Sign up
                    </Link>
                </p>
            </div>
        </div>
    )
}