// Client-safe types for the Fehlbedarf compliance status. The computation runs in
// the backend (GET /foerdermassnahmen/{id}/fehlbedarf-status); the frontend only
// needs the result shape consumed by ComplianceBanner + CrossFinanzierungWidget.

export type FehlbedarfStatus = "OK" | "HINWEIS" | "WARNUNG";

export type OverlappingFundingMeasure = {
  id: string;
  name: string;
  foerdergeber: string;
  finanzierungsart: string;
  zuwendung_hoechstbetrag: number;
  zuwendung_abgerufen: number;
  geteilte_cost_center_codes: string[];
  bewilligungszeitraum_overlap_tage: number;
};

export type FehlbedarfStatusResult = {
  status: FehlbedarfStatus;
  meldepflichtig: boolean;

  // Planwerte (aus Bescheid):
  gesamtausgaben_plan: number;
  eigenmittel_plan: number;
  drittmittel_plan: number;
  zuwendung_hoechstbetrag: number;

  // Istwerte:
  eigenmittel_ist: number;
  drittmittel_ist: number;
  zuwendung_abgerufen: number;

  // Berechnete Größen:
  fehlbedarf_zulaessig: number;
  verbleibend_abrufbar: number;

  // Deltas (für UI-Anzeige):
  delta_eigenmittel: number;
  delta_drittmittel: number;

  // Cross-Finanzierungs-Liste:
  andere_fundingmeasures_ueberlappend: OverlappingFundingMeasure[];

  nachricht?: string;
};
