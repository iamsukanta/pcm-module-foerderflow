/**
 * Server-side session helpers — BFF port of the monolith lib/session.ts.
 *
 * The monolith read NextAuth + Prisma directly; here we resolve the session by
 * calling the FastAPI backend GET /api/protected/me with the JWT cookie. Org
 * resolution order matches the monolith: explicit orgId → selected_org_id cookie
 * → first membership.
 */
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { Me, OrgRole, OrgSession } from "@/types/auth";
import { ApiError, ORG_COOKIE, serverFetch } from "@/lib/serverApi";

/** Fetch the current user (+memberships), or null if not authenticated. */
export async function getMe(): Promise<Me | null> {
  const store = await cookies();
  if (!store.get("ff_token")?.value) return null;
  try {
    // /me needs an org context header; any membership works. Send the selected
    // org if present so the backend doesn't 403 on the org guard.
    return await serverFetch<Me>("/protected/me");
  } catch (err) {
    if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
      // 403 here means "authenticated but no/!selected org" — still return the
      // user so callers can route to /org-select. Re-fetch without org guard via
      // the dedicated path is unnecessary; /me only needs auth in practice.
      if (err.status === 403) {
        try {
          return await serverFetch<Me>("/protected/me", { orgId: null });
        } catch {
          return null;
        }
      }
      return null;
    }
    throw err;
  }
}

export async function requireOrgSession(options?: {
  orgId?: string;
  requireRole?: OrgRole[];
}): Promise<OrgSession> {
  const me = await getMe();
  if (!me) redirect("/login");
  if (me.memberships.length === 0) redirect("/org-select");

  const store = await cookies();
  let membership = null;

  if (options?.orgId) {
    membership = me.memberships.find((m) => m.org_id === options.orgId) ?? null;
    if (!membership) redirect("/org-select");
  } else {
    const selected = store.get(ORG_COOKIE)?.value;
    if (selected) {
      membership = me.memberships.find((m) => m.org_id === selected) ?? null;
    }
    if (!membership) membership = me.memberships[0];
  }

  if (options?.requireRole && !options.requireRole.includes(membership.role)) {
    redirect("/dashboard?error=INSUFFICIENT_ROLE");
  }

  return {
    user: me,
    membership,
    org: { id: membership.org_id, name: membership.org_name },
  };
}

/** Super-admin guard — redirects non-super-admins to /dashboard (no 403 leak). */
export async function requireSuperAdmin(): Promise<Me> {
  const me = await getMe();
  if (!me) redirect("/login");
  if (!me.is_super_admin) redirect("/dashboard");
  return me;
}
