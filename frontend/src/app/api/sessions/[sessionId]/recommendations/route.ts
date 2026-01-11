import type { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_INTERNAL_URL || "http://backend:8000";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  try {
    const { sessionId } = await params;
    const response = await fetch(
      `${BACKEND_URL}/api/sessions/${sessionId}/recommendations`,
    );

    const text = await response.text();
    let data: unknown;
    try {
      data = JSON.parse(text);
    } catch {
      console.error("Backend returned non-JSON response:", text);
      return new Response(
        JSON.stringify({ detail: "Backend returned invalid response" }),
        {
          status: 502,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

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
