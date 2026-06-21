/**
 * POST /api/org/select — set the active org cookie (X-Org-Id source) and confirm.
 * Body: { org_id }. The client then navigates to /dashboard.
 */
import { NextRequest, NextResponse } from "next/server";

import { getMe } from "@/lib/session";
import { ORG_COOKIE } from "@/lib/serverApi";

export async function POST(req: NextRequest) {
  let orgId: string | undefined;
  try {
    const body = (await req.json()) as { org_id?: string };
    orgId = body.org_id;
  } catch {
    return NextResponse.json({ error: "Ungültige Anfrage." }, { status: 400 });
  }

  const me = await getMe();
  if (!me) return NextResponse.json({ error: "Nicht angemeldet." }, { status: 401 });
  if (!orgId || !me.memberships.some((m) => m.org_id === orgId)) {
    return NextResponse.json({ error: "Organisation nicht gefunden." }, { status: 404 });
  }

  const response = NextResponse.json({ ok: true });
  response.cookies.set(ORG_COOKIE, orgId, {
    httpOnly: true,
    sameSite: "lax",
    // Mirror the auth cookie: opt out of Secure for HTTP-only deployments.
    secure: process.env.COOKIE_SECURE !== "false",
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });
  return response;
}
