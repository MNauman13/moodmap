import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

type Params = { params: Promise<{ id: string }> };

export async function GET(req: NextRequest, { params }: Params) {
  const authHeader = req.headers.get("authorization");
  if (!authHeader) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;

  let backendRes: Response;
  try {
    backendRes = await fetch(`${BACKEND_URL}/api/v1/journal/${id}`, {
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

export async function DELETE(req: NextRequest, { params }: Params) {
  const authHeader = req.headers.get("authorization");
  if (!authHeader) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;

  let backendRes: Response;
  try {
    backendRes = await fetch(`${BACKEND_URL}/api/v1/journal/${id}`, {
      method: "DELETE",
      headers: { "Authorization": authHeader },
      signal: AbortSignal.timeout(25_000),
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
