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
    });
  } catch {
    return NextResponse.json({ detail: "Service unavailable" }, { status: 503 });
  }

  const data = await backendRes.json();

  return new NextResponse(JSON.stringify(data, null, 2), {
    status: backendRes.status,
    headers: {
      "Content-Type": "application/json",
      "Content-Disposition": `attachment; filename="moodmap_export.json"`,
    },
  });
}
