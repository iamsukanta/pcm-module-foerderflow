// Server Component: zeigt Plan/Ist-Aufstellung + Cross-Finanzierungs-Liste
// für eine Fehlbedarfs-Maßnahme (oder Vollfinanzierung).
//
// Datenquelle: lib/fehlbedarf-compliance.ts → getFehlbedarfStatus()
//
// UI-Konvention: konsistent mit anderen Maßnahmen-Detail-Sections
// (rounded-soft-sm, soft-line border, soft-* tokens, .numeric für Beträge).

import type { FehlbedarfStatus, OverlappingFundingMeasure } from "@/lib/fehlbedarf-compliance";
import { Info } from "lucide-react";

type Props = {
  status: FehlbedarfStatus;
  gesamtausgabenPlan: number;
  eigenmittelPlan: number;
  eigenmittelIst: number;
  drittmittelPlan: number;
  drittmittelIst: number;
  zuwendungHoechstbetrag: number;
  zuwendungAbgerufen: number;
  fehlbedarfZulaessig: number;
  verbleibendAbrufbar: number;
  andereMassnahmen: OverlappingFundingMeasure[];
};

function formatEur(n: number): string {
  return new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
  }).format(n);
}

function deltaSign(plan: number, ist: number): "ueber" | "unter" | "gleich" {
  if (Math.abs(plan - ist) < 0.005) return "gleich";
  return ist > plan ? "ueber" : "unter";
}

function deltaClass(sign: "ueber" | "unter" | "gleich"): string {
  if (sign === "ueber") return "text-soft-warn";
  if (sign === "unter") return "text-soft-ink3";
  return "text-soft-ink3";
}

