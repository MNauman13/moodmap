/**
 * Next.js Route Handler: /api/v1/journal and /api/v1/journal/presigned-url
 *
 * Proxies requests to FastAPI backend, forwarding the Supabase JWT.
 * This keeps the backend URL private and lets us add middleware here later.
 */
import { NextRequest, NextResponse } from "next/server"
import { supabase } from "@/lib/supabase"

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000"

async function proxyToBackend(
    req: NextRequest,
    path: string,
    method: string,
    body?: unknown
) {
    const authHeader = req.headers.get("authorization")
    if (!authHeader) {
        return NextResponse.json({ detail: "Unauthorized" }, { status: 401 })
    }

    const backendRes = await fetch(`${BACKEND_URL}${path}`, {
        method,
        headers: {
            "Content-Type": "application/json",
            "Authorization": authHeader
        },
        body: body ? JSON.stringify(body) : undefined
    })

    const data = await backendRes.json()
    return NextResponse.json(data, { status: backendRes.status })
}

// POST /api/v1/journal - create entry
export async function POST(req: NextRequest) {
    const body = await req.json()
    return proxyToBackend(req, "/api/v1/journal", "POST", body)
}

// GET /api/v1/journal - list entries
export async function GET(req: NextRequest) {
    const { searchParams } = new URL(req.url)
    const page = searchParams.get("page") || "1"
    const pageSize = searchParams.get("page_size") || "10"
    return proxyToBackend(req, `/api/v1/journal?page=${page}&page_size=${pageSize}`, "GET")
}