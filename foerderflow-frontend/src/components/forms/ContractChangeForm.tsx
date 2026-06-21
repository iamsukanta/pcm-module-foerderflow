"use client";

import { useState, useEffect, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/ToastProvider";

type Props = {
  employeeId: string;
  onSuccess: () => void;
  onCancel: () => void;
};

type TarifStufe = {
  stufe: number;
  betrag: string;
};

const VERTRAGSART_OPTIONS = [
  { value: "FESTANSTELLUNG", label: "Festanstellung" },
  { value: "MINIJOB", label: "Minijob" },
  { value: "WERKVERTRAG", label: "Werkvertrag" },
  { value: "EHRENAMT", label: "Ehrenamt" },
] as const;

const TARIFWERK_OPTIONS = [
  { value: "", label: "— Manuell —" },
  { value: "TVOEDD", label: "TVöD Bund/Kommunen" },
  { value: "TVOEL", label: "TV-L Länder" },
  { value: "AVR_CARITAS", label: "AVR Caritas" },
  { value: "AVR_DD", label: "AVR Diakonie Deutschland" },
  { value: "INDIVIDUELL", label: "Individuell" },
] as const;

const ENTGELTGRUPPEN = [
  "E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8",
  "E9a", "E9b", "E9c",
  "E10", "E11", "E12", "E13", "E14", "E15",
];

export function ContractChangeForm({ employeeId, onSuccess, onCancel }: Props) {
  const toast = useToast();

  const [vertragsart, setVertragsart] = useState("FESTANSTELLUNG");
  const [assignedHours, setAssignedHours] = useState(40);
  const [tarifwerk, setTarifwerk] = useState("");
  const [entgeltgruppe, setEntgeltgruppe] = useState("");
  const [stufe, setStufe] = useState<number | "">("");
  const [baseSalary, setBaseSalary] = useState<number | "">("");
  const [gueltigAb, setGueltigAb] = useState("");
  const [notiz, setNotiz] = useState("");

  const [tarifStufen, setTarifStufen] = useState<TarifStufe[]>([]);
  const [loadingTarif, setLoadingTarif] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const isTarifworkWithTable = tarifwerk && tarifwerk !== "" && tarifwerk !== "INDIVIDUELL";

  // Load tarif data
  useEffect(() => {
    if (!isTarifworkWithTable || !entgeltgruppe) {
      setTarifStufen([]);
      return;
    }
    const controller = new AbortController();
    setLoadingTarif(true);

    fetch(
      `/api/protected/tarif?tarifwerk=${tarifwerk}&entgeltgruppe=${entgeltgruppe}&jahr=2025`,
      { signal: controller.signal }
    )
      .then((res) => res.json() as Promise<{ data: TarifStufe[] }>)
      .then((json) => setTarifStufen(json.data ?? []))
      .catch(() => undefined)
      .finally(() => setLoadingTarif(false));

    return () => controller.abort();
  }, [tarifwerk, entgeltgruppe, isTarifworkWithTable]);

  // Auto-fill salary from tarif
  useEffect(() => {
    if (stufe === "") return;
    const row = tarifStufen.find((r) => r.stufe === stufe);
    if (row) setBaseSalary(Number(row.betrag));
  }, [stufe, tarifStufen]);

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!vertragsart) errs.vertragsart = "Vertragsart ist erforderlich.";
    if (!assignedHours || assignedHours <= 0) errs.assignedHours = "Stunden/Woche muss größer als 0 sein.";
    if (baseSalary === "" || Number(baseSalary) < 0) errs.baseSalary = "Grundgehalt ist erforderlich.";
    if (!gueltigAb) errs.gueltigAb = "Gültig ab ist erforderlich.";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setLoading(true);
    try {
      const res = await fetch(`/api/protected/employees/${employeeId}/contracts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vertragsart,
          assigned_hours: assignedHours,
          base_salary: Number(baseSalary),
          tarifwerk: tarifwerk || undefined,
          entgeltgruppe: entgeltgruppe || undefined,
          stufe: stufe !== "" ? stufe : undefined,
          gueltig_ab: gueltigAb,
          notiz: notiz.trim() || undefined,
        }),
      });

      const json = (await res.json()) as { error?: string; message?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Fehler beim Anlegen des Vertrags.");
        return;
      }

      onSuccess();
    } catch {
      toast.error("Netzwerkfehler. Bitte versuche es erneut.");
    } finally {
      setLoading(false);
    }
  };

  const inputClass = (field: string) =>
    `w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors focus:ring-2 focus:ring-soft-accent focus:border-soft-accent ${
      errors[field] ? "border-soft-crit bg-soft-critSoft" : "border-soft-line bg-white"
    }`;

  return (
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
          {errors.vertragsart && <p className="mt-1 text-xs text-soft-crit">{errors.vertragsart}</p>}
        </div>

        {/* Stunden/Woche */}
        <div>
          <label className="block text-sm font-medium text-soft-ink2 mb-1">
            Stunden/Woche <span className="text-soft-crit">*</span>
          </label>
          <input
            type="number"
            value={assignedHours}
            min={0}
            max={168}
            step={0.5}
            onChange={(e) => setAssignedHours(Number(e.target.value))}
            className={inputClass("assignedHours")}
          />
          {errors.assignedHours && <p className="mt-1 text-xs text-soft-crit">{errors.assignedHours}</p>}
        </div>

        {/* Tarifwerk */}
        <div>
          <label className="block text-sm font-medium text-soft-ink2 mb-1">Tarifwerk</label>
          <select
            value={tarifwerk}
            onChange={(e) => {
              setTarifwerk(e.target.value);
              setEntgeltgruppe("");
              setStufe("");
            }}
            className={inputClass("tarifwerk")}
          >
            {TARIFWERK_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
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
          {errors.gueltigAb && <p className="mt-1 text-xs text-soft-crit">{errors.gueltigAb}</p>}
        </div>

        {/* Entgeltgruppe + Stufe */}
        {isTarifworkWithTable && (
          <>
            <div>
              <label className="block text-sm font-medium text-soft-ink2 mb-1">Entgeltgruppe</label>
              <select
                value={entgeltgruppe}
                onChange={(e) => {
                  setEntgeltgruppe(e.target.value);
                  setStufe("");
                  setBaseSalary("");
                }}
                className={inputClass("entgeltgruppe")}
              >
                <option value="">— Gruppe wählen —</option>
                {ENTGELTGRUPPEN.map((g) => (
                  <option key={g} value={g}>{g}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-soft-ink2 mb-1">
                Stufe {loadingTarif && <span className="text-xs text-soft-ink4 ml-1">Laden…</span>}
              </label>
              <select
                value={stufe}
                onChange={(e) => setStufe(e.target.value ? Number(e.target.value) : "")}
                disabled={!entgeltgruppe || tarifStufen.length === 0}
                className={inputClass("stufe")}
              >
                <option value="">— Stufe wählen —</option>
                {tarifStufen.map((r) => (
                  <option key={r.stufe} value={r.stufe}>
                    Stufe {r.stufe} — {Number(r.betrag).toLocaleString("de-DE", { style: "currency", currency: "EUR" })}
                  </option>
                ))}
              </select>
            </div>
          </>
        )}

        {/* Grundgehalt */}
        <div className="col-span-2 sm:col-span-1">
          <label className="block text-sm font-medium text-soft-ink2 mb-1">
            Grundgehalt (€) <span className="text-soft-crit">*</span>
            <span className="ml-1 text-xs font-normal text-soft-ink3">(Vollzeit-Basis)</span>
          </label>
          <input
            type="number"
            value={baseSalary}
            min={0}
            step={0.01}
            onChange={(e) => setBaseSalary(e.target.value ? Number(e.target.value) : "")}
            placeholder="z.B. 3500.00"
            className={inputClass("baseSalary")}
          />
          {errors.baseSalary && <p className="mt-1 text-xs text-soft-crit">{errors.baseSalary}</p>}
        </div>

        {/* Notiz */}
        <div className="col-span-2">
          <label className="block text-sm font-medium text-soft-ink2 mb-1">
            Notiz <span className="text-xs text-soft-ink4">(optional)</span>
          </label>
          <textarea
            value={notiz}
            onChange={(e) => setNotiz(e.target.value)}
            rows={2}
            placeholder="z.B. Stundenerhöhung ab Q2, Tarifrunde 2025…"
            className="w-full rounded-soft-xs border border-soft-line bg-white px-3 py-2.5 text-sm outline-none transition-colors focus:ring-2 focus:ring-soft-accent focus:border-soft-accent resize-none"
          />
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-end gap-3 pt-1">
        <Button type="button" variant="secondary" size="sm" onClick={onCancel} disabled={loading}>
          Abbrechen
        </Button>
        <Button type="submit" variant="primary" size="sm" loading={loading}>
          Vertrag anlegen
        </Button>
      </div>
    </form>
  );
}
