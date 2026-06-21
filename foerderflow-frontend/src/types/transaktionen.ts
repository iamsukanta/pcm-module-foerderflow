export type TransactionWithMeta = {
  id: string;
  org_id: string;
  fiscal_year_id: string;
  import_batch_id: string | null;
  datum: string;
  betrag: string;
  typ: "AUSGABE" | "EINNAHME" | "INTERNE_UMBUCHUNG";
  auftraggeber: string | null;
  verwendungszweck: string | null;
  externe_referenz: string | null;
  kostenart: string | null;
  notiz: string | null;
  status: "IMPORTIERT" | "KATEGORISIERT" | "ZUGEORDNET" | "ABGESCHLOSSEN";
  duplikat_hash: string | null;
  created_at: string;
  updated_at: string;
  _count?: {
    splits: number;
    belege: number;
  };
};

export type SaldoCheckRow = {
  bank_account_id: string;
  iban: string;
  opening: number | null;
  sum_betrag: number;
  expected_end: number | null;
  csv_last_saldo: number | null;
  diff: number | null;
  passed: boolean;
};

export type ImportBatchResult = {
  batch_id: string;
  profile_used?: string;
  anzahl_importiert: number;
  anzahl_duplikate: number;
  anzahl_fehler: number;
  anzahl_auto_matched?: number;
  bank_accounts_neu?: string[];
  errors: { line: number; message: string }[];
  saldo_check?: SaldoCheckRow[];
};

export type SplitInput = {
  cost_center_id: string;
  prozent: number;
};
