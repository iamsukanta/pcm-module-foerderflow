"use client";

// Screen P-T — Upcoming Progressions dashboard. Read-only review of pending
// automatic Stufenaufstieg events within a configurable lookahead window.

import { useEffect, useMemo, useState, useCallback } from "react";
import Link from "next/link";
import { CalendarClock, ArrowUpRight, PlayCircle } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { useToast } from "@/components/ui/ToastProvider";
import { eur, deDate } from "@/lib/pcmFormat";
import type { ProgressionRow, PromotionRunResult } from "@/types/pcm";

const WINDOWS = [3, 6, 12];

export function ProgressionsClient({ initialRows }: { initialRows: ProgressionRow[] }) {
  const toast = useToast();
  const [months, setMonths] = useState(6);
  const [rows, setRows] = useState<ProgressionRow[]>(initialRows);
  const [tariff, setTariff] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);

  const reload = useCallback(() => {
    setLoading(true);
    fetch(`/api/protected/pcm/employees/progressions/upcoming?months_ahead=${months}`)
      .then((r) => r.json())
      .then((b) => setRows((b.data as ProgressionRow[]) ?? []))
      .finally(() => setLoading(false));
  }, [months]);

  useEffect(() => {
    if (months === 6) { setRows(initialRows); return; }
    reload();
  }, [months, initialRows, reload]);

  async function runPromotions() {
    setRunning(true);
    const res = await fetch("/api/protected/pcm/employees/promotions/run", { method: "POST" });
    const b = (await res.json().catch(() => ({}))) as { data?: PromotionRunResult; error?: string };
    setRunning(false);
    if (!res.ok || !b.data) {
      toast.error(b.error ?? "Promotion-Job fehlgeschlagen.");
      return;
    }
    const { promoted_count, skipped_count } = b.data;
    toast.success(`${promoted_count} Stufenaufstieg(e) durchgeführt${skipped_count ? `, ${skipped_count} übersprungen` : ""}.`);
    reload();
  }

  const tariffCodes = useMemo(() => [...new Set(rows.map((r) => r.tariff_code))].sort(), [rows]);
  const filtered = useMemo(() => (tariff ? rows.filter((r) => r.tariff_code === tariff) : rows), [rows, tariff]);
  const due30 = filtered.filter((r) => r.days_until <= 30).length;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs text-soft-ink3">Zeitfenster:</span>
          {WINDOWS.map((w) => (
            <button
              key={w}
              type="button"
              onClick={() => setMonths(w)}
              className={`px-3 py-1.5 rounded-soft-xs text-xs font-medium ${months === w ? "bg-soft-accent text-white" : "bg-soft-line2 text-soft-ink2 hover:bg-soft-ink/5"}`}
            >
              {w} Monate
            </button>
          ))}
          <select value={tariff} onChange={(e) => setTariff(e.target.value)} className="ml-2 rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-xs">
            <option value="">Alle Tarife</option>
            {tariffCodes.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-soft-ink2">
            <span className="font-semibold text-soft-ink">{due30}</span> in den nächsten 30 Tagen fällig
          </span>
          <Button variant="primary" onClick={runPromotions} loading={running}>
            <PlayCircle className="h-4 w-4 mr-1" aria-hidden="true" /> Promotion-Job ausführen
          </Button>
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon={CalendarClock}
          title={loading ? "Lade…" : "Keine anstehenden Stufenaufstiege"}
          description="Im gewählten Zeitfenster ist kein automatischer Aufstieg fällig."
        />
      ) : (
        <div className="overflow-x-auto bg-white rounded-soft border border-soft-line shadow-soft">
          <table className="w-full text-sm">
            <thead className="bg-soft-line2/40 text-soft-ink3 text-left">
              <tr>
                <th className="px-3 py-2 font-medium">Mitarbeiter:in</th>
                <th className="px-3 py-2 font-medium">Tarif</th>
                <th className="px-3 py-2 font-medium">Stufe</th>
                <th className="px-3 py-2 font-medium">Fortschritt</th>
                <th className="px-3 py-2 font-medium">Stichtag</th>
                <th className="px-3 py-2 font-medium text-right">Δ / Monat</th>
                <th className="px-3 py-2 font-medium">Prognose</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => {
                const pct = Math.min(100, Math.round((r.months_in_tier / r.months_required) * 100));
                const soon = r.days_until <= 30;
                return (
                  <tr key={r.employee_id} className="border-t border-soft-line2 hover:bg-soft-ink/[0.02]">
                    <td className="px-3 py-2 font-medium text-soft-ink">{r.employee_name}</td>
                    <td className="px-3 py-2 text-soft-ink2">{r.tariff_code} · {r.salary_group}</td>
                    <td className="px-3 py-2 numeric">{r.current_level} → {r.next_level}</td>
                    <td className="px-3 py-2 w-40">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-2 rounded-full bg-soft-line2 overflow-hidden">
                          <div className={`h-full ${soon ? "bg-soft-warn" : "bg-soft-accent"}`} style={{ width: `${pct}%` }} />
                        </div>
                        <span className="text-[11px] text-soft-ink3 numeric">{r.months_in_tier}/{r.months_required}</span>
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <span className={`numeric ${soon ? "text-soft-warn font-medium" : "text-soft-ink2"}`}>{deDate(r.progression_date)}</span>
                      <Badge variant={r.source === "MANUAL" ? "default" : "muted"} className="ml-2">{r.source === "MANUAL" ? "manuell" : "auto"}</Badge>
                    </td>
                    <td className="px-3 py-2 numeric text-right text-soft-ok font-medium">+{eur(r.delta_monthly)}</td>
                    <td className="px-3 py-2">
                      <Badge variant={r.in_forecast ? "success" : "muted"}>{r.in_forecast ? "enthalten" : "offen"}</Badge>
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Link href="/dashboard/personal" className="inline-flex items-center gap-1 text-xs text-soft-accent hover:underline">
                        Stichtag <ArrowUpRight className="h-3 w-3" />
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
