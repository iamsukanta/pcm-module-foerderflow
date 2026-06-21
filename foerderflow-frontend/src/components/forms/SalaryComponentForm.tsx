"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/ToastProvider";

type Props = {
  /** Full API path, e.g. /api/protected/employees/xxx/contracts/yyy/components */
  apiPath: string;
  onSuccess: () => void;
  onCancel: () => void;
};

const TYP_OPTIONS = [
  { value: "FESTBEZUG", label: "Festbezug" },
  { value: "VWL_AG_ZUSCHUSS", label: "VWL AG-Zuschuss" },
  { value: "JOBTICKET_SACHBEZUG", label: "Jobticket/Sachbezug" },
  { value: "SALARY_ADJUSTMENT", label: "Gehaltsanpassung" },
  { value: "SONSTIGES", label: "Sonstiges" },
] as const;

export function SalaryComponentForm({ apiPath, onSuccess, onCancel }: Props) {
  const toast = useToast();

  const [typ, setTyp] = useState("FESTBEZUG");
  const [bezeichnung, setBezeichnung] = useState("");
  const [betrag, setBetrag] = useState<number | "">("");
  const [nachMultiplikator, setNachMultiplikator] = useState(false);
  const [einmalig, setEinmalig] = useState(false);
  const [giltFuerMonat, setGiltFuerMonat] = useState("");

  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!bezeichnung.trim()) errs.bezeichnung = "Bezeichnung ist erforderlich.";
    if (betrag === "" || !Number.isFinite(Number(betrag))) {
      errs.betrag = "Betrag ist erforderlich.";
    }
    if (einmalig && !giltFuerMonat) {
      errs.giltFuerMonat = "Monat ist erforderlich wenn Einmalig.";
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setLoading(true);
    try {
      const res = await fetch(apiPath, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          typ,
          bezeichnung: bezeichnung.trim(),
          betrag: Number(betrag),
          nach_multiplikator: nachMultiplikator,
          einmalig,
          gilt_fuer_monat: einmalig && giltFuerMonat ? `${giltFuerMonat}-01` : undefined,
        }),
      });

      const json = (await res.json()) as { error?: string; message?: string };

      if (!res.ok) {
        toast.error(json.error ?? "Fehler beim Anlegen der Komponente.");
        return;
      }

      toast.success(json.message ?? "Gehaltskomponente angelegt.");
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
        {/* Typ */}
        <div>
          <label className="block text-sm font-medium text-soft-ink2 mb-1">
            Typ <span className="text-soft-crit">*</span>
          </label>
          <select
            value={typ}
            onChange={(e) => setTyp(e.target.value)}
            className={inputClass("typ")}
          >
            {TYP_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        {/* Betrag */}
        <div>
          <label className="block text-sm font-medium text-soft-ink2 mb-1">
            Betrag (€) <span className="text-soft-crit">*</span>
          </label>
          <input
            type="number"
            value={betrag}
            step={0.01}
            onChange={(e) => setBetrag(e.target.value ? Number(e.target.value) : "")}
            placeholder="z.B. 40.00"
            className={inputClass("betrag")}
          />
          {errors.betrag && <p className="mt-1 text-xs text-soft-crit">{errors.betrag}</p>}
        </div>

        {/* Bezeichnung */}
        <div className="col-span-2">
          <label className="block text-sm font-medium text-soft-ink2 mb-1">
            Bezeichnung <span className="text-soft-crit">*</span>
          </label>
          <input
            type="text"
            value={bezeichnung}
            onChange={(e) => setBezeichnung(e.target.value)}
            maxLength={100}
            placeholder="z.B. VWL, Jobticket, Sonderzulage…"
            className={inputClass("bezeichnung")}
          />
          {errors.bezeichnung && <p className="mt-1 text-xs text-soft-crit">{errors.bezeichnung}</p>}
        </div>
      </div>

      {/* SV-Multiplikator toggle */}
      <fieldset>
        <legend className="block text-sm font-medium text-soft-ink2 mb-2">
          SV-Multiplikator
        </legend>
        <div className="flex gap-3">
          <label
            className={`flex items-center gap-2 rounded-soft-xs border px-4 py-2.5 cursor-pointer text-sm transition-colors ${
              !nachMultiplikator
                ? "border-soft-accent bg-soft-accentSoft text-soft-accent"
                : "border-soft-line text-soft-ink2 hover:border-soft-line"
            }`}
          >
            <input
              type="radio"
              name="multiplikator"
              checked={!nachMultiplikator}
              onChange={() => setNachMultiplikator(false)}
              className="accent-soft-accent"
            />
            Vor SV-Multiplikator
          </label>
          <label
            className={`flex items-center gap-2 rounded-soft-xs border px-4 py-2.5 cursor-pointer text-sm transition-colors ${
              nachMultiplikator
                ? "border-soft-warn bg-soft-warnSoft text-soft-warn"
                : "border-soft-line text-soft-ink2 hover:border-soft-line"
            }`}
          >
            <input
              type="radio"
              name="multiplikator"
              checked={nachMultiplikator}
              onChange={() => setNachMultiplikator(true)}
              className="accent-yellow-600"
            />
            Nach SV-Multiplikator
          </label>
        </div>
        <p className="mt-1.5 text-xs text-soft-ink3">
          {nachMultiplikator
            ? "Wird direkt zum AG-Brutto addiert (z.B. Jobticket-Sachbezug)."
            : "Fließt ins AN-Brutto ein und wird mit AG-Faktor multipliziert."}
        </p>
      </fieldset>

      {/* Einmalig toggle */}
      <div className="flex items-start gap-3">
        <input
          id="einmalig-toggle"
          type="checkbox"
          checked={einmalig}
          onChange={(e) => {
            setEinmalig(e.target.checked);
            if (!e.target.checked) setGiltFuerMonat("");
          }}
          className="mt-0.5 h-4 w-4 accent-soft-accent"
        />
        <div className="flex-1">
          <label htmlFor="einmalig-toggle" className="text-sm font-medium text-soft-ink2 cursor-pointer">
            Einmalig
          </label>
          <p className="text-xs text-soft-ink3 mt-0.5">Gilt nur für einen bestimmten Monat.</p>

          {einmalig && (
            <div className="mt-3">
              <label className="block text-sm font-medium text-soft-ink2 mb-1">
                Monat <span className="text-soft-crit">*</span>
              </label>
              <input
                type="month"
                value={giltFuerMonat}
                onChange={(e) => setGiltFuerMonat(e.target.value)}
                className={inputClass("giltFuerMonat")}
              />
              {errors.giltFuerMonat && (
                <p className="mt-1 text-xs text-soft-crit">{errors.giltFuerMonat}</p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-end gap-3 pt-1">
        <Button type="button" variant="secondary" size="sm" onClick={onCancel} disabled={loading}>
          Abbrechen
        </Button>
        <Button type="submit" variant="primary" size="sm" loading={loading}>
          Komponente anlegen
        </Button>
      </div>
    </form>
  );
}
