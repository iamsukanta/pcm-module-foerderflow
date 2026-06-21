"use client";

// K.1 Dashboard · K.4 Matrix · K.6 Warnings · K.5 Detail — Personnel cost forecast.

import { useCallback, useEffect, useState } from "react";
import { PlayCircle, LayoutGrid, AlertTriangle, BarChart3, X } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { useToast } from "@/components/ui/ToastProvider";
import { eur, eur0, deDate } from "@/lib/pcmFormat";
import type { FiscalYearWithMeta } from "@/types/haushaltsjahre";
import type {
  ForecastDashboard,
  ForecastDetail,
  ForecastMatrix,
  ForecastWarnings,
  ForecastRunResult,
  PcmApiErrorBody,
} from "@/types/pcm";

const WARN_LABELS: Record<string, string> = {
  MISSING: "Keine Projektzuordnung",
  DATA_GAP: "Tariflücke",
  PROPOSED_TARIFF: "Geplanter Tarif verwendet",
  ON_LEAVE: "Abwesend",
};

type Tab = "dashboard" | "matrix" | "warnings";

export function PrognoseClient({ fiscalYears }: { fiscalYears: FiscalYearWithMeta[] }) {
  const toast = useToast();
  const defaultFy = fiscalYears.find((f) => f.status === "OFFEN") ?? fiscalYears[0];
  const [fyId, setFyId] = useState(defaultFy?.id ?? "");
  const [includeProposed, setIncludeProposed] = useState(true);
  const [tab, setTab] = useState<Tab>("dashboard");
  const [running, setRunning] = useState(false);
  const [dash, setDash] = useState<ForecastDashboard | null>(null);
  const [matrix, setMatrix] = useState<ForecastMatrix | null>(null);
  const [warnings, setWarnings] = useState<ForecastWarnings | null>(null);
  const [detail, setDetail] = useState<ForecastDetail | null>(null);

  const loadAll = useCallback(() => {
    if (!fyId) return;
    fetch(`/api/protected/pcm/forecast/dashboard?fiscal_year_id=${fyId}`).then((r) => r.json()).then((b) => setDash(b.data ?? null));
    fetch(`/api/protected/pcm/forecast/matrix?fiscal_year_id=${fyId}`).then((r) => r.json()).then((b) => setMatrix(b.data ?? null));
    fetch(`/api/protected/pcm/forecast/warnings?fiscal_year_id=${fyId}`).then((r) => r.json()).then((b) => setWarnings(b.data ?? null));
  }, [fyId]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  async function run() {
    setRunning(true);
    const res = await fetch("/api/protected/pcm/forecast/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fiscal_year_id: fyId, include_proposed: includeProposed }),
    });
    const b = (await res.json().catch(() => ({}))) as { data?: ForecastRunResult; error?: string };
    setRunning(false);
    if (!res.ok || !b.data) {
      toast.error(b.error ?? "Prognose fehlgeschlagen.");
      return;
    }
    toast.success(`Prognose berechnet: ${b.data.row_count} Zeilen.`);
    loadAll();
  }

  async function openDetail(employeeId: string, monat: string) {
    const res = await fetch(`/api/protected/pcm/forecast/detail?employee_id=${employeeId}&monat=${monat}`);
    const b = (await res.json().catch(() => ({}))) as { data?: ForecastDetail };
    if (b.data) setDetail(b.data);
  }

  const tabs: { key: Tab; label: string; icon: typeof BarChart3 }[] = [
    { key: "dashboard", label: "Übersicht", icon: BarChart3 },
    { key: "matrix", label: "Matrix", icon: LayoutGrid },
    { key: "warnings", label: "Warnungen", icon: AlertTriangle },
  ];

  return (
    <div className="space-y-5">
      {/* run controls */}
      <div className="bg-white rounded-soft border border-soft-line p-5 shadow-soft flex flex-wrap items-end gap-4">
        <div>
          <label className="block text-sm font-medium text-soft-ink2 mb-1">Haushaltsjahr</label>
          <select value={fyId} onChange={(e) => setFyId(e.target.value)} className="rounded-soft-xs border border-soft-line bg-white px-3 py-2 text-sm">
            {fiscalYears.map((f) => <option key={f.id} value={f.id}>{f.jahr} ({f.status === "OFFEN" ? "offen" : "geschlossen"})</option>)}
          </select>
        </div>
        <label className="flex items-center gap-2 text-sm text-soft-ink2 pb-2">
          <input type="checkbox" checked={includeProposed} onChange={(e) => setIncludeProposed(e.target.checked)} className="h-4 w-4 accent-soft-accent" />
          Geplante Tarife als Fallback
        </label>
        <Button variant="primary" onClick={run} loading={running}>
          <PlayCircle className="h-4 w-4 mr-1" aria-hidden="true" /> Prognose berechnen
        </Button>
        {dash?.last_run_at && <span className="text-xs text-soft-ink3 pb-2">Letzter Lauf: {deDate(dash.last_run_at)}</span>}
      </div>

      {!dash?.has_forecast ? (
        <EmptyState
          icon={BarChart3}
          title="Noch keine Prognose"
          description="Berechne die Prognose für das gewählte Haushaltsjahr, um die monatlichen Personalkosten zu projizieren."
        />
      ) : (
        <>
          <div className="flex gap-1 border-b border-soft-line">
            {tabs.map((t) => (
              <button key={t.key} type="button" onClick={() => setTab(t.key)}
                className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px ${tab === t.key ? "border-soft-accent text-soft-accent" : "border-transparent text-soft-ink3 hover:text-soft-ink"}`}>
                <t.icon className="h-4 w-4" aria-hidden="true" /> {t.label}
                {t.key === "warnings" && warnings && warnings.total > 0 && <Badge variant="warning">{warnings.total}</Badge>}
              </button>
            ))}
          </div>

          {tab === "dashboard" && dash && <DashboardView dash={dash} />}
          {tab === "matrix" && matrix && <MatrixView matrix={matrix} onCell={openDetail} />}
          {tab === "warnings" && warnings && <WarningsView warnings={warnings} />}
        </>
      )}

      {detail && <DetailModal detail={detail} onClose={() => setDetail(null)} />}
    </div>
  );
}

function DashboardView({ dash }: { dash: ForecastDashboard }) {
  const max = Math.max(1, ...dash.by_month.map((m) => Number(m.total)));
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <Stat label="Mitarbeitende" value={String(dash.employee_count)} />
        <Stat label="Gesamtprognose" value={eur(dash.grand_total)} />
        <Stat label="Warnungen" value={String(Object.values(dash.warnings).reduce((a, b) => a + b, 0))} />
      </div>
      <div className="bg-white rounded-soft border border-soft-line p-5 shadow-soft">
        <h3 className="text-sm font-semibold text-soft-ink mb-3">Prognose je Monat</h3>
        <div className="space-y-1.5">
          {dash.by_month.map((m) => (
            <div key={m.monat} className="flex items-center gap-2">
              <span className="w-16 text-xs text-soft-ink3 shrink-0">{m.label}</span>
              <div className="flex-1 h-5 rounded-soft-xs bg-soft-line2 overflow-hidden">
                <div className="h-full bg-soft-accent" style={{ width: `${(Number(m.total) / max) * 100}%` }} />
              </div>
              <span className="w-24 text-right numeric text-xs text-soft-ink2">{eur0(m.total)}</span>
            </div>
          ))}
        </div>
      </div>
      {Object.keys(dash.warnings).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(dash.warnings).map(([k, v]) => (
            <Badge key={k} variant="warning">{WARN_LABELS[k] ?? k}: {v}</Badge>
          ))}
        </div>
      )}
    </div>
  );
}

function MatrixView({ matrix, onCell }: { matrix: ForecastMatrix; onCell: (e: string, m: string) => void }) {
  return (
    <div className="overflow-x-auto bg-white rounded-soft border border-soft-line shadow-soft">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="text-soft-ink3 text-left">
            <th className="sticky left-0 bg-white px-3 py-2 font-medium border-b border-soft-line min-w-[11rem]">Mitarbeiter:in</th>
            {matrix.months.map((m) => <th key={m.monat} className="px-3 py-2 font-medium border-b border-soft-line text-right whitespace-nowrap">{m.label}</th>)}
            <th className="px-3 py-2 font-medium border-b border-soft-line text-right">Summe</th>
          </tr>
        </thead>
        <tbody>
          {matrix.rows.map((r) => (
            <tr key={r.employee_id} className="hover:bg-soft-ink/[0.02]">
              <td className="sticky left-0 bg-white px-3 py-2 font-medium text-soft-ink border-b border-soft-line2">{r.employee_name}</td>
              {matrix.months.map((m) => {
                const v = r.cells[m.monat];
                return (
                  <td key={m.monat} className="px-1 py-1 border-b border-soft-line2 text-right">
                    <button type="button" onClick={() => onCell(r.employee_id, m.monat)} className="w-full px-2 py-1 rounded-soft-xs numeric text-right hover:bg-soft-accentSoft text-soft-ink2">
                      {v ? eur0(v) : "—"}
                    </button>
                  </td>
                );
              })}
              <td className="px-3 py-2 border-b border-soft-line2 text-right numeric font-medium text-soft-ink">{eur0(r.row_total)}</td>
            </tr>
          ))}
          <tr className="bg-soft-line2/40 font-medium">
            <td className="sticky left-0 bg-soft-line2/40 px-3 py-2 text-soft-ink">Summe</td>
            {matrix.months.map((m) => <td key={m.monat} className="px-3 py-2 text-right numeric text-soft-ink2">{eur0(matrix.column_totals[m.monat] ?? 0)}</td>)}
            <td className="px-3 py-2"></td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function WarningsView({ warnings }: { warnings: ForecastWarnings }) {
  if (warnings.total === 0) {
    return <EmptyState icon={AlertTriangle} title="Keine Warnungen" description="Die Prognose enthält keine Datenqualitäts-Hinweise." />;
  }
  return (
    <div className="space-y-4">
      {warnings.groups.map((g) => (
        <div key={g.warning} className="bg-white rounded-soft border border-soft-line shadow-soft overflow-hidden">
          <div className="px-5 py-2.5 border-b border-soft-line flex items-center gap-2">
            <Badge variant="warning">{g.count}</Badge>
            <span className="text-sm font-semibold text-soft-ink">{WARN_LABELS[g.warning] ?? g.warning}</span>
          </div>
          <ul className="divide-y divide-soft-line2 max-h-72 overflow-y-auto">
            {g.rows.map((r, i) => (
              <li key={`${r.employee_id}-${i}`} className="px-5 py-2 text-sm flex items-center justify-between">
                <span className="text-soft-ink2">{r.employee_name} · {r.label}</span>
                <span className="numeric text-soft-ink3">{eur(r.total_forecast)}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function DetailModal({ detail, onClose }: { detail: ForecastDetail; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-soft-ink/30 p-4 overflow-y-auto" onClick={onClose}>
      <div className="bg-white rounded-soft border border-soft-line shadow-soft-lg w-full max-w-xl my-8" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-soft-line">
          <h2 className="text-base font-semibold text-soft-ink">{detail.employee_name} · {detail.label}</h2>
          <button type="button" onClick={onClose} aria-label="Schließen" className="text-soft-ink3 hover:text-soft-ink"><X className="h-5 w-5" /></button>
        </div>
        <div className="p-6 space-y-4 text-sm">
          {detail.warning && <Badge variant="warning">{WARN_LABELS[detail.warning] ?? detail.warning}</Badge>}
          <dl className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
            <Field label="Stufe" value={detail.forecast_level !== null ? String(detail.forecast_level) : "—"} />
            <Field label="Tarif-Vollzeit" value={eur(detail.forecast_salary)} />
            <Field label="Std. (Vollzeit)" value={detail.standard_hours} />
            <Field label="Std. (Projekt)" value={detail.forecast_hours} />
            <Field label="Ist-Gehalt" value={eur(detail.prorated_salary)} />
            <Field label="AG-Brutto" value={eur(detail.ag_brutto)} />
          </dl>
          <table className="w-full text-xs border border-soft-line rounded-soft-xs overflow-hidden">
            <thead className="bg-soft-line2/50 text-soft-ink3"><tr><th className="px-2 py-1 text-left">Komponente</th><th className="px-2 py-1 text-left">Beschreibung</th><th className="px-2 py-1 text-right">Betrag</th></tr></thead>
            <tbody>
              {detail.components.map((c, i) => (
                <tr key={i} className="border-t border-soft-line2">
                  <td className="px-2 py-1"><Badge variant="muted">{c.component}</Badge></td>
                  <td className="px-2 py-1 text-soft-ink2">{c.description}</td>
                  <td className="px-2 py-1 text-right numeric text-soft-ink">{eur(c.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex justify-between border-t border-soft-line pt-2 font-semibold">
            <span className="text-soft-ink">Gesamtprognose</span>
            <span className="numeric text-soft-ink">{eur(detail.total_forecast)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white rounded-soft border border-soft-line p-4 shadow-soft">
      <div className="text-xs text-soft-ink3">{label}</div>
      <div className="numeric text-lg font-semibold text-soft-ink mt-0.5">{value}</div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div><dt className="text-soft-ink3">{label}</dt><dd className="text-soft-ink numeric">{value}</dd></div>
  );
}
