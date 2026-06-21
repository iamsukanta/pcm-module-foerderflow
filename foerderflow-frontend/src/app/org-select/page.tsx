import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { getMe } from "@/lib/session";
import { ORG_COOKIE } from "@/lib/serverApi";
import OrgSelectClient from "./OrgSelectClient";

export default async function OrgSelectPage() {
  const me = await getMe();
  if (!me) redirect("/login");

  // Already chosen a still-valid org → straight to the dashboard.
  const store = await cookies();
  const selectedOrgId = store.get(ORG_COOKIE)?.value;
  if (me.memberships.length > 0 && selectedOrgId) {
    if (me.memberships.some((m) => m.org_id === selectedOrgId)) redirect("/dashboard");
  }

  const orgs = me.memberships.map((m) => ({
    id: m.org_id,
    name: m.org_name,
    role: m.role,
  }));

  const canCreateOrg =
    me.is_super_admin || process.env.ALLOW_SELF_SERVICE === "true";

  return <OrgSelectClient existingOrgs={orgs} canCreateOrg={canCreateOrg} />;
}
