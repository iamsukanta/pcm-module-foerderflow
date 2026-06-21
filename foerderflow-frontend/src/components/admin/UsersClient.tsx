"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/Badge";
import { useToast } from "@/components/ui/ToastProvider";
import { ShieldCheck, X } from "lucide-react";

export type AdminUserRow = {
  id: string;
  email: string;
  vorname: string | null;
  nachname: string | null;
  is_super_admin: boolean;
  org_count: number;
  letzter_login: string | null;
  memberships: { org_id: string; org_name: string; role: "ADMIN" | "FINANCE" | "READONLY" }[];
};

const ROLE_LABEL: Record<AdminUserRow["memberships"][0]["role"], string> = {
  ADMIN: "Org-Admin",
  FINANCE: "Finance",
  READONLY: "Nur-Lese",
};

export function UsersClient({ rows, myUserId }: { rows: AdminUserRow[]; myUserId: string }) {
  const router = useRouter();
  const toast = useToast();
  const [drawer, setDrawer] = useState<AdminUserRow | null>(null);
  const [pending, setPending] = useState<string | null>(null);

  async function toggleSuperAdmin(row: AdminUserRow) {
    if (row.id === myUserId && row.is_super_admin) {
      toast.error("Du kannst dir nicht selbst den Super-Admin-Status entziehen.");
      return;
    }
    setPending(row.id);
    try {
      const res = await fetch(`/api/admin/users/${row.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_super_admin: !row.is_super_admin }),
      });
      const json = (await res.json()) as { error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Update fehlgeschlagen.");
        return;
      }
      toast.success(
        !row.is_super_admin
          ? `${row.email} ist jetzt Super-Admin.`
          : `${row.email} ist nicht mehr Super-Admin.`,
      );
      router.refresh();
    } finally {
      setPending(null);
    }
  }

  return (
    <>
      <div className="bg-white rounded-soft-sm border border-soft-line overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-soft-surfaceAlt border-b border-soft-line text-left text-xs uppercase tracking-wide text-soft-ink3">
            <tr>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3 text-right">Orgs</th>
              <th className="px-4 py-3">Letzter Login</th>
              <th className="px-4 py-3 text-center">Super-Admin</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((u) => {
              const display = [u.vorname, u.nachname].filter(Boolean).join(" ");
              const lastLogin = u.letzter_login
                ? new Date(u.letzter_login).toLocaleDateString("de-DE")
                : "—";
              return (
                <tr
                  key={u.id}
                  className="border-b border-soft-line2 last:border-0 hover:bg-soft-surfaceAlt cursor-pointer"
                  onClick={() => setDrawer(u)}
                >
                  <td className="px-4 py-3 font-medium text-soft-ink">{u.email}</td>
                  <td className="px-4 py-3 text-soft-ink2">{display || "—"}</td>
                  <td className="px-4 py-3 text-right numeric">{u.org_count}</td>
                  <td className="px-4 py-3 text-xs text-soft-ink3">{lastLogin}</td>
                  <td className="px-4 py-3 text-center" onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      onClick={() => void toggleSuperAdmin(u)}
                      disabled={pending === u.id || (u.id === myUserId && u.is_super_admin)}
                      role="switch"
                      aria-checked={u.is_super_admin}
                      aria-label={`Super-Admin für ${u.email} ${u.is_super_admin ? "entziehen" : "setzen"}`}
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors disabled:opacity-50 ${
                        u.is_super_admin ? "bg-soft-accent" : "bg-soft-line2"
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          u.is_super_admin ? "translate-x-4" : "translate-x-0.5"
                        }`}
                      />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {drawer && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-end bg-soft-ink/40 p-4"
          onClick={() => setDrawer(null)}
        >
          <div
            className="bg-white rounded-soft border border-soft-line shadow-soft-lg w-full max-w-md max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-soft-line2 px-5 py-4">
              <h2 className="text-base font-semibold text-soft-ink">User-Details</h2>
              <button
                type="button"
                onClick={() => setDrawer(null)}
                className="p-1.5 rounded-soft-xs hover:bg-soft-line2"
                aria-label="Schließen"
              >
                <X className="h-4 w-4 text-soft-ink3" aria-hidden />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <p className="text-xs text-soft-ink3 uppercase tracking-wide mb-1">Email</p>
                <p className="text-sm font-mono text-soft-ink">{drawer.email}</p>
              </div>
              {(drawer.vorname || drawer.nachname) && (
                <div>
                  <p className="text-xs text-soft-ink3 uppercase tracking-wide mb-1">Name</p>
                  <p className="text-sm text-soft-ink">
                    {[drawer.vorname, drawer.nachname].filter(Boolean).join(" ")}
                  </p>
                </div>
              )}
              {drawer.is_super_admin && (
                <div>
                  <Badge variant="default">
                    <ShieldCheck className="h-3 w-3" aria-hidden /> VoluLink Super-Admin
                  </Badge>
                </div>
              )}
              <div>
                <p className="text-xs text-soft-ink3 uppercase tracking-wide mb-2">
                  Mitgliedschaften ({drawer.memberships.length})
                </p>
                {drawer.memberships.length === 0 ? (
                  <p className="text-sm text-soft-ink3">Keine Mitgliedschaft.</p>
                ) : (
                  <ul className="space-y-1.5 text-sm">
                    {drawer.memberships.map((m) => (
                      <li key={m.org_id} className="flex justify-between items-center">
                        <span className="text-soft-ink">{m.org_name}</span>
                        <span className="text-xs text-soft-ink3">{ROLE_LABEL[m.role]}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
