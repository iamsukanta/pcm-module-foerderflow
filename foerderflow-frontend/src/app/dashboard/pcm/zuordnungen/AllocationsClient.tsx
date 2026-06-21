"use client";

// N.1 Allocation overview (per period, grouped by funding measure) ·
// N.2 Allocation per grant project (cross-period matrix).

import { useCallback, useEffect, useState } from "react";
import { CalendarRange, FolderKanban } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { eur, eur0 } from "@/lib/pcmFormat";
import type { FiscalYearWithMeta } from "@/types/haushaltsjahre";
import type { AllocationOverview, AllocationPerGrant, FundingMeasureRef } from "@/types/pcm";

type Tab = "overview" | "per-grant";

export function AllocationsClient({
  fiscalYears,
  fundingMeasures,
}: {
  fiscalYears: FiscalYearWithMeta[];
  fundingMeasures: FundingMeasureRef[];
}) {
  const defaultFy = fiscalYears.find((f) => f.status === "OFFEN") ?? fiscalYears[0];
  const [tab, setTab] = useState<Tab>("overview");
  const [fyId, setFyId] = useState(defaultFy?.id ?? "");
  const [month, setMonth] = useState(defaultFy ? `${defaultFy.jahr}-01` : "");
  const [fmId, setFmId] = useState(fundingMeasures[0]?.id ?? "");
  const [overview, setOverview] = useState<AllocationOverview | null>(null);
  const [perGrant, setPerGrant] = useState<AllocationPerGrant | null>(null);

  const loadOverview = useCallback(() => {
    if (!fyId || !month) return;
    fetch(`/api/protected/pcm/allocations/overview?fiscal_year_id=${fyId}&monat=${month}-01`)
      .then((r) => r.json()).then((b) => setOverview(b.data ?? null));
  }, [fyId, month]);

  const loadPerGrant = useCallback(() => {
    if (!fyId || !fmId) return;
    fetch(`/api/protected/pcm/allocations/per-grant?fiscal_year_id=${fyId}&funding_measure_id=${fmId}`)
      .then((r) => r.json()).then((b) => setPerGrant(b.data ?? null));
  }, [fyId, fmId]);

  useEffect(() => { if (tab === "overview") loadOverview(); }, [tab, loadOverview]);
  useEffect(() => { if (tab === "per-grant") loadPerGrant(); }, [tab, loadPerGrant]);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1">
          <TabBtn active={tab === "overview"} onClick={() => setTab("overview")} icon={CalendarRange} label="Pro Periode" />
          <TabBtn active={tab === "per-grant"} onClick={() => setTab("per-grant")} icon={FolderKanban} label="Pro Projekt" />
        </div>
        <select value={fyId} onChange={(e) => setFyId(e.target.value)} className="rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-sm">
          {fiscalYears.map((f) => <option key={f.id} value={f.id}>{f.jahr}</option>)}
        </select>
        {tab === "overview" ? (
          <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-sm" />
        ) : (
          <select value={fmId} onChange={(e) => setFmId(e.target.value)} className="rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-sm">
            {fundingMeasures.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        )}
      </div>

      {tab === "overview" && <OverviewView overview={overview} />}
      {tab === "per-grant" && <PerGrantView data={perGrant} />}
    </div>
  );
}

