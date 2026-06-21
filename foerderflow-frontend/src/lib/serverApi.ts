/**
 * Server-side fetch to the FastAPI backend (BFF layer).
 *
 * Attaches the JWT (httpOnly `ff_token` cookie, set after magic-link verify) as a
 * Bearer token and the selected org (`selected_org_id` cookie) as the `X-Org-Id`
 * header the backend's get_org_context expects. Only usable from Server Components,
 * Server Actions and Route Handlers.
 */
import { cookies } from "next/headers";

export const TOKEN_COOKIE = "ff_token";
export const ORG_COOKIE = "selected_org_id";

const INTERNAL_BASE = (
  process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000/api"
).replace(/\/$/, "");

/**
 * Browser-facing origin for redirects. Derives from the (forwarded) Host header
 * the client actually used, not the server's bound address — `next start` inside
 * a container otherwise reports `http://0.0.0.0:3000` which a browser can't follow.
 */
export function requestOrigin(req: {
  headers: Headers;
  nextUrl: { origin: string };
}): string {
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host");
  if (host) {
    const proto = req.headers.get("x-forwarded-proto") ?? "http";
    return `${proto}://${host}`;
  }
  return req.nextUrl.origin;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string | null,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface ServerFetchOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  /** Override the org id (defaults to the selected_org_id cookie). */
  orgId?: string | null;
  /** Skip attaching the Authorization header (public endpoints). */
  anonymous?: boolean;
}

/** Raw fetch — returns the Response so callers can stream/inspect status. */
export async function serverFetchRaw(
  path: string,
  opts: ServerFetchOptions = {},
): Promise<Response> {
  const { body, orgId, anonymous, headers, ...rest } = opts;
  const store = await cookies();

  const finalHeaders = new Headers(headers);
  if (!anonymous) {
    const token = store.get(TOKEN_COOKIE)?.value;
    if (token) finalHeaders.set("Authorization", `Bearer ${token}`);
  }
  const resolvedOrg = orgId !== undefined ? orgId : store.get(ORG_COOKIE)?.value;
  if (resolvedOrg) finalHeaders.set("X-Org-Id", resolvedOrg);

  let serializedBody: BodyInit | undefined;
  if (body !== undefined && body !== null) {
    if (body instanceof FormData || typeof body === "string") {
      serializedBody = body as BodyInit;
    } else {
      finalHeaders.set("Content-Type", "application/json");
      serializedBody = JSON.stringify(body);
    }
  }

  return fetch(`${INTERNAL_BASE}${path}`, {
    ...rest,
    headers: finalHeaders,
    body: serializedBody,
    cache: "no-store",
  });
}

/** Parsed JSON fetch — unwraps the `{data}` envelope, throws ApiError on failure. */
export async function serverFetch<T = unknown>(
  path: string,
  opts: ServerFetchOptions = {},
): Promise<T> {
  const res = await serverFetchRaw(path, opts);
  const text = await res.text();
  const json = text ? JSON.parse(text) : {};

  if (!res.ok) {
    throw new ApiError(
      res.status,
      json?.code ?? null,
      json?.error ?? json?.detail ?? res.statusText,
    );
  }
  // Backend wraps successful payloads in { data: ... } (most routes); some return
  // the object directly — return data when present, else the whole body.
  return (json && typeof json === "object" && "data" in json ? json.data : json) as T;
}
