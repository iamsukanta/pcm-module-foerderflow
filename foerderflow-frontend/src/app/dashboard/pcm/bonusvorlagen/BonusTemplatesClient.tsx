"use client";

// G.1 Bonus Template List + G.2 Create/Edit form + G.3 Eligibility Preview.

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Plus, Gift, Trash2, Users, X } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { useToast } from "@/components/ui/ToastProvider";
import { eur } from "@/lib/pcmFormat";
import {
  APPLICABLE_TO_LABELS,
  BONUS_TYPE_LABELS,
  BRUTTO_TYPE_LABELS,
  PRORATION_LABELS,
} from "@/lib/pcmLabels";
import type {
  BonusApplicableToValue,
  BonusTemplate,
  BonusTypeValue,
  BruttoTypeValue,
  EligibilityPreview,
  ProrationRuleValue,
  PcmApiErrorBody,
} from "@/types/pcm";

function inputCls() {
  return "w-full rounded-soft-xs border border-soft-line bg-white px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-soft-accent focus:border-soft-accent";
}

function amountLabel(t: BonusTemplate): string {
  return t.type === "FIXED" ? eur(t.amount) : `${t.amount} %`;
}

export function BonusTemplatesClient({ templates }: { templates: BonusTemplate[] }) {
  const router = useRouter();
  const toast = useToast();
  const [editing, setEditing] = useState<BonusTemplate | "new" | null>(null);

  async function remove(id: string) {
    const res = await fetch(`/api/protected/pcm/bonus-templates/${id}`, { method: "DELETE" });
    if (res.ok) {
      toast.success("Vorlage gelöscht.");
      router.refresh();
    } else {
      toast.error("Löschen fehlgeschlagen.");
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex justify-end">
        <Button variant="primary" onClick={() => setEditing("new")}>
          <Plus className="h-4 w-4 mr-1" aria-hidden="true" /> Neue Vorlage
        </Button>
      </div>

      {templates.length === 0 ? (
        <EmptyState
          icon={Gift}
          title="Keine Bonusvorlagen"
          description="Lege organisationsweite Zulagen- oder Bonusregeln an, die automatisch auf passende Mitarbeitende angewendet werden."
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {templates.map((t) => (
            <div key={t.id} className="bg-white rounded-soft border border-soft-line p-5 shadow-soft">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-medium text-soft-ink">{t.name}</div>
                  <div className="text-xs text-soft-ink3 mt-0.5">
                    {BONUS_TYPE_LABELS[t.type]} · {BRUTTO_TYPE_LABELS[t.brutto_type]} · {PRORATION_LABELS[t.proration_rule]}
                  </div>
                </div>
                <span className="numeric font-semibold text-soft-ink">{amountLabel(t)}</span>
              </div>
              <div className="flex flex-wrap items-center gap-1.5 mt-3">
                <Badge variant="muted">{t.tariff_code ?? "Alle Tarife"}</Badge>
                <Badge variant="muted">
                  {t.salary_group_min || t.salary_group_max
                    ? `${t.salary_group_min ?? "…"}–${t.salary_group_max ?? "…"}`
                    : "Alle EG"}
                </Badge>
                <Badge variant="muted">{APPLICABLE_TO_LABELS[t.applicable_to]}</Badge>
                {typeof t.matched_count === "number" && (
                  <Badge variant="success">
                    <Users className="h-3 w-3" aria-hidden="true" /> {t.matched_count} MA
                  </Badge>
                )}
              </div>
              <div className="flex justify-end gap-2 mt-3">
                <Button variant="secondary" size="sm" onClick={() => setEditing(t)}>Bearbeiten</Button>
                <Button variant="ghost" size="sm" onClick={() => remove(t.id)}>
                  <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {editing && (
        <TemplateModal
          template={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}

function TemplateModal({ template, onClose }: { template: BonusTemplate | null; onClose: () => void }) {
  const router = useRouter();
  const toast = useToast();
  const isEdit = !!template;
  const [v, setV] = useState({
    name: template?.name ?? "",
    tariff_code: template?.tariff_code ?? "",
    salary_group_min: template?.salary_group_min ?? "",
    salary_group_max: template?.salary_group_max ?? "",
    applicable_to: (template?.applicable_to ?? "ALL") as BonusApplicableToValue,
    type: (template?.type ?? "FIXED") as BonusTypeValue,
    amount: template?.amount ?? "",
    brutto_type: (template?.brutto_type ?? "EMPLOYER") as BruttoTypeValue,
    proration_rule: (template?.proration_rule ?? "FULL") as ProrationRuleValue,
    reference_month: template?.reference_month?.toString() ?? "",
    payment_month: template?.payment_month?.toString() ?? "",
    prorate_by_employment_period: template?.prorate_by_employment_period ?? false,
    period_from: template?.period_from ?? "",
    period_to: template?.period_to ?? "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<EligibilityPreview | null>(null);
  const [loading, setLoading] = useState(false);

  function set<K extends keyof typeof v>(k: K, val: (typeof v)[K]) {
    setV((p) => ({ ...p, [k]: val }));
  }

  function payload() {
    return {
      name: v.name.trim(),
      tariff_code: v.tariff_code || null,
      salary_group_min: v.salary_group_min || null,
      salary_group_max: v.salary_group_max || null,
      applicable_to: v.applicable_to,
      type: v.type,
      amount: Number(v.amount),
      brutto_type: v.brutto_type,
      proration_rule: v.proration_rule,
      reference_month: v.reference_month ? Number(v.reference_month) : null,
      payment_month: v.payment_month ? Number(v.payment_month) : null,
      prorate_by_employment_period: v.prorate_by_employment_period,
      period_from: v.period_from,
      period_to: v.period_to || null,
    };
  }

  async function runPreview() {
    const res = await fetch("/api/protected/pcm/bonus-templates/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tariff_code: v.tariff_code || null,
        salary_group_min: v.salary_group_min || null,
        salary_group_max: v.salary_group_max || null,
        applicable_to: v.applicable_to,
      }),
    });
    const b = (await res.json().catch(() => ({}))) as { data?: EligibilityPreview };
    if (res.ok && b.data) setPreview(b.data);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    const next: Record<string, string> = {};
    if (!v.name.trim()) next.name = "Name erforderlich.";
    if (!v.amount) next.amount = "Betrag erforderlich.";
    if (!v.period_from) next.period_from = "Gültig-ab erforderlich.";
    if (v.type === "REFERENCE_MONTH" && (!v.reference_month || !v.payment_month))
      next.reference_month = "Referenz- und Zahlmonat erforderlich.";
    if (Object.keys(next).length) return setErrors(next);
    setErrors({});
    setLoading(true);
    const url = isEdit ? `/api/protected/pcm/bonus-templates/${template!.id}` : "/api/protected/pcm/bonus-templates";
    const res = await fetch(url, {
      method: isEdit ? "PATCH" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload()),
    });
    const b = (await res.json().catch(() => ({}))) as Partial<PcmApiErrorBody>;
    setLoading(false);
    if (!res.ok) return setErrors({ general: b.error ?? "Speichern fehlgeschlagen." });
    toast.success(isEdit ? "Vorlage gespeichert." : "Vorlage angelegt.");
    onClose();
    router.refresh();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-soft-ink/30 p-4 overflow-y-auto" onClick={onClose}>
      <div className="bg-white rounded-soft border border-soft-line shadow-soft-lg w-full max-w-2xl my-8" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-soft-line">
          <h2 className="text-base font-semibold text-soft-ink">{isEdit ? "Vorlage bearbeiten" : "Neue Bonusvorlage"}</h2>
          <button type="button" onClick={onClose} aria-label="Schließen" className="text-soft-ink3 hover:text-soft-ink"><X className="h-5 w-5" /></button>
        </div>
        <form onSubmit={submit} noValidate className="p-6 space-y-4">
          {errors.general && (
            <div role="alert" className="rounded-soft-xs bg-soft-critSoft border border-soft-crit/30 p-3 text-sm text-soft-crit">{errors.general}</div>
          )}
          <Field label="Name" error={errors.name}>
            <input value={v.name} onChange={(e) => set("name", e.target.value)} placeholder="Münchenzulage EG1–EG12" className={inputCls()} />
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Tarif (optional)"><input value={v.tariff_code} onChange={(e) => set("tariff_code", e.target.value)} placeholder="alle" className={inputCls()} /></Field>
            <Field label="Anwenden auf">
              <select value={v.applicable_to} onChange={(e) => set("applicable_to", e.target.value as BonusApplicableToValue)} className={inputCls()}>
                {(Object.keys(APPLICABLE_TO_LABELS) as BonusApplicableToValue[]).map((k) => <option key={k} value={k}>{APPLICABLE_TO_LABELS[k]}</option>)}
              </select>
            </Field>
            <Field label="EG von (optional)"><input value={v.salary_group_min} onChange={(e) => set("salary_group_min", e.target.value)} placeholder="E1" className={inputCls()} /></Field>
            <Field label="EG bis (optional)"><input value={v.salary_group_max} onChange={(e) => set("salary_group_max", e.target.value)} placeholder="E12" className={inputCls()} /></Field>
            <Field label="Art">
              <select value={v.type} onChange={(e) => set("type", e.target.value as BonusTypeValue)} className={inputCls()}>
                {(Object.keys(BONUS_TYPE_LABELS) as BonusTypeValue[]).map((k) => <option key={k} value={k}>{BONUS_TYPE_LABELS[k]}</option>)}
              </select>
            </Field>
            <Field label={v.type === "FIXED" ? "Betrag (€)" : "Satz (%)"} error={errors.amount}>
              <input type="number" step="0.01" value={v.amount} onChange={(e) => set("amount", e.target.value)} className={`${inputCls()} numeric`} />
            </Field>
            <Field label="Brutto-Art">
              <select value={v.brutto_type} onChange={(e) => set("brutto_type", e.target.value as BruttoTypeValue)} className={inputCls()}>
                {(Object.keys(BRUTTO_TYPE_LABELS) as BruttoTypeValue[]).map((k) => <option key={k} value={k}>{BRUTTO_TYPE_LABELS[k]}</option>)}
              </select>
            </Field>
            <Field label="Proration">
              <select value={v.proration_rule} onChange={(e) => set("proration_rule", e.target.value as ProrationRuleValue)} className={inputCls()}>
                {(Object.keys(PRORATION_LABELS) as ProrationRuleValue[]).map((k) => <option key={k} value={k}>{PRORATION_LABELS[k]}</option>)}
              </select>
            </Field>
            {v.type === "REFERENCE_MONTH" && (
              <>
                <Field label="Referenzmonat (1–12)" error={errors.reference_month}><input type="number" min={1} max={12} value={v.reference_month} onChange={(e) => set("reference_month", e.target.value)} className={`${inputCls()} numeric`} /></Field>
                <Field label="Zahlmonat (1–12)"><input type="number" min={1} max={12} value={v.payment_month} onChange={(e) => set("payment_month", e.target.value)} className={`${inputCls()} numeric`} /></Field>
              </>
            )}
            <Field label="Gültig ab" error={errors.period_from}><input type="date" value={v.period_from} onChange={(e) => set("period_from", e.target.value)} className={inputCls()} /></Field>
            <Field label="Gültig bis (optional)"><input type="date" value={v.period_to} onChange={(e) => set("period_to", e.target.value)} className={inputCls()} /></Field>
          </div>
          <label className="flex items-center gap-2 text-sm text-soft-ink2">
            <input type="checkbox" checked={v.prorate_by_employment_period} onChange={(e) => set("prorate_by_employment_period", e.target.checked)} className="h-4 w-4 accent-soft-accent" />
            Anteilig nach Beschäftigungsdauer (× Monate/12)
          </label>

          {preview && (
            <div className="rounded-soft-xs border border-soft-line p-3 max-h-48 overflow-y-auto">
              <p className="text-sm font-medium text-soft-ink mb-2">{preview.matched} von {preview.total} aktiven Mitarbeitenden</p>
              <ul className="text-xs space-y-1">
                {preview.rows.map((r) => (
                  <li key={r.employee_id} className="flex items-center justify-between">
                    <span className="text-soft-ink2">{r.employee_name} {r.salary_group ? `· ${r.salary_group}` : ""}</span>
                    {r.matched ? <Badge variant="success">passt</Badge> : <span className="text-soft-ink3">{r.reason}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex items-center justify-between pt-1">
            <Button type="button" variant="secondary" onClick={runPreview}>
              <Users className="h-4 w-4 mr-1" aria-hidden="true" /> Vorschau Berechtigung
            </Button>
            <div className="flex gap-3">
              <Button type="button" variant="ghost" onClick={onClose} disabled={loading}>Abbrechen</Button>
              <Button type="submit" variant="primary" loading={loading}>{isEdit ? "Speichern" : "Anlegen"}</Button>
            </div>
          </div>
        </form>
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
