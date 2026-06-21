"use client";

// M.1 VWN config (visible components) · M.2 preview · M.3 CSV export.

import { useCallback, useEffect, useState } from "react";
import { Settings2, Download, FileText } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { useToast } from "@/components/ui/ToastProvider";
import { eur, eur0 } from "@/lib/pcmFormat";
import type { FundingMeasureRef, VwnConfig, VwnPreview, PcmApiErrorBody } from "@/types/pcm";

const ALL_COMPONENTS = ["BASE", "ZULAGE", "BONUS", "JSZ", "WEIHNACHTSGELD", "BAV", "ADJUST_ADD", "ADJUST_DED", "FRINGE"];
const COMP_LABELS: Record<string, string> = {
  BASE: "Grundgehalt", ZULAGE: "Zulagen", BONUS: "Boni", JSZ: "JSZ",
  WEIHNACHTSGELD: "Weihnachtsgeld", BAV: "BAV", ADJUST_ADD: "Zuschläge",
  ADJUST_DED: "Abzüge", FRINGE: "Sachbezüge",
};

export function VwnClient({ fundingMeasures }: { fundingMeasures: FundingMeasureRef[] }) {
  const toast = useToast();
  const [fmId, setFmId] = useState(fundingMeasures[0]?.id ?? "");
  const [from, setFrom] = useState("2026-01");
  const [to, setTo] = useState("2026-12");
  const [config, setConfig] = useState<VwnConfig | null>(null);
  const [preview, setPreview] = useState<VwnPreview | null>(null);
  const [showConfig, setShowConfig] = useState(false);

  const loadConfig = useCallback(() => {
    if (!fmId) return;
    fetch(`/api/protected/pcm/vwn/config?funding_measure_id=${fmId}`).then((r) => r.json()).then((b) => setConfig(b.data ?? null));
  }, [fmId]);

  const loadPreview = useCallback(() => {
    if (!fmId) return;
    fetch(`/api/protected/pcm/vwn/preview?funding_measure_id=${fmId}&from_month=${from}-01&to_month=${to}-01`)
      .then((r) => r.json()).then((b) => setPreview(b.data ?? null));
  }, [fmId, from, to]);

  useEffect(() => { loadConfig(); }, [loadConfig]);
  useEffect(() => { loadPreview(); }, [loadPreview]);

  async function saveConfig() {
    if (!config) return;
    const res = await fetch("/api/protected/pcm/vwn/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...config, funding_measure_id: fmId }),
    });
    if (res.ok) {
      toast.success("Konfiguration gespeichert.");
      setShowConfig(false);
      loadPreview();
    } else {
      const b = (await res.json().catch(() => ({}))) as Partial<PcmApiErrorBody>;
      toast.error(b.error ?? "Speichern fehlgeschlagen.");
    }
  }

  function toggleComponent(c: string) {
    if (!config) return;
    const has = config.visible_components.includes(c);
    setConfig({
      ...config,
      visible_components: has
        ? config.visible_components.filter((x) => x !== c)
        : ALL_COMPONENTS.filter((x) => config.visible_components.includes(x) || x === c),
    });
  }

  const exportHref = `/api/protected/pcm/vwn/export?funding_measure_id=${fmId}&from_month=${from}-01&to_month=${to}-01`;

  return (
    <div className="space-y-5">
      <div className="bg-white rounded-soft border border-soft-line p-5 shadow-soft flex flex-wrap items-end gap-4">
        <Labeled label="Fördermaßnahme">
          <select value={fmId} onChange={(e) => setFmId(e.target.value)} className="rounded-soft-xs border border-soft-line bg-white px-3 py-2 text-sm">
            {fundingMeasures.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </Labeled>
        <Labeled label="Von"><input type="month" value={from} onChange={(e) => setFrom(e.target.value)} className="rounded-soft-xs border border-soft-line bg-white px-3 py-2 text-sm" /></Labeled>
        <Labeled label="Bis"><input type="month" value={to} onChange={(e) => setTo(e.target.value)} className="rounded-soft-xs border border-soft-line bg-white px-3 py-2 text-sm" /></Labeled>
        <Button variant="secondary" onClick={() => setShowConfig((s) => !s)}><Settings2 className="h-4 w-4 mr-1" /> Spalten</Button>
        <a href={exportHref} className="inline-flex">
          <Button variant="primary"><Download className="h-4 w-4 mr-1" /> CSV exportieren</Button>
        </a>
      </div>

      {showConfig && config && (
        <div className="bg-white rounded-soft border border-soft-line p-5 shadow-soft space-y-3">
          <h3 className="text-sm font-semibold text-soft-ink">Sichtbare Komponenten</h3>
          <div className="flex flex-wrap gap-2">
            {ALL_COMPONENTS.map((c) => (
              <label key={c} className={`flex items-center gap-1.5 px-2.5 py-1 rounded-soft-xs border text-xs cursor-pointer ${config.visible_components.includes(c) ? "bg-soft-accentSoft border-soft-accent/30 text-soft-accent" : "bg-soft-line2/40 border-soft-line text-soft-ink3"}`}>
                <input type="checkbox" checked={config.visible_components.includes(c)} onChange={() => toggleComponent(c)} className="h-3.5 w-3.5 accent-soft-accent" />
                {COMP_LABELS[c] ?? c}
              </label>
            ))}
          </div>
          <div className="flex items-center gap-4">
            <Labeled label="Sammelspalte"><input value={config.aggregate_label} onChange={(e) => setConfig({ ...config, aggregate_label: e.target.value })} className="rounded-soft-xs border border-soft-line bg-white px-3 py-2 text-sm" /></Labeled>
            <label className="flex items-center gap-2 text-sm text-soft-ink2 pt-5">
              <input type="checkbox" checked={config.hide_zero} onChange={(e) => setConfig({ ...config, hide_zero: e.target.checked })} className="h-4 w-4 accent-soft-accent" />
              Nullspalten ausblenden
            </label>
          </div>
          <div className="flex justify-end"><Button variant="primary" size="sm" onClick={saveConfig}>Speichern</Button></div>
        </div>
      )}

      {!preview || preview.rows.length === 0 ? (
        <EmptyState icon={FileText} title="Keine Personalkosten" description="Für die gewählte Maßnahme und den Zeitraum liegen keine zugeordneten Personalkosten vor." />
      ) : (
        <div className="overflow-x-auto bg-white rounded-soft border border-soft-line shadow-soft">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-soft-ink3 text-left">
                <th className="sticky left-0 bg-white px-3 py-2 font-medium border-b border-soft-line min-w-[11rem]">Mitarbeiter:in</th>
                {preview.components.map((c) => <th key={c} className="px-3 py-2 font-medium border-b border-soft-line text-right whitespace-nowrap">{COMP_LABELS[c] ?? c}</th>)}
                {preview.has_aggregate && <th className="px-3 py-2 font-medium border-b border-soft-line text-right">{preview.aggregate_label}</th>}
                <th className="px-3 py-2 font-medium border-b border-soft-line text-right">Summe</th>
              </tr>
            </thead>
            <tbody>
              {preview.rows.map((r) => (
                <tr key={r.employee_id} className="hover:bg-soft-ink/[0.02]">
                  <td className="sticky left-0 bg-white px-3 py-2 font-medium text-soft-ink border-b border-soft-line2">{r.employee_name}</td>
                  {preview.components.map((c) => <td key={c} className="px-3 py-2 border-b border-soft-line2 text-right numeric text-soft-ink2">{eur0(r.cells[c])}</td>)}
                  {preview.has_aggregate && <td className="px-3 py-2 border-b border-soft-line2 text-right numeric text-soft-ink2">{eur0(r.aggregate)}</td>}
                  <td className="px-3 py-2 border-b border-soft-line2 text-right numeric font-medium text-soft-ink">{eur0(r.total)}</td>
                </tr>
              ))}
              <tr className="bg-soft-line2/40 font-medium">
                <td className="sticky left-0 bg-soft-line2/40 px-3 py-2 text-soft-ink">Summe</td>
                {preview.components.map((c) => <td key={c} className="px-3 py-2 text-right numeric text-soft-ink2">{eur0(preview.component_totals[c] ?? 0)}</td>)}
                {preview.has_aggregate && <td className="px-3 py-2 text-right numeric text-soft-ink2">{eur0(preview.aggregate_total)}</td>}
                <td className="px-3 py-2 text-right numeric text-soft-ink">{eur(preview.grand_total)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Labeled({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><label className="block text-sm font-medium text-soft-ink2 mb-1">{label}</label>{children}</div>;
}
