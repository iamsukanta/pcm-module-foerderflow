// Client-safe BescheidExtraktion type. The full OCR extraction prompt lives in
// the FastAPI backend (app/services/bescheid/extraction_prompt.py); the frontend
// only needs the result shape returned by POST /foerdermassnahmen/import-bescheid.

export type BescheidExtraktion = {
  // Basisfelder
  name: string | null;
  funder_name: string | null;
  foerderquote: number | null;
  finanzierungsart: "ANTEIL" | "FEHLBEDARF" | "FESTBETRAG" | null;
  budget_gesamt: number | null;
  /// bei FEHLBEDARF die Eigenmittel-Plansumme aus dem Finanzierungsplan-Anhang
  eigenmittel: number | null;
  /// bei FEHLBEDARF die Summe aller Drittmittel (Zuwendungen anderer + sonstige)
  drittmittel: number | null;
  /// bewilligte Zuwendung als Höchstbetrag laut Bescheidkopf
  zuwendungsbetrag: number | null;
  laufzeit_von: string | null; // "YYYY-MM-DD"
  laufzeit_bis: string | null; // "YYYY-MM-DD"
  // Konditionen
  mittelabruf_verfahren: "ANFORDERUNG" | "ABRUF" | "ABSCHLAG" | null;
  verwaltungspauschale_erlaubt: boolean | null;
  verwaltungspauschale_prozent: number | null;
  budget_flexibilitaet_prozent: number | null;
  overhead_limit_prozent: number | null;
  mwst_nicht_foerderfahig: boolean;
  // Kostenplan (aus Tabellen im Bescheid)
  finanzplan_positionen: Array<{
    positionscode: string;
    bezeichnung: string;
    betrag_bewilligt: number;
    ueberziehung_limit_pct: number | null;
    kostenbereich_code: string | null;
    ist_pauschale: boolean;
    pauschale_typ: "FIXER_BETRAG" | "PROZENT_GESAMT" | "PROZENT_PERSONAL" | null;
    pauschale_prozent: number | null;
  }>;
  // Förderregeln
  rules: Array<{
    typ:
      | "KOSTENKATEGORIE_ERLAUBT"
      | "KOSTENKATEGORIE_VERBOTEN"
      | "BELEGPFLICHT_SPEZIAL"
      | "EIGENANTEIL_MIN"
      | "VERWENDUNGSFRIST_TAGE"
      | "ZWISCHENNACHWEIS_PFLICHT"
      | "PERSONALKOSTEN_HOECHSTSATZ";
    schluessel: string;
    wert: string | null;
    beschreibung: string | null;
  }>;
  // Qualitätskontrolle
  confidence: "HIGH" | "MEDIUM" | "LOW";
  raw_hinweise: string[];
};
