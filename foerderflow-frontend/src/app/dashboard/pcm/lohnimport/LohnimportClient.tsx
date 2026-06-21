"use client";

// J.1 Import Batch List + multi-step new-import wizard (source → upload → preview
// → commit). Covers CSV_QUARTERLY / DATEV_EXTF / PERSONIO / DIAMANT_BAB.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Upload, FileSpreadsheet, Check, AlertTriangle, ChevronLeft } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { useToast } from "@/components/ui/ToastProvider";
import { eur, eur0, deDate } from "@/lib/pcmFormat";
import type {
  ImportSourceTypeValue,
  PayrollImportBatchRow,
  PayrollImportPreview,
  PcmApiErrorBody,
} from "@/types/pcm";

const SOURCES: { key: ImportSourceTypeValue; title: string; desc: string }[] = [
  { key: "CSV_QUARTERLY", title: "Quartals-CSV", desc: "Quartalsbeträge je Mitarbeiter:in, gleichmäßig auf drei Monate verteilt." },
  { key: "DATEV_EXTF", title: "DATEV", desc: "Monatliche Buchungssätze je Mitarbeiter:in (EXTF/CSV)." },
  { key: "PERSONIO", title: "Personio", desc: "Personio-Gehaltsexport (CSV) — ein Monat." },
  { key: "DIAMANT_BAB", title: "Diamant BAB", desc: "Kostenstellen-Summen, anteilig nach Wochenstunden auf Mitarbeitende verteilt." },
];

const SOURCE_LABELS = Object.fromEntries(SOURCES.map((s) => [s.key, s.title])) as Record<string, string>;

function inputCls() {
  return "w-full rounded-soft-xs border border-soft-line bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-soft-accent focus:border-soft-accent";
}