export function CrossFinanzierungWidget({
  status,
  gesamtausgabenPlan,
  eigenmittelPlan,
  eigenmittelIst,
  drittmittelPlan,
  drittmittelIst,
  zuwendungHoechstbetrag,
  zuwendungAbgerufen,
  fehlbedarfZulaessig,
  verbleibendAbrufbar,
  andereMassnahmen,
}: Props) {
  const eigenSign = deltaSign(eigenmittelPlan, eigenmittelIst);
  const drittSign = deltaSign(drittmittelPlan, drittmittelIst);

  return (
    <section
      aria-label="Fehlbedarf-Compliance Übersicht"
      className="mb-6 rounded-soft-sm border border-soft-line bg-soft-surface p-5"
    >
      <header className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-soft-ink">
          Fehlbedarf-Compliance (ANBest-P §2.2)
        </h2>
        <span className="text-xs text-soft-ink4">
          {status === "OK" && "Status OK"}
          {status === "HINWEIS" && "Status Hinweis"}
          {status === "WARNUNG" && "Status Warnung"}
        </span>
      </header>

      {/* Plan/Ist-Tabelle */}
      <div className="mb-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-soft-ink4 border-b border-soft-line">
              <th className="py-2 pr-4 font-medium">Position</th>
              <th className="py-2 pr-4 font-medium text-right">Plan (Bescheid)</th>
              <th className="py-2 pr-4 font-medium text-right">Ist</th>
              <th className="py-2 font-medium text-right">Delta</th>
            </tr>
          </thead>
          <tbody className="text-soft-ink2">
            <tr className="border-b border-soft-line2">
              <td className="py-2 pr-4">Gesamtausgaben (Plan)</td>
              <td className="py-2 pr-4 text-right numeric">{formatEur(gesamtausgabenPlan)}</td>
              <td className="py-2 pr-4 text-right text-soft-ink4">—</td>
              <td className="py-2 text-right text-soft-ink4">—</td>
            </tr>
            <tr className="border-b border-soft-line2">
              <td className="py-2 pr-4">Eigenmittel</td>
              <td className="py-2 pr-4 text-right numeric">{formatEur(eigenmittelPlan)}</td>
              <td className="py-2 pr-4 text-right numeric">{formatEur(eigenmittelIst)}</td>
              <td className={`py-2 text-right numeric ${deltaClass(eigenSign)}`}>
                {eigenSign === "ueber" ? "+" : eigenSign === "unter" ? "−" : ""}
                {formatEur(Math.abs(eigenmittelIst - eigenmittelPlan))}
              </td>
            </tr>
            <tr className="border-b border-soft-line2">
              <td className="py-2 pr-4">
                Drittmittel{" "}
                <span className="text-xs text-soft-ink4" title="Heuristisch berechnet aus anderen FundingMeasures mit überlappendem Zeitraum + geteilten Cost-Centers">
                  (heuristisch)
                </span>
              </td>
              <td className="py-2 pr-4 text-right numeric">{formatEur(drittmittelPlan)}</td>
              <td className="py-2 pr-4 text-right numeric">{formatEur(drittmittelIst)}</td>
              <td className={`py-2 text-right numeric ${deltaClass(drittSign)}`}>
                {drittSign === "ueber" ? "+" : drittSign === "unter" ? "−" : ""}
                {formatEur(Math.abs(drittmittelIst - drittmittelPlan))}
              </td>
            </tr>
            <tr className="border-b-2 border-soft-line">
              <td className="py-2 pr-4 font-medium">Zuwendungs-Höchstbetrag (Bescheid)</td>
              <td className="py-2 pr-4 text-right numeric">{formatEur(zuwendungHoechstbetrag)}</td>
              <td className="py-2 pr-4 text-right text-soft-ink4">—</td>
              <td className="py-2 text-right text-soft-ink4">—</td>
            </tr>
            <tr className="border-b border-soft-line2">
              <td className="py-2 pr-4 font-medium">Aktuell zulässige Zuwendung</td>
              <td className="py-2 pr-4 text-right text-soft-ink4">—</td>
              <td className="py-2 pr-4 text-right numeric font-semibold text-soft-ink">
                {formatEur(fehlbedarfZulaessig)}
              </td>
              <td className="py-2 text-right text-soft-ink4">—</td>
            </tr>
            <tr className="border-b border-soft-line2">
              <td className="py-2 pr-4">Bereits abgerufen</td>
              <td className="py-2 pr-4 text-right text-soft-ink4">—</td>
              <td className="py-2 pr-4 text-right numeric">{formatEur(zuwendungAbgerufen)}</td>
              <td className="py-2 text-right text-soft-ink4">—</td>
            </tr>
            <tr>
              <td className="py-2 pr-4 font-medium">Verbleibend abrufbar</td>
              <td className="py-2 pr-4 text-right text-soft-ink4">—</td>
              <td
                className={`py-2 pr-4 text-right numeric font-semibold ${
                  status === "WARNUNG" ? "text-soft-crit" : "text-soft-ok"
                }`}
              >
                {formatEur(verbleibendAbrufbar)}
              </td>
              <td className="py-2 text-right text-soft-ink4">—</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Cross-Finanzierungs-Liste (nur wenn andere FundingMeasures überlappen) */}
      {andereMassnahmen.length > 0 && (
        <div className="mt-4 rounded-soft-xs border border-soft-line2 bg-soft-surfaceAlt p-3">
          <div className="mb-2 flex items-center gap-2 text-xs text-soft-ink3">
            <Info className="h-3.5 w-3.5 shrink-0" aria-hidden />
            <span>
              <strong>Cross-Finanzierung erkannt</strong> (heuristisch via überlappendem Bewilligungszeitraum + geteilten Kostenstellen).
              Falls die Zuordnung nicht zutrifft, KST-Zuordnungen im Maßnahmen-Editor anpassen.
            </span>
          </div>
          <ul className="space-y-2">
            {andereMassnahmen.map((m) => (
              <li
                key={m.id}
                className="rounded-soft-xs border border-soft-line2 bg-soft-surface p-2 text-sm"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="font-medium text-soft-ink">{m.name}</span>
                  <span className="text-xs text-soft-ink4 shrink-0">
                    {m.foerdergeber} · {m.finanzierungsart}
                  </span>
                </div>
                <div className="mt-1 grid grid-cols-2 gap-2 text-xs text-soft-ink3">
                  <span>
                    Höchstbetrag: <span className="numeric text-soft-ink2">{formatEur(m.zuwendung_hoechstbetrag)}</span>
                  </span>
                  <span>
                    Bereits abgerufen: <span className="numeric text-soft-ink2">{formatEur(m.zuwendung_abgerufen)}</span>
                  </span>
                  <span className="col-span-2">
                    Geteilte Kostenstellen:{" "}
                    <span className="text-soft-ink2 font-mono text-xs">
                      {m.geteilte_cost_center_codes.join(", ") || "—"}
                    </span>
                    {" · "}Zeitraum-Overlap: {m.bewilligungszeitraum_overlap_tage} Tage
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
