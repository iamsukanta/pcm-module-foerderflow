"use client";

import { useMemo, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2, Timer } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { useToast } from "@/components/ui/ToastProvider";
import type { FlatCostCenter, PcmEmployee, WochenstundenZuweisung } from "@/types/pcm";

function inputCls(error?: string): string {
  return `w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors
    focus:ring-2 focus:ring-soft-accent focus:border-soft-accent ${
      error
        ? "border-soft-crit bg-soft-critSoft text-soft-crit"
        : "border-soft-line bg-white"
    }`;
}

function activeContractHours(emp: PcmEmployee): number {
  const today = new Date();
  const active =
    emp.contracts.find((c) => {
      const ab = new Date(c.gueltig_ab);
      const bis = c.gueltig_bis ? new Date(c.gueltig_bis) : null;
      return ab <= today && (bis === null || bis >= today);
    }) ?? emp.contracts[0];
  return active ? Number(active.assigned_hours) : 0;
}

function isActiveAssignment(a: WochenstundenZuweisung): boolean {
  if (!a.end_date) return true;
  return new Date(a.end_date) >= new Date();
}

export function WochenstundenClient({
  employees,
  costCenters,
  assignments,
}: {
  employees: PcmEmployee[];
  costCenters: FlatCostCenter[];
  assignments: WochenstundenZuweisung[];
}) {
  const router = useRouter();
  const toast = useToast();

  const [employeeId, setEmployeeId] = useState(employees[0]?.id ?? "");
  const ccName = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of costCenters) m.set(c.id, `${c.code} — ${c.name}`);
    return m;
  }, [costCenters]);

  const employee = employees.find((e) => e.id === employeeId);
  const contracted = employee ? activeContractHours(employee) : 0;

  const mine = useMemo(
    () => assignments.filter((a) => a.employee_id === employeeId && isActiveAssignment(a)),
    [assignments, employeeId],
  );
  const used = mine.reduce((sum, a) => sum + Number(a.weekly_hours), 0);
  const remaining = Math.max(contracted - used, 0);

  if (employees.length === 0) {
    return (
      <EmptyState
        icon={Timer}
        title="Keine aktiven Mitarbeitenden"
        description="Lege zuerst Mitarbeitende mit einem Vertrag an, um Wochenstunden auf Kostenstellen zu verteilen."
      />
    );
  }

  async function handleDelete(id: string) {
    const res = await fetch(`/api/protected/pcm/wochenstunden-zuweisungen/${id}`, {
      method: "DELETE",
    });
    if (res.ok) {
      toast.success("Zuweisung gelöscht.");
      router.refresh();
    } else {
      toast.error("Löschen fehlgeschlagen.");
    }
  }

  const pct = contracted > 0 ? Math.min((used / contracted) * 100, 100) : 0;
  const over = used > contracted + 0.01;

  return (
    <div className="space-y-6">
      {/* Employee selector */}
      <div className="max-w-md">
        <label htmlFor="ws-emp" className="block text-sm font-medium text-soft-ink2 mb-1">
          Mitarbeiter:in
        </label>
        <select
          id="ws-emp"
          value={employeeId}
          onChange={(e) => setEmployeeId(e.target.value)}
          className={inputCls()}
        >
          {employees.map((e) => (
            <option key={e.id} value={e.id}>
              {e.employee_code} — {e.vorname} {e.nachname}
            </option>
          ))}
        </select>
      </div>

      {/* Capacity bar */}
      <div className="bg-white rounded-soft border border-soft-line p-5 shadow-soft">
        <div className="flex items-center justify-between text-sm mb-2">
          <span className="text-soft-ink2 font-medium">Kapazität</span>
          <span className="numeric text-soft-ink2">
            {used.toFixed(1)} / {contracted.toFixed(1)} h
            <span className={`ml-2 ${over ? "text-soft-crit" : "text-soft-ok"}`}>
              ({over ? "überbucht" : `${remaining.toFixed(1)} h frei`})
            </span>
          </span>
        </div>
        <div className="h-3 rounded-soft-xs bg-soft-line2 overflow-hidden">
          <div
            className={`h-full transition-all ${over ? "bg-soft-crit" : "bg-soft-ok"}`}
            style={{ width: `${over ? 100 : pct}%` }}
          />
        </div>
      </div>

      {/* Existing assignments */}
      {mine.length === 0 ? (
        <p className="text-sm text-soft-ink3">Noch keine Zuweisungen für diese:n Mitarbeiter:in.</p>
      ) : (
        <ul className="divide-y divide-soft-line2 bg-white rounded-soft border border-soft-line">
          {mine.map((a) => (
            <li key={a.id} className="flex items-center justify-between px-5 py-3 text-sm">
              <div className="flex items-center gap-3">
                <span className="numeric font-medium text-soft-ink">
                  {Number(a.weekly_hours).toFixed(1)} h
                </span>
                <span className="text-soft-ink2">{ccName.get(a.cost_center_id) ?? a.cost_center_id}</span>
                <span className="text-soft-ink4 text-xs">
                  ab {a.effective_date}
                  {a.end_date ? ` – ${a.end_date}` : ""}
                </span>
              </div>
              <button
                type="button"
                onClick={() => handleDelete(a.id)}
                aria-label="Zuweisung löschen"
                className="text-soft-ink3 hover:text-soft-crit p-1 rounded
                  focus:outline-none focus:ring-2 focus:ring-soft-crit"
              >
                <Trash2 className="h-4 w-4" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}

      {employee && (
        <AddForm
          employeeId={employee.id}
          costCenters={costCenters}
          used={used}
          contracted={contracted}
          onCreated={() => router.refresh()}
        />
      )}
    </div>
  );
}

function AddForm({
  employeeId,
  costCenters,
  used,
  contracted,
  onCreated,
}: {
  employeeId: string;
  costCenters: FlatCostCenter[];
  used: number;
  contracted: number;
  onCreated: () => void;
}) {
  const toast = useToast();
  const [costCenterId, setCostCenterId] = useState(costCenters[0]?.id ?? "");
  const [hours, setHours] = useState("");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  const projected = used + (Number(hours) || 0);
  const wouldExceed = projected > contracted + 0.01;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const next: Record<string, string> = {};
    if (!costCenterId) next.cost_center_id = "Kostenstelle ist erforderlich.";
    if (!hours || Number(hours) <= 0) next.weekly_hours = "Stunden müssen > 0 sein.";
    if (!effectiveDate) next.effective_date = "Gültig-ab ist erforderlich.";
    if (Object.keys(next).length) {
      setErrors(next);
      return;
    }
    setErrors({});
    setLoading(true);
    try {
      const res = await fetch("/api/protected/pcm/wochenstunden-zuweisungen", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          employee_id: employeeId,
          cost_center_id: costCenterId,
          weekly_hours: Number(hours),
          effective_date: effectiveDate,
        }),
      });
      const body = (await res.json().catch(() => ({}))) as { error?: string; code?: string };
      if (!res.ok) {
        if (body.code === "DOPPELFOERDERUNG") {
          setErrors({ weekly_hours: body.error ?? "Überschreitet die vertraglichen Stunden." });
        } else {
          setErrors({ general: body.error ?? "Speichern fehlgeschlagen." });
        }
        return;
      }
      toast.success("Zuweisung angelegt.");
      setHours("");
      onCreated();
    } catch {
      setErrors({ general: "Netzwerkfehler. Bitte erneut versuchen." });
    } finally {
      setLoading(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      className="bg-white rounded-soft border border-soft-line p-6 shadow-soft space-y-4"
    >
      <h2 className="text-base font-semibold text-soft-ink pb-2 border-b border-soft-line">
        Stunden zuweisen
      </h2>

      {errors.general && (
        <div
          role="alert"
          className="rounded-soft-xs bg-soft-critSoft border border-soft-crit/30 p-3 text-sm text-soft-crit"
        >
          {errors.general}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="sm:col-span-1">
          <label className="block text-sm font-medium text-soft-ink2 mb-1">Kostenstelle</label>
          <select
            value={costCenterId}
            onChange={(e) => setCostCenterId(e.target.value)}
            className={inputCls(errors.cost_center_id)}
            aria-invalid={!!errors.cost_center_id}
          >
            {costCenters.map((c) => (
              <option key={c.id} value={c.id}>
                {c.code} — {c.name}
              </option>
            ))}
          </select>
          {errors.cost_center_id && (
            <p role="alert" className="mt-1 text-xs text-soft-crit">
              {errors.cost_center_id}
            </p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-soft-ink2 mb-1">Wochenstunden</label>
          <input
            type="number"
            step="0.5"
            value={hours}
            onChange={(e) => setHours(e.target.value)}
            placeholder="20"
            className={`${inputCls(errors.weekly_hours)} numeric`}
            aria-invalid={!!errors.weekly_hours}
          />
          {errors.weekly_hours ? (
            <p role="alert" className="mt-1 text-xs text-soft-crit">
              {errors.weekly_hours}
            </p>
          ) : (
            hours && (
              <p className={`mt-1 text-xs ${wouldExceed ? "text-soft-crit" : "text-soft-ok"}`}>
                Ergäbe {projected.toFixed(1)} / {contracted.toFixed(1)} h
                {wouldExceed ? " — überschreitet die Kapazität" : ""}
              </p>
            )
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-soft-ink2 mb-1">Gültig ab</label>
          <input
            type="date"
            value={effectiveDate}
            onChange={(e) => setEffectiveDate(e.target.value)}
            className={inputCls(errors.effective_date)}
            aria-invalid={!!errors.effective_date}
          />
          {errors.effective_date && (
            <p role="alert" className="mt-1 text-xs text-soft-crit">
              {errors.effective_date}
            </p>
          )}
        </div>
      </div>

      <div className="flex justify-end pt-2">
        <Button type="submit" variant="primary" loading={loading}>
          <Plus className="h-4 w-4 mr-1" aria-hidden="true" />
          Zuweisen
        </Button>
      </div>
    </form>
  );
}
