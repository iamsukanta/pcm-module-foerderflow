"use client";

// Screen I-T — Tariff Import Wizard. 5-step linear flow; meta + parsed preview
// are persisted to sessionStorage so an interrupted import survives a refresh.
// CSV/Excel are parsed server-side; the grid path collects a manually transcribed
// table (used for the Image/manual route — no faked OCR).

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { FileSpreadsheet, Grid3x3, Upload, Check, AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { useToast } from "@/components/ui/ToastProvider";
import { eur, deDate } from "@/lib/pcmFormat";
import type { TariffImportPreview, TariffImportRow, PcmApiErrorBody } from "@/types/pcm";

type SourceKind = "FILE" | "GRID";
const STORE_KEY = "pcm_tariff_import_v1";

type Meta = {
  source: SourceKind;
  tariff_code: string;
  is_proposed: boolean;
  valid_from: string;
  valid_to: string;
  standard_hours: string;
  bav_rate_pct: string;
};

type Persisted = {
  step: number;
  meta: Meta;
  preview: TariffImportPreview | null;
  resolution: "skip" | "trim";
};

const EMPTY: Persisted = {
  step: 1,
  meta: { source: "FILE", tariff_code: "", is_proposed: false, valid_from: "", valid_to: "", standard_hours: "39", bav_rate_pct: "" },
  preview: null,
  resolution: "trim",
};

function inputCls() {
  return "w-full rounded-soft-xs border border-soft-line bg-white px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-soft-accent focus:border-soft-accent";
}

const STEPS = ["Quelle", "Tarif & Gültigkeit", "Daten", "Vorschau", "Bestätigen"];

export function ImportWizardClient() {
  const router = useRouter();
  const toast = useToast();
  const [s, setS] = useState<Persisted>(EMPTY);
  const [loading, setLoading] = useState(false);

  // hydrate from sessionStorage
  useEffect(() => {
    const raw = typeof window !== "undefined" ? window.sessionStorage.getItem(STORE_KEY) : null;
    if (raw) {
      try { setS(JSON.parse(raw)); } catch { /* ignore */ }
    }
  }, []);
  useEffect(() => {
    if (typeof window !== "undefined") window.sessionStorage.setItem(STORE_KEY, JSON.stringify(s));
  }, [s]);

  const setMeta = (patch: Partial<Meta>) => setS((p) => ({ ...p, meta: { ...p.meta, ...patch } }));
  const go = (step: number) => setS((p) => ({ ...p, step }));
  const reset = () => { window.sessionStorage.removeItem(STORE_KEY); setS(EMPTY); };

  async function uploadFile(file: File) {
    setLoading(true);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("source", /\.xlsx?$/i.test(file.name) ? "EXCEL" : "CSV");
    fd.append("tariff_code", s.meta.tariff_code);
    fd.append("is_proposed", String(s.meta.is_proposed));
    fd.append("valid_from", s.meta.valid_from);
    if (s.meta.valid_to) fd.append("valid_to", s.meta.valid_to);
    const res = await fetch("/api/protected/pcm/tariff-rows/import", { method: "POST", body: fd });
    const b = (await res.json().catch(() => ({}))) as { data?: TariffImportPreview; error?: string };
    setLoading(false);
    if (!res.ok || !b.data) { toast.error(b.error ?? "Datei konnte nicht gelesen werden."); return; }
    setS((p) => ({ ...p, preview: b.data!, step: 4 }));
  }

  function setGridPreview(rows: TariffImportRow[]) {
    const preview: TariffImportPreview = {
      import_id: "imp_" + Math.random().toString(16).slice(2, 18),
      tariff_code: s.meta.tariff_code,
      row_count: rows.length,
      valid_rows: rows.length,
      warning_rows: 0,
      error_rows: 0,
      preview: rows,
      conflicts: [],
    };
    setS((p) => ({ ...p, preview, step: 4 }));
  }

  async function confirm() {
    if (!s.preview) return;
    setLoading(true);
    const rows = s.preview.preview
      .filter((r) => r.status !== "error")
      .map((r) => ({ salary_group: r.salary_group, level: r.level, monthly_amount: r.monthly_amount }));
    const res = await fetch(`/api/protected/pcm/tariff-rows/import/${s.preview.import_id}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tariff_code: s.meta.tariff_code,
        is_proposed: s.meta.is_proposed,
        valid_from: s.meta.valid_from,
        valid_to: s.meta.valid_to || null,
        standard_hours: Number(s.meta.standard_hours),
        bav_rate_pct: s.meta.bav_rate_pct ? Number(s.meta.bav_rate_pct) : null,
        conflict_resolution: s.resolution,
        rows,
      }),
    });
    const b = (await res.json().catch(() => ({}))) as { data?: { written: number; trimmed: number; skipped: number }; error?: string };
    setLoading(false);
    if (!res.ok || !b.data) { toast.error(b.error ?? "Import fehlgeschlagen."); return; }
    toast.success(`${b.data.written} Zeilen importiert${b.data.trimmed ? `, ${b.data.trimmed} gekürzt` : ""}.`);
    reset();
    router.push(`/dashboard/pcm/tarife/${encodeURIComponent(s.meta.tariff_code)}`);
  }

  return (
    <div className="space-y-6">
      <Stepper current={s.step} />

      {s.step === 1 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <SourceCard
            icon={FileSpreadsheet}
            title="CSV / Excel"
            desc="Strukturierte Datei mit Entgeltgruppen-Zeilen und Stufen-Spalten."
            active={s.meta.source === "FILE"}
            onClick={() => { setMeta({ source: "FILE" }); go(2); }}
          />
          <SourceCard
            icon={Grid3x3}
            title="Manuelles Raster / Bild"
            desc="Werte aus einem Foto oder PDF direkt ins Raster übertragen."
            active={s.meta.source === "GRID"}
            onClick={() => { setMeta({ source: "GRID" }); go(2); }}
          />
        </div>
      )}

      {s.step === 2 && (
        <Card>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Labeled label="Tarifcode">
              <input value={s.meta.tariff_code} onChange={(e) => setMeta({ tariff_code: e.target.value })} placeholder="TVöD-VKA" className={inputCls()} />
            </Labeled>
            <Labeled label="Typ">
              <select value={String(s.meta.is_proposed)} onChange={(e) => setMeta({ is_proposed: e.target.value === "true" })} className={inputCls()}>
                <option value="false">Aktuell</option>
                <option value="true">Geplant</option>
              </select>
            </Labeled>
            <Labeled label="Gültig ab">
              <input type="date" value={s.meta.valid_from} onChange={(e) => setMeta({ valid_from: e.target.value })} className={inputCls()} />
            </Labeled>
            <Labeled label="Gültig bis (optional)">
              <input type="date" value={s.meta.valid_to} onChange={(e) => setMeta({ valid_to: e.target.value })} className={inputCls()} />
            </Labeled>
            <Labeled label="Wochenstunden (Vollzeit)">
              <input type="number" step="0.5" value={s.meta.standard_hours} onChange={(e) => setMeta({ standard_hours: e.target.value })} className={`${inputCls()} numeric`} />
            </Labeled>
            <Labeled label="BAV-Satz (%) optional">
              <input type="number" step="0.1" value={s.meta.bav_rate_pct} onChange={(e) => setMeta({ bav_rate_pct: e.target.value })} placeholder="4.7" className={`${inputCls()} numeric`} />
            </Labeled>
          </div>
          <NavButtons onBack={() => go(1)} onNext={() => go(3)} nextDisabled={!s.meta.tariff_code || !s.meta.valid_from} />
        </Card>
      )}

      {s.step === 3 && s.meta.source === "FILE" && (
        <Card>
          <label className="block border-2 border-dashed border-soft-line rounded-soft p-10 text-center cursor-pointer hover:border-soft-accent">
            <Upload className="h-8 w-8 mx-auto text-soft-ink3 mb-2" aria-hidden="true" />
            <span className="text-sm text-soft-ink2">CSV oder Excel auswählen (max. 10 MB)</span>
            <p className="text-xs text-soft-ink3 mt-1">Erste Spalte = Entgeltgruppe, weitere Spalten = Stufenbeträge.</p>
            <input
              type="file"
              accept=".csv,.xlsx,.xls"
              className="hidden"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadFile(f); }}
            />
          </label>
          {loading && <p className="text-sm text-soft-ink3 mt-3">Datei wird gelesen…</p>}
          <NavButtons onBack={() => go(2)} />
        </Card>
      )}

      {s.step === 3 && s.meta.source === "GRID" && (
        <GridEditor onBack={() => go(2)} onDone={setGridPreview} />
      )}

      {s.step === 4 && s.preview && (
        <Card>
          <div className="flex items-center gap-3 mb-4 text-sm">
            <Badge variant="success">{s.preview.valid_rows} bereit</Badge>
            {s.preview.warning_rows > 0 && <Badge variant="warning">{s.preview.warning_rows} Überschneidung</Badge>}
            {s.preview.error_rows > 0 && <Badge variant="danger">{s.preview.error_rows} Fehler</Badge>}
          </div>
          {s.preview.warning_rows > 0 && (
            <div className="rounded-soft-xs bg-soft-warnSoft border border-soft-warn/30 p-3 mb-4 text-sm">
              <div className="flex items-center gap-2 font-medium text-soft-warn mb-2">
                <AlertTriangle className="h-4 w-4" aria-hidden="true" /> Überschneidungen gefunden
              </div>
              <label className="flex items-center gap-2 text-xs text-soft-ink2">
                <input type="radio" checked={s.resolution === "trim"} onChange={() => setS((p) => ({ ...p, resolution: "trim" }))} /> Bestehende Zeilen kürzen
              </label>
              <label className="flex items-center gap-2 text-xs text-soft-ink2 mt-1">
                <input type="radio" checked={s.resolution === "skip"} onChange={() => setS((p) => ({ ...p, resolution: "skip" }))} /> Überschneidende Zeilen überspringen
              </label>
            </div>
          )}
          <div className="overflow-x-auto max-h-80 overflow-y-auto border border-soft-line rounded-soft-xs">
            <table className="w-full text-sm">
              <thead className="bg-soft-line2/50 sticky top-0">
                <tr className="text-soft-ink3 text-left">
                  <th className="px-3 py-2 font-medium">EG</th>
                  <th className="px-3 py-2 font-medium">Stufe</th>
                  <th className="px-3 py-2 font-medium text-right">Betrag</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {s.preview.preview.map((r, i) => (
                  <tr key={i} className="border-t border-soft-line2">
                    <td className="px-3 py-1.5 font-medium text-soft-ink">{r.salary_group}</td>
                    <td className="px-3 py-1.5 numeric">{r.level}</td>
                    <td className="px-3 py-1.5 numeric text-right">{eur(r.monthly_amount)}</td>
                    <td className="px-3 py-1.5">
                      {r.status === "error" ? <Badge variant="danger">Fehler</Badge>
                        : r.status === "warning" ? <Badge variant="warning">Überschneidung</Badge>
                        : <Badge variant="success">OK</Badge>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <NavButtons onBack={() => go(s.meta.source === "FILE" ? 2 : 3)} onNext={() => go(5)} nextLabel="Weiter zur Bestätigung" />
        </Card>
      )}

      {s.step === 5 && s.preview && (
        <Card>
          <h2 className="text-base font-semibold text-soft-ink mb-3">Import bestätigen</h2>
          <ul className="text-sm text-soft-ink2 space-y-1 mb-4">
            <li>Tarif: <span className="font-medium text-soft-ink">{s.meta.tariff_code}</span> · {s.meta.is_proposed ? "Geplant" : "Aktuell"} · ab {deDate(s.meta.valid_from)}</li>
            <li>{s.preview.preview.filter((r) => r.status !== "error").length} Zeilen werden geschrieben.</li>
            {s.preview.warning_rows > 0 && <li>Konfliktbehandlung: {s.resolution === "trim" ? "Bestehende Zeilen kürzen" : "Überspringen"}</li>}
          </ul>
          <div className="rounded-soft-xs bg-soft-accentSoft/40 border border-soft-accent/20 p-3 text-xs text-soft-ink2 mb-4">
            Nach dem Import werden Abrechnung und Prognose der betroffenen
            Mitarbeitenden mit den neuen Beträgen gerechnet.
          </div>
          <div className="flex items-center justify-between">
            <Button variant="ghost" onClick={() => go(4)} disabled={loading}>Zurück</Button>
            <Button variant="primary" loading={loading} onClick={confirm}>
              <Check className="h-4 w-4 mr-1" aria-hidden="true" /> Import übernehmen
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}

function Stepper({ current }: { current: number }) {
  return (
    <ol className="flex items-center gap-2 text-xs">
      {STEPS.map((label, i) => {
        const n = i + 1;
        const state = n < current ? "done" : n === current ? "active" : "todo";
        return (
          <li key={label} className="flex items-center gap-2">
            <span className={`flex items-center justify-center h-6 w-6 rounded-full font-semibold ${
              state === "done" ? "bg-soft-ok text-white" : state === "active" ? "bg-soft-accent text-white" : "bg-soft-line2 text-soft-ink3"
            }`}>
              {state === "done" ? <Check className="h-3.5 w-3.5" /> : n}
            </span>
            <span className={state === "active" ? "text-soft-ink font-medium" : "text-soft-ink3"}>{label}</span>
            {n < STEPS.length && <span className="w-6 h-px bg-soft-line2" />}
          </li>
        );
      })}
    </ol>
  );
}

function GridEditor({ onBack, onDone }: { onBack: () => void; onDone: (rows: TariffImportRow[]) => void }) {
  const [text, setText] = useState("E5\t2500\t2600\t2700\nE6\t2800\t2900\t3000");
  function parse() {
    const rows: TariffImportRow[] = [];
    for (const line of text.split("\n")) {
      const cells = line.split(/[\t;,]/).map((c) => c.trim()).filter(Boolean);
      if (cells.length < 2) continue;
      const group = cells[0];
      cells.slice(1).forEach((amt, idx) => {
        const n = Number(amt.replace(/\./g, "").replace(",", "."));
        if (!Number.isNaN(n) && n > 0) rows.push({ salary_group: group, level: idx + 1, monthly_amount: n, status: "valid" });
      });
    }
    onDone(rows);
  }
  return (
    <Card>
      <p className="text-sm text-soft-ink2 mb-2">
        Eine Zeile je Entgeltgruppe, Werte durch Tab/Komma/Semikolon getrennt:
        <span className="text-soft-ink3"> EG, Stufe1, Stufe2, …</span>
      </p>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={8}
        className="w-full rounded-soft-xs border border-soft-line bg-white px-3 py-2.5 text-sm font-mono outline-none focus:ring-2 focus:ring-soft-accent"
      />
      <NavButtons onBack={onBack} onNext={parse} nextLabel="Raster übernehmen" />
    </Card>
  );
}

function SourceCard({ icon: Icon, title, desc, active, onClick }: { icon: typeof Upload; title: string; desc: string; active: boolean; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className={`text-left bg-white rounded-soft border p-5 shadow-soft transition-all ${active ? "border-soft-accent" : "border-soft-line hover:border-soft-accent"}`}>
      <Icon className="h-7 w-7 text-soft-accent mb-3" aria-hidden="true" />
      <div className="font-medium text-soft-ink">{title}</div>
      <p className="text-xs text-soft-ink3 mt-1">{desc}</p>
    </button>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return <div className="bg-white rounded-soft border border-soft-line p-6 shadow-soft">{children}</div>;
}

function Labeled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-soft-ink2 mb-1">{label}</label>
      {children}
    </div>
  );
}

function NavButtons({ onBack, onNext, nextDisabled, nextLabel = "Weiter" }: { onBack: () => void; onNext?: () => void; nextDisabled?: boolean; nextLabel?: string }) {
  return (
    <div className="flex items-center justify-between pt-5">
      <Button variant="ghost" onClick={onBack}>Zurück</Button>
      {onNext && <Button variant="primary" onClick={onNext} disabled={nextDisabled}>{nextLabel}</Button>}
    </div>
  );
}
