import { requireSuperAdmin } from "@/lib/session";
import { AdminSidebar } from "@/components/admin/AdminSidebar";

export const dynamic = "force-dynamic";

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const user = await requireSuperAdmin();

  const displayName =
    [user.vorname, user.nachname].filter(Boolean).join(" ") ||
    user.name ||
    user.email ||
    "Super-Admin";

  return (
    <div className="flex h-screen overflow-hidden bg-soft-bg">
      <AdminSidebar displayName={displayName} email={user.email} />
      <main className="flex-1 overflow-y-auto flex flex-col min-w-0">{children}</main>
    </div>
  );
}
