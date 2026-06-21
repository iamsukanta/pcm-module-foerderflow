import { requireSuperAdmin } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";
import { UsersClient, type AdminUserRow } from "@/components/admin/UsersClient";

export const dynamic = "force-dynamic";

type UserApiRow = {
  id: string;
  email: string;
  vorname: string | null;
  nachname: string | null;
  is_super_admin: boolean;
  org_count: number;
  letzter_login: string | null;
  memberships: Array<{ org_id: string; org_name: string; role: AdminUserRow["memberships"][number]["role"] }>;
};

export default async function AdminUsersPage() {
  const me = await requireSuperAdmin();

  const users = await serverFetch<UserApiRow[]>("/admin/users");

  const rows: AdminUserRow[] = users.map((u) => ({
    id: u.id,
    email: u.email,
    vorname: u.vorname,
    nachname: u.nachname,
    is_super_admin: u.is_super_admin,
    org_count: u.org_count,
    letzter_login: u.letzter_login,
    memberships: u.memberships.map((m) => ({
      org_id: m.org_id,
      org_name: m.org_name,
      role: m.role,
    })),
  }));

  return (
    <PageShell width="wide">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-soft-ink">User</h1>
        <p className="mt-1 text-sm text-soft-ink3">
          {users.length} User insgesamt. VoluLink Super-Admin-Status hier setzen oder entziehen.
        </p>
      </div>

      <UsersClient rows={rows} myUserId={me.id} />
    </PageShell>
  );
}
