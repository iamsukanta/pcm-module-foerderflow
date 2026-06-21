/**
 * GET /api/auth/callback?token=...&callbackUrl=... — magic-link verification.
 *
 * The email link points at /login/verify?token=..., whose server component
 * forwards here. We exchange the token for a JWT at the backend, drop it into an
 * httpOnly cookie, and redirect onward (→ /org-select, which forwards to the
 * dashboard once an org is chosen).
 */
import { NextRequest, NextResponse } from "next/server";

import { requestOrigin, serverFetchRaw, TOKEN_COOKIE } from "@/lib/serverApi";

const COOKIE_MAX_AGE = 60 * 60 * 24; // 24h, matches backend token expiry

export async function GET(req: NextRequest) {
  const token = req.nextUrl.searchParams.get("token");
  const callbackUrl = req.nextUrl.searchParams.get("callbackUrl") || "/org-select";
  const origin = requestOrigin(req);

  if (!token) {
    return NextResponse.redirect(new URL("/login/error?error=Verification", origin));
  }

  const res = await serverFetchRaw(
    `/auth/verify?token=${encodeURIComponent(token)}`,
    { method: "POST", anonymous: true },
  );

  if (!res.ok) {
    return NextResponse.redirect(new URL("/login/error?error=Verification", origin));
  }

  const { access_token } = (await res.json()) as { access_token: string };

  // Land on /org-select so single-org users get auto-forwarded and multi-org
  // users can pick; honor an explicit non-dashboard callback otherwise.
  const target = callbackUrl === "/dashboard" ? "/org-select" : callbackUrl;
  const response = NextResponse.redirect(new URL(target, origin));
  response.cookies.set(TOKEN_COOKIE, access_token, {
    httpOnly: true,
    sameSite: "lax",
    // Secure cookies are dropped by browsers over plain HTTP. Default to secure,
    // but allow opt-out (COOKIE_SECURE=false) for HTTP-only IP/port deployments.
    secure: process.env.COOKIE_SECURE !== "false",
    path: "/",
    maxAge: COOKIE_MAX_AGE,
  });
  return response;
}
