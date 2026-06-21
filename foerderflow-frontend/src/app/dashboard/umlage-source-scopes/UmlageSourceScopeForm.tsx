"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/ToastProvider";

type CostCenterOption = { id: string; code: string; name: string; typ: string };

type Props = {
  costCenters: CostCenterOption[];
  initial?: {
    id: string;
    name: string;
    beschreibung: string | null;
    cost_center_ids: string[];
  };
};

export function UmlageSourceScopeForm({ costCenters, initial }: Props) {
  const router = useRouter();
  const toast = useToast();
  const [name, setName] = useState(initial?.name ?? "");
  const [beschreibung, setBeschreibung] = useState(initial?.beschreibung ?? "");
  const [selectedKstIds, setSelectedKstIds] = useState<Set<string>>(
    () => new Set(initial?.cost_center_ids ?? []),
  );
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const isEdit = !!initial;

  function toggleKst(id: string) {
    setSelectedKstIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrors({});

    const trimmedName = name.trim();
    const errs: Record<string, string> = {};
    if (!trimmedName) errs.name = "Name ist erforderlich.";
    if (selectedKstIds.size === 0) errs.kst = "Mindestens eine Quell-Kostenstelle wählen.";
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }

    setSubmitting(true);
    try {
      const url = isEdit
        ? `/api/protected/umlage-source-scopes/${initial!.id}`
        : `/api/protected/umlage-source-scopes`;
      const res = await fetch(url, {
        method: isEdit ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: trimmedName,
          beschreibung: beschreibung.trim() || null,
          cost_center_ids: Array.from(selectedKstIds),
        }),
      });
      const json = (await res.json()) as { error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Speichern fehlgeschlagen.");
        setSubmitting(false);
        return;
      }
      toast.success(isEdit ? "Pool aktualisiert." : "Pool wurde angelegt.");
      router.push("/dashboard/umlage-source-scopes");
      router.refresh();
    } catch (e) {
      toast.error(`Netzwerkfehler: ${String(e)}`);
      setSubmitting(false);
    }
  }

  // Gruppierung der KSTs nach Typ für bessere Übersicht
  const kstByTyp = new Map<string, CostCenterOption[]>();
  for (const cc of costCenters) {
    const arr = kstByTyp.get(cc.typ) ?? [];
    arr.push(cc);
    kstByTyp.set(cc.typ, arr);
  }
  const typLabels: Record<string, string> = {
    OVERHEAD: "Verwaltungs-/Overhead-KSTs (typisch für Umlage)",
    PROJECT: "Projekt-KSTs",
    INCOME: "Einnahmen-KSTs",
  };
  // Sortierreihenfolge: OVERHEAD zuerst
  const sortedTypes = Array.from(kstByTyp.keys()).sort((a, b) => {
    if (a === "OVERHEAD") return -1;
    if (b === "OVERHEAD") return 1;
    return a.localeCompare(b);
  });

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Name */}
      <div>
        <label htmlFor="name" className="block text-sm font-medium text-soft-ink2 mb-1">
          Name <span className="text-soft-crit">*</span>
        </label>
        <input
          id="name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="z.B. Geschäftsstelle 2025"
          maxLength={200}
          aria-invalid={!!errors.name}
          className={`w-full rounded-soft-xs border px-3 py-2.5 text-sm bg-white outline-none transition-colors
            focus:ring-2 focus:ring-soft-accent focus:border-soft-accent
            ${errors.name ? "border-soft-crit bg-soft-critSoft" : "border-soft-line"}`}
        />
        {errors.name && (
          <p role="alert" className="mt-1 text-xs text-soft-crit">
            {errors.name}
          </p>
        )}
      </div>

      {/* Beschreibung */}
      <div>
        <label htmlFor="beschreibung" className="block text-sm font-medium text-soft-ink2 mb-1">
          Beschreibung / Begründung des Schlüssels
          <span className="ml-2 text-xs font-normal text-soft-ink4">
            Optional, aber ANBest-P-relevant
          </span>
        </label>
        <textarea
          id="beschreibung"
          value={beschreibung}
          onChange={(e) => setBeschreibung(e.target.value)}
          placeholder="z.B. „Verwaltungs-KSTs der Geschäftsstelle, Aufteilung nach VZÄ-Anteilen der Standorte"
          rows={3}
          className="w-full rounded-soft-xs border border-soft-line bg-white px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-soft-accent"
        />
        <p className="mt-1 text-xs text-soft-ink3">
          Erklärt, welche KSTs warum im Pool sind und nach welchem Schlüssel sie verteilt werden. Bei
          Bescheid-Prüfungen abrufbar.
        </p>
      </div>

      {/* Kostenstellen-Auswahl */}
      <div>
        <label className="block text-sm font-medium text-soft-ink2 mb-2">
          Quell-Kostenstellen <span className="text-soft-crit">*</span>
          <span className="ml-2 text-xs font-normal text-soft-ink4">
            ({selectedKstIds.size} ausgewählt)
          </span>
        </label>
        <p className="text-xs text-soft-ink3 mb-3">
          Buchungen auf diese Kostenstellen werden bei UMLAGE_KOSTENSTELLEN-Pauschalen umgelegt.
        </p>

        {sortedTypes.map((typ) => {
          const list = kstByTyp.get(typ)!;
          return (
            <div key={typ} className="mb-4">
              <p className="text-xs font-semibold text-soft-ink3 uppercase tracking-wide mb-1.5">
                {typLabels[typ] ?? typ}
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-1.5">
                {list.map((cc) => {
                  const checked = selectedKstIds.has(cc.id);
                  return (
                    <label
                      key={cc.id}
                      className={`flex items-center gap-2 rounded-soft-xs border px-2.5 py-1.5 text-xs cursor-pointer transition-colors ${
                        checked
                          ? "border-soft-accent bg-soft-accentSoft text-soft-ink"
                          : "border-soft-line bg-white text-soft-ink2 hover:border-soft-line"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleKst(cc.id)}
                        className="h-3.5 w-3.5 rounded accent-soft-accent"
                      />
                      <span className="numeric font-medium shrink-0">{cc.code}</span>
                      <span className="truncate text-soft-ink4">— {cc.name}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          );
        })}

        {errors.kst && (
          <p role="alert" className="mt-1 text-xs text-soft-crit">
            {errors.kst}
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between border-t border-soft-line2 pt-6">
        <Button
          type="button"
          variant="secondary"
          onClick={() => router.push("/dashboard/umlage-source-scopes")}
        >
          Abbrechen
        </Button>
        <Button type="submit" variant="primary" disabled={submitting}>
          {submitting ? "Wird gespeichert …" : isEdit ? "Speichern" : "Pool anlegen"}
        </Button>
      </div>
    </form>
  );
}
