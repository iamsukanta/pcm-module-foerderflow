import { LogOut } from "lucide-react";

import { SidebarNav } from "@/components/dashboard/SidebarNav";
import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";

async function countKritischeFristen(): Promise<number> {
  try {
    const data = await serverFetch<{ count: number }>("/protected/fristen/kritische-count");
    return data.count ?? 0;
  } catch {
    return 0;
  }
}

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { org, user } = await requireOrgSession();
  const kritischeFristen = await countKritischeFristen();

  return (
    <div className="flex h-screen overflow-hidden bg-soft-bg">
      {/* Sidebar */}
      <aside className="w-64 bg-soft-sidebarBg border-r border-soft-line flex-shrink-0 flex flex-col overflow-y-auto">
        {/* Logo + Org */}
        <div className="p-5 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-soft-xs bg-gradient-to-br from-soft-accent to-soft-accentDark flex items-center justify-center text-white font-semibold text-sm shadow-soft">
              F
            </div>
            <div>
              <div className="text-[15px] font-semibold text-soft-ink -tracking-[0.01em]">
                FörderFlow
              </div>
              <div className="text-[10.5px] text-soft-ink3 -mt-0.5">{org.name}</div>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <SidebarNav
          kritischeFristen={kritischeFristen}
          isSuperAdmin={user.is_super_admin === true}
        />

        {/* User + Logout */}
        <div className="px-4 py-4 border-t border-soft-line">
          <p className="text-xs text-soft-ink3 truncate mb-2">{user.email}</p>
          <a
            href="/api/auth/signout"
            className="flex items-center gap-2 text-xs text-soft-ink2 hover:text-soft-ink transition-colors"
          >
            <LogOut className="h-3.5 w-3.5" />
            Abmelden
          </a>
        </div>
      </aside>

      {/* Hauptbereich */}
      <main className="flex-1 overflow-y-auto flex flex-col min-w-0">{children}</main>
    </div>
  );
}
