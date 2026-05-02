/**
 * Next.js Route Handler: GET /api/v1/dashboard/summary
 *
 * Proxies to FastAPI GET /api/v1/dashboard/summary, forwarding the Supabase
 * JWT. This is the single endpoint backing the dashboard — replaces the
 * previous /insights + /journal pair on page load.
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function GET(req: NextRequest) {
  const authHeader = req.headers.get("authorization");
  if (!authHeader) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  let backendRes: Response;
  try {
    backendRes = await fetch(`${BACKEND_URL}/api/v1/dashboard/summary`, {
      method: "GET",
      headers: {
        "Authorization": authHeader,
        "Content-Type": "application/json",
      },
      signal: AbortSignal.timeout(25_000),
    });
  } catch {
    return NextResponse.json({ detail: "Service unavailable" }, { status: 503 });
  }

  const data = await backendRes.json();
  return NextResponse.json(data, { status: backendRes.status });
}
