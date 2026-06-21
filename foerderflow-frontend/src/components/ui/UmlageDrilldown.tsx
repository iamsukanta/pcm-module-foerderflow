"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, AlertTriangle } from "lucide-react";

type DrilldownData = {
  schluessel: {
    name: string;
    gueltig_von: string;
    gueltig_bis: string | null;
  };
  ziel_kostenstelle: {
    code: string;
    name: string;
    anteil_prozent: number;
  };
  quell_pool: {
    name: string;
    cost_centers: Array<{ id: string; code: string; name: string; typ: string }>;
  };
  berechnung: {
    per_kostenstelle: Array<{ quell_cc_code: string; brutto_summe: number }>;
    brutto_umgelegt: number;
    anteil_prozent: number;
    foerderquote: number;
    mwst_foerderfahig: boolean;
    mwst_satz_prozent: number;
    betrag_foerderfahig: number;
    cap_bewilligt: number;
    ist_nach_cap: number;
    cap_erreicht: boolean;
  };
  doppelfoerderung_warnings: string[];
};

const eur = (n: number) =>
  new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(n);

/**
 * Lazy-loaded Drilldown für UMLAGE_KOSTENSTELLEN-Pauschale-Positionen.
 * Klick → fetch /umlage-preview → Anzeige der Aufstellung.
 */
export function UmlageDrilldown({
  measureId,
  positionId,
}: {
  measureId: string;
  positionId: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const [data, setData] = useState<DrilldownData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function toggle() {
    if (!expanded && !data && !loading) {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(
          `/api/protected/foerdermassnahmen/${measureId}/finanzplan-positionen/${positionId}/umlage-preview`
        );
        const json = (await res.json()) as { data?: DrilldownData; error?: string };
        if (!res.ok || !json.data) {
          setError(json.error ?? "Fehler beim Laden der Vorschau.");
        } else {
          setData(json.data);
        }
      } catch (e) {
        setError(`Netzwerkfehler: ${String(e)}`);
      } finally {
        setLoading(false);
      }
    }
    setExpanded((v) => !v);
  }

  return (
    <div className="mt-1 ml-0 border-l-2 border-soft-accent/20 pl-3">
      <button
        type="button"
        onClick={toggle}
        className="inline-flex items-center gap-1 text-[11px] text-soft-ink3 hover:text-soft-accent transition-colors"
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3" aria-hidden="true" />
        ) : (
          <ChevronRight className="h-3 w-3" aria-hidden="true" />
        )}
        Umlage-Details {expanded ? "ausblenden" : "anzeigen"}
      </button>

      {expanded && (
        <div className="mt-2 rounded-soft-xs bg-soft-line2/40 p-3 text-xs space-y-3">
          {loading && <p className="text-soft-ink3 italic">Lädt …</p>}
          {error && <p className="text-soft-crit" role="alert">{error}</p>}
          {data && (
            <>
              {/* Schlüssel-Info */}
              <div>
                <p className="font-semibold text-soft-ink2 mb-0.5">Verteilungsschlüssel</p>
                <p className="text-soft-ink3">
                  {data.schluessel.name} <span className="text-soft-ink4">(gültig ab {data.schluessel.gueltig_von}
                  {data.schluessel.gueltig_bis ? `, bis ${data.schluessel.gueltig_bis}` : ""})</span>
                </p>
              </div>

              {/* Ziel-KST */}
              <div>
                <p className="font-semibold text-soft-ink2 mb-0.5">Anteil aus Schlüssel</p>
                <p className="text-soft-ink3">
                  <span className="numeric font-medium">{data.ziel_kostenstelle.code}</span> —{" "}
                  {data.ziel_kostenstelle.name} ={" "}
                  <span className="numeric font-semibold text-soft-accent">{data.ziel_kostenstelle.anteil_prozent}%</span>
                </p>
              </div>

              {/* Quell-Pool */}
              <div>
                <p className="font-semibold text-soft-ink2 mb-0.5">
                  Quell-KST-Pool „{data.quell_pool.name}&ldquo; ({data.quell_pool.cost_centers.length})
                </p>
                <div className="flex flex-wrap gap-1">
                  {data.quell_pool.cost_centers.map((cc) => (
                    <span
                      key={cc.id}
                      className="inline-flex items-center rounded border border-soft-line bg-white px-1.5 py-0.5 text-[10px] text-soft-ink2"
                      title={cc.name}
                    >
                      <span className="numeric font-medium">{cc.code}</span>
                    </span>
                  ))}
                </div>
              </div>

              {/* Berechnung */}
              <div>
                <p className="font-semibold text-soft-ink2 mb-1">Berechnung</p>
                {data.berechnung.per_kostenstelle.length === 0 ? (
                  <p className="text-soft-ink4 italic">Keine Buchungen auf Quell-KSTs gefunden.</p>
                ) : (
                  <table className="w-full text-[11px]">
                    <thead>
                      <tr className="border-b border-soft-line2 text-soft-ink4">
                        <th className="text-left py-1 pr-2 font-medium">Quell-KST</th>
                        <th className="text-right py-1 pl-2 font-medium">Anteilig umgelegt</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.berechnung.per_kostenstelle.map((r) => (
                        <tr key={r.quell_cc_code}>
                          <td className="py-0.5 pr-2 numeric">{r.quell_cc_code}</td>
                          <td className="py-0.5 pl-2 text-right numeric">{eur(r.brutto_summe)}</td>
                        </tr>
                      ))}
                      <tr className="border-t border-soft-line2 font-semibold">
                        <td className="py-1 pr-2">Σ Brutto umgelegt</td>
                        <td className="py-1 pl-2 text-right numeric">{eur(data.berechnung.brutto_umgelegt)}</td>
                      </tr>
                    </tbody>
                  </table>
                )}

                <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px]">
                  <span className="text-soft-ink4">Förderquote:</span>
                  <span className="numeric text-right">{data.berechnung.foerderquote}%</span>
                  <span className="text-soft-ink4">MwSt förderfähig:</span>
                  <span className="text-right">{data.berechnung.mwst_foerderfahig ? "Ja" : "Nein"} ({data.berechnung.mwst_satz_prozent}%)</span>
                  <span className="text-soft-ink4">→ Förderfähig:</span>
                  <span className="numeric text-right font-medium">{eur(data.berechnung.betrag_foerderfahig)}</span>
                  <span className="text-soft-ink4">Bescheid-Cap:</span>
                  <span className="numeric text-right">{eur(data.berechnung.cap_bewilligt)}</span>
                  <span className="text-soft-ink2 font-semibold">Ist nach Cap:</span>
                  <span className="numeric text-right font-semibold text-soft-accent">
                    {eur(data.berechnung.ist_nach_cap)}
                    {data.berechnung.cap_erreicht && (
                      <span className="ml-1 text-soft-warn text-[10px]">(gecappt)</span>
                    )}
                  </span>
                </div>
              </div>

              {/* Doppelförderungs-Warnings */}
              {data.doppelfoerderung_warnings.length > 0 && (
                <div className="rounded border border-soft-crit/40 bg-soft-critSoft p-2">
                  <p className="flex items-center gap-1 font-semibold text-soft-crit mb-1">
                    <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                    Doppelförderungs-Risiko
                  </p>
                  <ul className="space-y-1 text-[11px] text-soft-crit">
                    {data.doppelfoerderung_warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
