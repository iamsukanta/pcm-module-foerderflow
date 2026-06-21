"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { useToast } from "@/components/ui/ToastProvider";
import { ShieldCheck, Info } from "lucide-react";

export type ProfilFormProps = {
  email: string;
  initialVorname: string;
  initialNachname: string;
  isSuperAdmin: boolean;
  memberships: {
    org_id: string;
    org_name: string;
    role: "ADMIN" | "FINANCE" | "READONLY";
  }[];
};

const ROLE_LABEL: Record<ProfilFormProps["memberships"][0]["role"], string> = {
  ADMIN: "Org-Admin",
  FINANCE: "Finance",
  READONLY: "Nur-Lese",
};

const ROLE_BADGE_VARIANT: Record<
  ProfilFormProps["memberships"][0]["role"],
  "default" | "muted" | "success"
> = {
  ADMIN: "default",
  FINANCE: "success",
  READONLY: "muted",
};

export function ProfilForm({
  email,
  initialVorname,
  initialNachname,
  isSuperAdmin,
  memberships,
}: ProfilFormProps) {
  const router = useRouter();
  const toast = useToast();
  const [vorname, setVorname] = useState(initialVorname);
  const [nachname, setNachname] = useState(initialNachname);
  const [submitting, setSubmitting] = useState(false);

  const dirty = vorname !== initialVorname || nachname !== initialNachname;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const res = await fetch("/api/protected/me", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vorname: vorname.trim() || null,
          nachname: nachname.trim() || null,
        }),
      });
      const json = (await res.json()) as { error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Speichern fehlgeschlagen.");
        return;
      }
      toast.success("Profil aktualisiert.");
      router.refresh();
    } catch {
      toast.error("Netzwerkfehler beim Speichern.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Editierbarer Bereich */}
      <form
        onSubmit={onSubmit}
        className="bg-white rounded-soft-sm border border-soft-line p-6 space-y-4"
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <label className="block">
            <span className="block text-sm font-medium text-soft-ink2 mb-1">Vorname</span>
            <input
              type="text"
              value={vorname}
              onChange={(e) => setVorname(e.target.value)}
              maxLength={100}
              className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
              placeholder="—"
            />
          </label>
          <label className="block">
            <span className="block text-sm font-medium text-soft-ink2 mb-1">Nachname</span>
            <input
              type="text"
              value={nachname}
              onChange={(e) => setNachname(e.target.value)}
              maxLength={100}
              className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
              placeholder="—"
            />
          </label>
        </div>

        <div className="flex justify-end pt-2">
          <Button type="submit" disabled={!dirty || submitting}>
            {submitting ? "Speichere…" : "Profil speichern"}
          </Button>
        </div>
      </form>

      {/* Read-only Bereich */}
      <div className="bg-white rounded-soft-sm border border-soft-line p-6 space-y-5">
        <div>
          <h2 className="text-sm font-medium text-soft-ink2 mb-1">Email-Adresse</h2>
          <p className="text-soft-ink font-mono">{email}</p>
          <p className="mt-1 text-xs text-soft-ink4 flex items-center gap-1">
            <Info className="h-3 w-3" aria-hidden /> Login-Identität — Änderung nur via Support.
          </p>
        </div>

        {isSuperAdmin && (
          <div>
            <h2 className="text-sm font-medium text-soft-ink2 mb-1">Plattform-Status</h2>
            <Badge variant="default">
              <ShieldCheck className="h-3 w-3" aria-hidden /> VoluLink Super-Admin
            </Badge>
            <p className="mt-1 text-xs text-soft-ink4">
              Cross-Org-Verwaltung. Status wird von einem anderen Super-Admin verwaltet.
            </p>
          </div>
        )}

        <div>
          <h2 className="text-sm font-medium text-soft-ink2 mb-2">
            Mitgliedschaften ({memberships.length})
          </h2>
          {memberships.length === 0 ? (
            <p className="text-sm text-soft-ink3">Du bist aktuell keiner Organisation zugeordnet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-soft-ink3">
                <tr>
                  <th className="pb-2 pr-3">Organisation</th>
                  <th className="pb-2">Rolle</th>
                </tr>
              </thead>
              <tbody>
                {memberships.map((m) => (
                  <tr key={m.org_id} className="border-t border-soft-line2">
                    <td className="py-2 pr-3 text-soft-ink">{m.org_name}</td>
                    <td className="py-2">
                      <Badge variant={ROLE_BADGE_VARIANT[m.role]}>{ROLE_LABEL[m.role]}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="mt-2 text-xs text-soft-ink4">
            Rollen werden vom jeweiligen Org-Admin verwaltet.
          </p>
        </div>
      </div>
    </div>
  );
}
