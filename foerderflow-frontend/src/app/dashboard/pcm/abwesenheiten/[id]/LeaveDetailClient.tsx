"use client";

// F.3 Leave Period Detail / Edit + F.4 Return Confirmation.

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { BellRing, LogIn, Save } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { useToast } from "@/components/ui/ToastProvider";
import { deDate } from "@/lib/pcmFormat";
import type { LeavePeriod, PlaceholderEmployee, PcmApiErrorBody } from "@/types/pcm";
import { LEAVE_LABELS } from "../LeaveClient";

function inputCls() {
  return "w-full rounded-soft-xs border border-soft-line bg-white px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-soft-accent focus:border-soft-accent";
}

export function LeaveDetailClient({
  leave,
  placeholders,
}: {
  leave: LeavePeriod;
  placeholders: PlaceholderEmployee[];
}) {
  const router = useRouter();
  const toast = useToast();
  const ended = leave.status === "ENDED";
  const [expectedEnd, setExpectedEnd] = useState(leave.expected_end_date ?? "");
  const [replacement, setReplacement] = useState(leave.replacement_employee_id ?? "");
  const [note, setNote] = useState(leave.note ?? "");
  const [notifyReq, setNotifyReq] = useState(leave.funder_notification_required);
  const [returnDate, setReturnDate] = useState(leave.expected_end_date ?? "");
  const [showReturn, setShowReturn] = useState(false);
  const [saving, setSaving] = useState(false);

  async function call(url: string, method: string, body?: unknown): Promise<boolean> {
    const res = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (res.ok) return true;
    const b = (await res.json().catch(() => ({}))) as Partial<PcmApiErrorBody>;
    toast.error(b.error ?? "Aktion fehlgeschlagen.");
    return false;
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    const ok = await call(`/api/protected/pcm/leave-periods/${leave.id}`, "PATCH", {
      expected_end_date: expectedEnd || null,
      replacement_employee_id: replacement || null,
      note: note || null,
      funder_notification_required: notifyReq,
    });
    setSaving(false);
    if (ok) {
      toast.success("Gespeichert.");
      router.refresh();
    }
  }

  async function markSent() {
    if (await call(`/api/protected/pcm/leave-periods/${leave.id}/notification-sent`, "POST")) {
      toast.success("Benachrichtigung als gesendet markiert.");
      router.refresh();
    }
  }

  async function recordReturn() {
    if (!returnDate) return;
    if (await call(`/api/protected/pcm/leave-periods/${leave.id}/return`, "POST", { actual_end_date: returnDate })) {
      toast.success("Rückkehr erfasst.");
      router.refresh();
    }
  }

  return (
    <div className="space-y-5">
      {/* header summary */}
      <div className="bg-white rounded-soft border border-soft-line p-5 shadow-soft">
        <div className="flex items-center gap-2 mb-3">
          <Badge variant={ended ? "muted" : "success"}>{ended ? "Beendet" : "Aktiv"}</Badge>
          <Badge variant="default">{LEAVE_LABELS[leave.leave_type]}</Badge>
          {leave.funder_notification_required &&
            (leave.funder_notification_sent_at ? (
              <Badge variant="success">Benachrichtigung gesendet</Badge>
            ) : (
              <Badge variant="danger">Benachrichtigung offen</Badge>
            ))}
        </div>
        <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          <div><dt className="text-soft-ink3 text-xs">Beginn</dt><dd className="numeric text-soft-ink">{deDate(leave.start_date)}</dd></div>
          <div><dt className="text-soft-ink3 text-xs">Vorauss. Ende</dt><dd className="numeric text-soft-ink">{deDate(leave.expected_end_date)}</dd></div>
          <div><dt className="text-soft-ink3 text-xs">Tatsächliche Rückkehr</dt><dd className="numeric text-soft-ink">{deDate(leave.actual_end_date, "—")}</dd></div>
          <div><dt className="text-soft-ink3 text-xs">Vertretung</dt><dd className="text-soft-ink">{leave.replacement_name ?? "—"}</dd></div>
        </dl>
      </div>

      {!ended && (
        <>
          {/* edit form */}
          <form onSubmit={save} className="bg-white rounded-soft border border-soft-line p-5 shadow-soft space-y-4">
            <h2 className="text-base font-semibold text-soft-ink">Bearbeiten</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-soft-ink2 mb-1">Voraussichtliches Ende</label>
                <input type="date" value={expectedEnd} onChange={(e) => setExpectedEnd(e.target.value)} className={inputCls()} />
              </div>
              <div>
                <label className="block text-sm font-medium text-soft-ink2 mb-1">Vertretung</label>
                <select value={replacement} onChange={(e) => setReplacement(e.target.value)} className={inputCls()}>
                  <option value="">— keine —</option>
                  {placeholders.map((p) => (
                    <option key={p.id} value={p.id}>{p.name} ({p.employee_code})</option>
                  ))}
                </select>
              </div>
              <div className="sm:col-span-2">
                <label className="block text-sm font-medium text-soft-ink2 mb-1">Notiz</label>
                <input value={note} onChange={(e) => setNote(e.target.value)} className={inputCls()} />
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm text-soft-ink2">
              <input type="checkbox" checked={notifyReq} onChange={(e) => setNotifyReq(e.target.checked)} className="h-4 w-4 accent-soft-accent" />
              Fördergeberin benachrichtigen
            </label>
            <div className="flex flex-wrap justify-between gap-3 pt-1">
              <div className="flex gap-2">
                {leave.funder_notification_required && !leave.funder_notification_sent_at && (
                  <Button type="button" variant="secondary" onClick={markSent}>
                    <BellRing className="h-4 w-4 mr-1" aria-hidden="true" /> Benachrichtigung gesendet
                  </Button>
                )}
                <Button type="button" variant="secondary" onClick={() => setShowReturn((s) => !s)}>
                  <LogIn className="h-4 w-4 mr-1" aria-hidden="true" /> Rückkehr erfassen
                </Button>
              </div>
              <Button type="submit" variant="primary" loading={saving}>
                <Save className="h-4 w-4 mr-1" aria-hidden="true" /> Speichern
              </Button>
            </div>
          </form>

          {/* F.4 return confirmation */}
          {showReturn && (
            <div className="bg-white rounded-soft border border-soft-accent/40 p-5 shadow-soft space-y-3">
              <h2 className="text-base font-semibold text-soft-ink">Rückkehr bestätigen</h2>
              <p className="text-sm text-soft-ink3">
                Setzt das tatsächliche Enddatum und schließt offene Stundenzuweisungen
                der Vertretung zum Vortag.
              </p>
              <div className="flex items-end gap-3">
                <div>
                  <label className="block text-sm font-medium text-soft-ink2 mb-1">Tatsächliche Rückkehr</label>
                  <input type="date" value={returnDate} onChange={(e) => setReturnDate(e.target.value)} className={inputCls()} />
                </div>
                <Button type="button" variant="primary" onClick={recordReturn}>Rückkehr bestätigen</Button>
                <Button type="button" variant="ghost" onClick={() => setShowReturn(false)}>Abbrechen</Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
