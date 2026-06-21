"use client";

import { useCallback } from "react";
import { clsx } from "clsx";
import type { PositionDraft } from "@/types/verteilungsschluessel";

type CostCenterOption = {
  id: string;
  name: string;
  code: string;
  typ: string;
};

type PositionenEditorProps = {
  positions: PositionDraft[];
  onChange: (positions: PositionDraft[]) => void;
  availableCostCenters: CostCenterOption[];
  disabled?: boolean;
};

function generateKey(): string {
  return `pos-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

function calcSum(positions: PositionDraft[]): number {
  const sum = positions.reduce((acc, p) => {
    const v = parseFloat(p.prozent);
    return acc + (isNaN(v) ? 0 : v);
  }, 0);
  return Number(sum.toFixed(3));
}

export function PositionenEditor({
  positions,
  onChange,
  availableCostCenters,
  disabled = false,
}: PositionenEditorProps) {
  const summe = calcSum(positions);
  const isComplete = Math.abs(summe - 100) < 0.001;
  const isOver = summe > 100.001;
  const isUnder = summe < 99.999;

  const selectedIds = new Set(positions.map((p) => p.cost_center_id));

  const handleAddRow = useCallback(() => {
    const unused = availableCostCenters.find((c) => !selectedIds.has(c.id));
    onChange([
      ...positions,
      {
        _key: generateKey(),
        cost_center_id: unused?.id ?? "",
        prozent: "",
      },
    ]);
  }, [positions, onChange, availableCostCenters, selectedIds]);

  const handleRemove = useCallback(
    (key: string) => {
      onChange(positions.filter((p) => p._key !== key));
    },
    [positions, onChange],
  );

  const handleKstChange = useCallback(
    (key: string, cost_center_id: string) => {
      onChange(positions.map((p) => (p._key === key ? { ...p, cost_center_id } : p)));
    },
    [positions, onChange],
  );

  const handleProzentChange = useCallback(
    (key: string, value: string) => {
      const cleaned = value.replace(/[^0-9.]/g, "");
      const formatted = cleaned.replace(/^(\d*\.?\d{0,2}).*$/, "$1");
      onChange(positions.map((p) => (p._key === key ? { ...p, prozent: formatted } : p)));
    },
    [positions, onChange],
  );

  // Enter im Prozent-Input → neue Zeile hinzufügen
  const handleProzentKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>, isLast: boolean) => {
      if (e.key === "Enter") {
        e.preventDefault();
        if (isLast && availableCostCenters.length > selectedIds.size) {
          handleAddRow();
        }
      }
    },
    [handleAddRow, availableCostCenters.length, selectedIds.size],
  );

  const barWidth = Math.min((summe / 100) * 100, 100);
  const barColor = isComplete ? "bg-soft-ok" : isOver ? "bg-soft-crit" : "bg-soft-warn";

  const hasEmptyKst = positions.some((p) => !p.cost_center_id);
  const canAddMore = !hasEmptyKst && availableCostCenters.length > positions.length;

  return (
    <div className="rounded-soft-sm border border-soft-line overflow-hidden">
      {/* Tabellen-Header */}
      <div className="grid grid-cols-[1fr_140px_44px] gap-2 bg-soft-line2 border-b border-soft-line px-4 py-2">
        <span className="text-xs font-medium text-soft-ink2">Kostenstelle</span>
        <span className="text-xs font-medium text-soft-ink2 text-right">Anteil %</span>
        <span />
      </div>

      {/* Positionen */}
      <div className="divide-y divide-slate-100">
        {positions.length === 0 && (
          <div className="px-4 py-6 text-center text-sm text-soft-ink4">
            Noch keine Kostenstelle hinzugefügt.
          </div>
        )}

        {positions.map((pos, idx) => {
          const isLast = idx === positions.length - 1;
          const options = availableCostCenters.filter(
            (c) => !selectedIds.has(c.id) || c.id === pos.cost_center_id,
          );

          return (
            <div
              key={pos._key}
              className="grid grid-cols-[1fr_140px_44px] gap-2 px-4 py-2.5 items-center bg-white hover:bg-soft-line2/50 transition-colors"
            >
              {/* KST-Dropdown */}
              <select
                value={pos.cost_center_id}
                onChange={(e) => handleKstChange(pos._key, e.target.value)}
                disabled={disabled}
                aria-label={`Kostenstelle für Position ${idx + 1}`}
                className={clsx(
                  "w-full rounded-soft-xs border border-soft-line px-2 py-1.5 text-sm bg-white outline-none",
                  "focus:ring-2 focus:ring-soft-accent focus:border-soft-accent transition-colors",
                  "disabled:bg-soft-line2 disabled:text-soft-ink4 disabled:cursor-not-allowed",
                  !pos.cost_center_id && "text-soft-ink4",
                )}
              >
                <option value="">— KST wählen —</option>
                {options.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.code} — {c.name}
                  </option>
                ))}
              </select>

              {/* Prozent-Input */}
              <div className="flex items-center gap-1">
                <input
                  type="text"
                  inputMode="decimal"
                  value={pos.prozent}
                  onChange={(e) => handleProzentChange(pos._key, e.target.value)}
                  onKeyDown={(e) => handleProzentKeyDown(e, isLast)}
                  disabled={disabled}
                  aria-label={`Prozentwert für Position ${idx + 1}`}
                  placeholder="0.00"
                  maxLength={6}
                  className={clsx(
                    "w-full rounded-soft-xs border border-soft-line px-2 py-1.5 text-sm text-right font-mono outline-none",
                    "focus:ring-2 focus:ring-soft-accent focus:border-soft-accent transition-colors",
                    "disabled:bg-soft-line2 disabled:text-soft-ink4 disabled:cursor-not-allowed",
                  )}
                />
                <span className="text-sm text-soft-ink3 shrink-0">%</span>
              </div>

              {/* Entfernen */}
              <button
                type="button"
                onClick={() => handleRemove(pos._key)}
                disabled={disabled}
                aria-label={`Position ${idx + 1} entfernen`}
                className={clsx(
                  "flex items-center justify-center w-9 h-9 rounded-soft-xs text-soft-ink4 hover:text-soft-crit hover:bg-soft-critSoft transition-colors",
                  "focus:outline-none focus:ring-2 focus:ring-soft-crit",
                  "disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:text-soft-ink4 disabled:hover:bg-transparent",
                )}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-4 w-4"
                  aria-hidden="true"
                >
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            </div>
          );
        })}
      </div>

      {/* KST hinzufügen */}
      <div className="border-t border-soft-line2 px-4 py-2">
        <button
          type="button"
          onClick={handleAddRow}
          disabled={disabled || !canAddMore}
          className={clsx(
            "text-sm font-medium text-soft-accent hover:text-soft-accent hover:underline",
            "flex items-center gap-1.5 py-1",
            "focus:outline-none focus:ring-2 focus:ring-soft-accent rounded",
            "disabled:text-soft-ink4 disabled:cursor-not-allowed disabled:no-underline",
          )}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-4 w-4"
            aria-hidden="true"
          >
            <path d="M12 5v14M5 12h14" />
          </svg>
          Kostenstelle hinzufügen
        </button>
      </div>

      {/* Summenbalken */}
      <div
        className={clsx(
          "border-t px-4 py-3",
          isComplete
            ? "border-soft-ok/30 bg-soft-okSoft"
            : isOver
              ? "border-soft-crit/30 bg-soft-critSoft"
              : "border-soft-warn/30 bg-soft-warnSoft",
        )}
        aria-live="polite"
        aria-label={`Summe: ${summe.toFixed(2)} Prozent`}
      >
        {/* Fortschrittsbalken */}
        <div className="flex items-center gap-3 mb-1.5">
          <div className="flex-1 h-2 rounded-full bg-soft-line overflow-hidden">
            <div
              className={clsx("h-full rounded-full transition-all duration-200", barColor)}
              style={{ width: `${barWidth}%` }}
            />
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <span
              className={clsx(
                "text-sm font-semibold tabular-nums",
                isComplete ? "text-soft-ok" : isOver ? "text-soft-crit" : "text-soft-warn",
              )}
            >
              {summe.toFixed(2)} %
            </span>
            {isComplete && (
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={2.5}
                strokeLinecap="round"
                strokeLinejoin="round"
                className="h-4 w-4 text-soft-ok"
                aria-hidden="true"
              >
                <path d="M20 6 9 17l-5-5" />
              </svg>
            )}
          </div>
        </div>

        {/* Status-Text */}
        <p
          className={clsx(
            "text-xs font-medium",
            isComplete ? "text-soft-ok" : isOver ? "text-soft-crit" : "text-soft-warn",
          )}
        >
          {isComplete && "Vollständig — die Summe ergibt exakt 100 %."}
          {isUnder && !isComplete && `Noch ${(100 - summe).toFixed(2)} % fehlen.`}
          {isOver && `${(summe - 100).toFixed(2)} % zu viel — bitte korrigieren.`}
        </p>
      </div>
    </div>
  );
}
