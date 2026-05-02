/**
 * Next.js Route Handler: GET /api/v1/account/export
 * Proxies to FastAPI GET /api/v1/account/export — returns all user data as JSON (GDPR Art. 15/20).
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
    backendRes = await fetch(`${BACKEND_URL}/api/v1/account/export`, {
      method: "GET",
      headers: { Authorization: authHeader },
      signal: AbortSignal.timeout(25_000),
    });
  } catch {
    return NextResponse.json({ detail: "Service unavailable" }, { status: 503 });
  }

  // Read body as text first — the backend may return plain-text errors (e.g. 500)
  // rather than JSON when an unhandled exception escapes its middleware stack.
  const text = await backendRes.text();

  if (!backendRes.ok) {
    // Attempt to surface a useful error detail; fall back to the raw text.
    let detail = text.trim();
    try {
      const parsed = JSON.parse(text);
      detail = parsed?.detail ?? detail;
    } catch { /* keep raw text */ }
    return NextResponse.json(
      { detail: detail || `Export failed (${backendRes.status})` },
      { status: backendRes.status },
    );
  }

  // Success — pipe the JSON through as a downloadable file.
  return new NextResponse(text, {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      "Content-Disposition": `attachment; filename="moodmap_export.json"`,
    },
  });
}
