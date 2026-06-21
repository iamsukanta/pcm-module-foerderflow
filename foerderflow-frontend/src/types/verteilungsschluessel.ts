// FoerderFlow — Verteilungsschlüssel-Typen
// Prüfregel: Summe aller pozent-Werte je allocation_key_id MUSS exakt 100.00 sein.

export type AllocationKeyBasis =
  | "MITARBEITERZAHL"
  | "QUADRATMETER"
  | "BUDGET_ANTEIL"
  | "MANUELL";

export const ALLOCATION_BASIS_LABELS: Record<AllocationKeyBasis, string> = {
  MITARBEITERZAHL: "Mitarbeiterzahl",
  QUADRATMETER: "Quadratmeter",
  BUDGET_ANTEIL: "Budgetanteil",
  MANUELL: "Manuell",
};

export const ALLOCATION_BASIS_DESCRIPTIONS: Record<AllocationKeyBasis, string> = {
  MITARBEITERZAHL: "Nach Anzahl Mitarbeiter je Kostenstelle",
  QUADRATMETER: "Nach genutzter Fläche in m²",
  BUDGET_ANTEIL: "Nach Budgetvolumen der Kostenstellen",
  MANUELL: "Freie Prozentangaben",
};

export type AllocationKeyPosition = {
  id: string;
  org_id: string;
  allocation_key_id: string;
  cost_center_id: string;
  /** Decimal als String */
  prozent: string;
  cost_center?: {
    id: string;
    name: string;
    code: string;
    typ: string;
  };
};

export type AllocationKeyWithPositions = {
  id: string;
  org_id: string;
  name: string;
  basis: AllocationKeyBasis;
  /** ISO-Date-String, z.B. "2026-01-01" */
  gueltig_von: string;
  /** ISO-Date-String oder null = unbegrenzt */
  gueltig_bis: string | null;
  ist_aktiv: boolean;
  positions: AllocationKeyPosition[];
  /** Berechnete Felder: von der API hinzugefügt */
  summe_prozent?: number;
  /** true wenn summe_prozent exakt 100 ergibt */
  is_valid?: boolean;
};

/** Für den Positionen-Editor — leichtgewichtig ohne IDs */
export type PositionDraft = {
  /** Client-seitige temp-ID (uuid oder laufende Nummer) */
  _key: string;
  cost_center_id: string;
  prozent: string;
};

/** Payload für POST /api/protected/verteilungsschluessel */
export type CreateAllocationKeyPayload = {
  name: string;
  basis: AllocationKeyBasis;
  gueltig_von: string;
  gueltig_bis: string | null;
  positions: Array<{ cost_center_id: string; prozent: string }>;
};

/** Payload für PATCH /api/protected/verteilungsschluessel/[id] */
export type PatchAllocationKeyPayload = {
  name?: string;
  gueltig_bis?: string | null;
};

/** Payload für POST /api/protected/verteilungsschluessel/[id]/neue-version */
export type NeueVersionPayload = {
  gueltig_von: string;
  positions: Array<{ cost_center_id: string; prozent: string }>;
};