export function LohnimportClient({ batches }: { batches: PayrollImportBatchRow[] }) {
  const router = useRouter();
  const toast = useToast();
  const [wizard, setWizard] = useState(false);
  const [step, setStep] = useState(1);
  const [source, setSource] = useState<ImportSourceTypeValue | null>(null);
  const [from, setFrom] = useState("2026-01");
  const [to, setTo] = useState("");
  const [note, setNote] = useState("");
  const [preview, setPreview] = useState<PayrollImportPreview | null>(null);
  const [loading, setLoading] = useState(false);

  function reset() {
    setWizard(false); setStep(1); setSource(null); setPreview(null);
    setFrom("2026-01"); setTo(""); setNote("");
  }

  async function upload(file: File) {
    if (!source) return;
    setLoading(true);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("source_type", source);
    fd.append("period_from", `${from}-01`);
    if (to) fd.append("period_to", `${to}-01`);
    const res = await fetch("/api/protected/pcm/payroll-import/preview", { method: "POST", body: fd });
    const b = (await res.json().catch(() => ({}))) as { data?: PayrollImportPreview; error?: string };
    setLoading(false);
    if (!res.ok || !b.data) { toast.error(b.error ?? "Datei konnte nicht gelesen werden."); return; }
    setPreview(b.data);
    setStep(3);
  }

  async function confirm() {
    if (!preview) return;
    setLoading(true);
    const res = await fetch("/api/protected/pcm/payroll-import/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_type: preview.source_type, period_from: preview.period_from,
        period_to: preview.period_to, note: note || null, rows: preview.rows,
      }),
    });
    const b = (await res.json().catch(() => ({}))) as { data?: { written: number; skipped: number }; error?: string };
    setLoading(false);
    if (!res.ok || !b.data) { toast.error(b.error ?? "Import fehlgeschlagen."); return; }
    toast.success(`${b.data.written} Abrechnungszeilen importiert${b.data.skipped ? `, ${b.data.skipped} übersprungen` : ""}.`);
    reset();
    router.refresh();
  }

  if (!wizard) {
    return (
      <div className="space-y-5">
        <div className="flex justify-end">
          <Button variant="primary" onClick={() => setWizard(true)}><Plus className="h-4 w-4 mr-1" /> Neuer Import</Button>
        </div>
        {batches.length === 0 ? (
          <EmptyState icon={FileSpreadsheet} title="Keine Importe" description="Importiere externe Lohndaten, um sie in die Monatsabrechnung zu übernehmen." />
        ) : (
          <div className="overflow-x-auto bg-white rounded-soft border border-soft-line shadow-soft">
            <table className="w-full text-sm">
              <thead className="bg-soft-line2/40 text-soft-ink3 text-left">
                <tr>
                  <th className="px-4 py-2 font-medium">Quelle</th>
                  <th className="px-4 py-2 font-medium">Zeitraum</th>
                  <th className="px-4 py-2 font-medium">Notiz</th>
                  <th className="px-4 py-2 font-medium text-right">MA</th>
                  <th className="px-4 py-2 font-medium text-right">Summe</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {batches.map((b) => (
                  <tr key={b.id} className="border-t border-soft-line2">
                    <td className="px-4 py-2 font-medium text-soft-ink">{SOURCE_LABELS[b.source_type] ?? b.source_type}</td>
                    <td className="px-4 py-2 numeric text-soft-ink2">{deDate(b.period_from)} – {deDate(b.period_to)}</td>
                    <td className="px-4 py-2 text-soft-ink3">{b.note ?? "—"}</td>
                    <td className="px-4 py-2 text-right numeric">{b.matched_count}</td>
                    <td className="px-4 py-2 text-right numeric">{eur(b.total_gross)}</td>
                    <td className="px-4 py-2"><Badge variant="success">{b.status}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <button type="button" onClick={reset} className="inline-flex items-center gap-1 text-sm text-soft-ink3 hover:text-soft-ink">
        <ChevronLeft className="h-4 w-4" /> Zurück zur Liste
      </button>

      {step === 1 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {SOURCES.map((s) => (
            <button key={s.key} type="button" onClick={() => { setSource(s.key); setStep(2); }}
              className={`text-left bg-white rounded-soft border p-5 shadow-soft transition-all ${source === s.key ? "border-soft-accent" : "border-soft-line hover:border-soft-accent"}`}>
              <FileSpreadsheet className="h-6 w-6 text-soft-accent mb-2" aria-hidden="true" />
              <div className="font-medium text-soft-ink">{s.title}</div>
              <p className="text-xs text-soft-ink3 mt-1">{s.desc}</p>
            </button>
          ))}
        </div>
      )}

      {step === 2 && source && (
        <div className="bg-white rounded-soft border border-soft-line p-6 shadow-soft space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-soft-ink2 mb-1">Zeitraum von</label>
              <input type="month" value={from} onChange={(e) => setFrom(e.target.value)} className={inputCls()} />
            </div>
            <div>
              <label className="block text-sm font-medium text-soft-ink2 mb-1">
                bis {source === "CSV_QUARTERLY" ? "(optional, +2 Monate)" : "(optional)"}
              </label>
              <input type="month" value={to} onChange={(e) => setTo(e.target.value)} className={inputCls()} />
            </div>
            <div>
              <label className="block text-sm font-medium text-soft-ink2 mb-1">Notiz</label>
              <input value={note} onChange={(e) => setNote(e.target.value)} className={inputCls()} placeholder="Q1 2026" />
            </div>
          </div>
          <label className="block border-2 border-dashed border-soft-line rounded-soft p-8 text-center cursor-pointer hover:border-soft-accent">
            <Upload className="h-7 w-7 mx-auto text-soft-ink3 mb-2" aria-hidden="true" />
            <span className="text-sm text-soft-ink2">CSV-Datei auswählen (max. 10 MB)</span>
            <p className="text-xs text-soft-ink3 mt-1">
              {source === "DIAMANT_BAB" ? "Spalten: Kostenstelle · Betrag" : "Spalten: Personalnummer/Name · AG-Brutto"}
            </p>
            <input type="file" accept=".csv,.txt" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); }} />
          </label>
          {loading && <p className="text-sm text-soft-ink3">Datei wird gelesen…</p>}
        </div>
      )}

      {step === 3 && preview && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Badge variant="success">{preview.matched_count} zugeordnet</Badge>
            {preview.unmatched_count > 0 && <Badge variant="warning"><AlertTriangle className="h-3 w-3" /> {preview.unmatched_count} ohne Zuordnung</Badge>}
            <span className="text-sm text-soft-ink2 ml-auto">Summe: <span className="numeric font-semibold text-soft-ink">{eur(preview.total_gross)}</span></span>
          </div>
          <div className="overflow-x-auto max-h-96 overflow-y-auto bg-white border border-soft-line rounded-soft-xs">
            <table className="w-full text-sm">
              <thead className="bg-soft-line2/50 sticky top-0 text-soft-ink3 text-left">
                <tr><th className="px-3 py-2 font-medium">Quelle/ID</th><th className="px-3 py-2 font-medium">Zuordnung</th><th className="px-3 py-2 font-medium text-right">Brutto</th><th className="px-3 py-2 font-medium">Verteilung</th></tr>
              </thead>
              <tbody>
                {preview.rows.map((r, i) => (
                  <tr key={i} className="border-t border-soft-line2">
                    <td className="px-3 py-1.5 text-soft-ink2">{r.external_id ?? r.name ?? "?"}</td>
                    <td className="px-3 py-1.5">{r.matched_employee_id ? <span className="text-soft-ink">{r.matched_name}</span> : <Badge variant="warning">offen</Badge>}</td>
                    <td className="px-3 py-1.5 text-right numeric">{eur(r.gross)}</td>
                    <td className="px-3 py-1.5 text-xs text-soft-ink3">{r.distribution.map((d) => `${deDate(d.monat)}: ${eur0(d.amount)}`).join(" · ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between">
            <Button variant="ghost" onClick={() => setStep(2)} disabled={loading}>Zurück</Button>
            <Button variant="primary" loading={loading} onClick={confirm}><Check className="h-4 w-4 mr-1" /> Import übernehmen</Button>
          </div>
        </div>
      )}
    </div>
  );
}
