"use client";

import { useState } from "react";
import { clsx } from "clsx";
import { Button } from "@/components/ui/Button";
import {
  VerteilungsschluesselForm,
  positionsToEditorDrafts,
} from "@/components/forms/VerteilungsschluesselForm";
import {
  ALLOCATION_BASIS_DESCRIPTIONS,
  type AllocationKeyWithPositions,
} from "@/types/verteilungsschluessel";

type CostCenterOption = {
  id: string;
  name: string;
  code: string;
  typ: string;
};

type Props = {
  allocationKey: AllocationKeyWithPositions;
  availableCostCenters: CostCenterOption[];
  initialShowNeueVersion: boolean;
};

function calcSum(positions: Array<{ prozent: string }>): number {
  const sum = positions.reduce((acc, p) => acc + Number(p.prozent), 0);
  return Number(sum.toFixed(3));
}

/** Summenbalken — read-only Anzeige */
function SummenBalken({ positions }: { positions: AllocationKeyWithPositions["positions"] }) {
  const summe = calcSum(positions);
  const isComplete = Math.abs(summe - 100) < 0.001;
  const isOver = summe > 100.001;
  const barWidth = Math.min((summe / 100) * 100, 100);

  const barColor = isComplete ? "bg-soft-ok" : isOver ? "bg-soft-crit" : "bg-soft-warn";
  const bgColor = isComplete
    ? "bg-soft-okSoft border-soft-ok/20"
    : isOver
      ? "bg-soft-critSoft border-soft-crit/20"
      : "bg-soft-warnSoft border-soft-warn/20";
  const textColor = isComplete ? "text-soft-ok" : isOver ? "text-soft-crit" : "text-soft-warn";

  return (
    <div className={clsx("rounded-soft-xs border p-3", bgColor)}>
      <div className="flex items-center gap-3 mb-1">
        <div className="flex-1 h-2 rounded-full bg-soft-line overflow-hidden">
          <div className={clsx("h-full rounded-full", barColor)} style={{ width: `${barWidth}%` }} />
        </div>
        <span className={clsx("text-sm font-semibold tabular-nums shrink-0", textColor)}>
          {summe.toFixed(2)} %
        </span>
      </div>
      <p className={clsx("text-xs font-medium", textColor)}>
        {isComplete && "Vollständig — die Summe ergibt exakt 100 %."}
        {!isComplete && !isOver && `Noch ${(100 - summe).toFixed(2)} % fehlen.`}
        {isOver && `${(summe - 100).toFixed(2)} % zu viel.`}
      </p>
    </div>
  );
}

export function VerteilungsschluesselDetailClient({
  allocationKey,
  availableCostCenters,
  initialShowNeueVersion,
}: Props) {
  const [showNeueVersion, setShowNeueVersion] = useState(initialShowNeueVersion);

  return (
    <div className="space-y-8">
      {/* ── Read-only Positions-Übersicht ─────────── */}
      <section>
        <h2 className="text-lg font-semibold text-soft-ink mb-4">Kostenstellenanteile</h2>

        <div className="rounded-soft-sm border border-soft-line overflow-hidden mb-4">
          <div className="grid grid-cols-[1fr_120px] gap-2 bg-soft-line2 border-b border-soft-line px-4 py-2">
            <span className="text-xs font-medium text-soft-ink2">Kostenstelle</span>
            <span className="text-xs font-medium text-soft-ink2 text-right">Anteil</span>
          </div>
          <div className="divide-y divide-soft-line2">
            {allocationKey.positions.length === 0 && (
              <p className="px-4 py-4 text-sm text-soft-ink4">Keine Positionen</p>
            )}
            {allocationKey.positions.map((pos) => (
              <div key={pos.id} className="grid grid-cols-[1fr_120px] gap-2 px-4 py-3 items-center">
                <div>
                  <span className="text-sm font-medium text-soft-ink">
                    {pos.cost_center?.code ?? "—"}
                  </span>
                  <span className="ml-2 text-sm text-soft-ink3">
                    {pos.cost_center?.name ?? pos.cost_center_id}
                  </span>
                </div>
                <div className="text-right font-mono text-sm font-semibold text-soft-ink2">
                  {Number(pos.prozent).toFixed(2)} %
                </div>
              </div>
            ))}
          </div>
        </div>

        <SummenBalken positions={allocationKey.positions} />
      </section>

      {/* Basis-Info */}
      <section className="rounded-soft-xs bg-soft-line2 border border-soft-line p-4 text-sm text-soft-ink2">
        <strong className="text-soft-ink2">Berechnungsbasis:</strong>{" "}
        {ALLOCATION_BASIS_DESCRIPTIONS[allocationKey.basis]}
      </section>

      {/* ── Edit: Name / gueltig_bis ─────────────── */}
      <section>
        <h2 className="text-lg font-semibold text-soft-ink mb-1">Schlüssel bearbeiten</h2>
        <p className="text-sm text-soft-ink3 mb-4">
          Name und Gültig-bis-Datum können angepasst werden. Für Änderungen an Basis oder Anteilen
          bitte eine neue Version anlegen — so bleiben historische Auswertungen reproduzierbar.
        </p>

        <VerteilungsschluesselForm
          mode="edit"
          keyId={allocationKey.id}
          initialValues={{
            name: allocationKey.name,
            gueltig_von: allocationKey.gueltig_von,
            gueltig_bis: allocationKey.gueltig_bis,
          }}
          availableCostCenters={availableCostCenters}
        />
      </section>

      {/* ── Neue Version ─────────────────────────── */}
      {allocationKey.ist_aktiv && (
        <section>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-semibold text-soft-ink">Neue Version anlegen</h2>
              <p className="text-sm text-soft-ink3 mt-0.5">
                Legt einen neuen Schlüssel mit aktualisierten Anteilen an. Der aktuelle Schlüssel
                wird automatisch abgeschlossen.
              </p>
            </div>
            {!showNeueVersion && (
              <Button variant="secondary" size="sm" onClick={() => setShowNeueVersion(true)}>
                Neue Version
              </Button>
            )}
          </div>

          {showNeueVersion && (
            <div className="rounded-soft-sm border border-soft-accent bg-soft-accentWash p-5">
              <VerteilungsschluesselForm
                mode="neue-version"
                keyId={allocationKey.id}
                initialValues={{
                  name: allocationKey.name,
                  basis: allocationKey.basis,
                  gueltig_von: "",
                  gueltig_bis: null,
                  positions: positionsToEditorDrafts(allocationKey.positions),
                }}
                availableCostCenters={availableCostCenters}
              />
            </div>
          )}
        </section>
      )}
    </div>
  );
}
