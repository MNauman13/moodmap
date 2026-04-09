'use client'

import { supabase } from "@/lib/supabase"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useState } from "react"

export default function SignUp() {
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [error, setError] = useState<string | null>(null)
    const router = useRouter()

    const handleSignUp = async (e: React.FormEvent) => {
        e.preventDefault()
        setError(null)

        // 1. Send the email and password to Supabase
        const { data, error } = await supabase.auth.signUp({
            email,
            password
        })

        // 2. If Supabase rejects it (e.g. password too short), show an error
        if (error) {
            setError(error.message)
            return
        }

        // 3. If successful, send them to the login page
        if (data) {
            alert("Check your email for the confirmation link!")
            router.push('login')
        }
    }

    return (
        <div className="flex min-h-screen items-center justify-center bg-gray-900">
            <div className="w-full max-w-md rounded-lg bg-gray-800 p-8 shadow-lg">
                <h2 className="mb-6 text-center text-3xl font-bold text-white">
                    Join MoodMap
                </h2>
                {error && <p className="mb-4 text-sm text-red-500">{error}</p>}
                <form onSubmit={handleSignUp} className="space-y-4">
                    <div>
                        <input 
                            type="email"
                            placeholder="Email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="w-full rounded border border-gray-600 bg-gray-700 p-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                            required
                        />
                    </div>
                    <div>
                        <input
                            type="password"
                            placeholder="Password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="w-full rounded border border-gray-600 bg-gray-700 p-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                            required
                        />
                    </div>
                    <button
                        type="submit"
                        className="w-full rounded bg-blue-600 p-3 font-bold text-white transition hover:bg-blue-700"
                    >
                        Sign Up
                    </button>
                </form>

                <p className="mt-4 text-center text-sm text-gray-400">
                    Already have an account? <Link href="/login" className="text-blue-400 hover:underline">Log in</Link>
                </p>
            </div>
        </div>
    )
}