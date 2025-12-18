import type { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_INTERNAL_URL || "http://backend:8000";

export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  try {
    const { sessionId } = await params;
    const response = await fetch(
      `${BACKEND_URL}/api/sessions/${sessionId}/reset`,
      {
        method: "POST",
      },
    );

    const data = await response.json();

    return new Response(JSON.stringify(data), {
      status: response.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("Proxy error:", error);
    return new Response(JSON.stringify({ detail: "Internal proxy error" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
}
