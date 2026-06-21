"use client";

// D.2 Tariff Code Detail — hosts the Salary Grid, Tier Progression Rules (D.5),
// and Validity Timeline tabs, plus the inline Row form (D.3) with overlap
// resolution (D.4) and the Level form (D.6).

import { useMemo, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Plus, Table2, ListTree, CalendarClock, X, AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { useToast } from "@/components/ui/ToastProvider";
import { compareGroups, eur, eur0, deDate } from "@/lib/pcmFormat";
import type { OverlapCheck, SalaryLevel, SalaryTariff, PcmApiErrorBody } from "@/types/pcm";

const TODAY = new Date().toISOString().slice(0, 10);
const MONTHS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];

function inputCls(error?: string): string {
  return `w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors
    focus:ring-2 focus:ring-soft-accent focus:border-soft-accent ${
      error ? "border-soft-crit bg-soft-critSoft text-soft-crit" : "border-soft-line bg-white"
    }`;
}

function prevDay(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() - 1);
  return d.toISOString().slice(0, 10);
}

function covers(r: SalaryTariff, month: string): boolean {
  return r.valid_from <= month && (r.valid_to === null || r.valid_to >= month);
}

type Tab = "grid" | "levels" | "timeline";

export function TariffDetailClient({
  tariffCode,
  rows,
  levels,
}: {
  tariffCode: string;
  rows: SalaryTariff[];
  levels: SalaryLevel[];
}) {
  const [tab, setTab] = useState<Tab>("grid");
  const [rowForm, setRowForm] = useState<Partial<SalaryTariff> | null>(null);
  const [levelForm, setLevelForm] = useState<{ level: SalaryLevel | null; tariffId: string; group: string; nextNo: number } | null>(null);

  const groups = useMemo(
    () => [...new Set(rows.map((r) => r.salary_group))].sort(compareGroups),
    [rows],
  );
  const maxLevel = useMemo(
    () => rows.reduce((m, r) => Math.max(m, r.level), 0),
    [rows],
  );
  const isMaxTier = useMemo(() => {
    const s = new Set<string>();
    for (const l of levels) if (l.months_to_next_level === null) s.add(`${l.salary_group}__${l.level_no}`);
    return s;
  }, [levels]);

  function repTariffId(group: string): string | null {
    const cur = rows.find((r) => r.salary_group === group && !r.is_proposed && covers(r, TODAY));
    return (cur ?? rows.find((r) => r.salary_group === group))?.id ?? null;
  }

  const tabs: { key: Tab; label: string; icon: typeof Table2 }[] = [
    { key: "grid", label: "Entgelttabelle", icon: Table2 },
    { key: "levels", label: "Stufen-Regeln", icon: ListTree },
    { key: "timeline", label: "Gültigkeits-Timeline", icon: CalendarClock },
  ];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 border-b border-soft-line">
        <div className="flex gap-1">
          {tabs.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
                tab === t.key
                  ? "border-soft-accent text-soft-accent"
                  : "border-transparent text-soft-ink3 hover:text-soft-ink"
              }`}
            >
              <t.icon className="h-4 w-4" aria-hidden="true" />
              {t.label}
            </button>
          ))}
        </div>
        {tab === "grid" && (
          <Button
            variant="primary"
            onClick={() => setRowForm({ tariff_code: tariffCode, salary_group: "", level: maxLevel + 1, standard_hours: rows[0]?.standard_hours, is_proposed: false })}
          >
            <Plus className="h-4 w-4 mr-1" aria-hidden="true" />
            Zeile hinzufügen
          </Button>
        )}
      </div>

      {tab === "grid" && (
        <SalaryGrid
          groups={groups}
          maxLevel={maxLevel}
          rows={rows}
          isMaxTier={isMaxTier}
          onCell={(group, level) => {
            const existing = rows
              .filter((r) => r.salary_group === group && r.level === level && !r.is_proposed && covers(r, TODAY))
              .sort((a, b) => b.valid_from.localeCompare(a.valid_from))[0];
            setRowForm(existing ?? { tariff_code: tariffCode, salary_group: group, level, standard_hours: rows[0]?.standard_hours, is_proposed: false });
          }}
        />
      )}

      {tab === "levels" && (
        <LevelTable
          groups={groups}
          levels={levels}
          onEdit={(lvl) => setLevelForm({ level: lvl, tariffId: lvl.tariff_id, group: lvl.salary_group, nextNo: lvl.level_no })}
          onAdd={(group) => {
            const tid = repTariffId(group);
            if (!tid) return;
            const nextNo = Math.max(0, ...levels.filter((l) => l.salary_group === group).map((l) => l.level_no)) + 1;
            setLevelForm({ level: null, tariffId: tid, group, nextNo });
          }}
        />
      )}

      {tab === "timeline" && <ValidityTimeline groups={groups} rows={rows} onSegment={(r) => setRowForm(r)} />}

      {rowForm && (
        <RowFormModal
          tariffCode={tariffCode}
          initial={rowForm}
          onClose={() => setRowForm(null)}
        />
      )}
      {levelForm && (
        <LevelFormModal
          state={levelForm}
          onClose={() => setLevelForm(null)}
        />
      )}
    </div>
  );
}

// ── D.2 Salary Grid ───────────────────────────────────────────────────────────
function SalaryGrid({
  groups,
  maxLevel,
  rows,
  isMaxTier,
  onCell,
}: {
  groups: string[];
  maxLevel: number;
  rows: SalaryTariff[];
  isMaxTier: Set<string>;
  onCell: (group: string, level: number) => void;
}) {
  if (groups.length === 0) {
    return <p className="text-sm text-soft-ink3 py-8 text-center">Noch keine Tarif-Zeilen. Lege die erste Zeile an.</p>;
  }
  const tiers = Array.from({ length: maxLevel }, (_, i) => i + 1);
  return (
    <div className="overflow-x-auto bg-white rounded-soft border border-soft-line shadow-soft">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="text-soft-ink3">
            <th className="sticky left-0 bg-white text-left font-medium px-3 py-2 border-b border-soft-line">EG</th>
            {tiers.map((t) => (
              <th key={t} className="text-right font-medium px-3 py-2 border-b border-soft-line whitespace-nowrap">
                Stufe {t}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {groups.map((g) => (
            <tr key={g} className="hover:bg-soft-ink/[0.02]">
              <td className="sticky left-0 bg-white font-medium text-soft-ink px-3 py-2 border-b border-soft-line2">{g}</td>
              {tiers.map((level) => {
                const current = rows
                  .filter((r) => r.salary_group === g && r.level === level && !r.is_proposed && covers(r, TODAY))
                  .sort((a, b) => b.valid_from.localeCompare(a.valid_from));
                const cell = current[0];
                const max = isMaxTier.has(`${g}__${level}`);
                return (
                  <td key={level} className="px-1 py-1 border-b border-soft-line2 text-right">
                    <button
                      type="button"
                      onClick={() => onCell(g, level)}
                      className={`w-full px-2 py-1.5 rounded-soft-xs numeric text-right transition-colors ${
                        cell
                          ? max
                            ? "bg-soft-warnSoft text-soft-warn hover:brightness-95"
                            : "text-soft-ink hover:bg-soft-accentSoft"
                          : "text-soft-ink4 hover:bg-soft-line2"
                      }`}
                      title={cell ? `${eur(cell.monthly_amount)} · ${deDate(cell.valid_from)}–${deDate(cell.valid_to)}` : "Zeile anlegen"}
                    >
                      {cell ? eur0(cell.monthly_amount) : "—"}
                      {current.length > 1 && <span className="ml-1 text-[10px] text-soft-accent" aria-label="Mehrere Gültigkeitsfenster">⧉</span>}
                    </button>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-[11px] text-soft-ink3 px-3 py-2">
        Gelbe Zelle = Endstufe (keine automatische Höhergruppierung). ⧉ = mehrere
        Gültigkeitsfenster (unterjähriger Wechsel).
      </p>
    </div>
  );
}

// ── D.5 Tier Progression Rules ──────────────────────────────────────────────
function LevelTable({
  groups,
  levels,
  onEdit,
  onAdd,
}: {
  groups: string[];
  levels: SalaryLevel[];
  onEdit: (lvl: SalaryLevel) => void;
  onAdd: (group: string) => void;
}) {
  return (
    <div className="space-y-4">
      <div className="rounded-soft-xs bg-soft-accentSoft/40 border border-soft-accent/20 p-3 text-xs text-soft-ink2">
        Diese Regeln steuern den automatischen Stufenaufstieg. Der nächtliche
        Promotion-Job hebt Mitarbeitende, deren Monate in der Stufe ≥
        <code className="mx-1">months_to_next_level</code> sind, in die nächste
        Stufe. Endstufe = „MAX“.
      </div>
      {groups.map((g) => {
        const tiers = levels
          .filter((l) => l.salary_group === g)
          .sort((a, b) => a.level_no - b.level_no);
        return (
          <div key={g} className="bg-white rounded-soft border border-soft-line p-4 shadow-soft">
            <div className="flex items-center justify-between mb-3">
              <span className="font-medium text-soft-ink">{g}</span>
              <Button variant="secondary" onClick={() => onAdd(g)}>
                <Plus className="h-3.5 w-3.5 mr-1" aria-hidden="true" />
                Stufe
              </Button>
            </div>
            {tiers.length === 0 ? (
              <p className="text-xs text-soft-ink3">Keine Stufen-Regeln hinterlegt.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {tiers.map((l) => (
                  <button
                    key={l.id}
                    type="button"
                    onClick={() => onEdit(l)}
                    className={`text-left px-3 py-2 rounded-soft-xs border transition-colors ${
                      l.months_to_next_level === null
                        ? "bg-soft-warnSoft border-soft-warn/30 text-soft-warn"
                        : "bg-soft-line2/50 border-soft-line hover:border-soft-accent"
                    }`}
                  >
                    <div className="text-xs font-medium">Stufe {l.level_no}</div>
                    <div className="numeric text-sm text-soft-ink">{eur0(l.monthly_amount)}</div>
                    <div className="text-[11px] text-soft-ink3">
                      {l.months_to_next_level === null ? "MAX" : `${l.months_to_next_level} Mon. → Stufe ${l.level_no + 1}`}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Validity Timeline ───────────────────────────────────────────────────────
function ValidityTimeline({
  groups,
  rows,
  onSegment,
}: {
  groups: string[];
  rows: SalaryTariff[];
  onSegment: (r: SalaryTariff) => void;
}) {
  const year = new Date().getFullYear();
  function seg(r: SalaryTariff): { left: number; width: number } {
    const from = new Date(r.valid_from);
    const startMonth = from.getFullYear() < year ? 0 : from.getMonth();
    let endMonth = 11;
    if (r.valid_to) {
      const to = new Date(r.valid_to);
      endMonth = to.getFullYear() > year ? 11 : to.getMonth();
    }
    return { left: (startMonth / 12) * 100, width: Math.max(((endMonth - startMonth + 1) / 12) * 100, 4) };
  }
  return (
    <div className="space-y-4">
      <div className="flex text-[10px] text-soft-ink3 pl-24">
        {MONTHS.map((m, i) => (
          <span key={i} className="flex-1 text-center">{m}</span>
        ))}
      </div>
      {groups.map((g) => {
        const groupRows = rows.filter((r) => r.salary_group === g).sort((a, b) => a.level - b.level || a.valid_from.localeCompare(b.valid_from));
        const byLevel = [...new Set(groupRows.map((r) => r.level))].sort((a, b) => a - b);
        return (
          <div key={g}>
            <div className="text-xs font-medium text-soft-ink2 mb-1">{g} · Bezugsjahr {year}</div>
            {byLevel.map((lvl) => (
              <div key={lvl} className="flex items-center gap-2 mb-1">
                <span className="w-20 shrink-0 text-[11px] text-soft-ink3">Stufe {lvl}</span>
                <div className="relative flex-1 h-6 rounded-soft-xs bg-soft-line2 overflow-hidden">
                  {groupRows.filter((r) => r.level === lvl).map((r) => {
                    const { left, width } = seg(r);
                    return (
                      <button
                        key={r.id}
                        type="button"
                        onClick={() => onSegment(r)}
                        style={{ left: `${left}%`, width: `${width}%` }}
                        title={`${eur(r.monthly_amount)} · ${deDate(r.valid_from)}–${deDate(r.valid_to)}`}
                        className={`absolute top-0 h-full flex items-center justify-center text-[10px] font-medium numeric ${
                          r.is_proposed
                            ? "bg-soft-accentSoft text-soft-accent border border-dashed border-soft-accent"
                            : "bg-soft-accent text-white"
                        }`}
                      >
                        <span className="truncate px-1">{eur0(r.monthly_amount)}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}

// ── D.3 Row form + D.4 overlap resolution ───────────────────────────────────
function RowFormModal({
  tariffCode,
  initial,
  onClose,
}: {
  tariffCode: string;
  initial: Partial<SalaryTariff>;
  onClose: () => void;
}) {
  const router = useRouter();
  const toast = useToast();
  const isEdit = !!initial.id;
  const [v, setV] = useState({
    salary_group: initial.salary_group ?? "",
    level: String(initial.level ?? 1),
    monthly_amount: initial.monthly_amount ?? "",
    standard_hours: initial.standard_hours ?? "39",
    valid_from: initial.valid_from ?? "",
    valid_to: initial.valid_to ?? "",
    bav_rate_pct: initial.bav_rate_pct ?? "",
    is_proposed: initial.is_proposed ?? false,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [conflict, setConflict] = useState<SalaryTariff | null>(null);
  const [loading, setLoading] = useState(false);

  function set<K extends keyof typeof v>(k: K, val: (typeof v)[K]) {
    setV((p) => ({ ...p, [k]: val }));
  }

  async function checkOverlap() {
    if (!v.salary_group || !v.valid_from) return;
    const params = new URLSearchParams({
      tariff_code: tariffCode,
      salary_group: v.salary_group,
      level: v.level,
      valid_from: v.valid_from,
      is_proposed: String(v.is_proposed),
    });
    if (v.valid_to) params.set("valid_to", v.valid_to);
    if (initial.id) params.set("exclude_id", initial.id);
    const res = await fetch(`/api/protected/pcm/tariff-rows/check-overlap?${params}`);
    if (!res.ok) return;
    const { data } = (await res.json()) as { data: OverlapCheck };
    setConflict(data.overlap ? data.conflict : null);
  }

  async function trimConflict() {
    if (!conflict) return;
    const res = await fetch(`/api/protected/pcm/salary-tariffs/${conflict.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ valid_to: prevDay(v.valid_from) }),
    });
    if (res.ok) {
      toast.success(`Bestehende Zeile auf ${deDate(prevDay(v.valid_from))} gekürzt.`);
      setConflict(null);
    } else {
      const b = (await res.json().catch(() => ({}))) as Partial<PcmApiErrorBody>;
      toast.error(b.error ?? "Kürzen fehlgeschlagen.");
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    const next: Record<string, string> = {};
    if (!v.salary_group.trim()) next.salary_group = "Entgeltgruppe erforderlich.";
    if (!v.monthly_amount) next.monthly_amount = "Betrag erforderlich.";
    if (!v.valid_from) next.valid_from = "Gültig-ab erforderlich.";
    if (Object.keys(next).length) return setErrors(next);
    setErrors({});
    setLoading(true);
    const payload = {
      tariff_code: tariffCode,
      salary_group: v.salary_group.trim(),
      level: Number(v.level),
      monthly_amount: Number(v.monthly_amount),
      standard_hours: Number(v.standard_hours),
      valid_from: v.valid_from,
      valid_to: v.valid_to || null,
      bav_rate_pct: v.bav_rate_pct ? Number(v.bav_rate_pct) : null,
      is_proposed: v.is_proposed,
    };
    const url = isEdit
      ? `/api/protected/pcm/salary-tariffs/${initial.id}`
      : "/api/protected/pcm/salary-tariffs";
    const res = await fetch(url, {
      method: isEdit ? "PATCH" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const b = (await res.json().catch(() => ({}))) as { data?: SalaryTariff; error?: string; code?: string; conflict_id?: string };
    setLoading(false);
    if (!res.ok) {
      if (b.code === "TARIFF_WINDOW_OVERLAP") {
        await checkOverlap();
        setErrors({ valid_from: b.error ?? "Gültigkeitsfenster überschneidet sich." });
      } else {
        setErrors({ general: b.error ?? "Speichern fehlgeschlagen." });
      }
      return;
    }
    toast.success(isEdit ? "Tarif-Zeile gespeichert." : "Tarif-Zeile angelegt.");
    onClose();
    router.refresh();
  }

  async function remove() {
    if (!initial.id) return;
    const res = await fetch(`/api/protected/pcm/salary-tariffs/${initial.id}`, { method: "DELETE" });
    const b = (await res.json().catch(() => ({}))) as Partial<PcmApiErrorBody>;
    if (res.ok) {
      toast.success("Tarif-Zeile gelöscht.");
      onClose();
      router.refresh();
    } else {
      toast.error(b.error ?? "Löschen fehlgeschlagen.");
    }
  }

  return (
    <Modal title={`${isEdit ? "Tarif-Zeile bearbeiten" : "Neue Tarif-Zeile"} · ${tariffCode}`} onClose={onClose}>
      <form onSubmit={submit} noValidate className="space-y-4">
        {errors.general && (
          <div role="alert" className="rounded-soft-xs bg-soft-critSoft border border-soft-crit/30 p-3 text-sm text-soft-crit">
            {errors.general}
          </div>
        )}
        {conflict && (
          <div className="rounded-soft-xs bg-soft-warnSoft border border-soft-warn/30 p-3 text-sm space-y-2">
            <div className="flex items-center gap-2 font-medium text-soft-warn">
              <AlertTriangle className="h-4 w-4" aria-hidden="true" />
              Überschneidung mit bestehender Zeile
            </div>
            <p className="text-soft-ink2 text-xs">
              {conflict.salary_group} · Stufe {conflict.level} · {eur(conflict.monthly_amount)} ·{" "}
              {deDate(conflict.valid_from)}–{deDate(conflict.valid_to)}
            </p>
            <Button type="button" variant="secondary" onClick={trimConflict}>
              Bestehende Zeile auf {deDate(prevDay(v.valid_from))} kürzen
            </Button>
          </div>
        )}
        <div className="grid grid-cols-2 gap-4">
          <Field label="Entgeltgruppe" error={errors.salary_group}>
            <input value={v.salary_group} onChange={(e) => set("salary_group", e.target.value)} placeholder="E10" className={inputCls(errors.salary_group)} />
          </Field>
          <Field label="Stufe">
            <input type="number" min={1} value={v.level} onChange={(e) => set("level", e.target.value)} className={`${inputCls()} numeric`} />
          </Field>
          <Field label="Monatsbetrag (€)" error={errors.monthly_amount}>
            <input type="number" step="0.01" value={v.monthly_amount} onChange={(e) => set("monthly_amount", e.target.value)} className={`${inputCls(errors.monthly_amount)} numeric`} />
          </Field>
          <Field label="Wochenstunden (Vollzeit)">
            <input type="number" step="0.5" value={v.standard_hours} onChange={(e) => set("standard_hours", e.target.value)} className={`${inputCls()} numeric`} />
          </Field>
          <Field label="Gültig ab" error={errors.valid_from}>
            <input type="date" value={v.valid_from} onChange={(e) => set("valid_from", e.target.value)} onBlur={checkOverlap} className={inputCls(errors.valid_from)} />
          </Field>
          <Field label="Gültig bis (optional)">
            <input type="date" value={v.valid_to ?? ""} onChange={(e) => set("valid_to", e.target.value)} onBlur={checkOverlap} className={inputCls()} />
          </Field>
          <Field label="BAV-Satz (%)">
            <input type="number" step="0.1" value={v.bav_rate_pct ?? ""} onChange={(e) => set("bav_rate_pct", e.target.value)} placeholder="4.7" className={`${inputCls()} numeric`} />
          </Field>
          <div className="flex items-end">
            <label className="flex items-center gap-2 text-sm text-soft-ink2">
              <input type="checkbox" checked={v.is_proposed} onChange={(e) => set("is_proposed", e.target.checked)} className="h-4 w-4 accent-soft-accent" />
              Geplant (noch nicht in Kraft)
            </label>
          </div>
        </div>
        <div className="flex items-center justify-between pt-2">
          {isEdit ? (
            <Button type="button" variant="ghost" onClick={remove}>Löschen</Button>
          ) : <span />}
          <div className="flex gap-3">
            <Button type="button" variant="secondary" onClick={onClose} disabled={loading}>Abbrechen</Button>
            <Button type="submit" variant="primary" loading={loading}>{isEdit ? "Speichern" : "Anlegen"}</Button>
          </div>
        </div>
      </form>
    </Modal>
  );
}

// ── D.6 Level form ───────────────────────────────────────────────────────────
function LevelFormModal({
  state,
  onClose,
}: {
  state: { level: SalaryLevel | null; tariffId: string; group: string; nextNo: number };
  onClose: () => void;
}) {
  const router = useRouter();
  const toast = useToast();
  const isEdit = !!state.level;
  const [amount, setAmount] = useState(state.level?.monthly_amount ?? "");
  const [months, setMonths] = useState(state.level?.months_to_next_level != null ? String(state.level.months_to_next_level) : "");
  const [isMax, setIsMax] = useState(state.level ? state.level.months_to_next_level === null : false);
  const [loading, setLoading] = useState(false);
  const levelNo = state.level?.level_no ?? state.nextNo;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    const body = {
      monthly_amount: Number(amount),
      months_to_next_level: isMax ? null : Number(months),
    };
    const res = isEdit
      ? await fetch(`/api/protected/pcm/salary-levels/${state.level!.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        })
      : await fetch(`/api/protected/pcm/salary-tariffs/${state.tariffId}/levels`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...body, salary_group: state.group, level_no: levelNo }),
        });
    const b = (await res.json().catch(() => ({}))) as Partial<PcmApiErrorBody>;
    setLoading(false);
    if (res.ok) {
      toast.success(isEdit ? "Stufe gespeichert." : "Stufe angelegt.");
      onClose();
      router.refresh();
    } else {
      toast.error(b.error ?? "Speichern fehlgeschlagen.");
    }
  }

  async function remove() {
    if (!state.level) return;
    const res = await fetch(`/api/protected/pcm/salary-levels/${state.level.id}`, { method: "DELETE" });
    if (res.ok) {
      toast.success("Stufe gelöscht.");
      onClose();
      router.refresh();
    } else {
      const b = (await res.json().catch(() => ({}))) as Partial<PcmApiErrorBody>;
      toast.error(b.error ?? "Löschen fehlgeschlagen.");
    }
  }

  return (
    <Modal title={`${isEdit ? "Stufe bearbeiten" : "Neue Stufe"} · ${state.group} Stufe ${levelNo}`} onClose={onClose}>
      <form onSubmit={submit} noValidate className="space-y-4">
        <Field label="Monatsbetrag (€)">
          <input type="number" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} className={`${inputCls()} numeric`} required />
        </Field>
        <Field label="Monate bis nächste Stufe">
          <input type="number" min={1} value={months} onChange={(e) => setMonths(e.target.value)} disabled={isMax} className={`${inputCls()} numeric ${isMax ? "opacity-50" : ""}`} />
        </Field>
        <label className="flex items-center gap-2 text-sm text-soft-ink2">
          <input type="checkbox" checked={isMax} onChange={(e) => setIsMax(e.target.checked)} className="h-4 w-4 accent-soft-accent" />
          Endstufe (kein automatischer Aufstieg)
        </label>
        <div className="flex items-center justify-between pt-2">
          {isEdit ? <Button type="button" variant="ghost" onClick={remove}>Löschen</Button> : <span />}
          <div className="flex gap-3">
            <Button type="button" variant="secondary" onClick={onClose} disabled={loading}>Abbrechen</Button>
            <Button type="submit" variant="primary" loading={loading}>{isEdit ? "Speichern" : "Anlegen"}</Button>
          </div>
        </div>
      </form>
    </Modal>
  );
}

// ── shared modal + field ────────────────────────────────────────────────────
function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-soft-ink/30 p-4 overflow-y-auto" onClick={onClose}>
      <div className="bg-white rounded-soft border border-soft-line shadow-soft-lg w-full max-w-2xl my-8" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-soft-line">
          <h2 className="text-base font-semibold text-soft-ink">{title}</h2>
          <button type="button" onClick={onClose} aria-label="Schließen" className="text-soft-ink3 hover:text-soft-ink">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="p-6">{children}</div>
      </div>
    </div>
  );
}

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-soft-ink2 mb-1">{label}</label>
      {children}
      {error && <p role="alert" className="mt-1 text-xs text-soft-crit">{error}</p>}
    </div>
  );
}
