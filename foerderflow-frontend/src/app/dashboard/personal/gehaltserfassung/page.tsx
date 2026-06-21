"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/ToastProvider";
import { Download, RefreshCw, Plus } from "lucide-react";
import { PageShell } from "@/components/ui/PageShell";

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────

type FiscalYear = { id: string; jahr: number; beginn: string; ende: string; status: string };

type CostCenter = { id: string; name: string; code: string };

type EmployeeRow = {
  employee: { id: string; vorname: string; nachname: string; employee_code: string };
  payroll: { id: string; betrag_ag_brutto: number; betrag_an_brutto: number; quelle: string } | null;
  allocations: Array<{ cost_center_id: string; cost_center_name: string; prozent: number; betrag_anteil: number }>;
  summe_prozent: number;
  hat_abrechnung: boolean;
};

type AllocationKey = { id: string; name: string };

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────

function getProzentBadgeVariant(summe: number): "success" | "warning" | "danger" | "muted" {
  if (summe === 0) return "muted";
  if (Math.abs(summe - 100) < 0.01) return "success";
  if (summe >= 95 && summe <= 105) return "warning";
  return "danger";
}

function formatEur(value: number): string {
  return value.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const MONTHS = [
  "Januar", "Februar", "März", "April", "Mai", "Juni",
  "Juli", "August", "September", "Oktober", "November", "Dezember",
];

// ─────────────────────────────────────────────
// Page
// ─────────────────────────────────────────────

export default function GehaltserfassungPage() {
  const toast = useToast();
  const now = new Date();

  const [fiscalYears, setFiscalYears] = useState<FiscalYear[]>([]);
  const [selectedFiscalYearId, setSelectedFiscalYearId] = useState<string>("");
  const [selectedYear, setSelectedYear] = useState(now.getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(now.getMonth() + 1); // 1-based

  const [costCenters, setCostCenters] = useState<CostCenter[]>([]);
  const [allocationKeys, setAllocationKeys] = useState<AllocationKey[]>([]);
  const [rows, setRows] = useState<EmployeeRow[]>([]);
  const [loading, setLoading] = useState(false);

  // Local edits: Map<employee_id, Map<cost_center_id, prozent>>
  const [edits, setEdits] = useState<Map<string, Map<string, number>>>(new Map());
  const [saving, setSaving] = useState(false);
  const [creatingFor, setCreatingFor] = useState<string | null>(null);
  const [selectedKeyId, setSelectedKeyId] = useState<string>("");

  // Load fiscal years on mount
  useEffect(() => {
    void (async () => {
      try {
        const res = await fetch("/api/protected/haushaltsjahre");
        const json = (await res.json()) as { data: FiscalYear[] };
        const open = (json.data ?? []).filter((y) => y.status !== "GESCHLOSSEN");
        setFiscalYears(open);
        if (open.length > 0 && open[0]) {
          setSelectedFiscalYearId(open[0].id);
          setSelectedYear(open[0].jahr);
        }
      } catch {
        toast.error("Haushaltsjahre konnten nicht geladen werden.");
      }
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load cost centers on mount
  useEffect(() => {
    void (async () => {
      try {
        const res = await fetch("/api/protected/kostenstellen");
        const json = (await res.json()) as { data: CostCenter[] };
        setCostCenters((json.data ?? []).filter((kst) => (kst as { ist_aktiv?: boolean }).ist_aktiv !== false));
      } catch {
        // ignore
      }
    })();
  }, []);

  // Load allocation keys
  useEffect(() => {
    void (async () => {
      try {
        const res = await fetch("/api/protected/verteilungsschluessel");
        const json = (await res.json()) as { data: AllocationKey[] };
        setAllocationKeys(json.data ?? []);
      } catch {
        // ignore
      }
    })();
  }, []);

  const monatStr = `${selectedYear}-${String(selectedMonth).padStart(2, "0")}`;

  const loadData = useCallback(async () => {
    if (!selectedFiscalYearId) return;
    setLoading(true);
    try {
      const params = new URLSearchParams({
        monat: monatStr,
        fiscal_year_id: selectedFiscalYearId,
      });
      const res = await fetch(`/api/protected/payroll/monat-uebersicht?${params.toString()}`);
      if (!res.ok) throw new Error("Fehler beim Laden der Übersicht.");
      const json = (await res.json()) as { data: EmployeeRow[] };
      setRows(json.data ?? []);
      setEdits(new Map());
    } catch {
      toast.error("Gehaltsübersicht konnte nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, [monatStr, selectedFiscalYearId, toast]);

  useEffect(() => {
    if (selectedFiscalYearId) {
      void loadData();
    }
  }, [loadData, selectedFiscalYearId, monatStr]);

  // Track changes to allocation percentages
  const handleProzentChange = (employeeId: string, costCenterId: string, value: number) => {
    setEdits((prev) => {
      const next = new Map(prev);
      const empMap = new Map(next.get(employeeId) ?? new Map<string, number>());
      empMap.set(costCenterId, value);
      next.set(employeeId, empMap);
      return next;
    });
  };

  // Get current prozent for a cell (edits override server value)
  const getProzent = (row: EmployeeRow, costCenterId: string): string => {
    const empEdits = edits.get(row.employee.id);
    if (empEdits?.has(costCenterId)) {
      return String(empEdits.get(costCenterId) ?? 0);
    }
    const alloc = row.allocations.find((a) => a.cost_center_id === costCenterId);
    return alloc ? String(alloc.prozent) : "";
  };

  // Save allocations for rows that have edits
  const handleSave = async () => {
    if (edits.size === 0) {
      toast.error("Keine Änderungen vorhanden.");
      return;
    }
    setSaving(true);
    let successCount = 0;
    let errorCount = 0;

    for (const [employeeId, empEdits] of Array.from(edits.entries())) {
      const row = rows.find((r) => r.employee.id === employeeId);
      if (!row?.payroll) continue;

      // Merge with existing allocations
      const existingMap = new Map(row.allocations.map((a) => [a.cost_center_id, a.prozent]));
      for (const [kstId, val] of Array.from(empEdits.entries())) {
        existingMap.set(kstId, val);
      }

      const allocations = Array.from(existingMap.entries())
        .filter(([, prozent]) => prozent > 0)
        .map(([cost_center_id, prozent]) => ({ cost_center_id, prozent }));

      try {
        const res = await fetch(`/api/protected/payroll/${row.payroll.id}/allocations`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ allocations }),
        });
        if (res.ok) {
          successCount++;
        } else {
          const json = (await res.json()) as { error?: string };
          toast.error(json.error ?? `Fehler für ${row.employee.nachname}`);
          errorCount++;
        }
      } catch {
        toast.error(`Netzwerkfehler für ${row.employee.nachname}`);
        errorCount++;
      }
    }

    setSaving(false);
    if (successCount > 0) {
      toast.success(`${successCount} Zuordnung(en) gespeichert.`);
    }
    if (errorCount === 0) {
      await loadData();
    }
  };

  // Apply allocation key to all rows that have payrolls
  const handleApplyKey = async () => {
    if (!selectedKeyId) {
      toast.error("Bitte einen Verteilungsschlüssel auswählen.");
      return;
    }
    setSaving(true);
    let successCount = 0;
    let errorCount = 0;

    for (const row of rows) {
      if (!row.payroll) continue;
      try {
        const res = await fetch(`/api/protected/payroll/${row.payroll.id}/allocations`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ allocation_key_id: selectedKeyId }),
        });
        if (res.ok) successCount++;
        else errorCount++;
      } catch {
        errorCount++;
      }
    }

    setSaving(false);
    if (successCount > 0) toast.success(`Schlüssel auf ${successCount} Abrechnungen angewendet.`);
    if (errorCount > 0) toast.error(`${errorCount} Fehler beim Anwenden.`);
    await loadData();
  };

  // Create payroll for employee
  const handleErfassen = async (employeeId: string) => {
    if (!selectedFiscalYearId) return;
    setCreatingFor(employeeId);
    try {
      const res = await fetch("/api/protected/payroll", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          employee_id: employeeId,
          fiscal_year_id: selectedFiscalYearId,
          monat: monatStr,
        }),
      });
      const json = (await res.json()) as { error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Abrechnung konnte nicht erstellt werden.");
        return;
      }
      toast.success("Abrechnung erfasst.");
      await loadData();
    } catch {
      toast.error("Netzwerkfehler beim Erfassen.");
    } finally {
      setCreatingFor(null);
    }
  };

  // "Alle erfassen" — create payrolls for all employees without one
  const handleAlleErfassen = async () => {
    const missing = rows.filter((r) => !r.hat_abrechnung);
    if (missing.length === 0) {
      toast.error("Alle Mitarbeiter haben bereits eine Abrechnung für diesen Monat.");
      return;
    }
    for (const row of missing) {
      await handleErfassen(row.employee.id);
    }
  };

  // KST sum row
  const kstSums = costCenters.map((kst) => {
    const sum = rows
      .filter((r) => r.payroll)
      .reduce((acc, r) => {
        const alloc = r.allocations.find((a) => a.cost_center_id === kst.id);
        return acc + (alloc?.betrag_anteil ?? 0);
      }, 0);
    return { kst, sum };
  });

  const exportUrl = `/dashboard/personal/gehaltserfassung/export?monat=${monatStr}&fiscal_year_id=${selectedFiscalYearId}`;

  const yearOptions: number[] = [];
  for (let y = now.getFullYear() - 2; y <= now.getFullYear() + 1; y++) {
    yearOptions.push(y);
  }

  return (
    <PageShell width="full">
      {/* Header */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <h1 className="text-xl font-semibold text-soft-ink">Gehaltserfassung</h1>
        <div className="flex items-center gap-2 flex-wrap">
          {/* Month/Year pickers */}
          <select
            value={selectedMonth}
            onChange={(e) => setSelectedMonth(Number(e.target.value))}
            className="border border-soft-line rounded-soft-xs px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-soft-accent"
          >
            {MONTHS.map((name, i) => (
              <option key={i} value={i + 1}>{name}</option>
            ))}
          </select>
          <select
            value={selectedYear}
            onChange={(e) => setSelectedYear(Number(e.target.value))}
            className="border border-soft-line rounded-soft-xs px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-soft-accent"
          >
            {yearOptions.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>

          {/* Fiscal year */}
          <select
            value={selectedFiscalYearId}
            onChange={(e) => setSelectedFiscalYearId(e.target.value)}
            className="border border-soft-line rounded-soft-xs px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-soft-accent"
          >
            <option value="">Haushaltsjahr…</option>
            {fiscalYears.map((y) => (
              <option key={y.id} value={y.id}>{y.jahr} ({new Date(y.beginn).toLocaleDateString("de-DE", { day:"2-digit", month:"2-digit" })} – {new Date(y.ende).toLocaleDateString("de-DE", { day:"2-digit", month:"2-digit", year:"numeric" })})</option>
            ))}
          </select>

          <Button variant="secondary" size="sm" onClick={() => void loadData()} disabled={loading}>
            <RefreshCw className="h-4 w-4 mr-1.5" />
            Aktualisieren
          </Button>

          <Button variant="secondary" size="sm" onClick={() => void handleAlleErfassen()} disabled={loading || saving}>
            <Plus className="h-4 w-4 mr-1.5" />
            Alle erfassen
          </Button>

          <Link href={exportUrl}>
            <Button variant="secondary" size="sm">
              <Download className="h-4 w-4 mr-1.5" />
              Lohnbüro-Export
            </Button>
          </Link>
        </div>
      </div>

      {/* Allocation key toolbar */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <select
          value={selectedKeyId}
          onChange={(e) => setSelectedKeyId(e.target.value)}
          className="border border-soft-line rounded-soft-xs px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-soft-accent"
        >
          <option value="">Verteilungsschlüssel auswählen…</option>
          {allocationKeys.map((k) => (
            <option key={k.id} value={k.id}>{k.name}</option>
          ))}
        </select>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => void handleApplyKey()}
          disabled={!selectedKeyId || saving}
        >
          Schlüssel anwenden
        </Button>

        <div className="ml-auto">
          <Button
            variant="primary"
            size="sm"
            onClick={() => void handleSave()}
            disabled={saving || edits.size === 0}
            loading={saving}
          >
            Speichern
          </Button>
        </div>
      </div>

      {/* Pivot table */}
      {loading ? (
        <div className="py-16 text-center text-soft-ink4 text-sm">Laden…</div>
      ) : rows.length === 0 ? (
        <div className="py-16 text-center text-soft-ink4 text-sm">Keine aktiven Mitarbeiter gefunden.</div>
      ) : (
        <div className="overflow-x-auto rounded-soft-sm border border-soft-line">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-soft-line2 border-b border-soft-line">
                <th className="text-left px-4 py-3 font-medium text-soft-ink2 text-xs uppercase tracking-wide whitespace-nowrap sticky left-0 bg-soft-line2 z-10">
                  Mitarbeiter
                </th>
                <th className="text-right px-3 py-3 font-medium text-soft-ink2 text-xs uppercase tracking-wide whitespace-nowrap">
                  AN-Brutto
                </th>
                <th className="text-right px-3 py-3 font-medium text-soft-ink2 text-xs uppercase tracking-wide whitespace-nowrap">
                  AG-Brutto
                </th>
                {costCenters.map((kst) => (
                  <th
                    key={kst.id}
                    className="text-right px-3 py-3 font-medium text-soft-ink2 text-xs uppercase tracking-wide whitespace-nowrap"
                    title={kst.name}
                  >
                    {kst.code}
                  </th>
                ))}
                <th className="text-right px-3 py-3 font-medium text-soft-ink2 text-xs uppercase tracking-wide whitespace-nowrap">
                  Summe %
                </th>
                <th className="text-center px-3 py-3 font-medium text-soft-ink2 text-xs uppercase tracking-wide whitespace-nowrap">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row) => {
                const hasPayroll = row.hat_abrechnung;
                const summe = hasPayroll
                  ? (() => {
                      // Compute live summe from edits + existing
                      const empEdits = edits.get(row.employee.id);
                      if (!empEdits || empEdits.size === 0) return row.summe_prozent;
                      const existingMap = new Map(row.allocations.map((a) => [a.cost_center_id, a.prozent]));
                      for (const [kstId, val] of Array.from(empEdits.entries())) {
                        existingMap.set(kstId, val);
                      }
                      return Array.from(existingMap.values())
                        .filter((v) => v > 0)
                        .reduce((a, b) => a + b, 0);
                    })()
                  : 0;

                return (
                  <tr
                    key={row.employee.id}
                    className={!hasPayroll ? "bg-soft-line2 opacity-60" : "hover:bg-soft-line2"}
                  >
                    {/* Name */}
                    <td className="px-4 py-2 font-medium text-soft-ink whitespace-nowrap sticky left-0 bg-white z-10">
                      <span className="font-mono text-xs text-soft-ink4 mr-2">
                        {row.employee.employee_code}
                      </span>
                      {row.employee.nachname}, {row.employee.vorname}
                    </td>

                    {/* AN-Brutto */}
                    <td className="px-3 py-2 text-right text-soft-ink2 whitespace-nowrap">
                      {hasPayroll && row.payroll
                        ? formatEur(row.payroll.betrag_an_brutto)
                        : <span className="text-soft-ink4">–</span>
                      }
                    </td>

                    {/* AG-Brutto */}
                    <td className="px-3 py-2 text-right text-soft-ink2 whitespace-nowrap">
                      {hasPayroll && row.payroll
                        ? formatEur(row.payroll.betrag_ag_brutto)
                        : <span className="text-soft-ink4">–</span>
                      }
                    </td>

                    {/* KST cells */}
                    {costCenters.map((kst) =>
                      hasPayroll ? (
                        <td key={kst.id} className="px-2 py-1.5 text-right">
                          <input
                            type="number"
                            min={0}
                            max={100}
                            step={0.1}
                            value={getProzent(row, kst.id)}
                            onChange={(e) => {
                              const v = parseFloat(e.target.value);
                              if (!isNaN(v)) {
                                handleProzentChange(row.employee.id, kst.id, v);
                              }
                            }}
                            className="w-20 text-right border border-soft-line rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                            placeholder="0"
                          />
                        </td>
                      ) : (
                        <td key={kst.id} className="px-3 py-2 text-center text-soft-ink4 text-xs">–</td>
                      )
                    )}

                    {/* Summe % */}
                    <td className="px-3 py-2 text-right text-soft-ink2 whitespace-nowrap font-medium">
                      {hasPayroll ? `${summe.toFixed(1)} %` : <span className="text-soft-ink4">–</span>}
                    </td>

                    {/* Status */}
                    <td className="px-3 py-2 text-center whitespace-nowrap">
                      {hasPayroll ? (
                        <Badge variant={getProzentBadgeVariant(summe)}>
                          {Math.abs(summe - 100) < 0.01 ? "Vollständig" : `${summe.toFixed(1)} %`}
                        </Badge>
                      ) : (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => void handleErfassen(row.employee.id)}
                          disabled={creatingFor === row.employee.id || !selectedFiscalYearId}
                          loading={creatingFor === row.employee.id}
                        >
                          <Plus className="h-3 w-3 mr-1" />
                          Erfassen
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })}

              {/* Sum row */}
              <tr className="bg-soft-line2 border-t-2 border-soft-line font-medium">
                <td className="px-4 py-3 text-soft-ink2 sticky left-0 bg-soft-line2 z-10">Summe AG-Brutto</td>
                <td className="px-3 py-3 text-right text-soft-ink2">
                  {formatEur(rows.filter((r) => r.payroll).reduce((s, r) => s + (r.payroll?.betrag_an_brutto ?? 0), 0))}
                </td>
                <td className="px-3 py-3 text-right text-soft-ink2">
                  {formatEur(rows.filter((r) => r.payroll).reduce((s, r) => s + (r.payroll?.betrag_ag_brutto ?? 0), 0))}
                </td>
                {kstSums.map(({ kst, sum }) => (
                  <td key={kst.id} className="px-3 py-3 text-right text-soft-ink2">
                    {sum > 0 ? formatEur(sum) : <span className="text-soft-ink4">–</span>}
                  </td>
                ))}
                <td colSpan={2} />
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </PageShell>
  );
}
