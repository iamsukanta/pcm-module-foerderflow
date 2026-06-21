"use client";

// A.1 Settings overview (setup checklist) · A.2 org BAV rate · A.4 external ID
// mapping. A.3 payroll-period management links to the Abrechnung screen.

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Check, X, Save, ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { useToast } from "@/components/ui/ToastProvider";
import type { PcmBavConfig, PcmExternalId, PcmSettingsOverview, PcmApiErrorBody } from "@/types/pcm";

const CHECK_LABELS: Record<keyof PcmSettingsOverview["checklist"], string> = {
  tariffs_entered: "Tariftabellen erfasst",
  levels_entered: "Stufen-Regeln erfasst",
  bav_configured: "BAV-Satz konfiguriert",
  has_employees: "Mindestens ein:e Mitarbeiter:in",
  fiscal_year_active: "Aktives Haushaltsjahr",
};

function inputCls() {
  return "rounded-soft-xs border border-soft-line bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-soft-accent focus:border-soft-accent";
}

export function SettingsClient({
  overview,
  bav,
  externalIds,
}: {
  overview: PcmSettingsOverview;
  bav: PcmBavConfig;
  externalIds: PcmExternalId[];
}) {
  const router = useRouter();
  const toast = useToast();
  const [rate, setRate] = useState(bav.bav_rate_pct ?? "0");
  const [savingBav, setSavingBav] = useState(false);
  const [ids, setIds] = useState(externalIds);
  const [dirty, setDirty] = useState<Record<string, boolean>>({});

  async function saveBav() {
    setSavingBav(true);
    const res = await fetch("/api/protected/pcm/settings/bav", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bav_rate_pct: Number(rate) }),
    });
    const b = (await res.json().catch(() => ({}))) as Partial<PcmApiErrorBody>;
    setSavingBav(false);
    if (res.ok) {
      toast.success("BAV-Satz gespeichert.");
      router.refresh();
    } else toast.error(b.error ?? "Speichern fehlgeschlagen.");
  }

  async function saveExternalId(emp: PcmExternalId) {
    const res = await fetch(`/api/protected/pcm/settings/external-ids/${emp.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ employee_external_id: emp.employee_external_id || null }),
    });
    if (res.ok) {
      toast.success(`${emp.name}: externe ID gespeichert.`);
      setDirty((d) => ({ ...d, [emp.id]: false }));
    } else toast.error("Speichern fehlgeschlagen.");
  }

  return (
    <div className="space-y-6">
      {/* A.1 checklist */}
      <section className="bg-white rounded-soft border border-soft-line p-5 shadow-soft">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-soft-ink">Einrichtungs-Status</h2>
          {overview.active_fiscal_year && (
            <Badge variant={overview.active_fiscal_year.status === "OFFEN" ? "success" : "muted"}>
              HHJ {overview.active_fiscal_year.jahr} · {overview.active_fiscal_year.status === "OFFEN" ? "offen" : "geschlossen"}
            </Badge>
          )}
        </div>
        <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {(Object.keys(CHECK_LABELS) as (keyof PcmSettingsOverview["checklist"])[]).map((k) => {
            const ok = overview.checklist[k];
            return (
              <li key={k} className="flex items-center gap-2 text-sm">
                <span className={`flex items-center justify-center h-5 w-5 rounded-full ${ok ? "bg-soft-okSoft text-soft-ok" : "bg-soft-line2 text-soft-ink3"}`}>
                  {ok ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
                </span>
                <span className={ok ? "text-soft-ink" : "text-soft-ink3"}>{CHECK_LABELS[k]}</span>
              </li>
            );
          })}
        </ul>
        <div className="flex flex-wrap gap-3 mt-4 text-sm">
          <Link href="/dashboard/pcm/tarife" className="text-soft-accent hover:underline">Tarif-Register →</Link>
          <Link href="/dashboard/pcm/abrechnung" className="text-soft-accent hover:underline">Abrechnungsperioden →</Link>
          <Link href="/dashboard/personal" className="text-soft-accent hover:underline">Mitarbeitende →</Link>
        </div>
      </section>

      {/* A.2 BAV rate */}
      <section className="bg-white rounded-soft border border-soft-line p-5 shadow-soft">
        <h2 className="text-base font-semibold text-soft-ink mb-1">BAV-Satz (org-weit)</h2>
        <p className="text-xs text-soft-ink3 mb-3">
          Standard-Satz für die betriebliche Altersversorgung. Wird genutzt, wenn
          eine Tarif-Zeile keinen eigenen BAV-Satz trägt. Bei {Number(rate || 0)}% ergibt
          ein Ist-Gehalt von 3.200&nbsp;€ eine BAV von {(3200 * Number(rate || 0) / 100).toLocaleString("de-DE", { style: "currency", currency: "EUR" })}/Monat.
        </p>
        <div className="flex items-end gap-3">
          <div>
            <label className="block text-sm font-medium text-soft-ink2 mb-1">BAV-Satz (%)</label>
            <input type="number" step="0.1" min={0} max={100} value={rate} onChange={(e) => setRate(e.target.value)} className={`${inputCls()} numeric w-32`} />
          </div>
          <Button variant="primary" loading={savingBav} onClick={saveBav}><Save className="h-4 w-4 mr-1" /> Speichern</Button>
        </div>
        {bav.tariff_overrides.length > 0 && (
          <div className="mt-4">
            <p className="text-xs font-medium text-soft-ink3 mb-1">Tarif-spezifische Überschreibungen</p>
            <div className="flex flex-wrap gap-2">
              {bav.tariff_overrides.map((o) => (
                <Badge key={o.tariff_code} variant="muted">{o.tariff_code}: {o.bav_rate_pct}%</Badge>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* A.4 external IDs */}
      <section className="bg-white rounded-soft border border-soft-line shadow-soft overflow-hidden">
        <div className="px-5 py-3 border-b border-soft-line">
          <h2 className="text-base font-semibold text-soft-ink">Externe Personalnummern</h2>
          <p className="text-xs text-soft-ink3 mt-0.5">Verknüpft Mitarbeitende mit ihrer ID im externen Lohnsystem (für den Lohnimport).</p>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-soft-line2/40 text-soft-ink3 text-left">
            <tr><th className="px-5 py-2 font-medium">Mitarbeiter:in</th><th className="px-3 py-2 font-medium">Code</th><th className="px-3 py-2 font-medium">Externe ID</th><th className="px-3 py-2"></th></tr>
          </thead>
          <tbody>
            {ids.map((e) => (
              <tr key={e.id} className="border-t border-soft-line2">
                <td className="px-5 py-2 font-medium text-soft-ink">{e.name}</td>
                <td className="px-3 py-2 text-soft-ink3 numeric">{e.employee_code}</td>
                <td className="px-3 py-2">
                  <input
                    value={e.employee_external_id ?? ""}
                    onChange={(ev) => {
                      setIds((prev) => prev.map((x) => x.id === e.id ? { ...x, employee_external_id: ev.target.value } : x));
                      setDirty((d) => ({ ...d, [e.id]: true }));
                    }}
                    placeholder="—"
                    className={`${inputCls()} w-40`}
                  />
                </td>
                <td className="px-3 py-2 text-right">
                  {dirty[e.id] && <Button variant="secondary" size="sm" onClick={() => saveExternalId(e)}>Speichern</Button>}
                </td>
              </tr>
            ))}
            {ids.length === 0 && (
              <tr><td colSpan={4} className="px-5 py-4 text-sm text-soft-ink3">Keine Mitarbeitenden. <Link href="/dashboard/personal" className="text-soft-accent hover:underline inline-flex items-center gap-1">Anlegen <ExternalLink className="h-3 w-3" /></Link></td></tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
