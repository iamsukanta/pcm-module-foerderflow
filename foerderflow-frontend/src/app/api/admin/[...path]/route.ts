/**
 * Catch-all BFF proxy for /api/admin/* → FastAPI backend /admin/*.
 *
 * The backend admin routes are super-admin gated (require_super_admin) and
 * cross-org. Same mechanics as the /api/protected proxy: inject the JWT
 * (httpOnly `ff_token` cookie) as Bearer, relay the response verbatim.
 */
import { NextRequest } from "next/server";
import { cookies } from "next/headers";

import { ORG_COOKIE, TOKEN_COOKIE } from "@/lib/serverApi";

const INTERNAL_BASE = (
  process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000/api"
).replace(/\/$/, "");

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

  const search = req.nextUrl.search;
  const url = `${INTERNAL_BASE}/admin/${segments.map(encodeURIComponent).join("/")}${search}`;

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

  const respHeaders = new Headers();
  const ct = upstream.headers.get("content-type");
  if (ct) respHeaders.set("content-type", ct);
  const cd = upstream.headers.get("content-disposition");
  if (cd) respHeaders.set("content-disposition", cd);

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
