"use client";

// H.1–H.4 — per-employee bonus payments + salary adjustments. Employee selector
// drives two managed lists with inline create forms.

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Plus, Trash2, Gift, Coins } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { useToast } from "@/components/ui/ToastProvider";
import { eur, deDate } from "@/lib/pcmFormat";
import {
  ADJUSTMENT_TYPE_LABELS,
  BONUS_TYPE_LABELS,
  BRUTTO_TYPE_LABELS,
  PRORATION_LABELS,
} from "@/lib/pcmLabels";
import type {
  AdjustmentTypeValue,
  BonusPayment,
  BonusTypeValue,
  BruttoTypeValue,
  PcmEmployee,
  ProrationRuleValue,
  SalaryAdjustment,
  PcmApiErrorBody,
} from "@/types/pcm";

function inputCls() {
  return "w-full rounded-soft-xs border border-soft-line bg-white px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-soft-accent focus:border-soft-accent";
}

export function ZulagenClient({ employees }: { employees: PcmEmployee[] }) {
  const toast = useToast();
  const [empId, setEmpId] = useState(employees[0]?.id ?? "");
  const [bonuses, setBonuses] = useState<BonusPayment[]>([]);
  const [adjustments, setAdjustments] = useState<SalaryAdjustment[]>([]);
  const [showBonus, setShowBonus] = useState(false);
  const [showAdj, setShowAdj] = useState(false);

  const load = useCallback(async () => {
    if (!empId) return;
    const [b, a] = await Promise.all([
      fetch(`/api/protected/pcm/bonus-payments?employee_id=${empId}`).then((r) => r.json()),
      fetch(`/api/protected/pcm/salary-adjustments?employee_id=${empId}`).then((r) => r.json()),
    ]);
    setBonuses((b.data as BonusPayment[]) ?? []);
    setAdjustments((a.data as SalaryAdjustment[]) ?? []);
  }, [empId]);

  useEffect(() => {
    load();
  }, [load]);

  async function del(kind: "bonus-payments" | "salary-adjustments", id: string) {
    const res = await fetch(`/api/protected/pcm/${kind}/${id}`, { method: "DELETE" });
    if (res.ok) {
      toast.success("Gelöscht.");
      load();
    } else {
      toast.error("Löschen fehlgeschlagen.");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <label className="text-sm text-soft-ink2">Mitarbeiter:in</label>
        <select value={empId} onChange={(e) => setEmpId(e.target.value)} className="rounded-soft-xs border border-soft-line bg-white px-3 py-2 text-sm">
          {employees.map((e) => (
            <option key={e.id} value={e.id}>{e.vorname} {e.nachname}</option>
          ))}
        </select>
      </div>

      {/* H.1 / H.2 — Bonuses */}
      <section className="bg-white rounded-soft border border-soft-line p-5 shadow-soft">
        <div className="flex items-center justify-between mb-3">
          <h2 className="flex items-center gap-2 text-base font-semibold text-soft-ink">
            <Gift className="h-4 w-4 text-soft-accent" aria-hidden="true" /> Boni
          </h2>
          <Button variant="secondary" size="sm" onClick={() => setShowBonus((s) => !s)}>
            <Plus className="h-3.5 w-3.5 mr-1" aria-hidden="true" /> Bonus
          </Button>
        </div>
        {showBonus && empId && (
          <BonusForm employeeId={empId} onSaved={() => { setShowBonus(false); load(); }} onClose={() => setShowBonus(false)} />
        )}
        {bonuses.length === 0 ? (
          <p className="text-sm text-soft-ink3">Keine Boni erfasst.</p>
        ) : (
          <ul className="divide-y divide-soft-line2">
            {bonuses.map((b) => (
              <li key={b.id} className="flex items-center justify-between py-2 text-sm">
                <div className="flex items-center gap-3">
                  <span className="numeric font-medium text-soft-ink">{b.type === "FIXED" ? eur(b.amount) : `${b.amount} %`}</span>
                  <Badge variant="muted">{BONUS_TYPE_LABELS[b.type]}</Badge>
                  <Badge variant="muted">{BRUTTO_TYPE_LABELS[b.brutto_type]}</Badge>
                  <span className="text-soft-ink3 text-xs">{b.description ?? ""}</span>
                  <span className="text-soft-ink4 text-xs numeric">ab {deDate(b.period_from)}</span>
                </div>
                <button type="button" onClick={() => del("bonus-payments", b.id)} aria-label="Löschen" className="text-soft-ink3 hover:text-soft-crit p-1">
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* H.3 / H.4 — Adjustments */}
      <section className="bg-white rounded-soft border border-soft-line p-5 shadow-soft">
        <div className="flex items-center justify-between mb-3">
          <h2 className="flex items-center gap-2 text-base font-semibold text-soft-ink">
            <Coins className="h-4 w-4 text-soft-accent" aria-hidden="true" /> Gehaltsanpassungen
          </h2>
          <Button variant="secondary" size="sm" onClick={() => setShowAdj((s) => !s)}>
            <Plus className="h-3.5 w-3.5 mr-1" aria-hidden="true" /> Anpassung
          </Button>
        </div>
        {showAdj && empId && (
          <AdjustmentForm employeeId={empId} onSaved={() => { setShowAdj(false); load(); }} onClose={() => setShowAdj(false)} />
        )}
        {adjustments.length === 0 ? (
          <p className="text-sm text-soft-ink3">Keine Anpassungen erfasst.</p>
        ) : (
          <ul className="divide-y divide-soft-line2">
            {adjustments.map((a) => (
              <li key={a.id} className="flex items-center justify-between py-2 text-sm">
                <div className="flex items-center gap-3">
                  <Badge variant={a.type === "DEDUCTION" ? "danger" : "success"}>{ADJUSTMENT_TYPE_LABELS[a.type]}</Badge>
                  <span className="numeric font-medium text-soft-ink">{eur(a.amount)}</span>
                  <Badge variant="muted">{BRUTTO_TYPE_LABELS[a.brutto_type]}</Badge>
                  <span className="text-soft-ink3 text-xs">{a.description ?? ""}</span>
                  <span className="text-soft-ink4 text-xs numeric">ab {deDate(a.period_from)}</span>
                </div>
                <button type="button" onClick={() => del("salary-adjustments", a.id)} aria-label="Löschen" className="text-soft-ink3 hover:text-soft-crit p-1">
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function BonusForm({ employeeId, onSaved, onClose }: { employeeId: string; onSaved: () => void; onClose: () => void }) {
  const toast = useToast();
  const [v, setV] = useState({
    type: "FIXED" as BonusTypeValue,
    amount: "",
    brutto_type: "EMPLOYEE" as BruttoTypeValue,
    proration_rule: "FULL" as ProrationRuleValue,
    reference_month: "",
    payment_month: "",
    prorate_by_employment_period: false,
    period_from: "",
    period_to: "",
    description: "",
  });
  const [loading, setLoading] = useState(false);
  function set<K extends keyof typeof v>(k: K, val: (typeof v)[K]) { setV((p) => ({ ...p, [k]: val })); }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!v.amount || !v.period_from) { toast.error("Betrag und Gültig-ab erforderlich."); return; }
    setLoading(true);
    const res = await fetch("/api/protected/pcm/bonus-payments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        employee_id: employeeId, type: v.type, amount: Number(v.amount),
        brutto_type: v.brutto_type, proration_rule: v.proration_rule,
        reference_month: v.reference_month ? Number(v.reference_month) : null,
        payment_month: v.payment_month ? Number(v.payment_month) : null,
        prorate_by_employment_period: v.prorate_by_employment_period,
        period_from: v.period_from, period_to: v.period_to || null,
        description: v.description || null,
      }),
    });
    const b = (await res.json().catch(() => ({}))) as Partial<PcmApiErrorBody>;
    setLoading(false);
    if (!res.ok) { toast.error(b.error ?? "Speichern fehlgeschlagen."); return; }
    toast.success("Bonus angelegt.");
    onSaved();
  }

  return (
    <form onSubmit={submit} className="rounded-soft-xs border border-soft-line bg-soft-surfaceAlt/40 p-4 mb-4 space-y-3">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Labeled label="Art">
          <select value={v.type} onChange={(e) => set("type", e.target.value as BonusTypeValue)} className={inputCls()}>
            {(Object.keys(BONUS_TYPE_LABELS) as BonusTypeValue[]).map((k) => <option key={k} value={k}>{BONUS_TYPE_LABELS[k]}</option>)}
          </select>
        </Labeled>
        <Labeled label={v.type === "FIXED" ? "Betrag (€)" : "Satz (%)"}><input type="number" step="0.01" value={v.amount} onChange={(e) => set("amount", e.target.value)} className={`${inputCls()} numeric`} /></Labeled>
        <Labeled label="Brutto-Art">
          <select value={v.brutto_type} onChange={(e) => set("brutto_type", e.target.value as BruttoTypeValue)} className={inputCls()}>
            {(Object.keys(BRUTTO_TYPE_LABELS) as BruttoTypeValue[]).map((k) => <option key={k} value={k}>{BRUTTO_TYPE_LABELS[k]}</option>)}
          </select>
        </Labeled>
        <Labeled label="Proration">
          <select value={v.proration_rule} onChange={(e) => set("proration_rule", e.target.value as ProrationRuleValue)} className={inputCls()}>
            {(Object.keys(PRORATION_LABELS) as ProrationRuleValue[]).map((k) => <option key={k} value={k}>{PRORATION_LABELS[k]}</option>)}
          </select>
        </Labeled>
        {v.type === "REFERENCE_MONTH" && (
          <>
            <Labeled label="Referenzmonat"><input type="number" min={1} max={12} value={v.reference_month} onChange={(e) => set("reference_month", e.target.value)} className={`${inputCls()} numeric`} /></Labeled>
            <Labeled label="Zahlmonat"><input type="number" min={1} max={12} value={v.payment_month} onChange={(e) => set("payment_month", e.target.value)} className={`${inputCls()} numeric`} /></Labeled>
          </>
        )}
        <Labeled label="Gültig ab"><input type="date" value={v.period_from} onChange={(e) => set("period_from", e.target.value)} className={inputCls()} /></Labeled>
        <Labeled label="Gültig bis"><input type="date" value={v.period_to} onChange={(e) => set("period_to", e.target.value)} className={inputCls()} /></Labeled>
        <Labeled label="Beschreibung"><input value={v.description} onChange={(e) => set("description", e.target.value)} className={inputCls()} /></Labeled>
      </div>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onClose}>Abbrechen</Button>
        <Button type="submit" variant="primary" size="sm" loading={loading}>Anlegen</Button>
      </div>
    </form>
  );
}

function AdjustmentForm({ employeeId, onSaved, onClose }: { employeeId: string; onSaved: () => void; onClose: () => void }) {
  const toast = useToast();
  const [v, setV] = useState({
    type: "ADDITION" as AdjustmentTypeValue,
    amount: "",
    brutto_type: "EMPLOYER" as BruttoTypeValue,
    proration_rule: "FULL" as ProrationRuleValue,
    period_from: "",
    period_to: "",
    description: "",
  });
  const [loading, setLoading] = useState(false);
  function set<K extends keyof typeof v>(k: K, val: (typeof v)[K]) { setV((p) => ({ ...p, [k]: val })); }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!v.amount || !v.period_from) { toast.error("Betrag und Gültig-ab erforderlich."); return; }
    setLoading(true);
    const res = await fetch("/api/protected/pcm/salary-adjustments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        employee_id: employeeId, type: v.type, amount: Number(v.amount),
        brutto_type: v.brutto_type, proration_rule: v.proration_rule,
        period_from: v.period_from, period_to: v.period_to || null,
        description: v.description || null,
      }),
    });
    const b = (await res.json().catch(() => ({}))) as Partial<PcmApiErrorBody>;
    setLoading(false);
    if (!res.ok) { toast.error(b.error ?? "Speichern fehlgeschlagen."); return; }
    toast.success("Anpassung angelegt.");
    onSaved();
  }

  return (
    <form onSubmit={submit} className="rounded-soft-xs border border-soft-line bg-soft-surfaceAlt/40 p-4 mb-4 space-y-3">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Labeled label="Art">
          <select value={v.type} onChange={(e) => set("type", e.target.value as AdjustmentTypeValue)} className={inputCls()}>
            {(Object.keys(ADJUSTMENT_TYPE_LABELS) as AdjustmentTypeValue[]).map((k) => <option key={k} value={k}>{ADJUSTMENT_TYPE_LABELS[k]}</option>)}
          </select>
        </Labeled>
        <Labeled label="Betrag (€/Monat)"><input type="number" step="0.01" value={v.amount} onChange={(e) => set("amount", e.target.value)} className={`${inputCls()} numeric`} /></Labeled>
        <Labeled label="Brutto-Art">
          <select value={v.brutto_type} onChange={(e) => set("brutto_type", e.target.value as BruttoTypeValue)} className={inputCls()}>
            {(Object.keys(BRUTTO_TYPE_LABELS) as BruttoTypeValue[]).map((k) => <option key={k} value={k}>{BRUTTO_TYPE_LABELS[k]}</option>)}
          </select>
        </Labeled>
        <Labeled label="Proration">
          <select value={v.proration_rule} onChange={(e) => set("proration_rule", e.target.value as ProrationRuleValue)} className={inputCls()}>
            {(Object.keys(PRORATION_LABELS) as ProrationRuleValue[]).map((k) => <option key={k} value={k}>{PRORATION_LABELS[k]}</option>)}
          </select>
        </Labeled>
        <Labeled label="Gültig ab"><input type="date" value={v.period_from} onChange={(e) => set("period_from", e.target.value)} className={inputCls()} /></Labeled>
        <Labeled label="Gültig bis"><input type="date" value={v.period_to} onChange={(e) => set("period_to", e.target.value)} className={inputCls()} /></Labeled>
        <Labeled label="Beschreibung"><input value={v.description} onChange={(e) => set("description", e.target.value)} className={inputCls()} /></Labeled>
      </div>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onClose}>Abbrechen</Button>
        <Button type="submit" variant="primary" size="sm" loading={loading}>Anlegen</Button>
      </div>
    </form>
  );
}

function Labeled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-soft-ink2 mb-1">{label}</label>
      {children}
    </div>
  );
}
