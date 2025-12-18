import type { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_INTERNAL_URL || "http://backend:8000";

export async function GET(_request: NextRequest) {
  try {
    const response = await fetch(`${BACKEND_URL}/health`);
    const data = await response.json();

    return new Response(JSON.stringify(data), {
      status: response.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("Proxy error:", error);
    return new Response(
      JSON.stringify({ status: "error", detail: "Backend unreachable" }),
      { status: 503, headers: { "Content-Type": "application/json" } },
    );
  }
}
