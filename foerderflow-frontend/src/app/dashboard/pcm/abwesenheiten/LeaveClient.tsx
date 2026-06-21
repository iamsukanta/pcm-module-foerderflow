"use client";

// F.1 Leave Periods List + inline F.2 create form + F.5 placeholder creation.

import { useMemo, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Plus, CalendarOff, UserPlus, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { useToast } from "@/components/ui/ToastProvider";
import { deDate } from "@/lib/pcmFormat";
import type {
  LeavePeriod,
  LeaveTypeValue,
  PcmEmployee,
  PlaceholderEmployee,
  PcmApiErrorBody,
} from "@/types/pcm";

export const LEAVE_LABELS: Record<LeaveTypeValue, string> = {
  ELTERNZEIT: "Elternzeit",
  MUTTERSCHUTZ: "Mutterschutz",
  LANGZEITERKRANKUNG: "Langzeiterkrankung",
  OTHER: "Sonstige",
};

type StatusFilter = "all" | "active" | "ended";

function inputCls(error?: string): string {
  return `w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors
    focus:ring-2 focus:ring-soft-accent focus:border-soft-accent ${
      error ? "border-soft-crit bg-soft-critSoft" : "border-soft-line bg-white"
    }`;
}

export function LeaveClient({
  leaves,
  employees,
  placeholders,
}: {
  leaves: LeavePeriod[];
  employees: PcmEmployee[];
  placeholders: PlaceholderEmployee[];
}) {
  const router = useRouter();
  const [status, setStatus] = useState<StatusFilter>("all");
  const [showForm, setShowForm] = useState(false);

  const filtered = useMemo(
    () => leaves.filter((l) => (status === "all" ? true : l.status.toLowerCase() === status)),
    [leaves, status],
  );

  function rowVariant(l: LeavePeriod): "muted" | "danger" | "success" {
    if (l.status === "ENDED") return "muted";
    if (l.funder_notification_required && !l.funder_notification_sent_at) return "danger";
    return "success";
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <div className="flex gap-1">
          {(["all", "active", "ended"] as StatusFilter[]).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setStatus(k)}
              className={`px-3 py-1.5 rounded-soft-xs text-xs font-medium ${
                status === k ? "bg-soft-accent text-white" : "bg-soft-line2 text-soft-ink2 hover:bg-soft-ink/5"
              }`}
            >
              {k === "all" ? "Alle" : k === "active" ? "Aktiv" : "Beendet"}
            </button>
          ))}
        </div>
        <Button variant="primary" onClick={() => setShowForm((s) => !s)}>
          <Plus className="h-4 w-4 mr-1" aria-hidden="true" />
          {showForm ? "Schließen" : "Neue Abwesenheit"}
        </Button>
      </div>

      {showForm && (
        <LeaveForm
          employees={employees}
          placeholders={placeholders}
          onClose={() => setShowForm(false)}
          onSaved={() => {
            setShowForm(false);
            router.refresh();
          }}
        />
      )}

      {filtered.length === 0 ? (
        <EmptyState
          icon={CalendarOff}
          title="Keine Abwesenheiten"
          description="Erfasse Elternzeit, Mutterschutz oder Langzeiterkrankung, um Abrechnung und Prognose automatisch auszusetzen."
        />
      ) : (
        <div className="overflow-x-auto bg-white rounded-soft border border-soft-line shadow-soft">
          <table className="w-full text-sm">
            <thead className="bg-soft-line2/40 text-soft-ink3 text-left">
              <tr>
                <th className="px-3 py-2 font-medium">Mitarbeiter:in</th>
                <th className="px-3 py-2 font-medium">Art</th>
                <th className="px-3 py-2 font-medium">Zeitraum</th>
                <th className="px-3 py-2 font-medium">Vertretung</th>
                <th className="px-3 py-2 font-medium">Benachrichtigung</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((l) => (
                <tr key={l.id} className="border-t border-soft-line2 hover:bg-soft-ink/[0.02]">
                  <td className="px-3 py-2 font-medium text-soft-ink">{l.employee_name}</td>
                  <td className="px-3 py-2 text-soft-ink2">{LEAVE_LABELS[l.leave_type]}</td>
                  <td className="px-3 py-2 numeric text-soft-ink2">
                    {deDate(l.start_date)} – {deDate(l.actual_end_date ?? l.expected_end_date)}
                  </td>
                  <td className="px-3 py-2 text-soft-ink2">{l.replacement_name ?? "—"}</td>
                  <td className="px-3 py-2">
                    {l.funder_notification_required ? (
                      l.funder_notification_sent_at ? (
                        <Badge variant="success">gesendet</Badge>
                      ) : (
                        <Badge variant="danger">offen</Badge>
                      )
                    ) : (
                      <span className="text-soft-ink3 text-xs">nicht nötig</span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <Badge variant={rowVariant(l)}>{l.status === "ACTIVE" ? "Aktiv" : "Beendet"}</Badge>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <Link
                      href={`/dashboard/pcm/abwesenheiten/${l.id}`}
                      className="inline-flex items-center text-soft-accent hover:underline text-xs"
                    >
                      Details <ChevronRight className="h-3.5 w-3.5" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function LeaveForm({
  employees,
  placeholders,
  onClose,
  onSaved,
}: {
  employees: PcmEmployee[];
  placeholders: PlaceholderEmployee[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const router = useRouter();
  const toast = useToast();
  const [v, setV] = useState({
    employee_id: "",
    leave_type: "ELTERNZEIT" as LeaveTypeValue,
    start_date: "",
    expected_end_date: "",
    replacement_employee_id: "",
    funder_notification_required: false,
    note: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [newPlaceholder, setNewPlaceholder] = useState("");

  function set<K extends keyof typeof v>(k: K, val: (typeof v)[K]) {
    setV((p) => ({ ...p, [k]: val }));
  }

  async function createPlaceholder() {
    if (!newPlaceholder.trim()) return;
    const res = await fetch("/api/protected/pcm/placeholder-employees", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nachname: newPlaceholder.trim() }),
    });
    const b = (await res.json().catch(() => ({}))) as { data?: PlaceholderEmployee; error?: string };
    if (res.ok && b.data) {
      toast.success("Platzhalter angelegt.");
      setV((p) => ({ ...p, replacement_employee_id: b.data!.id }));
      setNewPlaceholder("");
      router.refresh();
    } else {
      toast.error(b.error ?? "Anlegen fehlgeschlagen.");
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    const next: Record<string, string> = {};
    if (!v.employee_id) next.employee_id = "Mitarbeiter:in erforderlich.";
    if (!v.start_date) next.start_date = "Beginn erforderlich.";
    if (Object.keys(next).length) return setErrors(next);
    setErrors({});
    setLoading(true);
    const res = await fetch("/api/protected/pcm/leave-periods", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        employee_id: v.employee_id,
        leave_type: v.leave_type,
        start_date: v.start_date,
        expected_end_date: v.expected_end_date || null,
        replacement_employee_id: v.replacement_employee_id || null,
        funder_notification_required: v.funder_notification_required,
        note: v.note || null,
      }),
    });
    const b = (await res.json().catch(() => ({}))) as Partial<PcmApiErrorBody>;
    setLoading(false);
    if (!res.ok) {
      setErrors({ general: b.error ?? "Speichern fehlgeschlagen." });
      return;
    }
    toast.success("Abwesenheit erfasst.");
    onSaved();
  }

  return (
    <form onSubmit={submit} noValidate className="bg-white rounded-soft border border-soft-line p-6 shadow-soft space-y-4">
      <h2 className="text-base font-semibold text-soft-ink pb-2 border-b border-soft-line">Neue Abwesenheit</h2>
      {errors.general && (
        <div role="alert" className="rounded-soft-xs bg-soft-critSoft border border-soft-crit/30 p-3 text-sm text-soft-crit">
          {errors.general}
        </div>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Mitarbeiter:in" error={errors.employee_id}>
          <select value={v.employee_id} onChange={(e) => set("employee_id", e.target.value)} className={inputCls(errors.employee_id)}>
            <option value="">— wählen —</option>
            {employees.map((e) => (
              <option key={e.id} value={e.id}>{e.vorname} {e.nachname}</option>
            ))}
          </select>
        </Field>
        <Field label="Art">
          <select value={v.leave_type} onChange={(e) => set("leave_type", e.target.value as LeaveTypeValue)} className={inputCls()}>
            {(Object.keys(LEAVE_LABELS) as LeaveTypeValue[]).map((k) => (
              <option key={k} value={k}>{LEAVE_LABELS[k]}</option>
            ))}
          </select>
        </Field>
        <Field label="Beginn" error={errors.start_date}>
          <input type="date" value={v.start_date} onChange={(e) => set("start_date", e.target.value)} className={inputCls(errors.start_date)} />
        </Field>
        <Field label="Voraussichtliches Ende (optional)">
          <input type="date" value={v.expected_end_date} onChange={(e) => set("expected_end_date", e.target.value)} className={inputCls()} />
        </Field>
        <Field label="Vertretung (Platzhalter)">
          <select value={v.replacement_employee_id} onChange={(e) => set("replacement_employee_id", e.target.value)} className={inputCls()}>
            <option value="">— keine —</option>
            {placeholders.map((p) => (
              <option key={p.id} value={p.id}>{p.name} ({p.employee_code})</option>
            ))}
          </select>
          <div className="flex items-center gap-2 mt-2">
            <input
              value={newPlaceholder}
              onChange={(e) => setNewPlaceholder(e.target.value)}
              placeholder="Neuer Platzhalter (Name)"
              className="flex-1 rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-xs outline-none focus:ring-2 focus:ring-soft-accent"
            />
            <Button type="button" variant="secondary" size="sm" onClick={createPlaceholder}>
              <UserPlus className="h-3.5 w-3.5 mr-1" aria-hidden="true" /> Anlegen
            </Button>
          </div>
        </Field>
        <Field label="Notiz">
          <input value={v.note} onChange={(e) => set("note", e.target.value)} className={inputCls()} />
        </Field>
      </div>
      <label className="flex items-center gap-2 text-sm text-soft-ink2">
        <input type="checkbox" checked={v.funder_notification_required} onChange={(e) => set("funder_notification_required", e.target.checked)} className="h-4 w-4 accent-soft-accent" />
        Fördergeberin benachrichtigen (erzeugt eine Frist)
      </label>
      <div className="flex justify-end gap-3 pt-2">
        <Button type="button" variant="secondary" onClick={onClose} disabled={loading}>Abbrechen</Button>
        <Button type="submit" variant="primary" loading={loading}>Erfassen</Button>
      </div>
    </form>
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
