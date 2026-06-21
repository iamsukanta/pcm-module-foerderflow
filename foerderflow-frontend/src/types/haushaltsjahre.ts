// FoerderFlow — Haushaltsjahre (FiscalYear) Types

export type FiscalYearStatus = "OFFEN" | "GESCHLOSSEN";

export type FiscalYearWithMeta = {
  id: string;
  org_id: string;
  /** Kalenderjahr, z.B. 2025 */
  jahr: number;
  /** ISO date string, z.B. "2025-01-01" */
  beginn: string;
  /** ISO date string, z.B. "2025-12-31" */
  ende: string;
  status: FiscalYearStatus;
  /** ISO datetime string — wird bei Schließung gesetzt */
  geschlossen_am: string | null;
  /** User-ID — wird bei Schließung gesetzt */
  geschlossen_von: string | null;
  created_at: string;
  _count?: Record<string, number>;
};

export type FiscalYearCreateInput = {
  jahr: number;
  beginn: string;
  ende: string;
};

export type FiscalYearUpdateInput = {
  beginn?: string;
  ende?: string;
};

export type FiscalYearCloseInput = {
  confirmation: "SCHLIESSEN";
};

export type ApiError = {
  error: string;
  code: string;
};

export type ApiSuccess<T> = {
  data: T;
  message?: string;
  warning?: string;
};
