"use client";

import { useState, useEffect, useCallback, type FormEvent } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/ToastProvider";
import { Settings, Plus } from "lucide-react";
import { PageShell } from "@/components/ui/PageShell";

type AgFaktor = {
  id: string;
  vertragsart: string;
  faktor: string;
  gueltig_ab: string;
  gueltig_bis: string | null;
  notiz: string | null;
};

const VERTRAGSART_OPTIONS = [
  { value: "FESTANSTELLUNG", label: "Festanstellung" },
  { value: "MINIJOB", label: "Minijob" },
  { value: "WERKVERTRAG", label: "Werkvertrag" },
  { value: "EHRENAMT", label: "Ehrenamt" },
] as const;

const VERTRAGSART_LABELS: Record<string, string> = {
  FESTANSTELLUNG: "Festanstellung",
  MINIJOB: "Minijob",
  WERKVERTRAG: "Werkvertrag",
  EHRENAMT: "Ehrenamt",
};

const DEFAULT_FAKTOREN: Record<string, { faktor: string; note: string }> = {
  FESTANSTELLUNG: { faktor: "1.2121", note: "Typisch TVöD" },
  MINIJOB: { faktor: "1.30", note: "Pauschalbeiträge" },
  WERKVERTRAG: { faktor: "1.00", note: "Kein AG-Anteil" },
  EHRENAMT: { faktor: "1.00", note: "Kein AG-Anteil" },
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export default function AgFaktorenPage() {
  const toast = useToast();

  const [faktoren, setFaktoren] = useState<AgFaktor[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);

  // Form state
  const [vertragsart, setVertragsart] = useState("FESTANSTELLUNG");
  const [faktor, setFaktor] = useState<number | "">("");
  const [gueltigAb, setGueltigAb] = useState("");
  const [notiz, setNotiz] = useState("");
  const [formLoading, setFormLoading] = useState(false);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  const loadFaktoren = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/protected/employer-gross-factors");
      if (!res.ok) throw new Error("Fehler.");
      const json = (await res.json()) as { data: AgFaktor[] };
      setFaktoren(json.data);
    } catch {
      toast.error("AG-Faktoren konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void loadFaktoren();
  }, [loadFaktoren]);

  const validateForm = (): boolean => {
    const errs: Record<string, string> = {};
    if (!vertragsart) errs.vertragsart = "Vertragsart ist erforderlich.";
    if (faktor === "" || Number(faktor) <= 0) errs.faktor = "Faktor muss größer als 0 sein.";
    if (!gueltigAb) errs.gueltigAb = "Gültig ab ist erforderlich.";
    setFormErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    setFormLoading(true);
    try {
      const res = await fetch("/api/protected/employer-gross-factors", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vertragsart,
          faktor: Number(faktor),
          gueltig_ab: gueltigAb,
          notiz: notiz.trim() || undefined,
        }),
      });

      const json = (await res.json()) as { error?: string; message?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Fehler beim Anlegen.");
        return;
      }

      toast.success(json.message ?? "AG-Faktor angelegt.");
      setShowForm(false);
      setFaktor("");
      setGueltigAb("");
      setNotiz("");
      void loadFaktoren();
    } catch {
      toast.error("Netzwerkfehler. Bitte versuche es erneut.");
    } finally {
      setFormLoading(false);
    }
  };

  const inputClass = (field: string) =>
    `w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors focus:ring-2 focus:ring-soft-accent focus:border-soft-accent ${
      formErrors[field] ? "border-soft-crit bg-soft-critSoft" : "border-soft-line bg-white"
    }`;

  return (
    <PageShell width="form">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-soft-surfaceAlt rounded-soft-xs">
            <Settings className="h-5 w-5 text-soft-ink2" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-soft-ink">AG-Faktoren Einstellungen</h1>
            <p className="text-sm text-soft-ink3">
              AG-Brutto-Multiplikatoren je Vertragsart und Gültigkeitszeitraum
            </p>
          </div>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setShowForm(!showForm)}
        >
          <Plus className="h-4 w-4 mr-1.5" />
          Neuer Faktor
        </Button>
      </div>

      {/* New factor form */}
      {showForm && (
        <div className="bg-white rounded-soft-sm border border-soft-line p-5 mb-6">
          <h2 className="text-sm font-semibold text-soft-ink mb-4">Neuen AG-Faktor anlegen</h2>
          <form onSubmit={handleSubmit} noValidate className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              {/* Vertragsart */}
              <div>
                <label className="block text-sm font-medium text-soft-ink2 mb-1">
                  Vertragsart <span className="text-soft-crit">*</span>
                </label>
                <select
                  value={vertragsart}
                  onChange={(e) => setVertragsart(e.target.value)}
                  className={inputClass("vertragsart")}
                >
                  {VERTRAGSART_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
                {formErrors.vertragsart && (
                  <p className="mt-1 text-xs text-soft-crit">{formErrors.vertragsart}</p>
                )}
              </div>

              {/* Faktor */}
              <div>
                <label className="block text-sm font-medium text-soft-ink2 mb-1">
                  Faktor <span className="text-soft-crit">*</span>
                </label>
                <input
                  type="number"
                  value={faktor}
                  step={0.0001}
                  min={0.0001}
                  onChange={(e) => setFaktor(e.target.value ? Number(e.target.value) : "")}
                  placeholder="z.B. 1.2121"
                  className={inputClass("faktor")}
                />
                {formErrors.faktor && (
                  <p className="mt-1 text-xs text-soft-crit">{formErrors.faktor}</p>
                )}
              </div>

              {/* Gültig ab */}
              <div>
                <label className="block text-sm font-medium text-soft-ink2 mb-1">
                  Gültig ab <span className="text-soft-crit">*</span>
                </label>
                <input
                  type="date"
                  value={gueltigAb}
                  onChange={(e) => setGueltigAb(e.target.value)}
                  className={inputClass("gueltigAb")}
                />
                {formErrors.gueltigAb && (
                  <p className="mt-1 text-xs text-soft-crit">{formErrors.gueltigAb}</p>
                )}
              </div>

              {/* Notiz */}
              <div>
                <label className="block text-sm font-medium text-soft-ink2 mb-1">
                  Notiz <span className="text-xs text-soft-ink4">(optional)</span>
                </label>
                <input
                  type="text"
                  value={notiz}
                  onChange={(e) => setNotiz(e.target.value)}
                  placeholder="z.B. Tarifrunde 2025"
                  className={inputClass("notiz")}
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-1">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setShowForm(false)}
                disabled={formLoading}
              >
                Abbrechen
              </Button>
              <Button type="submit" variant="primary" size="sm" loading={formLoading}>
                Faktor anlegen
              </Button>
            </div>
          </form>
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div className="py-12 text-center text-soft-ink4 text-sm">Laden…</div>
      ) : faktoren.length === 0 ? (
        <div className="bg-soft-accentSoft border border-soft-accent/20 rounded-soft-sm p-5">
          <p className="text-sm font-medium text-soft-accent mb-2">Noch keine AG-Faktoren angelegt</p>
          <p className="text-xs text-soft-accent mb-3">
            Empfohlene Standardwerte als Orientierung:
          </p>
          <div className="space-y-2">
            {Object.entries(DEFAULT_FAKTOREN).map(([va, { faktor: f, note }]) => (
              <div key={va} className="flex items-center justify-between text-sm">
                <span className="text-soft-accent">{VERTRAGSART_LABELS[va]}</span>
                <span className="font-mono text-soft-accent">{f}</span>
                <span className="text-soft-accent text-xs">{note}</span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-soft-sm border border-soft-line overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-soft-line2 bg-soft-line2">
                <th className="text-left px-4 py-3 font-medium text-soft-ink2 text-xs uppercase tracking-wide">
                  Vertragsart
                </th>
                <th className="text-left px-4 py-3 font-medium text-soft-ink2 text-xs uppercase tracking-wide">
                  Faktor
                </th>
                <th className="text-left px-4 py-3 font-medium text-soft-ink2 text-xs uppercase tracking-wide">
                  Gültig ab
                </th>
                <th className="text-left px-4 py-3 font-medium text-soft-ink2 text-xs uppercase tracking-wide">
                  Gültig bis
                </th>
                <th className="text-left px-4 py-3 font-medium text-soft-ink2 text-xs uppercase tracking-wide">
                  Notiz
                </th>
                <th className="text-left px-4 py-3 font-medium text-soft-ink2 text-xs uppercase tracking-wide">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {faktoren.map((f) => (
                <tr key={f.id}>
                  <td className="px-4 py-3 font-medium text-soft-ink">
                    {VERTRAGSART_LABELS[f.vertragsart] ?? f.vertragsart}
                  </td>
                  <td className="px-4 py-3 font-mono text-soft-ink2">{f.faktor}</td>
                  <td className="px-4 py-3 text-soft-ink2">{formatDate(f.gueltig_ab)}</td>
                  <td className="px-4 py-3 text-soft-ink2">
                    {f.gueltig_bis ? formatDate(f.gueltig_bis) : "–"}
                  </td>
                  <td className="px-4 py-3 text-soft-ink3">{f.notiz ?? "–"}</td>
                  <td className="px-4 py-3">
                    <Badge variant={f.gueltig_bis === null ? "success" : "muted"}>
                      {f.gueltig_bis === null ? "Aktuell" : "Abgelöst"}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </PageShell>
  );
}
