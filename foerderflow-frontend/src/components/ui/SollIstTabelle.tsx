type SollIstRow = {
  id: string;
  kostenart: string;
  beschreibung: string | null;
  betrag_beantragt: string;
  betrag_bewilligt: string;
  betrag_ist: string;
  differenz: string;
  ausschoepfung_prozent: number;
  status: "OK" | "WARNING" | "KRITISCH" | "UEBERSCHRITTEN";
  // Phase J — optionale Pauschale-Kennzeichnung. UI rendert ein Badge.
  ist_pauschale?: boolean;
  pauschale_typ?: "FIXER_BETRAG" | "PROZENT_GESAMT" | "PROZENT_PERSONAL" | "UMLAGE_KOSTENSTELLEN" | null;
  pauschale_prozent?: number | null;
  // Phase J9 — Maßnahmen-Default für Badge-Fallback wenn pauschale_prozent null
  pauschale_default_prozent?: number | null;
};

type Props = {
  data: SollIstRow[];
  gesamt_beantragt: string;
  gesamt_bewilligt: string;
  gesamt_ist: string;
  /** Optionaler Header-Label für die erste Spalte (Default "Kostenart") */
  titleColumn?: string;
  /**
   * Phase K — wenn gesetzt, wird unter UMLAGE_KOSTENSTELLEN-Positionen ein
   * Drilldown-Expander gerendert (lazy-loaded via /umlage-preview-Endpoint).
   */
  measureId?: string;
};

const STATUS_CONFIG: Record<SollIstRow["status"], { label: string; badge: string }> = {
  OK: { label: "OK", badge: "bg-soft-okSoft text-soft-ok" },
  WARNING: { label: "Warnung", badge: "bg-soft-warnSoft text-soft-warn" },
  KRITISCH: { label: "Kritisch", badge: "bg-soft-warnSoft text-soft-warn" },
  UEBERSCHRITTEN: { label: "Überschritten", badge: "bg-soft-critSoft text-soft-crit" },
};

import { UmlageDrilldown } from "./UmlageDrilldown";

function formatEur(val: string): string {
  return new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(
    parseFloat(val)
  );
}

function pauschaleBadgeLabel(row: SollIstRow): string {
  if (!row.ist_pauschale) return "";
  // Effektiver Prozentsatz: pro-Position-Wert hat Vorrang, sonst Maßnahmen-Default.
  // Wenn Default greift, mit Suffix "(Default)" markieren.
  const effProzent =
    row.pauschale_prozent != null ? row.pauschale_prozent : row.pauschale_default_prozent ?? null;
  const istDefault = row.pauschale_prozent == null && effProzent != null;
  const suffix = istDefault ? " (Default)" : "";
  switch (row.pauschale_typ) {
    case "FIXER_BETRAG":
      return "Pauschale (fixer Betrag)";
    case "PROZENT_PERSONAL":
      return effProzent != null
        ? `Pauschale (${effProzent}% × Personal${suffix})`
        : "Pauschale (% × Personal)";
    case "PROZENT_GESAMT":
      return effProzent != null
        ? `Pauschale (${effProzent}% × Gesamt${suffix})`
        : "Pauschale (% × Gesamt)";
    case "UMLAGE_KOSTENSTELLEN":
      // Phase K — Umlage nach Verteilungsschlüssel × Quell-KSTs. Drilldown
      // zeigt Schlüssel-Version + Anteil; hier nur Mode-Indikator.
      return "Pauschale (Umlage)";
    default:
      return "Pauschale";
  }
}

function isPauschaleCapped(row: SollIstRow): boolean {
  // PROZENT_*-Pauschale gilt als gecappt, wenn Ist exakt auf Bewilligt landet
  // — das ist der Hard-Cap-Trigger in lib/finanzplan-ist.ts.
  if (!row.ist_pauschale) return false;
  if (row.pauschale_typ !== "PROZENT_GESAMT" && row.pauschale_typ !== "PROZENT_PERSONAL") return false;
  const ist = parseFloat(row.betrag_ist);
  const bew = parseFloat(row.betrag_bewilligt);
  return bew > 0 && Math.abs(ist - bew) < 0.005;
}

/**
 * Soll-Ist-Vergleichstabelle für Fördermassnahmen.
 * Server-gerendert, erhält vorberechnete Daten als Props.
 */
