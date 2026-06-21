"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Calendar, Layers, RefreshCw, Trash2, AlertCircle } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { SkeletonCard } from "@/components/ui/SkeletonCard";
import { useToast } from "@/components/ui/ToastProvider";

type Quelle = "MANUELL" | "PERSONALMODUL" | "IMPORT";

type MonatCell = {
  fuer_monat: string;
  betrag_geplant: string;
  quelle: Quelle;
  posten_id: string | null;
};

type KostenbereichRow = {
  kostenbereich_id: string;
  kostenbereich_code: string;
  kostenbereich_bezeichnung: string;
  ist_personal: boolean;
  monate: MonatCell[];
  summe_geplant: string;
};

type PositionRow = {
  id: string;
  positionscode: string;
  bezeichnung: string;
  betrag_bewilligt: string;
  eigenanteil_typ: "KOFINANZIERUNG" | "NICHT_FOERDERFAHIGER_OVERHEAD" | null;
  kostenbereiche: KostenbereichRow[];
};

type FinanzplanData = {
  positionen: PositionRow[];
  laufzeit_monate: string[];
  gesamt_geplant: string;
  gesamt_bewilligt: string;
  diff: string;
};

type Props = {
  measureId: string;
  canEdit: boolean;
  /** Server-vorgerendertes Grid — wenn vorhanden, kein initial fetch */
  initialGrid?: FinanzplanData;
};

const QUELLE_ABBR: Record<Quelle, string> = {
  MANUELL: "M",
  PERSONALMODUL: "P",
  IMPORT: "I",
};
const QUELLE_LABEL: Record<Quelle, string> = {
  MANUELL: "Manuell",
  PERSONALMODUL: "Personalmodul",
  IMPORT: "Import",
};

function formatEuroFromString(s: string): string {
  const n = parseFloat(s);
  if (!isFinite(n)) return s;
  return new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(n);
}

function formatMonth(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  return new Intl.DateTimeFormat("de-DE", { month: "short", year: "2-digit", timeZone: "UTC" }).format(d);
}

function cellKey(posId: string, kbId: string, monat: string): string {
  return `${posId}|${kbId}|${monat}`;
}

