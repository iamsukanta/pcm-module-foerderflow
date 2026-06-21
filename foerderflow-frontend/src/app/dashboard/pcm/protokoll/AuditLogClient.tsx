"use client";

// O.1 Audit Log List + O.2 Entry Detail (old → new comparison).

import { useMemo, useState } from "react";
import { ScrollText, X, Search } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import type { AuditActionTypeValue, AuditLogEntry } from "@/types/pcm";

const ACTION_LABELS: Record<AuditActionTypeValue, string> = {
  UPDATE: "Änderung",
  DELETE: "Löschung",
  AUTO_PROMOTION: "Stufenaufstieg",
  LEAVE_START: "Abwesenheit Beginn",
  LEAVE_END: "Abwesenheit Ende",
};

const ACTION_VARIANT: Record<AuditActionTypeValue, "default" | "danger" | "success" | "warning" | "muted"> = {
  UPDATE: "default",
  DELETE: "danger",
  AUTO_PROMOTION: "success",
  LEAVE_START: "warning",
  LEAVE_END: "muted",
};

function fmtTs(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("de-DE", { dateStyle: "medium", timeStyle: "short" });
}

export function AuditLogClient({ entries }: { entries: AuditLogEntry[] }) {
  const [action, setAction] = useState<AuditActionTypeValue | "all">("all");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<AuditLogEntry | null>(null);

  const filtered = useMemo(
    () =>
      entries.filter((e) => {
        if (action !== "all" && e.action_type !== action) return false;
        if (query && !(e.employee_name ?? "").toLowerCase().includes(query.toLowerCase()))
          return false;
        return true;
      }),
    [entries, action, query],
  );

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-soft-ink3" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Mitarbeiter:in suchen…"
            className="rounded-soft-xs border border-soft-line bg-white pl-9 pr-3 py-2 text-sm outline-none focus:ring-2 focus:ring-soft-accent"
          />
        </div>
        <select
          value={action}
          onChange={(e) => setAction(e.target.value as AuditActionTypeValue | "all")}
          className="rounded-soft-xs border border-soft-line bg-white px-3 py-2 text-sm"
        >
          <option value="all">Alle Aktionen</option>
          {(Object.keys(ACTION_LABELS) as AuditActionTypeValue[]).map((k) => (
            <option key={k} value={k}>{ACTION_LABELS[k]}</option>
          ))}
        </select>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon={ScrollText}
          title="Keine Protokolleinträge"
          description="Vertragsänderungen, Stufenaufstiege und Abwesenheitsereignisse erscheinen hier automatisch."
        />
      ) : (
        <div className="overflow-x-auto bg-white rounded-soft border border-soft-line shadow-soft">
          <table className="w-full text-sm">
            <thead className="bg-soft-line2/40 text-soft-ink3 text-left">
              <tr>
                <th className="px-3 py-2 font-medium">Zeitpunkt</th>
                <th className="px-3 py-2 font-medium">Mitarbeiter:in</th>
                <th className="px-3 py-2 font-medium">Aktion</th>
                <th className="px-3 py-2 font-medium">Beschreibung</th>
                <th className="px-3 py-2 font-medium">Geändert von</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((e) => (
                <tr
                  key={e.id}
                  onClick={() => setSelected(e)}
                  className="border-t border-soft-line2 hover:bg-soft-accentSoft/30 cursor-pointer"
                >
                  <td className="px-3 py-2 numeric text-soft-ink2 whitespace-nowrap">{fmtTs(e.changed_at)}</td>
                  <td className="px-3 py-2 font-medium text-soft-ink">{e.employee_name}</td>
                  <td className="px-3 py-2"><Badge variant={ACTION_VARIANT[e.action_type]}>{ACTION_LABELS[e.action_type]}</Badge></td>
                  <td className="px-3 py-2 text-soft-ink2">{e.summary}</td>
                  <td className="px-3 py-2 text-soft-ink3 text-xs">{e.changed_by ?? "System"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected && <DetailModal entry={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function DetailModal({ entry, onClose }: { entry: AuditLogEntry; onClose: () => void }) {
  const keys = [
    ...new Set([
      ...Object.keys(entry.old_values ?? {}),
      ...Object.keys(entry.new_values ?? {}),
    ]),
  ];
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-soft-ink/30 p-4 overflow-y-auto" onClick={onClose}>
      <div className="bg-white rounded-soft border border-soft-line shadow-soft-lg w-full max-w-xl my-8" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-soft-line">
          <h2 className="text-base font-semibold text-soft-ink">{ACTION_LABELS[entry.action_type]}</h2>
          <button type="button" onClick={onClose} aria-label="Schließen" className="text-soft-ink3 hover:text-soft-ink"><X className="h-5 w-5" /></button>
        </div>
        <div className="p-6 space-y-4 text-sm">
          <p className="text-soft-ink2">{entry.summary}</p>
          <dl className="grid grid-cols-2 gap-2 text-xs">
            <div><dt className="text-soft-ink3">Mitarbeiter:in</dt><dd className="text-soft-ink">{entry.employee_name}</dd></div>
            <div><dt className="text-soft-ink3">Zeitpunkt</dt><dd className="text-soft-ink numeric">{fmtTs(entry.changed_at)}</dd></div>
            <div><dt className="text-soft-ink3">Geändert von</dt><dd className="text-soft-ink">{entry.changed_by ?? "System"}</dd></div>
          </dl>
          {keys.length > 0 && (
            <table className="w-full text-xs border border-soft-line rounded-soft-xs overflow-hidden">
              <thead className="bg-soft-line2/50 text-soft-ink3">
                <tr><th className="px-2 py-1 text-left">Feld</th><th className="px-2 py-1 text-left">Vorher</th><th className="px-2 py-1 text-left">Nachher</th></tr>
              </thead>
              <tbody>
                {keys.map((k) => {
                  const oldV = entry.old_values?.[k];
                  const newV = entry.new_values?.[k];
                  const changed = String(oldV ?? "") !== String(newV ?? "");
                  return (
                    <tr key={k} className={`border-t border-soft-line2 ${changed ? "bg-soft-warnSoft/40" : ""}`}>
                      <td className="px-2 py-1 font-medium text-soft-ink">{k}</td>
                      <td className="px-2 py-1 text-soft-ink2 numeric">{oldV === undefined || oldV === null ? "—" : String(oldV)}</td>
                      <td className="px-2 py-1 text-soft-ink numeric">{newV === undefined || newV === null ? "—" : String(newV)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
