import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const authHeader = req.headers.get("authorization");
  if (!authHeader) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;

  const backendRes = await fetch(
    `${BACKEND_URL}/api/v1/journal/${id}/analysis-status`,
    {
      method: "GET",
      headers: { "Authorization": authHeader },
    }
  );

  const data = await backendRes.json();
  return NextResponse.json(data, { status: backendRes.status });
}