export function FinanzplanTab({ measureId, canEdit, initialGrid }: Props) {
  const toast = useToast();
  const [data, setData] = useState<FinanzplanData | null>(initialGrid ?? null);
  const [loading, setLoading] = useState(initialGrid === undefined);
  const [pendingChanges, setPendingChanges] = useState<Map<string, string>>(new Map());
  const [saving, setSaving] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [resetting, setResetting] = useState(false);
  const inputsRef = useRef<HTMLInputElement[]>([]);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/protected/foerdermassnahmen/${measureId}/finanzplan`);
      const json = await res.json();
      if (!res.ok) {
        toast.error(json.error ?? "Konnte Finanzplan nicht laden.");
        setLoading(false);
        return;
      }
      setData(json.data as FinanzplanData);
      setPendingChanges(new Map());
    } catch {
      toast.error("Netzwerkfehler beim Laden des Finanzplans.");
    } finally {
      setLoading(false);
    }
  }, [measureId, toast]);

  // Nur reload bei mount wenn KEIN initialGrid vorhanden ist (Standalone-Verwendung)
  useEffect(() => {
    if (initialGrid === undefined) {
      void reload();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onCellChange = useCallback((key: string, value: string) => {
    setPendingChanges((prev) => {
      const next = new Map(prev);
      next.set(key, value);
      return next;
    });
  }, []);

  const onSave = useCallback(async () => {
    if (!data || pendingChanges.size === 0) return;
    setSaving(true);
    try {
      const updates: Array<{
        finanzplan_position_id: string;
        kostenbereich_id: string;
        fuer_monat: string;
        betrag_geplant: string;
      }> = [];
      for (const [key, betrag] of pendingChanges.entries()) {
        const [pos_id, kb_id, fuer_monat] = key.split("|");
        updates.push({
          finanzplan_position_id: pos_id,
          kostenbereich_id: kb_id,
          fuer_monat,
          betrag_geplant: betrag === "" ? "0" : betrag,
        });
      }
      const res = await fetch(`/api/protected/foerdermassnahmen/${measureId}/finanzplan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ updates }),
      });
      const json = await res.json();
      if (!res.ok) {
        toast.error(json.error ?? "Speichern fehlgeschlagen.");
        return;
      }
      const { updated, deleted } = json.data ?? {};
      toast.success(`${updated} aktualisiert, ${deleted} gelöscht.`);
      await reload();
    } catch {
      toast.error("Netzwerkfehler beim Speichern.");
    } finally {
      setSaving(false);
    }
  }, [data, measureId, pendingChanges, reload, toast]);

  const onReset = useCallback(async () => {
    setResetting(true);
    try {
      const res = await fetch(
        `/api/protected/foerdermassnahmen/${measureId}/finanzplan?quelle=MANUELL`,
        { method: "DELETE" }
      );
      const json = await res.json();
      if (!res.ok) {
        toast.error(json.error ?? "Reset fehlgeschlagen.");
        return;
      }
      const { deleted } = json.data ?? {};
      toast.success(`${deleted} manuelle Einträge gelöscht.`);
      setResetOpen(false);
      await reload();
    } catch {
      toast.error("Netzwerkfehler beim Reset.");
    } finally {
      setResetting(false);
    }
  }, [measureId, reload, toast]);

  // Tab/Enter springt zur nächsten Zelle (linearer Index)
  const onCellKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>, idx: number) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const next = inputsRef.current[idx + 1];
      if (next) next.focus();
    }
  }, []);

  // Loading State
  if (loading) {
    return (
      <div className="space-y-4">
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }

  if (!data) return null;

  // EmptyState 1: Keine Positionen
  if (data.positionen.length === 0) {
    return (
      <div className="space-y-4">
        <EmptyState
          icon={Layers}
          title="Noch keine Finanzplan-Positionen"
          description="Lege Positionen manuell an oder importiere einen Bescheid — beide Wege öffnen den Wizard."
          action={{
            label: "Positionen anlegen",
            href: `/dashboard/foerdermassnahmen/${measureId}/edit?step=4`,
          }}
        />
        <p className="text-center text-xs text-soft-ink4">
          Alternativ:{" "}
          <Link
            href="/dashboard/foerdermassnahmen/import-bescheid"
            className="text-soft-accent hover:underline"
          >
            Bescheid importieren
          </Link>
        </p>
      </div>
    );
  }

  // EmptyState 2: Positionen vorhanden, aber keine Kostenbereiche
  const alleKostenbereicheLeer = data.positionen.every((p) => p.kostenbereiche.length === 0);
  if (alleKostenbereicheLeer) {
    return (
      <EmptyState
        icon={Calendar}
        title={`${data.positionen.length} Position(en) vorhanden — Kostenbereiche fehlen`}
        description="Ordne den Positionen Kostenbereiche zu, um die monatliche Planung zu starten."
        action={{
          label: "Finanzplan-Positionen bearbeiten",
          href: `/dashboard/foerdermassnahmen/${measureId}/edit?step=4`,
        }}
      />
    );
  }

  // Editor
  return (
    <div className="space-y-4">
      {!canEdit && (
        <div
          role="alert"
          className="rounded-soft-sm bg-soft-warnSoft border border-soft-warn/30 p-4 text-sm text-soft-warn flex items-start gap-2"
        >
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" aria-hidden="true" />
          <span>Massnahme ist widerrufen — Read-Only.</span>
        </div>
      )}

      {/* Action-Bar */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          {pendingChanges.size > 0 && (
            <span className="text-xs text-soft-warn font-medium">
              ● <span className="numeric">{pendingChanges.size}</span> ungespeicherte Änderung(en)
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={true}
            title="Kostenstellen-Zuordnung zuerst einrichten"
            aria-label="Aus Personalmodul übernehmen — derzeit nicht verfügbar"
          >
            <RefreshCw className="h-4 w-4 mr-1.5" aria-hidden="true" />
            Aus Personalmodul übernehmen
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={!canEdit}
            onClick={() => setResetOpen(true)}
          >
            <Trash2 className="h-4 w-4 mr-1.5" aria-hidden="true" />
            Manuelle Einträge löschen
          </Button>
          <Button
            variant="primary"
            size="sm"
            disabled={!canEdit || pendingChanges.size === 0 || saving}
            loading={saving}
            onClick={onSave}
          >
            Speichern
          </Button>
        </div>
      </div>

      {/* Grid mit Sticky-Left + Horizontal Scroll für Monate */}
      {/* TODO UX-Verbesserung Phase F.next:
          Bei Laufzeiten > 12 Monate ist das Grid sehr breit.
          Quartals-Toggle evaluieren: Standard = Quartalsansicht, Drill-in auf Monate.
          Aktuell: horizontales Scrollen ist akzeptabel für MVP, aber nicht ideal
          für Tablets. */}
      <FinanzplanGrid
        data={data}
        canEdit={canEdit}
        pendingChanges={pendingChanges}
        onCellChange={onCellChange}
        onCellKeyDown={onCellKeyDown}
        inputsRef={inputsRef}
      />

      <ConfirmDialog
        open={resetOpen}
        title="Manuelle Einträge löschen?"
        description={
          "Alle MANUELL-Einträge dieser Massnahme werden gelöscht. " +
          "Personalmodul- und Import-Einträge bleiben erhalten. " +
          "Diese Aktion kann nicht rückgängig gemacht werden."
        }
        confirmLabel={resetting ? "Wird gelöscht…" : "Ja, löschen"}
        variant="danger"
        loading={resetting}
        onConfirm={onReset}
        onCancel={() => setResetOpen(false)}
      />
    </div>
  );
}

// ─────────────────────────────────────────────
// Inneres Grid (sticky-left + scrollable months)
// ─────────────────────────────────────────────

function FinanzplanGrid({
  data,
  canEdit,
  pendingChanges,
  onCellChange,
  onCellKeyDown,
  inputsRef,
}: {
  data: FinanzplanData;
  canEdit: boolean;
  pendingChanges: Map<string, string>;
  onCellChange: (key: string, value: string) => void;
  onCellKeyDown: (e: React.KeyboardEvent<HTMLInputElement>, idx: number) => void;
  inputsRef: React.MutableRefObject<HTMLInputElement[]>;
}) {
  // Linearer Input-Index für Tab/Enter-Navigation
  const inputIndex = useMemo(() => {
    let idx = 0;
    const map = new Map<string, number>();
    for (const pos of data.positionen) {
      for (const kb of pos.kostenbereiche) {
        for (const m of kb.monate) {
          map.set(cellKey(pos.id, kb.kostenbereich_id, m.fuer_monat), idx++);
        }
      }
    }
    return map;
  }, [data]);

  // Monatsspalten-Summen (mit pending changes)
  const monatsSummen = useMemo(() => {
    const sums = new Map<string, number>();
    for (const pos of data.positionen) {
      for (const kb of pos.kostenbereiche) {
        for (const m of kb.monate) {
          const key = cellKey(pos.id, kb.kostenbereich_id, m.fuer_monat);
          const value = pendingChanges.has(key) ? pendingChanges.get(key)! : m.betrag_geplant;
          const n = parseFloat(value || "0");
          sums.set(m.fuer_monat, (sums.get(m.fuer_monat) ?? 0) + (isFinite(n) ? n : 0));
        }
      }
    }
    return sums;
  }, [data, pendingChanges]);

  // Per-row "geplant" mit pending changes
  const computeRowSum = useCallback(
    (posId: string, kbId: string, monate: MonatCell[]): number => {
      let sum = 0;
      for (const m of monate) {
        const key = cellKey(posId, kbId, m.fuer_monat);
        const value = pendingChanges.has(key) ? pendingChanges.get(key)! : m.betrag_geplant;
        const n = parseFloat(value || "0");
        sum += isFinite(n) ? n : 0;
      }
      return sum;
    },
    [pendingChanges]
  );

  const gesamtGeplantWithPending = useMemo(() => {
    let total = 0;
    for (const pos of data.positionen) {
      for (const kb of pos.kostenbereiche) {
        total += computeRowSum(pos.id, kb.kostenbereich_id, kb.monate);
      }
    }
    return total;
  }, [data, computeRowSum]);

  const gesamtBewilligt = parseFloat(data.gesamt_bewilligt);
  const diffTotal = gesamtBewilligt - gesamtGeplantWithPending;

  // Reset inputsRef array length on each render
  inputsRef.current = [];

  return (
    <div className="flex border border-soft-line rounded-soft overflow-hidden bg-white shadow-soft">
      {/* Sticky linke Spalte */}
      <div className="w-72 shrink-0 bg-white border-r border-soft-line">
        <div className="px-4 py-3 border-b border-soft-line2 bg-soft-surfaceAlt">
          <span className="text-xs font-semibold text-soft-ink3 uppercase tracking-wide">
            Position / Kostenbereich
          </span>
        </div>
        {data.positionen.map((pos) => (
          <div key={pos.id}>
            <div className="px-4 py-2 bg-soft-line2/40 border-b border-soft-line2">
              <span className="font-semibold text-sm text-soft-ink">
                {pos.positionscode}: {pos.bezeichnung}
              </span>
            </div>
            {pos.kostenbereiche.length === 0 ? (
              <div className="px-6 py-2 border-b border-soft-line2 text-xs text-soft-ink4 italic">
                Keine Kostenbereiche zugeordnet
              </div>
            ) : (
              pos.kostenbereiche.map((kb) => (
                <div
                  key={kb.kostenbereich_id}
                  className="px-6 py-2 border-b border-soft-line2 flex items-center gap-2"
                >
                  <span className="text-sm text-soft-ink2 truncate flex-1">
                    {kb.kostenbereich_bezeichnung}
                  </span>
                  {kb.ist_personal && (
                    <Badge variant="muted">Personal</Badge>
                  )}
                </div>
              ))
            )}
          </div>
        ))}
        <div className="px-4 py-3 border-t-2 border-soft-line bg-soft-line2/60">
          <span className="font-semibold text-sm text-soft-ink">GESAMT</span>
        </div>
      </div>

      {/* Scrollbarer Monatsbereich */}
      <div className="flex-1 overflow-x-auto">
        <table className="w-full text-sm" style={{ minWidth: "fit-content" }}>
          <thead className="bg-soft-surfaceAlt">
            <tr>
              {data.laufzeit_monate.map((m) => (
                <th
                  key={m}
                  scope="col"
                  className="numeric px-3 py-3 text-right text-xs font-semibold text-soft-ink3 uppercase tracking-wide whitespace-nowrap min-w-[100px]"
                >
                  {formatMonth(m)}
                </th>
              ))}
              <th
                scope="col"
                className="numeric px-3 py-3 text-right text-xs font-semibold text-soft-ink3 uppercase tracking-wide whitespace-nowrap border-l border-soft-line min-w-[110px]"
              >
                Gesamt
              </th>
              <th
                scope="col"
                className="numeric px-3 py-3 text-right text-xs font-semibold text-soft-ink3 uppercase tracking-wide whitespace-nowrap min-w-[110px]"
              >
                Bewilligt
              </th>
              <th
                scope="col"
                className="numeric px-3 py-3 text-right text-xs font-semibold text-soft-ink3 uppercase tracking-wide whitespace-nowrap min-w-[100px]"
              >
                Diff
              </th>
            </tr>
          </thead>
          <tbody>
            {data.positionen.map((pos) => (
              <FinanzplanPositionRows
                key={pos.id}
                pos={pos}
                canEdit={canEdit}
                pendingChanges={pendingChanges}
                onCellChange={onCellChange}
                onCellKeyDown={onCellKeyDown}
                inputsRef={inputsRef}
                inputIndex={inputIndex}
                computeRowSum={computeRowSum}
                laufzeitMonate={data.laufzeit_monate}
              />
            ))}
          </tbody>
          <tfoot className="bg-soft-line2/60 border-t-2 border-soft-line">
            <tr>
              {data.laufzeit_monate.map((m) => (
                <td
                  key={m}
                  className="numeric px-3 py-3 text-right text-sm font-semibold text-soft-ink whitespace-nowrap"
                >
                  {formatEuroFromString((monatsSummen.get(m) ?? 0).toFixed(2))}
                </td>
              ))}
              <td className="numeric px-3 py-3 text-right text-sm font-bold text-soft-ink whitespace-nowrap border-l border-soft-line">
                {formatEuroFromString(gesamtGeplantWithPending.toFixed(2))}
              </td>
              <td className="numeric px-3 py-3 text-right text-sm font-semibold text-soft-ink2 whitespace-nowrap">
                {formatEuroFromString(gesamtBewilligt.toFixed(2))}
              </td>
              {/* TODO Phase G: Diff-Farbe basierend auf Umwidmungsrahmen
                  (FundingMeasure.overhead_limit_prozent + fördergeber-spezifische Grenzen) */}
              <td className="numeric px-3 py-3 text-right text-sm font-semibold text-soft-ink2 whitespace-nowrap">
                {(diffTotal >= 0 ? "+" : "") + formatEuroFromString(diffTotal.toFixed(2))}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}

function FinanzplanPositionRows({
  pos,
  canEdit,
  pendingChanges,
  onCellChange,
  onCellKeyDown,
  inputsRef,
  inputIndex,
  computeRowSum,
  laufzeitMonate,
}: {
  pos: PositionRow;
  canEdit: boolean;
  pendingChanges: Map<string, string>;
  onCellChange: (key: string, value: string) => void;
  onCellKeyDown: (e: React.KeyboardEvent<HTMLInputElement>, idx: number) => void;
  inputsRef: React.MutableRefObject<HTMLInputElement[]>;
  inputIndex: Map<string, number>;
  computeRowSum: (posId: string, kbId: string, monate: MonatCell[]) => number;
  laufzeitMonate: string[];
}) {
  const betragBewilligt = parseFloat(pos.betrag_bewilligt);

  return (
    <>
      {/* Spacer-Zeile für Position-Header (linke Spalte hat eigene Position-Zeile) */}
      <tr className="bg-soft-line2/40 border-b border-soft-line2">
        {laufzeitMonate.map((m) => (
          <td key={m} className="px-3 py-2">&nbsp;</td>
        ))}
        <td className="px-3 py-2 border-l border-soft-line">&nbsp;</td>
        <td className="numeric px-3 py-2 text-right text-xs font-medium text-soft-ink2 whitespace-nowrap">
          {formatEuroFromString(betragBewilligt.toFixed(2))}
        </td>
        <td className="px-3 py-2">&nbsp;</td>
      </tr>

      {pos.kostenbereiche.length === 0 ? (
        <tr className="border-b border-soft-line2">
          {laufzeitMonate.map((m) => (
            <td key={m} className="px-3 py-2 text-xs text-soft-ink4 italic">—</td>
          ))}
          <td className="px-3 py-2 border-l border-soft-line">&nbsp;</td>
          <td className="px-3 py-2">&nbsp;</td>
          <td className="px-3 py-2">&nbsp;</td>
        </tr>
      ) : (
        pos.kostenbereiche.map((kb) => {
          const summe = computeRowSum(pos.id, kb.kostenbereich_id, kb.monate);
          return (
            <tr key={kb.kostenbereich_id} className="border-b border-soft-line2 hover:bg-soft-surfaceAlt/40">
              {kb.monate.map((cell) => {
                const key = cellKey(pos.id, kb.kostenbereich_id, cell.fuer_monat);
                const value = pendingChanges.has(key) ? pendingChanges.get(key)! : cell.betrag_geplant;
                const idx = inputIndex.get(key) ?? 0;
                const isPending = pendingChanges.has(key);
                return (
                  <td key={cell.fuer_monat} className="px-2 py-1.5 relative">
                    <input
                      ref={(el) => {
                        if (el) inputsRef.current[idx] = el;
                      }}
                      type="number"
                      step="0.01"
                      min="0"
                      inputMode="decimal"
                      disabled={!canEdit}
                      value={value}
                      onChange={(e) => onCellChange(key, e.target.value)}
                      onKeyDown={(e) => onCellKeyDown(e, idx)}
                      aria-label={`${kb.kostenbereich_bezeichnung} ${formatMonth(cell.fuer_monat)}`}
                      className={`numeric w-full text-right rounded-soft-xs border px-2 py-1 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-soft-accent disabled:bg-soft-line2 disabled:text-soft-ink3 ${
                        isPending ? "border-soft-accent" : "border-soft-line"
                      }`}
                    />
                    <span
                      className="absolute right-3 bottom-0 text-[9px] text-soft-ink4 select-none pointer-events-none"
                      title={QUELLE_LABEL[cell.quelle]}
                      aria-hidden="true"
                    >
                      {QUELLE_ABBR[cell.quelle]}
                    </span>
                  </td>
                );
              })}
              <td className="numeric px-3 py-1.5 text-right text-sm font-semibold text-soft-ink whitespace-nowrap border-l border-soft-line">
                {formatEuroFromString(summe.toFixed(2))}
              </td>
              <td className="px-3 py-1.5">&nbsp;</td>
              <td className="px-3 py-1.5">&nbsp;</td>
            </tr>
          );
        })
      )}
    </>
  );
}
