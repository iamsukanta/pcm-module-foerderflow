/**
 * POST /api/auth/magic-link — proxy to the backend magic-link request.
 * Body: { email }. Always returns 202 (no user enumeration), mirroring backend.
 */
import { NextRequest, NextResponse } from "next/server";

import { serverFetchRaw } from "@/lib/serverApi";

export async function POST(req: NextRequest) {
  let email: string | undefined;
  try {
    const body = (await req.json()) as { email?: string };
    email = body.email?.trim();
  } catch {
    return NextResponse.json({ error: "Ungültige Anfrage." }, { status: 400 });
  }

  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return NextResponse.json(
      { error: "Bitte eine gültige E-Mail-Adresse eingeben." },
      { status: 400 },
    );
  }

  const res = await serverFetchRaw("/auth/magic-link", {
    method: "POST",
    anonymous: true,
    body: { email, callback_url: "/dashboard" },
  });

  if (res.status === 429) {
    return NextResponse.json({ error: "TooManyRequests" }, { status: 429 });
  }
  if (!res.ok) {
    return NextResponse.json({ error: "EMAIL_SEND_FAILED" }, { status: 502 });
  }
  return NextResponse.json({ ok: true }, { status: 202 });
}
