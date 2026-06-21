/**
 * Catch-all BFF proxy for /api/protected/* → FastAPI backend.
 *
 * This lets every client component keep calling `/api/protected/...` exactly as
 * the monolith did; the proxy injects the JWT (httpOnly `ff_token` cookie) as a
 * Bearer token and the active org (`selected_org_id` cookie) as `X-Org-Id`, then
 * relays the backend response verbatim — including non-JSON bodies (CSV/PDF/xlsx
 * downloads) and multipart uploads.
 */
import { NextRequest } from "next/server";
import { cookies } from "next/headers";

import { ORG_COOKIE, TOKEN_COOKIE } from "@/lib/serverApi";

const INTERNAL_BASE = (
  process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000/api"
).replace(/\/$/, "");

// Hop-by-hop / problematic headers we must not forward upstream.
const STRIP_REQUEST_HEADERS = new Set([
  "host",
  "connection",
  "content-length",
  "accept-encoding",
]);

async function proxy(req: NextRequest, segments: string[]): Promise<Response> {
  const store = await cookies();
  const token = store.get(TOKEN_COOKIE)?.value;
  const orgId = store.get(ORG_COOKIE)?.value;

  const search = req.nextUrl.search; // includes leading "?" or ""
  const url = `${INTERNAL_BASE}/protected/${segments.map(encodeURIComponent).join("/")}${search}`;

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!STRIP_REQUEST_HEADERS.has(key.toLowerCase())) headers.set(key, value);
  });
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (orgId) headers.set("X-Org-Id", orgId);

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  const body = hasBody ? await req.arrayBuffer() : undefined;

  const upstream = await fetch(url, {
    method: req.method,
    headers,
    body: body && body.byteLength > 0 ? body : undefined,
    cache: "no-store",
    redirect: "manual",
  });

  // Relay status + body + content headers (so downloads/streams pass through).
  const respHeaders = new Headers();
  const ct = upstream.headers.get("content-type");
  const cd = upstream.headers.get("content-disposition");
  const xf = upstream.headers.get("x-filename");
  if (ct) respHeaders.set("content-type", ct);
  if (cd) respHeaders.set("content-disposition", cd);
  // Download filename hint used by client download handlers (e.g. ZIP exports).
  if (xf) respHeaders.set("x-filename", xf);

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: respHeaders,
  });
}

type Ctx = { params: Promise<{ path: string[] }> };

async function handler(req: NextRequest, ctx: Ctx): Promise<Response> {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export const GET = handler;
export const POST = handler;
export const PATCH = handler;
export const PUT = handler;
export const DELETE = handler;
