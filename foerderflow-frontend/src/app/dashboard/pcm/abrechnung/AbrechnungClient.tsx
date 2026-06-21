"use client";

import { useMemo, useState } from "react";
import { Calculator, CheckCircle2, AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { useToast } from "@/components/ui/ToastProvider";
import type { FiscalYearWithMeta } from "@/types/haushaltsjahre";
import type { PayrollDetailLine, PcmEmployee, RunMonatResult } from "@/types/pcm";

const eur = (v: string | number) =>
  new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(Number(v));

function inputCls(): string {
  return `w-full rounded-soft-xs border border-soft-line bg-white px-3 py-2.5 text-sm outline-none
    transition-colors focus:ring-2 focus:ring-soft-accent focus:border-soft-accent`;
}

export function AbrechnungClient({
  fiscalYears,
  employees,
}: {
  fiscalYears: FiscalYearWithMeta[];
  employees: PcmEmployee[];
}) {
  const toast = useToast();
  const empName = useMemo(() => {
    const m = new Map<string, string>();
    for (const e of employees) m.set(e.id, `${e.employee_code} — ${e.vorname} ${e.nachname}`);
    return m;
  }, [employees]);

  const defaultFy = fiscalYears.find((f) => f.status === "OFFEN") ?? fiscalYears[0];
  const [fiscalYearId, setFiscalYearId] = useState(defaultFy?.id ?? "");
  const [month, setMonth] = useState(defaultFy ? `${defaultFy.jahr}-01` : "");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RunMonatResult | null>(null);

  const selectedFy = fiscalYears.find((f) => f.id === fiscalYearId);

  async function handleRun() {
    if (!fiscalYearId || !month) {
      toast.error("Haushaltsjahr und Monat sind erforderlich.");
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch("/api/protected/pcm/payroll/run-monat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fiscal_year_id: fiscalYearId, monat: `${month}-01` }),
      });
      const json = (await res.json().catch(() => ({}))) as {
        data?: RunMonatResult;
        error?: string;
      };
      if (!res.ok || !json.data) {
        toast.error(json.error ?? "Lauf fehlgeschlagen.");
        return;
      }
      setResult(json.data);
      toast.success(
        `${json.data.run_count} berechnet, ${json.data.skipped_count} übersprungen.`,
      );
    } catch {
      toast.error("Netzwerkfehler. Bitte erneut versuchen.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="bg-white rounded-soft border border-soft-line p-6 shadow-soft">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-end">
          <div>
            <label htmlFor="ab-fy" className="block text-sm font-medium text-soft-ink2 mb-1">
              Haushaltsjahr
            </label>
            <select
              id="ab-fy"
              value={fiscalYearId}
              onChange={(e) => {
                setFiscalYearId(e.target.value);
                const fy = fiscalYears.find((f) => f.id === e.target.value);
                if (fy) setMonth(`${fy.jahr}-01`);
              }}
              className={inputCls()}
            >
              {fiscalYears.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.jahr} ({f.status === "OFFEN" ? "offen" : "geschlossen"})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="ab-month" className="block text-sm font-medium text-soft-ink2 mb-1">
              Monat
            </label>
            <input
              id="ab-month"
              type="month"
              value={month}
              onChange={(e) => setMonth(e.target.value)}
              className={inputCls()}
            />
          </div>
          <div>
            <Button variant="primary" onClick={handleRun} loading={loading} className="w-full">
              <Calculator className="h-4 w-4 mr-1" aria-hidden="true" />
              Monatslauf starten
            </Button>
          </div>
        </div>
        {selectedFy?.status === "GESCHLOSSEN" && (
          <p className="mt-3 text-xs text-soft-warn">
            Hinweis: Das gewählte Haushaltsjahr ist geschlossen — Läufe werden abgewiesen.
          </p>
        )}
      </div>

      {result && <RunResult result={result} empName={empName} />}
    </div>
  );
}

function RunResult({
  result,
  empName,
}: {
  result: RunMonatResult;
  empName: Map<string, string>;
}) {
  return (
    <div className="space-y-4">
      <div className="flex gap-3">
        <Badge variant="success">
          <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
          {result.run_count} berechnet
        </Badge>
        {result.skipped_count > 0 && (
          <Badge variant="warning">
            <AlertTriangle className="h-3 w-3" aria-hidden="true" />
            {result.skipped_count} übersprungen
          </Badge>
        )}
      </div>

      {result.run.length > 0 && (
        <div className="bg-white rounded-soft border border-soft-line shadow-soft overflow-hidden">
          <div className="px-5 py-2.5 border-b border-soft-line text-sm font-semibold text-soft-ink">
            Berechnete Abrechnungen
          </div>
          <ul className="divide-y divide-soft-line2">
            {result.run.map((r) => (
              <PayrollRow
                key={r.payroll_id}
                payrollId={r.payroll_id}
                label={empName.get(r.employee_id) ?? r.employee_id}
              />
            ))}
          </ul>
        </div>
      )}

      {result.skipped.length > 0 && (
        <div className="bg-white rounded-soft border border-soft-line shadow-soft overflow-hidden">
          <div className="px-5 py-2.5 border-b border-soft-line text-sm font-semibold text-soft-ink">
            Übersprungen
          </div>
          <ul className="divide-y divide-soft-line2">
            {result.skipped.map((s) => (
              <li key={s.employee_id} className="px-5 py-3 text-sm flex items-center gap-3">
                <span className="text-soft-ink2">{empName.get(s.employee_id) ?? s.employee_id}</span>
                <Badge variant="muted">{s.code}</Badge>
                <span className="text-soft-ink3 text-xs">{s.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function PayrollRow({ payrollId, label }: { payrollId: string; label: string }) {
  const [open, setOpen] = useState(false);
  const [lines, setLines] = useState<PayrollDetailLine[] | null>(null);
  const [loading, setLoading] = useState(false);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && lines === null) {
      setLoading(true);
      try {
        const res = await fetch(`/api/protected/pcm/payroll/${payrollId}/detail-lines`);
        const json = (await res.json().catch(() => ({}))) as { data?: PayrollDetailLine[] };
        setLines(json.data ?? []);
      } finally {
        setLoading(false);
      }
    }
  }

  return (
    <li className="px-5 py-3 text-sm">
      <button
        type="button"
        onClick={toggle}
        className="w-full flex items-center justify-between text-left
          focus:outline-none focus:ring-2 focus:ring-soft-accent rounded"
      >
        <span className="flex items-center gap-2 text-soft-ink2">
          {open ? (
            <ChevronDown className="h-4 w-4 text-soft-ink3" aria-hidden="true" />
          ) : (
            <ChevronRight className="h-4 w-4 text-soft-ink3" aria-hidden="true" />
          )}
          {label}
        </span>
        <span className="text-xs text-soft-ink3">Abrechnungspositionen</span>
      </button>

      {open && (
        <div className="mt-2 pl-6">
          {loading ? (
            <p className="text-xs text-soft-ink3">Lade…</p>
          ) : lines && lines.length > 0 ? (
            <ul className="space-y-1">
              {lines.map((l) => (
                <li key={l.id} className="flex items-center justify-between text-xs">
                  <span className="flex items-center gap-2">
                    <Badge variant="muted">{l.component}</Badge>
                    <span className="text-soft-ink3">{l.description}</span>
                  </span>
                  <span className="numeric text-soft-ink2">{eur(l.amount)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-soft-ink3">Keine Positionen.</p>
          )}
        </div>
      )}
    </li>
  );
}
