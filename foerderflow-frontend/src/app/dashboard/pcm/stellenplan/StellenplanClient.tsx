"use client";

// E.1 — Stellenplan Overview (organisation matrix). Rows = employees, columns =
// cost centres; row footer shows allocated/contracted with the Doppelförderungs
// status (green = OK · amber = under · red = over).

import Link from "next/link";
import { LayoutGrid } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { deDate } from "@/lib/pcmFormat";
import type { StellenplanMatrix, StellenplanRow } from "@/types/pcm";

const STATUS: Record<StellenplanRow["status"], { label: string; variant: "success" | "warning" | "danger" }> = {
  OK: { label: "OK", variant: "success" },
  UNDER: { label: "Unterbelegt", variant: "warning" },
  OVER: { label: "Überbelegt", variant: "danger" },
};

function num(v: number, unit: string): string {
  return `${v.toLocaleString("de-DE", { maximumFractionDigits: 2 })}${unit === "%" ? "%" : " h"}`;
}

export function StellenplanClient({ matrix }: { matrix: StellenplanMatrix }) {
  if (matrix.rows.length === 0) {
    return (
      <EmptyState
        icon={LayoutGrid}
        title="Keine aktiven Mitarbeitenden"
        description="Sobald Mitarbeitende mit Verträgen und Stundenzuweisungen erfasst sind, erscheint hier die Verteilungsmatrix."
      />
    );
  }

  const { cost_centers } = matrix;

  return (
    <div className="space-y-3">
      <p className="text-xs text-soft-ink3">Stand: {deDate(matrix.as_of)}</p>
      <div className="overflow-x-auto bg-white rounded-soft border border-soft-line shadow-soft">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="text-soft-ink3 text-left">
              <th className="sticky left-0 bg-white px-3 py-2 font-medium border-b border-soft-line min-w-[12rem]">
                Mitarbeiter:in
              </th>
              {cost_centers.map((c) => (
                <th key={c.id} className="px-3 py-2 font-medium border-b border-soft-line text-right whitespace-nowrap" title={c.name}>
                  {c.code}
                </th>
              ))}
              <th className="px-3 py-2 font-medium border-b border-soft-line text-right whitespace-nowrap">Verplant / Vertrag</th>
              <th className="px-3 py-2 font-medium border-b border-soft-line">Status</th>
            </tr>
          </thead>
          <tbody>
            {matrix.rows.map((r) => {
              const pct = r.capacity > 0 ? Math.min(120, (r.total_allocated / r.capacity) * 100) : 0;
              const barColor = r.status === "OVER" ? "bg-soft-crit" : r.status === "UNDER" ? "bg-soft-warn" : "bg-soft-ok";
              return (
                <tr key={r.employee_id} className="hover:bg-soft-ink/[0.02]">
                  <td className="sticky left-0 bg-white px-3 py-2 font-medium text-soft-ink border-b border-soft-line2">
                    <Link href={`/dashboard/pcm/wochenstunden?employee_id=${r.employee_id}`} className="hover:text-soft-accent hover:underline">
                      {r.employee_name}
                    </Link>
                  </td>
                  {cost_centers.map((c) => {
                    const val = r.cells[c.id];
                    return (
                      <td key={c.id} className="px-3 py-2 border-b border-soft-line2 text-right numeric">
                        {val ? num(val, r.unit) : <span className="text-soft-ink4">—</span>}
                      </td>
                    );
                  })}
                  <td className="px-3 py-2 border-b border-soft-line2 text-right">
                    <div className="flex flex-col items-end gap-1">
                      <span className="numeric text-soft-ink">{num(r.total_allocated, r.unit)} / {num(r.capacity, r.unit)}</span>
                      <div className="w-24 h-1.5 rounded-full bg-soft-line2 overflow-hidden">
                        <div className={`h-full ${barColor}`} style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-2 border-b border-soft-line2">
                    <Badge variant={STATUS[r.status].variant}>{STATUS[r.status].label}</Badge>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-soft-ink3">
        Name anklicken, um die Stundenzuweisungen der Person zu bearbeiten. PLAN_PERCENTAGE-Verträge werden in % statt Stunden geführt.
      </p>
    </div>
  );
}
