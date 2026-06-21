"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

type ExistingOrg = {
  id: string;
  name: string;
  rechtsform?: string;
  role: string;
};

const RECHTSFORM_LABELS: Record<string, string> = {
  EV: "e.V.",
  GGMBH: "gGmbH",
  STIFTUNG: "Stiftung",
  ANDERE: "Andere",
};

const ROLE_LABELS: Record<string, string> = {
  ADMIN: "Administrator",
  FINANCE: "Finanzen",
  READONLY: "Lesezugriff",
};

export default function OrgSelectClient({
  existingOrgs,
  canCreateOrg = false,
}: {
  existingOrgs: ExistingOrg[];
  canCreateOrg?: boolean;
}) {
  const router = useRouter();
  const [showCreateForm, setShowCreateForm] = useState(
    existingOrgs.length === 0 && canCreateOrg,
  );
  const [name, setName] = useState("");
  const [rechtsform, setRechtsform] = useState("EV");
  const [regelarbeitszeit, setRegelarbeitszeit] = useState("39");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function selectOrg(orgId: string) {
    // Cookie is httpOnly — set it via the BFF rather than document.cookie.
    const res = await fetch("/api/org/select", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ org_id: orgId }),
    });
    if (res.ok) {
      router.push("/dashboard");
      router.refresh();
    } else {
      setError("Organisation konnte nicht ausgewählt werden.");
    }
  }

  async function handleCreateOrg(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/setup/organisation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          rechtsform,
          regelarbeitszeit_stunden: parseFloat(regelarbeitszeit),
        }),
      });
      const json = (await res.json()) as { data?: { org_id: string }; error?: string };
      if (!res.ok) {
        setError(json.error ?? "Fehler beim Anlegen der Organisation.");
        return;
      }
      await selectOrg(json.data!.org_id);
    } catch {
      setError("Netzwerkfehler — bitte prüfe deine Verbindung.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-soft-bg flex items-center justify-center px-4">
      <div className="bg-soft-surface rounded-soft-sm border border-soft-line p-8 max-w-md w-full shadow-soft space-y-6">
        {existingOrgs.length > 0 && !showCreateForm && (
          <>
            <div>
              <h1 className="text-2xl font-bold text-soft-ink">Organisation wählen</h1>
              <p className="text-sm text-soft-ink3 mt-1">
                Wähle eine Organisation um fortzufahren.
              </p>
            </div>

            <div className="space-y-2">
              {existingOrgs.map((org) => (
                <button
                  key={org.id}
                  onClick={() => selectOrg(org.id)}
                  className="w-full text-left px-4 py-3 rounded-soft-sm border border-soft-line hover:border-soft-accent hover:bg-soft-accentWash transition-colors group"
                >
                  <div className="font-medium text-soft-ink group-hover:text-soft-accent">
                    {org.name}
                  </div>
                  <div className="text-xs text-soft-ink3 mt-0.5">
                    {org.rechtsform
                      ? `${RECHTSFORM_LABELS[org.rechtsform] ?? org.rechtsform} · `
                      : ""}
                    {ROLE_LABELS[org.role] ?? org.role}
                  </div>
                </button>
              ))}
            </div>

            {canCreateOrg && (
              <button
                onClick={() => setShowCreateForm(true)}
                className="w-full text-sm text-soft-accent hover:text-soft-accentDark hover:underline text-center"
              >
                + Neue Organisation anlegen (Super-Admin)
              </button>
            )}
          </>
        )}

        {existingOrgs.length === 0 && !canCreateOrg && (
          <>
            <div>
              <h1 className="text-2xl font-bold text-soft-ink">
                Noch keiner Organisation zugeordnet
              </h1>
              <p className="text-sm text-soft-ink3 mt-2">
                Dein Account ist noch keiner Organisation zugeordnet. VoluLink legt
                Organisationen kontrolliert an — bitte VoluLink kontaktieren, um eine
                Einladung zu erhalten.
              </p>
            </div>
            <a
              href="/api/auth/signout"
              className="block text-center text-sm text-soft-ink3 hover:text-soft-ink hover:underline"
            >
              Abmelden
            </a>
          </>
        )}

        {showCreateForm && (
          <>
            <div>
              <h1 className="text-2xl font-bold text-soft-ink">Organisation einrichten</h1>
              <p className="text-sm text-soft-ink3 mt-1">
                {existingOrgs.length === 0
                  ? "Erstelle deine erste Organisation um loszulegen."
                  : "Lege eine weitere Organisation an."}
              </p>
            </div>

            <form onSubmit={handleCreateOrg} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-soft-ink2 mb-1">
                  Name der Organisation
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  placeholder="z.B. Caritas München e.V."
                  className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm min-h-[44px] focus:outline-none focus:ring-2 focus:ring-soft-accent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-soft-ink2 mb-1">Rechtsform</label>
                <select
                  value={rechtsform}
                  onChange={(e) => setRechtsform(e.target.value)}
                  className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm min-h-[44px] focus:outline-none focus:ring-2 focus:ring-soft-accent"
                >
                  <option value="EV">e.V. (eingetragener Verein)</option>
                  <option value="GGMBH">gGmbH (gemeinnützige GmbH)</option>
                  <option value="STIFTUNG">Stiftung</option>
                  <option value="ANDERE">Andere</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-soft-ink2 mb-1">
                  Regelarbeitszeit (Stunden/Woche)
                </label>
                <input
                  type="number"
                  value={regelarbeitszeit}
                  onChange={(e) => setRegelarbeitszeit(e.target.value)}
                  min="20"
                  max="48"
                  step="0.5"
                  required
                  className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm min-h-[44px] numeric focus:outline-none focus:ring-2 focus:ring-soft-accent"
                />
                <p className="text-xs text-soft-ink3 mt-1">
                  Basis für VZÄ-Berechnung (TVöD typisch: 39h)
                </p>
              </div>

              {error && (
                <p className="text-sm text-soft-crit bg-soft-critSoft border border-soft-crit/20 rounded-soft-xs px-3 py-2">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-soft-accent text-white px-4 py-2.5 rounded-soft-sm text-sm font-medium hover:bg-soft-accentDark transition-colors shadow-soft disabled:opacity-50 min-h-[44px]"
              >
                {loading ? "Wird angelegt…" : "Organisation erstellen & starten"}
              </button>

              {existingOrgs.length > 0 && (
                <button
                  type="button"
                  onClick={() => setShowCreateForm(false)}
                  className="w-full text-sm text-soft-ink3 hover:text-soft-ink hover:underline text-center"
                >
                  Abbrechen
                </button>
              )}
            </form>
          </>
        )}
      </div>
    </main>
  );
}
