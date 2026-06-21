"use client";

import { useEffect, useState } from "react";

type PreviewData = {
  massnahme: {
    name: string;
    foerdergeber: string;
    laufzeit_von: string;
    laufzeit_bis: string;
    foerderquote_prozent: number;
  };
  budget: {
    positionen: Array<{ kostenart: string; bewilligt: number; ist: number; abweichung: number }>;
    gesamt_bewilligt: number;
    gesamt_ist: number;
    unmapped_ist: number;
  };
  transaktionen_count: number;
  belege_count: number;
  fehlende_belege: number;
  mittelabrufe: Array<{ datum: string; betrag: number; status: string }>;
  ampel_status: "GRUEN" | "GELB" | "ROT";
  ampel_gruende: string[];
};

type Props = {
  measureId: string;
};

const AMPEL_BADGE: Record<"GRUEN" | "GELB" | "ROT", { label: string; className: string }> = {
  GRUEN: {
    label: "Im Zielkorridor",
    className: "bg-soft-okSoft text-soft-ok border border-soft-ok/30",
  },
  GELB: { label: "Achtung", className: "bg-soft-warnSoft text-soft-warn border border-soft-warn/30" },
  ROT: {
    label: "Handlungsbedarf",
    className: "bg-soft-critSoft text-soft-crit border border-soft-crit/30",
  },
};

const MITTELABRUF_STATUS_LABEL: Record<string, string> = {
  ABGERUFEN: "Abgerufen",
  VERWENDET: "Verwendet",
  ABGELAUFEN: "Frist abgelaufen",
  ZURUECKGEZAHLT: "Zurückgezahlt",
};

function formatEuro(value: number): string {
  return new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(value);
}

