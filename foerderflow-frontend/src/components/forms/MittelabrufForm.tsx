"use client";

import { useState, useEffect } from "react";
import { useToast } from "@/components/ui/ToastProvider";

type FoerdermassnahmeOption = {
  id: string;
  name: string;
  funder: { name: string };
};

type HaushaltsjahreOption = {
  id: string;
  jahr: number;
};

type ComplianceInfo = {
  active: boolean;
  hoechstbetrag: number;
  abgerufen: number;
  drittmittel_ist: number;
  eigenmittel_ist: number;
  eigenmittel_plan: number;
  verbleibend: number;
  status: "OK" | "HINWEIS" | "WARNUNG";
};

function formatEur(n: number): string {
  return new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(n);
}

type Props = {
  onSuccess?: () => void;
};

export function MittelabrufForm({ onSuccess }: Props) {
  const { success, error } = useToast();
  const [massnahmen, setMassnahmen] = useState<FoerdermassnahmeOption[]>([]);
  const [haushaltsjahre, setHaushaltsjahre] = useState<HaushaltsjahreOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [fristModus, setFristModus] = useState<"standard" | "individuell">("standard");
  const [compliance, setCompliance] = useState<ComplianceInfo | null>(null);
  const [betragError, setBetragError] = useState<string | null>(null);

  const [form, setForm] = useState({
    funding_measure_id: "",
    fiscal_year_id: "",
    abruf_datum: "",
    betrag: "",
    verwendungsfrist_tage: "42",
    notiz: "",
  });

  useEffect(() => {
    fetch("/api/protected/foerdermassnahmen")
      .then((r) => r.json())
      .then((j) => {
        const active = (j.data as Array<FoerdermassnahmeOption & { status: string }>).filter(
          (m) => m.status === "AKTIV",
        );
        setMassnahmen(active);
      })
      .catch(() => error("Fördermassnahmen konnten nicht geladen werden."));

    fetch("/api/protected/haushaltsjahre")
      .then((r) => r.json())
      .then((j) => {
        const open = (j.data as (HaushaltsjahreOption & { status: string })[]).filter(
          (y) => y.status === "OFFEN",
        );
        setHaushaltsjahre(open);
      })
      .catch(() => error("Haushaltsjahre konnten nicht geladen werden."));
  }, [error]);

  // Compliance-Status nachladen, wenn Maßnahme gewählt wird.
  useEffect(() => {
    if (!form.funding_measure_id) {
      setCompliance(null);
      return;
    }
    fetch(`/api/protected/foerdermassnahmen/${form.funding_measure_id}/fehlbedarf-status`)
      .then((r) => (r.ok ? r.json() : null))
      .then((j: { data?: { status: ComplianceInfo } } | null) => {
        const data = j?.data;
        if (!data) {
          setCompliance(null);
          return;
        }
        setCompliance(data.status);
      })
      .catch(() => setCompliance(null));
  }, [form.funding_measure_id]);

  // Inline-Validation gegen verbleibend abrufbar
  useEffect(() => {
    if (!compliance || !compliance.active || !form.betrag) {
      setBetragError(null);
      return;
    }
    const b = parseFloat(form.betrag);
    if (isNaN(b)) {
      setBetragError(null);
      return;
    }
    if (b > compliance.verbleibend) {
      setBetragError(
        `Beantragter Betrag überschreitet verbleibend abrufbaren Betrag von ${formatEur(compliance.verbleibend)} (ANBest-P §2.2).`,
      );
    } else {
      setBetragError(null);
    }
  }, [form.betrag, compliance]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const body: Record<string, unknown> = {
        funding_measure_id: form.funding_measure_id,
        fiscal_year_id: form.fiscal_year_id,
        abruf_datum: form.abruf_datum,
        betrag: parseFloat(form.betrag),
        notiz: form.notiz || undefined,
      };
      if (fristModus === "individuell") {
        body.verwendungsfrist_tage = parseInt(form.verwendungsfrist_tage, 10);
      }

      const res = await fetch("/api/protected/mittelabrufe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const json = await res.json();
      if (!res.ok) {
        error(json.error ?? "Fehler beim Anlegen.");
        return;
      }
      success("Mittelabruf erfolgreich angelegt.");
      onSuccess?.();
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-soft-ink2 mb-1">Fördermassnahme *</label>
        <select
          required
          value={form.funding_measure_id}
          onChange={(e) => setForm((f) => ({ ...f, funding_measure_id: e.target.value }))}
          className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
        >
          <option value="">— bitte wählen —</option>
          {massnahmen.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name} ({m.funder.name})
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-soft-ink2 mb-1">Haushaltsjahr *</label>
        <select
          required
          value={form.fiscal_year_id}
          onChange={(e) => setForm((f) => ({ ...f, fiscal_year_id: e.target.value }))}
          className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
        >
          <option value="">— bitte wählen —</option>
          {haushaltsjahre.map((y) => (
            <option key={y.id} value={y.id}>
              {y.jahr}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-soft-ink2 mb-1">Abruf-Datum *</label>
        <input
          type="date"
          required
          value={form.abruf_datum}
          onChange={(e) => setForm((f) => ({ ...f, abruf_datum: e.target.value }))}
          className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-soft-ink2 mb-1">Betrag (€) *</label>
        <input
          type="number"
          required
          min="0.01"
          step="0.01"
          value={form.betrag}
          onChange={(e) => setForm((f) => ({ ...f, betrag: e.target.value }))}
          placeholder="0,00"
          aria-invalid={betragError ? true : undefined}
          aria-describedby={
            betragError ? "betrag-error" : compliance?.active ? "betrag-hint" : undefined
          }
          className={`w-full border rounded-soft-xs px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent ${
            betragError ? "border-soft-crit" : "border-soft-line"
          }`}
        />
        {compliance?.active && !betragError && (
          <div
            id="betrag-hint"
            className="mt-2 rounded-soft-xs bg-soft-surfaceAlt border border-soft-line2 p-2 text-xs text-soft-ink3 space-y-0.5"
          >
            <div className="flex justify-between">
              <span>Höchstbetrag laut Bescheid:</span>
              <span className="numeric text-soft-ink2">{formatEur(compliance.hoechstbetrag)}</span>
            </div>
            <div className="flex justify-between">
              <span>− bereits abgerufen:</span>
              <span className="numeric text-soft-ink2">{formatEur(compliance.abgerufen)}</span>
            </div>
            {compliance.drittmittel_ist > 0 && (
              <div className="flex justify-between">
                <span>− Drittmittel (heuristisch):</span>
                <span className="numeric text-soft-ink2">
                  {formatEur(compliance.drittmittel_ist)}
                </span>
              </div>
            )}
            {compliance.eigenmittel_ist > compliance.eigenmittel_plan && (
              <div className="flex justify-between">
                <span>− Eigenmittel-Mehr-Einnahmen:</span>
                <span className="numeric text-soft-ink2">
                  {formatEur(compliance.eigenmittel_ist - compliance.eigenmittel_plan)}
                </span>
              </div>
            )}
            <div className="flex justify-between border-t border-soft-line2 pt-1 mt-1 font-medium">
              <span>Verbleibend abrufbar:</span>
              <span className="numeric text-soft-ink">{formatEur(compliance.verbleibend)}</span>
            </div>
          </div>
        )}
        {betragError && (
          <p id="betrag-error" role="alert" className="mt-2 text-xs text-soft-crit">
            {betragError}
          </p>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium text-soft-ink2 mb-1">Verwendungsfrist</label>
        <div className="flex gap-4 mb-2">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              value="standard"
              checked={fristModus === "standard"}
              onChange={() => setFristModus("standard")}
            />
            Standard (42 Tage)
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              value="individuell"
              checked={fristModus === "individuell"}
              onChange={() => setFristModus("individuell")}
            />
            Individuell
          </label>
        </div>
        {fristModus === "individuell" && (
          <input
            type="number"
            min="1"
            max="180"
            value={form.verwendungsfrist_tage}
            onChange={(e) => setForm((f) => ({ ...f, verwendungsfrist_tage: e.target.value }))}
            className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
            placeholder="Tage"
          />
        )}
      </div>

      <div>
        <label className="block text-sm font-medium text-soft-ink2 mb-1">Notiz (optional)</label>
        <textarea
          value={form.notiz}
          onChange={(e) => setForm((f) => ({ ...f, notiz: e.target.value }))}
          rows={3}
          className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
        />
      </div>

      <button
        type="submit"
        disabled={loading || !!betragError}
        className="w-full bg-soft-accent text-white py-2 px-4 rounded-soft-xs text-sm font-medium hover:bg-soft-accentDark disabled:opacity-50 transition-colors"
      >
        {loading ? "Speichere…" : "Mittelabruf anlegen"}
      </button>
    </form>
  );
}
