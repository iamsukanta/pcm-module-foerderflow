/** Auth/session types — mirror the backend GET /api/protected/me envelope. */

export type OrgRole = "ADMIN" | "FINANCE" | "READONLY";

export interface Membership {
  org_id: string;
  org_name: string;
  role: OrgRole;
  created_at: string;
}

export interface Me {
  id: string;
  email: string;
  name: string | null;
  vorname: string | null;
  nachname: string | null;
  is_super_admin: boolean;
  memberships: Membership[];
}

/** Resolved session for a server component (mirrors monolith requireOrgSession). */
export interface OrgSession {
  user: Me;
  membership: Membership;
  org: { id: string; name: string };
}