export function VerwNachweisVorschau({ measureId }: Props) {
  const [data, setData] = useState<PreviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(
          `/api/protected/foerdermassnahmen/${measureId}/verwendungsnachweis/preview`,
        );
        const json = (await res.json()) as { data?: PreviewData; error?: string };
        if (cancelled) return;
        if (!res.ok) {
          setError(json.error ?? "Vorschau konnte nicht geladen werden.");
          return;
        }
        setData(json.data ?? null);
      } catch {
        if (!cancelled) setError("Netzwerkfehler beim Laden der Vorschau.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [measureId]);

  return (
    <div className="rounded-soft border border-soft-line bg-white p-6">
      <div className="flex items-baseline justify-between gap-4 mb-4">
        <h2 className="text-sm font-semibold text-soft-ink2 uppercase tracking-wide">Vorschau</h2>
        <p className="text-xs text-soft-ink3">
          Aktueller Stand der Massnahme — vor Einreichung prüfen
        </p>
      </div>

      {loading && (
        <div className="space-y-3 animate-pulse">
          <div className="h-4 bg-soft-line2 rounded w-1/2" />
          <div className="h-20 bg-soft-line2 rounded" />
          <div className="h-32 bg-soft-line2 rounded" />
        </div>
      )}

      {error && !loading && <p className="text-sm text-soft-crit">{error}</p>}

      {data && !loading && (
        <div className="space-y-5">
          {/* Zusammenfassung */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            <div>
              <span className="block text-xs text-soft-ink4 mb-0.5">Massnahme</span>
              <span className="font-medium text-soft-ink line-clamp-2">{data.massnahme.name}</span>
            </div>
            <div>
              <span className="block text-xs text-soft-ink4 mb-0.5">Fördergeber</span>
              <span className="font-medium text-soft-ink">{data.massnahme.foerdergeber}</span>
            </div>
            <div>
              <span className="block text-xs text-soft-ink4 mb-0.5">Laufzeit</span>
              <span className="numeric font-medium text-soft-ink">
                {data.massnahme.laufzeit_von} – {data.massnahme.laufzeit_bis}
              </span>
            </div>
            <div>
              <span className="block text-xs text-soft-ink4 mb-0.5">Förderquote</span>
              <span className="numeric font-medium text-soft-ink">
                {data.massnahme.foerderquote_prozent.toFixed(0)}%
              </span>
            </div>
          </div>

          {/* Ampel */}
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${AMPEL_BADGE[data.ampel_status].className}`}
            >
              {AMPEL_BADGE[data.ampel_status].label}
            </span>
            {data.ampel_gruende[0] && (
              <span className="text-xs text-soft-ink3">{data.ampel_gruende[0]}</span>
            )}
          </div>

          {/* Budget-Tabelle */}
          {data.budget.positionen.length > 0 ? (
            <div>
              <p className="text-xs font-semibold text-soft-ink2 uppercase tracking-wide mb-2">
                Budget-Positionen
              </p>
              <div className="rounded-soft-sm border border-soft-line2 overflow-hidden">
                <table className="w-full text-xs">
                  <thead className="bg-soft-surfaceAlt">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium text-soft-ink2">Kostenart</th>
                      <th className="px-3 py-2 text-right font-medium text-soft-ink2">Bewilligt</th>
                      <th className="px-3 py-2 text-right font-medium text-soft-ink2">Ist</th>
                      <th className="px-3 py-2 text-right font-medium text-soft-ink2">Abweichung</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white">
                    {data.budget.positionen.map((pos) => (
                      <tr key={pos.kostenart}>
                        <td className="px-3 py-2 text-soft-ink2 font-medium">{pos.kostenart}</td>
                        <td className="px-3 py-2 numeric text-right text-soft-ink2">
                          {formatEuro(pos.bewilligt)}
                        </td>
                        <td className="px-3 py-2 numeric text-right text-soft-ink2">
                          {formatEuro(pos.ist)}
                        </td>
                        <td
                          className={`px-3 py-2 numeric text-right font-medium ${
                            pos.abweichung < 0 ? "text-soft-crit" : "text-soft-ink2"
                          }`}
                        >
                          {pos.abweichung >= 0 ? "+" : ""}
                          {formatEuro(pos.abweichung)}
                        </td>
                      </tr>
                    ))}
                    <tr className="bg-soft-line2 font-semibold">
                      <td className="px-3 py-2 text-soft-ink2">Gesamt</td>
                      <td className="px-3 py-2 numeric text-right text-soft-ink2">
                        {formatEuro(data.budget.gesamt_bewilligt)}
                      </td>
                      <td className="px-3 py-2 numeric text-right text-soft-ink2">
                        {formatEuro(data.budget.gesamt_ist)}
                      </td>
                      <td
                        className={`px-3 py-2 numeric text-right ${
                          data.budget.gesamt_ist - data.budget.gesamt_bewilligt < 0
                            ? "text-soft-crit"
                            : "text-soft-ink2"
                        }`}
                      >
                        {data.budget.gesamt_ist - data.budget.gesamt_bewilligt >= 0 ? "+" : ""}
                        {formatEuro(data.budget.gesamt_ist - data.budget.gesamt_bewilligt)}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <p className="text-xs text-soft-ink4 italic">Keine Budgetpositionen hinterlegt.</p>
          )}

          {/* Unmapped-Ist-Warnung */}
          {data.budget.unmapped_ist > 0 && (
            <div className="rounded-soft-sm border border-soft-warn/40 bg-soft-warnSoft px-3 py-2.5">
              <p className="text-xs text-soft-warn">
                <span className="font-semibold">
                  <span className="numeric">{formatEuro(data.budget.unmapped_ist)}</span> Ist sind
                  keiner Bescheid-Position zugeordnet
                </span>
                {" — "}
                diese Beträge erscheinen in keiner Soll-Ist-Zeile und werden im Verwendungsnachweis
                nicht aufgeführt. Bridge zwischen Kostenbereich und FinanzplanPosition vor der
                Generierung prüfen.
              </p>
            </div>
          )}

          {/* Kennzahlen */}
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-soft-sm bg-white border border-soft-line px-3 py-2.5 text-center">
              <div className="numeric text-lg font-bold text-soft-ink">
                {data.transaktionen_count}
              </div>
              <div className="text-xs text-soft-ink3">Transaktionen</div>
            </div>
            <div className="rounded-soft-sm bg-white border border-soft-line px-3 py-2.5 text-center">
              <div className="numeric text-lg font-bold text-soft-ink">{data.belege_count}</div>
              <div className="text-xs text-soft-ink3">Belege vorhanden</div>
            </div>
            <div
              className={`rounded-soft-sm border px-3 py-2.5 text-center ${
                data.fehlende_belege > 0
                  ? "bg-soft-critSoft border-soft-crit/30"
                  : "bg-white border-soft-line"
              }`}
            >
              <div
                className={`numeric text-lg font-bold ${
                  data.fehlende_belege > 0 ? "text-soft-crit" : "text-soft-ink"
                }`}
              >
                {data.fehlende_belege}
              </div>
              <div className="text-xs text-soft-ink3">Belege fehlend</div>
            </div>
          </div>

          {/* Mittelabrufe */}
          {data.mittelabrufe.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-soft-ink2 uppercase tracking-wide mb-2">
                Mittelabrufe
              </p>
              <div className="space-y-1">
                {data.mittelabrufe.map((ma, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between text-xs bg-soft-line2 border border-soft-line2 rounded-soft-xs px-3 py-1.5"
                  >
                    <span className="numeric text-soft-ink3">{ma.datum}</span>
                    <span className="numeric font-medium text-soft-ink2">
                      {formatEuro(ma.betrag)}
                    </span>
                    <span className="text-soft-ink3">
                      {MITTELABRUF_STATUS_LABEL[ma.status] ?? ma.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
