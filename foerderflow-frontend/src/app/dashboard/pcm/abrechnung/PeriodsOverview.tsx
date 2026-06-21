"use client";

// I.1 Payroll Periods Overview + I.4 Results + I.7 Lock / re-open. Sits above
// the month-run controls on the PCM-Abrechnung page.

import { useCallback, useEffect, useState } from "react";
import { Lock, LockOpen, ListChecks, X } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { useToast } from "@/components/ui/ToastProvider";
import { eur, deDate } from "@/lib/pcmFormat";
import type { FiscalYearWithMeta } from "@/types/haushaltsjahre";
import type {
  PayrollPeriodRow,
  PayrollPeriodStatusValue,
  PayrollPeriodResults,
  PayrollPeriodsOverview,
  PcmApiErrorBody,
} from "@/types/pcm";

const STATUS: Record<PayrollPeriodStatusValue, { label: string; variant: "muted" | "default" | "success" }> = {
  NOT_STARTED: { label: "Nicht gestartet", variant: "muted" },
  CALCULATED: { label: "Berechnet", variant: "default" },
  LOCKED: { label: "Gesperrt", variant: "success" },
};

export function PeriodsOverview({ fiscalYears }: { fiscalYears: FiscalYearWithMeta[] }) {
  const toast = useToast();
  const defaultFy = fiscalYears.find((f) => f.status === "OFFEN") ?? fiscalYears[0];
  const [fyId, setFyId] = useState(defaultFy?.id ?? "");
  const [overview, setOverview] = useState<PayrollPeriodsOverview | null>(null);
  const [results, setResults] = useState<PayrollPeriodResults | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!fyId) return;
    fetch(`/api/protected/pcm/payroll/periods?fiscal_year_id=${fyId}`)
      .then((r) => r.json())
      .then((b) => setOverview((b.data as PayrollPeriodsOverview) ?? null));
  }, [fyId]);

  useEffect(() => {
    load();
  }, [load]);

  async function lockToggle(p: PayrollPeriodRow) {
    setBusy(p.monat);
    const action = p.status === "LOCKED" ? "reopen" : "lock";
    const res = await fetch(`/api/protected/pcm/payroll/periods/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fiscal_year_id: fyId, monat: p.monat }),
    });
    setBusy(null);
    if (res.ok) {
      toast.success(action === "lock" ? "Periode gesperrt." : "Periode geöffnet.");
      load();
    } else {
      const b = (await res.json().catch(() => ({}))) as Partial<PcmApiErrorBody>;
      toast.error(b.error ?? "Aktion fehlgeschlagen.");
    }
  }

  async function openResults(monat: string) {
    const res = await fetch(`/api/protected/pcm/payroll/periods/results?fiscal_year_id=${fyId}&monat=${monat}`);
    const b = (await res.json().catch(() => ({}))) as { data?: PayrollPeriodResults };
    if (b.data) setResults(b.data);
  }

  return (
    <div className="bg-white rounded-soft border border-soft-line shadow-soft overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-soft-line">
        <h2 className="text-sm font-semibold text-soft-ink">Abrechnungsperioden</h2>
        <select value={fyId} onChange={(e) => setFyId(e.target.value)} className="rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-xs">
          {fiscalYears.map((f) => (
            <option key={f.id} value={f.id}>{f.jahr} ({f.status === "OFFEN" ? "offen" : "geschlossen"})</option>
          ))}
        </select>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-soft-line2/40 text-soft-ink3 text-left">
            <tr>
              <th className="px-4 py-2 font-medium">Periode</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium text-right">MA</th>
              <th className="px-4 py-2 font-medium text-right">AG-Brutto</th>
              <th className="px-4 py-2 font-medium">Letzter Lauf</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {overview?.periods.map((p) => (
              <tr key={p.monat} className="border-t border-soft-line2 hover:bg-soft-ink/[0.02]">
                <td className="px-4 py-2 font-medium text-soft-ink">{p.label}</td>
                <td className="px-4 py-2">
                  <span className="flex items-center gap-1.5">
                    <Badge variant={STATUS[p.status].variant}>{STATUS[p.status].label}</Badge>
                    {p.error_count > 0 && <Badge variant="danger">{p.error_count} Fehler</Badge>}
                    {p.on_leave_count > 0 && <Badge variant="warning">{p.on_leave_count} Abwesend</Badge>}
                  </span>
                </td>
                <td className="px-4 py-2 numeric text-right">{p.employee_count || "—"}</td>
                <td className="px-4 py-2 numeric text-right">{p.employee_count ? eur(p.total_ag_brutto) : "—"}</td>
                <td className="px-4 py-2 numeric text-soft-ink3 text-xs">{p.last_run_at ? deDate(p.last_run_at) : "—"}</td>
                <td className="px-4 py-2 text-right whitespace-nowrap">
                  {p.employee_count > 0 && (
                    <>
                      <button type="button" onClick={() => openResults(p.monat)} className="text-xs text-soft-accent hover:underline mr-3 inline-flex items-center gap-1">
                        <ListChecks className="h-3.5 w-3.5" /> Ergebnisse
                      </button>
                      <Button variant="secondary" size="sm" loading={busy === p.monat} onClick={() => lockToggle(p)}>
                        {p.status === "LOCKED" ? <><LockOpen className="h-3.5 w-3.5 mr-1" /> Öffnen</> : <><Lock className="h-3.5 w-3.5 mr-1" /> Sperren</>}
                      </Button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {results && <ResultsModal results={results} onClose={() => setResults(null)} />}
    </div>
  );
}

function ResultsModal({ results, onClose }: { results: PayrollPeriodResults; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-soft-ink/30 p-4 overflow-y-auto" onClick={onClose}>
      <div className="bg-white rounded-soft border border-soft-line shadow-soft-lg w-full max-w-3xl my-8" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-soft-line">
          <h2 className="text-base font-semibold text-soft-ink">
            Ergebnisse · {results.label}
            {results.locked && <Badge variant="success" className="ml-2">Gesperrt</Badge>}
          </h2>
          <button type="button" onClick={onClose} aria-label="Schließen" className="text-soft-ink3 hover:text-soft-ink"><X className="h-5 w-5" /></button>
        </div>
        <div className="p-6 space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            <Stat label="Mitarbeitende" value={String(results.summary.employee_count)} />
            <Stat label="AG-Brutto" value={eur(results.summary.total_ag_brutto)} />
            <Stat label="AN-Brutto" value={eur(results.summary.total_an_brutto)} />
            <Stat label="BAV" value={eur(results.summary.total_bav)} />
          </div>
          <div className="overflow-x-auto max-h-96 overflow-y-auto border border-soft-line rounded-soft-xs">
            <table className="w-full text-sm">
              <thead className="bg-soft-line2/50 sticky top-0 text-soft-ink3 text-left">
                <tr>
                  <th className="px-3 py-2 font-medium">Mitarbeiter:in</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium text-right">Ist-Gehalt</th>
                  <th className="px-3 py-2 font-medium text-right">AG-Brutto</th>
                  <th className="px-3 py-2 font-medium text-right">Zuordnungen</th>
                </tr>
              </thead>
              <tbody>
                {results.rows.map((r) => (
                  <tr key={r.payroll_id} className="border-t border-soft-line2">
                    <td className="px-3 py-1.5 font-medium text-soft-ink">{r.employee_name}</td>
                    <td className="px-3 py-1.5">
                      <Badge variant={r.status === "ERROR" ? "danger" : r.status === "ON_LEAVE" ? "warning" : "success"}>{r.status}</Badge>
                    </td>
                    <td className="px-3 py-1.5 numeric text-right">{eur(r.actual_salary)}</td>
                    <td className="px-3 py-1.5 numeric text-right">{eur(r.ag_brutto)}</td>
                    <td className="px-3 py-1.5 numeric text-right">{r.allocation_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-soft-xs bg-soft-line2/40 px-3 py-2">
      <div className="text-[11px] text-soft-ink3">{label}</div>
      <div className="numeric font-semibold text-soft-ink">{value}</div>
    </div>
  );
}
