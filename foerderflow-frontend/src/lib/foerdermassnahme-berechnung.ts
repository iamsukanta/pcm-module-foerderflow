// Zentraler Berechnungs-Helper für Zuwendung + Förderquote je Finanzierungsart.
//
// Ohne diesen Helper würde überall im UI/API die Formel `gesamt × quote/100`
// genutzt — das stimmt nur für ANTEIL. Für FEHLBEDARF und FESTBETRAG sind die
// Eingaben / Ausgaben anders verteilt (siehe Switch unten).

export type FinanzierungsartTyp = "ANTEIL" | "FEHLBEDARF" | "FESTBETRAG";

export type ZuwendungsBerechnung = {
  /** Bewilligte Zuwendung in EUR (entweder Eingabe oder berechnet). */
  zuwendung: number;
  /** Förderquote in % — bei ANTEIL = Eingabe, bei FEHLBEDARF abgeleitet, bei FESTBETRAG = 0. */
  foerderquote: number;
};

export type BerechnungsInput = {
  finanzierungsart: FinanzierungsartTyp;
  /** Zuwendungsfähige Gesamtausgaben in EUR. Bei FESTBETRAG = Zuwendung selbst. */
  gesamtausgaben: number;
  /** Bei ANTEIL: Eingabe-Förderquote in % (0–100). Sonst ignoriert. */
  foerderquoteInput?: number;
  /** Bei FEHLBEDARF: Eigenmittel-Plansumme der Org in EUR (Pflicht). */
  eigenmittel?: number;
  /** Bei FEHLBEDARF: Drittmittel-Plansumme in EUR (default 0). */
  drittmittel?: number;
};

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

export function berechneZuwendung(input: BerechnungsInput): ZuwendungsBerechnung {
  switch (input.finanzierungsart) {
    case "ANTEIL": {
      const q = input.foerderquoteInput ?? 0;
      return {
        zuwendung: round2(input.gesamtausgaben * (q / 100)),
        foerderquote: q,
      };
    }
    case "FEHLBEDARF": {
      const eigen = input.eigenmittel ?? 0;
      const dritt = input.drittmittel ?? 0;
      const zuwendung = input.gesamtausgaben - eigen - dritt;
      const quote = input.gesamtausgaben > 0 ? (zuwendung / input.gesamtausgaben) * 100 : 0;
      return {
        zuwendung: round2(zuwendung),
        foerderquote: round2(quote),
      };
    }
    case "FESTBETRAG":
      return { zuwendung: round2(input.gesamtausgaben), foerderquote: 0 };
  }
}

export type ValidationResult = {
  valid: boolean;
  error?: string;
  warning?: string;
};

export function validiereFehlbedarf(input: {
  gesamtausgaben: number;
  eigenmittel: number;
  drittmittel: number;
  /** Optional: Höchstbetrag aus Bescheid für Warnungs-Check. */
  zuwendungHoechstbetrag?: number;
}): ValidationResult {
  if (input.eigenmittel < 0) {
    return { valid: false, error: "Eigenmittel können nicht negativ sein." };
  }
  if (input.drittmittel < 0) {
    return { valid: false, error: "Drittmittel können nicht negativ sein." };
  }

  const fehlbedarf = round2(input.gesamtausgaben - input.eigenmittel - input.drittmittel);
  if (fehlbedarf < 0) {
    return {
      valid: false,
      error:
        "Eigenmittel und Drittmittel übersteigen die Gesamtausgaben — bitte Eingaben prüfen.",
    };
  }

  if (
    input.zuwendungHoechstbetrag !== undefined &&
    fehlbedarf > round2(input.zuwendungHoechstbetrag)
  ) {
    return {
      valid: true,
      warning:
        `Berechneter Fehlbedarf (${fehlbedarf.toFixed(2)} €) überschreitet ` +
        `den bewilligten Höchstbetrag (${round2(input.zuwendungHoechstbetrag).toFixed(2)} €). ` +
        `Bitte Eigenmittel prüfen oder Höchstbetrag aus Bescheid korrigieren.`,
    };
  }

  return { valid: true };
}
