/**
 * Next.js Route Handler: GET /api/v1/journal/[id]/analysis-stream
 *
 * Proxies the FastAPI SSE stream to the browser, forwarding the Supabase JWT.
 * Replaces the 3-second polling loop — the server pushes status changes instead.
 */
import { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  const authHeader = req.headers.get("authorization");
  if (!authHeader) {
    return new Response(
      `event: error\ndata: unauthorized\n\n`,
      {
        status: 401,
        headers: { "Content-Type": "text/event-stream" },
      }
    );
  }

  const backendRes = await fetch(
    `${BACKEND_URL}/api/v1/journal/${params.id}/analysis-stream`,
    {
      method: "GET",
      headers: {
        Authorization: authHeader,
        Accept: "text/event-stream",
        "Cache-Control": "no-cache",
      },
    }
  );

  return new Response(backendRes.body, {
    status: backendRes.status,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no",
    },
  });
}
