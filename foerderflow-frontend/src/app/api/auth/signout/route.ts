/**
 * GET/POST /api/auth/signout — clears the session cookies and returns to /login.
 * GET is supported so the sidebar can use a plain <a href> like the monolith.
 */
import { NextRequest, NextResponse } from "next/server";

import { ORG_COOKIE, requestOrigin, serverFetchRaw, TOKEN_COOKIE } from "@/lib/serverApi";

async function handle(req: NextRequest) {
  // Best-effort backend notify (stateless JWT — purely for parity).
  try {
    await serverFetchRaw("/auth/signout", { method: "POST" });
  } catch {
    /* ignore */
  }
  const response = NextResponse.redirect(new URL("/login", requestOrigin(req)));
  response.cookies.delete(TOKEN_COOKIE);
  response.cookies.delete(ORG_COOKIE);
  return response;
}

export const GET = handle;
export const POST = handle;
