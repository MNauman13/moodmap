/**
 * Next.js Route Handler: /api/v1/journal/presigned-url
 * Returns a presigned R2 upload URL for direct browser → R2 upload.
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function POST(req: NextRequest) {
    const authHeader = req.headers.get("authorization")

    if (!authHeader) {
        return NextResponse.json({ detail: "Unauthorized" }, { status: 401 })
    }

    const body = await req.json()

    const backendRes = await fetch(`${BACKEND_URL}/api/v1/journal/presigned-url`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": authHeader
        },
        body: JSON.stringify(body)
    })

    const data = await backendRes.json()
    return NextResponse.json(data, { status: backendRes.status })
}