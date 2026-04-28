/**
 * Next.js Route Handler: DELETE /api/v1/account
 * Proxies to FastAPI DELETE /api/v1/account — hard-deletes all user data (GDPR Art. 17).
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function DELETE(req: NextRequest) {
  const authHeader = req.headers.get("authorization");
  if (!authHeader) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  let backendRes: Response;
  try {
    backendRes = await fetch(`${BACKEND_URL}/api/v1/account`, {
      method: "DELETE",
      headers: { Authorization: authHeader },
    });
  } catch {
    return NextResponse.json({ detail: "Service unavailable" }, { status: 503 });
  }

  if (backendRes.status === 204) {
    return new NextResponse(null, { status: 204 });
  }

  const data = await backendRes.json();
  return NextResponse.json(data, { status: backendRes.status });
}
