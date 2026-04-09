'use client'

import { useState } from 'react'
import { supabase } from '@/lib/supabase'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

export default function Login() {
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [error, setError] = useState<string | null>(null)
    const router = useRouter()

    const handleLogin = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault()
        setError(null)

        // 1. Try to log the user in
        const { error } = await supabase.auth.signInWithPassword({
            email,
            password
        })

        // 2. Handle incorrect password/email
        if (error) {
            setError(error.message)
            return
        }

        // 3. If successful, send them to their dashboard
        router.push('/dashboard')
    }

    return (
    <div className="flex min-h-screen items-center justify-center bg-gray-900">
        <div className="w-full max-w-md rounded-lg bg-gray-800 p-8 shadow-lg">
            <h2 className="mb-6 text-center text-3xl font-bold text-white">Welcome Back</h2>
            
            {error && <p className="mb-4 text-sm text-red-500">{error}</p>}
            
            <form onSubmit={handleLogin} className="space-y-4">
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
                    Log In
                </button>
            </form>
            
            <p className="mt-4 text-center text-sm text-gray-400">
                Don't have an account? <Link href="/signup" className="text-blue-400 hover:underline">Sign up</Link>
            </p>
        </div>
    </div>
    )
}