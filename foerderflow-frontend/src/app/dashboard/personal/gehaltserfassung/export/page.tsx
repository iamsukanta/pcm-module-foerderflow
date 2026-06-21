"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/ToastProvider";
import { Download } from "lucide-react";
import { PageShell } from "@/components/ui/PageShell";

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────

type ColumnDef = {
  key: string;
  label: string;
  defaultChecked: boolean;
};

const COLUMNS: ColumnDef[] = [
  { key: "personalnummer", label: "Personalnummer", defaultChecked: true },
  { key: "name", label: "Name", defaultChecked: true },
  { key: "kst", label: "Kostenstelle", defaultChecked: true },
  { key: "prozent", label: "Anteil %", defaultChecked: true },
  { key: "an_brutto_anteil", label: "AN-Brutto-Anteil", defaultChecked: true },
  { key: "ag_brutto_anteil", label: "AG-Brutto-Anteil", defaultChecked: true },
  { key: "tarifgruppe", label: "Tarifgruppe", defaultChecked: false },
  { key: "stufe", label: "Stufe", defaultChecked: false },
  { key: "stunden", label: "Stunden/Woche", defaultChecked: false },
];

type PreviewRow = Record<string, string>;

const MONTHS = [
  "Januar", "Februar", "März", "April", "Mai", "Juni",
  "Juli", "August", "September", "Oktober", "November", "Dezember",
];

// ─────────────────────────────────────────────
// Inner component (uses useSearchParams)
// ─────────────────────────────────────────────

function ExportPageInner() {
  const searchParams = useSearchParams();
  const toast = useToast();
  const now = new Date();

  const initialMonat = searchParams.get("monat") ?? `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const initialFiscalYearId = searchParams.get("fiscal_year_id") ?? "";

  const [monat, setMonat] = useState(initialMonat);
  const [fiscalYearId] = useState(initialFiscalYearId);
  const [selectedColumns, setSelectedColumns] = useState<Set<string>>(
    new Set(COLUMNS.filter((c) => c.defaultChecked).map((c) => c.key))
  );
  const [previewRows, setPreviewRows] = useState<PreviewRow[]>([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);

  // Parse monat
  const [selectedYear, selectedMonthNum] = monat.split("-").map(Number);
  const yearOptions: number[] = [];
  for (let y = now.getFullYear() - 2; y <= now.getFullYear() + 1; y++) {
    yearOptions.push(y);
  }

  const buildExportUrl = () => {
    const params = new URLSearchParams({ monat });
    if (fiscalYearId) params.set("fiscal_year_id", fiscalYearId);
    params.set("spalten", Array.from(selectedColumns).join(","));
    return `/api/protected/payroll/lohnbuero-export?${params.toString()}`;
  };

  const loadPreview = async () => {
    if (!monat) return;
    setPreviewLoading(true);
    try {
      const res = await fetch(buildExportUrl());
      if (!res.ok) throw new Error("Vorschau konnte nicht geladen werden.");
      const text = await res.text();
      const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
      const headers = (lines[0] ?? "").split(";");
      const rows: PreviewRow[] = lines.slice(1, 6).map((line) => {
        const values = line.split(";");
        const row: PreviewRow = {};
        headers.forEach((h, i) => { row[h] = values[i] ?? ""; });
        return row;
      });
      setPreviewRows(rows);
    } catch {
      setPreviewRows([]);
    } finally {
      setPreviewLoading(false);
    }
  };

  useEffect(() => {
    if (monat && selectedColumns.size > 0) {
      void loadPreview();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [monat, selectedColumns]);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const res = await fetch(buildExportUrl());
      if (!res.ok) {
        toast.error("Export fehlgeschlagen.");
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `lohnschluessel_${monat}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Export erfolgreich heruntergeladen.");
    } catch {
      toast.error("Netzwerkfehler beim Export.");
    } finally {
      setDownloading(false);
    }
  };

  const toggleColumn = (key: string) => {
    setSelectedColumns((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const headerKeys = Array.from(selectedColumns);

  return (
    <PageShell width="form">
      <h1 className="text-xl font-semibold text-soft-ink mb-6">Lohnbüro-Export</h1>

      {/* Month / year picker */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-soft-ink2 mb-2">Monat</label>
        <div className="flex gap-2">
          <select
            value={selectedMonthNum}
            onChange={(e) => {
              const m = Number(e.target.value);
              setMonat(`${selectedYear}-${String(m).padStart(2, "0")}`);
            }}
            className="border border-soft-line rounded-soft-xs px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-soft-accent"
          >
            {MONTHS.map((name, i) => (
              <option key={i} value={i + 1}>{name}</option>
            ))}
          </select>
          <select
            value={selectedYear}
            onChange={(e) => {
              const y = Number(e.target.value);
              setMonat(`${y}-${String(selectedMonthNum).padStart(2, "0")}`);
            }}
            className="border border-soft-line rounded-soft-xs px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-soft-accent"
          >
            {yearOptions.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
      </div>

      {/* Column selection */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-soft-ink2 mb-3">Spalten</label>
        <div className="grid grid-cols-2 gap-2">
          {COLUMNS.map((col) => (
            <label
              key={col.key}
              className="flex items-center gap-2 cursor-pointer text-sm text-soft-ink2"
            >
              <input
                type="checkbox"
                checked={selectedColumns.has(col.key)}
                onChange={() => toggleColumn(col.key)}
                className="rounded border-soft-line text-soft-accent focus:ring-soft-accent"
              />
              {col.label}
            </label>
          ))}
        </div>
      </div>

      {/* Export button */}
      <Button
        variant="primary"
        onClick={() => void handleDownload()}
        disabled={downloading || selectedColumns.size === 0 || !monat}
        loading={downloading}
        className="w-full mb-8"
      >
        <Download className="h-4 w-4 mr-2" />
        CSV exportieren
      </Button>

      {/* Preview */}
      <div>
        <h2 className="text-sm font-medium text-soft-ink2 mb-3">
          Vorschau (erste 5 Zeilen)
        </h2>
        {previewLoading ? (
          <div className="py-8 text-center text-soft-ink4 text-sm">Laden…</div>
        ) : previewRows.length === 0 ? (
          <div className="py-8 text-center text-soft-ink4 text-sm">Keine Daten für diesen Monat.</div>
        ) : (
          <div className="overflow-x-auto rounded-soft-xs border border-soft-line">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-soft-line2 border-b border-soft-line">
                  {headerKeys.map((key) => {
                    const col = COLUMNS.find((c) => c.key === key);
                    return (
                      <th key={key} className="px-3 py-2 text-left font-medium text-soft-ink2 whitespace-nowrap">
                        {col?.label ?? key}
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {previewRows.map((row, i) => (
                  <tr key={i} className="hover:bg-soft-line2">
                    {headerKeys.map((key) => {
                      const col = COLUMNS.find((c) => c.key === key);
                      const headerLabel = col?.label ?? key;
                      return (
                        <td key={key} className="px-3 py-2 text-soft-ink2 whitespace-nowrap">
                          {row[headerLabel] ?? ""}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </PageShell>
  );
}

// ─────────────────────────────────────────────
// Page export (wrapped in Suspense for useSearchParams)
// ─────────────────────────────────────────────

export default function ExportPage() {
  return (
    <Suspense fallback={<div className="p-6 text-soft-ink4 text-sm">Laden…</div>}>
      <ExportPageInner />
    </Suspense>
  );
}