export function SollIstTabelle({
  data,
  gesamt_beantragt,
  gesamt_bewilligt,
  gesamt_ist,
  titleColumn = "Kostenart",
  measureId,
}: Props) {
  if (data.length === 0) {
    return (
      <p className="text-sm text-soft-ink3 italic">
        Keine Bescheid-Positionen hinterlegt. Bescheid via Bescheid-Import zur Maßnahme
        hinzufügen, um den Soll-Ist-Vergleich zu sehen.
      </p>
    );
  }

  const gesamtDifferenz = parseFloat(gesamt_bewilligt) - parseFloat(gesamt_ist);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-soft-line">
            <th className="text-left py-2 pr-3 text-xs font-medium text-soft-ink3 uppercase tracking-wide">{titleColumn}</th>
            <th className="text-right py-2 px-2 text-xs font-medium text-soft-ink3 uppercase tracking-wide whitespace-nowrap">Beantragt</th>
            <th className="text-right py-2 px-2 text-xs font-medium text-soft-ink3 uppercase tracking-wide whitespace-nowrap">Bewilligt</th>
            <th className="text-right py-2 px-2 text-xs font-medium text-soft-ink3 uppercase tracking-wide whitespace-nowrap">Ist</th>
            <th className="text-right py-2 px-2 text-xs font-medium text-soft-ink3 uppercase tracking-wide whitespace-nowrap">Differenz</th>
            <th className="text-right py-2 pl-2 text-xs font-medium text-soft-ink3 uppercase tracking-wide">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-soft-line2">
          {data.map((row) => {
            const differenzNum = parseFloat(row.differenz);
            const cfg = STATUS_CONFIG[row.status];
            return (
              <tr key={row.id} className="hover:bg-soft-line2">
                <td className="py-2.5 pr-3">
                  <div className="font-medium text-soft-ink flex items-center gap-2 flex-wrap">
                    <span>{row.kostenart}</span>
                    {row.ist_pauschale && (
                      <span
                        className="inline-flex items-center rounded-soft-xs bg-soft-accentSoft px-1.5 py-0.5 text-[10px] font-medium text-soft-accent border border-soft-accent/30"
                        title="Pauschale-Position: Ist wird nach Bescheid-Modus berechnet, nicht aus direkten Buchungen."
                      >
                        {pauschaleBadgeLabel(row)}
                      </span>
                    )}
                    {isPauschaleCapped(row) && (
                      <span
                        className="inline-flex items-center rounded-soft-xs bg-soft-warnSoft px-1.5 py-0.5 text-[10px] font-medium text-soft-warn border border-soft-warn/30"
                        title="Berechneter Pauschale-Betrag war höher als der Bescheid-Höchstbetrag und wurde gecappt."
                      >
                        Cap erreicht
                      </span>
                    )}
                  </div>
                  {row.beschreibung && (
                    <div className="text-xs text-soft-ink3">{row.beschreibung}</div>
                  )}
                  {/* Phase K — UMLAGE-Drilldown */}
                  {row.ist_pauschale && row.pauschale_typ === "UMLAGE_KOSTENSTELLEN" && measureId && (
                    <UmlageDrilldown measureId={measureId} positionId={row.id} />
                  )}
                </td>
                <td className="py-2.5 px-2 text-right text-soft-ink2 numeric">
                  {formatEur(row.betrag_beantragt)}
                </td>
                <td className="py-2.5 px-2 text-right text-soft-ink numeric font-medium">
                  {formatEur(row.betrag_bewilligt)}
                </td>
                <td className="py-2.5 px-2 text-right text-soft-ink numeric font-semibold">
                  {formatEur(row.betrag_ist)}
                </td>
                <td className={`py-2.5 px-2 text-right numeric font-medium ${
                  differenzNum < 0 ? "text-soft-crit" : "text-soft-ok"
                }`}>
                  {differenzNum >= 0 ? "+" : ""}{formatEur(row.differenz)}
                </td>
                <td className="py-2.5 pl-2 text-right">
                  <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${cfg.badge}`}>
                    {cfg.label}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-soft-line font-semibold">
            <td className="py-2.5 pr-3 text-soft-ink">Gesamt</td>
            <td className="py-2.5 px-2 text-right numeric text-soft-ink2">
              {formatEur(gesamt_beantragt)}
            </td>
            <td className="py-2.5 px-2 text-right numeric text-soft-ink">
              {formatEur(gesamt_bewilligt)}
            </td>
            <td className="py-2.5 px-2 text-right numeric text-soft-ink">
              {formatEur(gesamt_ist)}
            </td>
            <td className={`py-2.5 px-2 text-right numeric ${
              gesamtDifferenz < 0 ? "text-soft-crit" : "text-soft-ok"
            }`}>
              {gesamtDifferenz >= 0 ? "+" : ""}{formatEur(gesamtDifferenz.toFixed(2))}
            </td>
            <td />
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
