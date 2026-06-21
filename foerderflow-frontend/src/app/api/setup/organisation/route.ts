/**
 * POST /api/setup/organisation — BFF proxy to the backend setup endpoint.
 * Forwards the authenticated request and relays the backend's {data}/{error} body.
 */
import { NextRequest, NextResponse } from "next/server";

import { serverFetchRaw } from "@/lib/serverApi";

export async function POST(req: NextRequest) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Ungültige Anfrage." }, { status: 400 });
  }

  const res = await serverFetchRaw("/setup/organisation", { method: "POST", body });
  const text = await res.text();
  const json = text ? JSON.parse(text) : {};
  return NextResponse.json(json, { status: res.status });
}
