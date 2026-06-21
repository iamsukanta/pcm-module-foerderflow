"use client";

// L.1 Scenario List · L.2 Configuration · L.4 Results · L.5 Promote.

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2, FlaskConical, Play, ArrowUpCircle, X } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { useToast } from "@/components/ui/ToastProvider";
import { eur, eur0, deDate } from "@/lib/pcmFormat";
import type { FiscalYearWithMeta } from "@/types/haushaltsjahre";
import type {
  PcmEmployee,
  Scenario,
  ScenarioParams,
  ScenarioResults,
  PcmApiErrorBody,
} from "@/types/pcm";

const STATUS: Record<Scenario["status"], { label: string; variant: "muted" | "default" | "success" }> = {
  DRAFT: { label: "Entwurf", variant: "muted" },
  COMPUTED: { label: "Berechnet", variant: "default" },
  PROMOTED: { label: "Übernommen", variant: "success" },
};

function inputCls() {
  return "w-full rounded-soft-xs border border-soft-line bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-soft-accent focus:border-soft-accent";
}

export function ScenarioClient({
  scenarios,
  fiscalYears,
  employees,
}: {
  scenarios: Scenario[];
  fiscalYears: FiscalYearWithMeta[];
  employees: PcmEmployee[];
}) {
  const router = useRouter();
  const toast = useToast();
  const [editing, setEditing] = useState<Scenario | "new" | null>(null);
  const [results, setResults] = useState<ScenarioResults | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function compute(id: string) {
    setBusy(id);
    const res = await fetch(`/api/protected/pcm/scenarios/${id}/compute`, { method: "POST" });
    const b = (await res.json().catch(() => ({}))) as { data?: ScenarioResults; error?: string };
    setBusy(null);
    if (res.ok && b.data) {
      setResults(b.data);
      router.refresh();
    } else {
      toast.error(b.error ?? "Berechnung fehlgeschlagen.");
    }
  }

  async function openResults(id: string) {
    const res = await fetch(`/api/protected/pcm/scenarios/${id}/results`);
    const b = (await res.json().catch(() => ({}))) as { data?: ScenarioResults };
    if (b.data) setResults(b.data);
  }

  async function remove(id: string) {
    const res = await fetch(`/api/protected/pcm/scenarios/${id}`, { method: "DELETE" });
    if (res.ok) {
      toast.success("Szenario gelöscht.");
      router.refresh();
    } else toast.error("Löschen fehlgeschlagen.");
  }

  return (
    <div className="space-y-5">
      <div className="flex justify-end">
        <Button variant="primary" onClick={() => setEditing("new")}>
          <Plus className="h-4 w-4 mr-1" aria-hidden="true" /> Neues Szenario
        </Button>
      </div>

      {scenarios.length === 0 ? (
        <EmptyState
          icon={FlaskConical}
          title="Keine Szenarien"
          description="Lege ein Szenario an, um Personalveränderungen gegen die aktuelle Prognose zu testen."
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {scenarios.map((s) => {
            const fy = fiscalYears.find((f) => f.id === s.fiscal_year_id);
            return (
              <div key={s.id} className="bg-white rounded-soft border border-soft-line p-5 shadow-soft">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="font-medium text-soft-ink">{s.name}</div>
                    <div className="text-xs text-soft-ink3 mt-0.5">HHJ {fy?.jahr ?? "—"}</div>
                  </div>
                  <Badge variant={STATUS[s.status].variant}>{STATUS[s.status].label}</Badge>
                </div>
                {s.delta_total !== null && (
                  <div className="mt-3 text-sm">
                    <span className="text-soft-ink3">Δ Prognose: </span>
                    <span className={`numeric font-semibold ${Number(s.delta_total) >= 0 ? "text-soft-crit" : "text-soft-ok"}`}>
                      {Number(s.delta_total) >= 0 ? "+" : ""}{eur(s.delta_total)}
                    </span>
                  </div>
                )}
                <div className="flex flex-wrap justify-end gap-2 mt-3">
                  {s.status !== "PROMOTED" && (
                    <Button variant="secondary" size="sm" onClick={() => setEditing(s)}>Bearbeiten</Button>
                  )}
                  <Button variant="secondary" size="sm" loading={busy === s.id} onClick={() => compute(s.id)}>
                    <Play className="h-3.5 w-3.5 mr-1" /> Berechnen
                  </Button>
                  {s.status !== "DRAFT" && (
                    <Button variant="secondary" size="sm" onClick={() => openResults(s.id)}>Ergebnisse</Button>
                  )}
                  <Button variant="ghost" size="sm" onClick={() => remove(s.id)}>
                    <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {editing && (
        <ConfigModal
          scenario={editing === "new" ? null : editing}
          fiscalYears={fiscalYears}
          employees={employees}
          onClose={() => setEditing(null)}
        />
      )}
      {results && (
        <ResultsModal
          results={results}
          onClose={() => setResults(null)}
          onPromoted={() => { setResults(null); router.refresh(); }}
        />
      )}
    </div>
  );
}

function ConfigModal({
  scenario,
  fiscalYears,
  employees,
  onClose,
}: {
  scenario: Scenario | null;
  fiscalYears: FiscalYearWithMeta[];
  employees: PcmEmployee[];
  onClose: () => void;
}) {
  const router = useRouter();
  const toast = useToast();
  const isEdit = !!scenario;
  const defaultFy = fiscalYears.find((f) => f.status === "OFFEN") ?? fiscalYears[0];
  const [name, setName] = useState(scenario?.name ?? "");
  const [fyId, setFyId] = useState(scenario?.fiscal_year_id ?? defaultFy?.id ?? "");
  const [growth, setGrowth] = useState(scenario?.params.growth_rate_pct?.toString() ?? "");
  const [hours, setHours] = useState(scenario?.params.hour_overrides ?? []);
  const [levels, setLevels] = useState(scenario?.params.level_overrides ?? []);
  const [hires, setHires] = useState(scenario?.params.hires ?? []);
  const [loading, setLoading] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || !fyId) { toast.error("Name und Haushaltsjahr erforderlich."); return; }
    const params: ScenarioParams = {};
    if (growth) params.growth_rate_pct = Number(growth);
    if (hours.length) params.hour_overrides = hours.filter((h) => h.employee_id);
    if (levels.length) params.level_overrides = levels.filter((l) => l.employee_id);
    if (hires.length) params.hires = hires;
    setLoading(true);
    const url = isEdit ? `/api/protected/pcm/scenarios/${scenario!.id}` : "/api/protected/pcm/scenarios";
    const res = await fetch(url, {
      method: isEdit ? "PATCH" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim(), fiscal_year_id: fyId, params }),
    });
    const b = (await res.json().catch(() => ({}))) as Partial<PcmApiErrorBody>;
    setLoading(false);
    if (!res.ok) { toast.error(b.error ?? "Speichern fehlgeschlagen."); return; }
    toast.success(isEdit ? "Szenario gespeichert." : "Szenario angelegt.");
    onClose();
    router.refresh();
  }

  return (
    <Modal title={isEdit ? "Szenario bearbeiten" : "Neues Szenario"} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <Labeled label="Name"><input value={name} onChange={(e) => setName(e.target.value)} className={inputCls()} placeholder="Tarifrunde +3%" /></Labeled>
          <Labeled label="Haushaltsjahr">
            <select value={fyId} onChange={(e) => setFyId(e.target.value)} className={inputCls()}>
              {fiscalYears.map((f) => <option key={f.id} value={f.id}>{f.jahr}</option>)}
            </select>
          </Labeled>
          <Labeled label="Tarifsteigerung (% global)"><input type="number" step="0.1" value={growth} onChange={(e) => setGrowth(e.target.value)} className={`${inputCls()} numeric`} placeholder="3" /></Labeled>
        </div>

        {/* hour overrides */}
        <Section title="Stunden-Anpassungen" onAdd={() => setHours([...hours, { employee_id: "", weekly_hours: 0 }])}>
          {hours.map((h, i) => (
            <div key={i} className="flex items-center gap-2">
              <select value={h.employee_id} onChange={(e) => setHours(hours.map((x, j) => j === i ? { ...x, employee_id: e.target.value } : x))} className={`${inputCls()} flex-1`}>
                <option value="">— Mitarbeiter:in —</option>
                {employees.map((e) => <option key={e.id} value={e.id}>{e.vorname} {e.nachname}</option>)}
              </select>
              <input type="number" value={h.weekly_hours} onChange={(e) => setHours(hours.map((x, j) => j === i ? { ...x, weekly_hours: Number(e.target.value) } : x))} className={`${inputCls()} numeric w-24`} placeholder="h" />
              <RemoveBtn onClick={() => setHours(hours.filter((_, j) => j !== i))} />
            </div>
          ))}
        </Section>

        {/* level overrides */}
        <Section title="Stufen-Anpassungen" onAdd={() => setLevels([...levels, { employee_id: "", level: 1 }])}>
          {levels.map((l, i) => (
            <div key={i} className="flex items-center gap-2">
              <select value={l.employee_id} onChange={(e) => setLevels(levels.map((x, j) => j === i ? { ...x, employee_id: e.target.value } : x))} className={`${inputCls()} flex-1`}>
                <option value="">— Mitarbeiter:in —</option>
                {employees.map((e) => <option key={e.id} value={e.id}>{e.vorname} {e.nachname}</option>)}
              </select>
              <input type="number" min={1} value={l.level} onChange={(e) => setLevels(levels.map((x, j) => j === i ? { ...x, level: Number(e.target.value) } : x))} className={`${inputCls()} numeric w-24`} placeholder="Stufe" />
              <RemoveBtn onClick={() => setLevels(levels.filter((_, j) => j !== i))} />
            </div>
          ))}
        </Section>

        {/* hires */}
        <Section title="Hypothetische Neueinstellungen" onAdd={() => setHires([...hires, { name: "", tariff_code: "", salary_group: "", level: 1, weekly_hours: 39, start_month: "" }])}>
          {hires.map((h, i) => (
            <div key={i} className="grid grid-cols-2 sm:grid-cols-6 gap-2 items-center">
              <input value={h.name ?? ""} onChange={(e) => setHires(hires.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} className={inputCls()} placeholder="Bezeichnung" />
              <input value={h.tariff_code ?? ""} onChange={(e) => setHires(hires.map((x, j) => j === i ? { ...x, tariff_code: e.target.value } : x))} className={inputCls()} placeholder="Tarif" />
              <input value={h.salary_group ?? ""} onChange={(e) => setHires(hires.map((x, j) => j === i ? { ...x, salary_group: e.target.value } : x))} className={inputCls()} placeholder="EG" />
              <input type="number" value={h.level ?? 1} onChange={(e) => setHires(hires.map((x, j) => j === i ? { ...x, level: Number(e.target.value) } : x))} className={`${inputCls()} numeric`} placeholder="Stufe" />
              <input type="number" value={h.weekly_hours ?? 39} onChange={(e) => setHires(hires.map((x, j) => j === i ? { ...x, weekly_hours: Number(e.target.value) } : x))} className={`${inputCls()} numeric`} placeholder="h" />
              <div className="flex items-center gap-1">
                <input type="date" value={h.start_month ?? ""} onChange={(e) => setHires(hires.map((x, j) => j === i ? { ...x, start_month: e.target.value } : x))} className={inputCls()} />
                <RemoveBtn onClick={() => setHires(hires.filter((_, j) => j !== i))} />
              </div>
            </div>
          ))}
        </Section>

        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={loading}>Abbrechen</Button>
          <Button type="submit" variant="primary" loading={loading}>{isEdit ? "Speichern" : "Anlegen"}</Button>
        </div>
      </form>
    </Modal>
  );
}

function ResultsModal({
  results,
  onClose,
  onPromoted,
}: {
  results: ScenarioResults;
  onClose: () => void;
  onPromoted: () => void;
}) {
  const toast = useToast();
  const [confirming, setConfirming] = useState(false);
  const [loading, setLoading] = useState(false);
  const s = results.scenario;
  const maxV = Math.max(1, ...results.by_month.flatMap((m) => [Number(m.baseline), Number(m.scenario)]));

  async function promote() {
    setLoading(true);
    const res = await fetch(`/api/protected/pcm/scenarios/${s.id}/promote`, { method: "POST" });
    setLoading(false);
    if (res.ok) {
      toast.success("Szenario übernommen — Prognose neu berechnet.");
      onPromoted();
    } else {
      const b = (await res.json().catch(() => ({}))) as Partial<PcmApiErrorBody>;
      toast.error(b.error ?? "Übernahme fehlgeschlagen.");
    }
  }

  return (
    <Modal title={`Ergebnisse · ${s.name}`} onClose={onClose}>
      <div className="space-y-4">
        <div className="grid grid-cols-3 gap-3 text-sm">
          <Stat label="Baseline" value={eur(s.baseline_total)} />
          <Stat label="Szenario" value={eur(s.scenario_total)} />
          <Stat label="Delta" value={`${Number(s.delta_total) >= 0 ? "+" : ""}${eur(s.delta_total)}`} accent={Number(s.delta_total) >= 0 ? "crit" : "ok"} />
        </div>

        <div>
          <h3 className="text-xs font-semibold text-soft-ink3 mb-2">Je Monat — Baseline vs. Szenario</h3>
          <div className="space-y-1">
            {results.by_month.map((m) => (
              <div key={m.monat} className="flex items-center gap-2">
                <span className="w-12 text-[11px] text-soft-ink3 shrink-0">{m.label}</span>
                <div className="flex-1 space-y-0.5">
                  <div className="h-2 rounded-full bg-soft-line2 overflow-hidden"><div className="h-full bg-soft-ink3/40" style={{ width: `${(Number(m.baseline) / maxV) * 100}%` }} /></div>
                  <div className="h-2 rounded-full bg-soft-line2 overflow-hidden"><div className="h-full bg-soft-accent" style={{ width: `${(Number(m.scenario) / maxV) * 100}%` }} /></div>
                </div>
                <span className="w-20 text-right numeric text-[11px] text-soft-ink2">{Number(m.delta) >= 0 ? "+" : ""}{eur0(m.delta)}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto max-h-56 overflow-y-auto border border-soft-line rounded-soft-xs">
          <table className="w-full text-xs">
            <thead className="bg-soft-line2/50 sticky top-0 text-soft-ink3 text-left"><tr><th className="px-2 py-1">Mitarbeiter:in</th><th className="px-2 py-1 text-right">Baseline</th><th className="px-2 py-1 text-right">Szenario</th><th className="px-2 py-1 text-right">Delta</th></tr></thead>
            <tbody>
              {results.by_employee.map((e) => (
                <tr key={e.label} className="border-t border-soft-line2">
                  <td className="px-2 py-1 text-soft-ink">{e.label}{e.employee_id === null && <Badge variant="default" className="ml-1">neu</Badge>}</td>
                  <td className="px-2 py-1 text-right numeric">{eur0(e.baseline)}</td>
                  <td className="px-2 py-1 text-right numeric">{eur0(e.scenario)}</td>
                  <td className="px-2 py-1 text-right numeric">{Number(e.delta) >= 0 ? "+" : ""}{eur0(e.delta)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {s.status === "PROMOTED" ? (
          <p className="text-xs text-soft-ok">Bereits übernommen{s.computed_at ? ` · ${deDate(s.computed_at)}` : ""}.</p>
        ) : confirming ? (
          <div className="rounded-soft-xs bg-soft-warnSoft border border-soft-warn/30 p-3 text-sm space-y-2">
            <p className="text-soft-ink2 text-xs">Übernahme berechnet die Ist-Prognose mit den Szenario-Parametern neu. Hypothetische Neueinstellungen werden dabei nicht übernommen.</p>
            <div className="flex gap-2">
              <Button variant="primary" size="sm" loading={loading} onClick={promote}><ArrowUpCircle className="h-3.5 w-3.5 mr-1" /> Wirklich übernehmen</Button>
              <Button variant="ghost" size="sm" onClick={() => setConfirming(false)}>Abbrechen</Button>
            </div>
          </div>
        ) : (
          <div className="flex justify-end">
            <Button variant="primary" onClick={() => setConfirming(true)}><ArrowUpCircle className="h-4 w-4 mr-1" /> In Prognose übernehmen</Button>
          </div>
        )}
      </div>
    </Modal>
  );
}

function Section({ title, onAdd, children }: { title: string; onAdd: () => void; children: React.ReactNode }) {
  return (
    <div className="border border-soft-line rounded-soft-xs p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-soft-ink2">{title}</span>
        <Button type="button" variant="ghost" size="sm" onClick={onAdd}><Plus className="h-3.5 w-3.5 mr-1" /> Hinzufügen</Button>
      </div>
      {children}
    </div>
  );
}

function RemoveBtn({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} aria-label="Entfernen" className="text-soft-ink3 hover:text-soft-crit p-1 shrink-0">
      <Trash2 className="h-4 w-4" aria-hidden="true" />
    </button>
  );
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-soft-ink/30 p-4 overflow-y-auto" onClick={onClose}>
      <div className="bg-white rounded-soft border border-soft-line shadow-soft-lg w-full max-w-3xl my-8" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-soft-line">
          <h2 className="text-base font-semibold text-soft-ink">{title}</h2>
          <button type="button" onClick={onClose} aria-label="Schließen" className="text-soft-ink3 hover:text-soft-ink"><X className="h-5 w-5" /></button>
        </div>
        <div className="p-6">{children}</div>
      </div>
    </div>
  );
}

function Labeled({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><label className="block text-sm font-medium text-soft-ink2 mb-1">{label}</label>{children}</div>;
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: "crit" | "ok" }) {
  return (
    <div className="rounded-soft-xs bg-soft-line2/40 px-3 py-2">
      <div className="text-[11px] text-soft-ink3">{label}</div>
      <div className={`numeric font-semibold ${accent === "crit" ? "text-soft-crit" : accent === "ok" ? "text-soft-ok" : "text-soft-ink"}`}>{value}</div>
    </div>
  );
}