function OverviewView({ overview }: { overview: AllocationOverview | null }) {
  if (!overview || overview.groups.length === 0) {
    return <EmptyState icon={CalendarRange} title="Keine Zuordnungen" description="Für diesen Monat liegen keine vom PCM-Lauf erzeugten Zuordnungen vor." />;
  }
  return (
    <div className="space-y-4">
      <div className="flex justify-end text-sm text-soft-ink2">
        Gesamt: <span className="numeric font-semibold text-soft-ink ml-1">{eur(overview.grand_total)}</span>
      </div>
      {overview.groups.map((g) => (
        <div key={g.funding_measure_id ?? "none"} className="bg-white rounded-soft border border-soft-line shadow-soft overflow-hidden">
          <div className="px-5 py-2.5 border-b border-soft-line flex items-center justify-between">
            <span className="text-sm font-semibold text-soft-ink">{g.funding_measure_name}</span>
            <span className="numeric text-sm font-medium text-soft-ink">{eur(g.total)}</span>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-soft-line2/40 text-soft-ink3 text-left">
              <tr>
                <th className="px-5 py-2 font-medium">Mitarbeiter:in</th>
                <th className="px-3 py-2 font-medium">Kostenstelle</th>
                <th className="px-3 py-2 font-medium">Position</th>
                <th className="px-3 py-2 font-medium text-right">%</th>
                <th className="px-3 py-2 font-medium text-right">Betrag</th>
              </tr>
            </thead>
            <tbody>
              {g.rows.map((r, i) => (
                <tr key={i} className="border-t border-soft-line2">
                  <td className="px-5 py-1.5 font-medium text-soft-ink">{r.employee_name}</td>
                  <td className="px-3 py-1.5 text-soft-ink2">{r.cost_center ?? "—"}</td>
                  <td className="px-3 py-1.5 text-soft-ink2">{r.finanzplan_position ?? "—"}</td>
                  <td className="px-3 py-1.5 text-right numeric text-soft-ink3">{r.prozent}%</td>
                  <td className="px-3 py-1.5 text-right numeric text-soft-ink">{eur(r.betrag_anteil)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}

function PerGrantView({ data }: { data: AllocationPerGrant | null }) {
  if (!data || data.rows.length === 0) {
    return <EmptyState icon={FolderKanban} title="Keine Zuordnungen" description="Diesem Projekt wurden noch keine Personalkosten zugeordnet." />;
  }
  return (
    <div className="overflow-x-auto bg-white rounded-soft border border-soft-line shadow-soft">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="text-soft-ink3 text-left">
            <th className="sticky left-0 bg-white px-3 py-2 font-medium border-b border-soft-line min-w-[11rem]">Mitarbeiter:in</th>
            {data.months.map((m) => <th key={m.monat} className="px-3 py-2 font-medium border-b border-soft-line text-right whitespace-nowrap">{m.label}</th>)}
            <th className="px-3 py-2 font-medium border-b border-soft-line text-right">Summe</th>
          </tr>
        </thead>
        <tbody>
          {data.rows.map((r) => (
            <tr key={r.employee_id} className="hover:bg-soft-ink/[0.02]">
              <td className="sticky left-0 bg-white px-3 py-2 font-medium text-soft-ink border-b border-soft-line2">{r.employee_name}</td>
              {data.months.map((m) => <td key={m.monat} className="px-3 py-2 border-b border-soft-line2 text-right numeric text-soft-ink2">{r.cells[m.monat] ? eur0(r.cells[m.monat]) : "—"}</td>)}
              <td className="px-3 py-2 border-b border-soft-line2 text-right numeric font-medium text-soft-ink">{eur0(r.row_total)}</td>
            </tr>
          ))}
          <tr className="bg-soft-line2/40 font-medium">
            <td className="sticky left-0 bg-soft-line2/40 px-3 py-2 text-soft-ink">Summe</td>
            {data.months.map((m) => <td key={m.monat} className="px-3 py-2 text-right numeric text-soft-ink2">{eur0(data.column_totals[m.monat] ?? 0)}</td>)}
            <td className="px-3 py-2 text-right numeric text-soft-ink">{eur0(data.grand_total)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function TabBtn({ active, onClick, icon: Icon, label }: { active: boolean; onClick: () => void; icon: typeof CalendarRange; label: string }) {
  return (
    <button type="button" onClick={onClick} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-soft-xs text-xs font-medium ${active ? "bg-soft-accent text-white" : "bg-soft-line2 text-soft-ink2 hover:bg-soft-ink/5"}`}>
      <Icon className="h-3.5 w-3.5" aria-hidden="true" /> {label}
    </button>
  );
}
