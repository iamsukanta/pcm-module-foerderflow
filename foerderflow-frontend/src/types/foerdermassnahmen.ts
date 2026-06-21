// ─────────────────────────────────────────────
// Fördermassnahmen — TypeScript Types
// ─────────────────────────────────────────────

export type FunderTyp = "STIFTUNG" | "KOMMUNE" | "MINISTERIUM" | "EU" | "ANDERE" | "KIRCHE" | "PRIVAT";
export type MittelabrufVerfahren = "ANFORDERUNG" | "ABRUF" | "ABSCHLAG";
export type FundingMeasureStatus = "AKTIV" | "ABGESCHLOSSEN" | "WIDERRUFEN";
export type FundingRuleTyp =
  | "KOSTENKATEGORIE_ERLAUBT"
  | "KOSTENKATEGORIE_VERBOTEN"
  | "BELEGPFLICHT_SPEZIAL"
  | "EIGENANTEIL_MIN"
  | "VERWENDUNGSFRIST_TAGE"
  | "ZWISCHENNACHWEIS_PFLICHT"
  | "PERSONALKOSTEN_HOECHSTSATZ";

// ─── Funder ───────────────────────────────────

export type FunderBase = {
  id: string;
  org_id: string;
  name: string;
  typ: FunderTyp;
  notizen: string | null;
  created_at: Date;
  updated_at: Date;
};

export type FunderWithMeasureCount = FunderBase & {
  _count: {
    funding_measures: number;
  };
};

export type FunderWithMeasures = FunderBase & {
  funding_measures: FundingMeasureBase[];
};

// ─── FundingRule ──────────────────────────────

export type FundingRuleBase = {
  id: string;
  org_id: string;
  funding_measure_id: string;
  typ: FundingRuleTyp;
  schluessel: string;
  wert: string | null;
  beschreibung: string | null;
  created_at: Date;
  updated_at: Date;
};

export type FundingRuleInput = {
  typ: FundingRuleTyp;
  schluessel: string;
  wert?: string | null;
  beschreibung?: string | null;
};

// ─── FundingMeasureCostCenter ─────────────────

export type FundingMeasureCostCenterBase = {
  id: string;
  org_id: string;
  funding_measure_id: string;
  cost_center_id: string;
  created_at: Date;
  cost_center?: {
    id: string;
    name: string;
    code: string;
    typ: string;
    ist_aktiv: boolean;
  };
};

// ─── FundingMeasure ───────────────────────────

export type FundingMeasureBase = {
  id: string;
  org_id: string;
  funder_id: string;
  name: string;
  budget_gesamt: string; // Decimal serialized as string
  foerderquote: string;
  /// Bewilligungszeitraum (vom Fördergeber bewilligter Rahmen)
  laufzeit_von: Date;
  laufzeit_bis: Date;
  /// Optionaler engerer Durchführungszeitraum. Null = identisch zur Bewilligung.
  durchfuehrungs_von: Date | null;
  durchfuehrungs_bis: Date | null;
  /// Antragsnummer beim Fördergeber (z.B. ISP/2025/P 081, 100738705)
  antragsnummer: string | null;
  verwaltungspauschale_erlaubt: boolean;
  verwaltungspauschale_prozent: string | null;
  budget_flexibilitaet_prozent: string;
  mwst_foerderfahig: boolean;
  mwst_satz_prozent: string; // Decimal serialized as string
  mittelabruf_verfahren: MittelabrufVerfahren;
  status: FundingMeasureStatus;
  created_at: Date;
  updated_at: Date;
};

export type FundingMeasureWithDetails = FundingMeasureBase & {
  funder: FunderBase;
  rules: FundingRuleBase[];
  cost_centers: FundingMeasureCostCenterBase[];
  _count: {
    rules: number;
    cost_centers: number;
  };
  // Computed fields
  is_expired: boolean;
  days_until_expiry: number | null;
};

export type FundingMeasureListItem = FundingMeasureBase & {
  funder: Pick<FunderBase, "id" | "name" | "typ">;
  is_expired: boolean;
  days_until_expiry: number | null;
  _count: {
    rules: number;
    cost_centers: number;
  };
};

// ─── Input Types ──────────────────────────────

export type CreateFunderInput = {
  name: string;
  typ: FunderTyp;
  notizen?: string | null;
};

export type UpdateFunderInput = {
  name?: string;
  typ?: FunderTyp;
  notizen?: string | null;
};

export type CreateFundingMeasureInput = {
  funder_id: string;
  name: string;
  budget_gesamt: number;
  foerderquote: number;
  laufzeit_von: string; // ISO date string (Bewilligungszeitraum von)
  laufzeit_bis: string; // ISO date string (Bewilligungszeitraum bis)
  /// Optionaler Durchführungszeitraum: beide oder keiner
  durchfuehrungs_von?: string | null;
  durchfuehrungs_bis?: string | null;
  antragsnummer?: string | null;
  status?: FundingMeasureStatus;
  verwaltungspauschale_erlaubt: boolean;
  verwaltungspauschale_prozent?: number | null;
  budget_flexibilitaet_prozent?: number;
  mwst_foerderfahig?: boolean;
  mwst_satz_prozent?: number;
  mittelabruf_verfahren: MittelabrufVerfahren;
  rules?: FundingRuleInput[];
  cost_center_ids?: string[];
};

export type UpdateFundingMeasureInput = {
  funder_id?: string;
  name?: string;
  budget_gesamt?: number;
  foerderquote?: number;
  laufzeit_von?: string;
  laufzeit_bis?: string;
  durchfuehrungs_von?: string | null;
  durchfuehrungs_bis?: string | null;
  antragsnummer?: string | null;
  status?: FundingMeasureStatus;
  verwaltungspauschale_erlaubt?: boolean;
  verwaltungspauschale_prozent?: number | null;
  budget_flexibilitaet_prozent?: number;
  mwst_foerderfahig?: boolean;
  mwst_satz_prozent?: number;
  mittelabruf_verfahren?: MittelabrufVerfahren;
};

// ─── API Response Shape ───────────────────────

export type ApiError = {
  error: string;
  code: string;
};

export type ApiSuccess<T> = {
  data: T;
  message?: string;
};
