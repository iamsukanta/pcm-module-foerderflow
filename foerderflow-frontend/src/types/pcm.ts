// FoerderFlow — Module PCM (Personal Cost Management) frontend types.
// Wire shapes mirror the /api/protected/pcm/* responses (Decimals as strings).

export type SalaryLevel = {
  id: string;
  org_id: string;
  tariff_id: string;
  salary_group: string;
  level_no: number;
  monthly_amount: string;
  months_to_next_level: number | null;
};

export type SalaryTariff = {
  id: string;
  org_id: string;
  tariff_code: string;
  salary_group: string;
  level: number;
  monthly_amount: string;
  standard_hours: string;
  is_proposed: boolean;
  /** ISO date — start of the validity window. */
  valid_from: string;
  /** ISO date or null (open-ended). */
  valid_to: string | null;
  bav_rate_pct: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  levels?: SalaryLevel[];
};

export type SalaryTariffCreateInput = {
  tariff_code: string;
  salary_group: string;
  level: number;
  monthly_amount: number;
  standard_hours: number;
  valid_from: string;
  valid_to?: string | null;
  is_proposed?: boolean;
  bav_rate_pct?: number | null;
};

export type WochenstundenZuweisung = {
  id: string;
  org_id: string;
  employee_id: string;
  salary_assignment_id: string;
  cost_center_id: string;
  funding_measure_id: string | null;
  finanzplan_position_id: string | null;
  weekly_hours: string;
  effective_date: string;
  end_date: string | null;
  note: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type PayrollDetailLine = {
  id: string;
  monthly_payroll_id: string;
  component: string;
  description: string;
  amount: string;
  brutto_type: string;
  source_record_id: string | null;
};

export type RunMonatResult = {
  monat: string;
  fiscal_year_id: string;
  run_count: number;
  skipped_count: number;
  run: { employee_id: string; payroll_id: string }[];
  skipped: { employee_id: string; code: string; message: string }[];
};

/** Minimal employee shape needed by the PCM screens. */
export type PcmEmployeeContract = {
  id: string;
  assigned_hours: string;
  gueltig_ab: string;
  gueltig_bis: string | null;
};

export type PcmEmployee = {
  id: string;
  employee_code: string;
  vorname: string;
  nachname: string;
  ist_aktiv: boolean;
  contracts: PcmEmployeeContract[];
};

// ── Tariff Registry (D.1–D.6, Import, Progressions) ──────────────────────────

/** D.1 aggregated card — one per distinct tariff_code. */
export type TariffCodeSummary = {
  tariff_code: string;
  grade_count: number;
  row_count: number;
  proposed_count: number;
  employee_count: number;
  has_current: boolean;
  has_proposed: boolean;
  has_gap: boolean;
  current_valid_from: string | null;
  current_valid_to: string | null;
  standard_hours: string | null;
  bav_rate_pct: string | null;
};

/** D.3 inline overlap check result. */
export type OverlapCheck = { overlap: boolean; conflict: SalaryTariff | null };

/** One parsed/previewed import row. */
export type TariffImportRow = {
  salary_group: string;
  level: number;
  monthly_amount: number;
  status?: "valid" | "warning" | "error";
  conflict?: {
    id: string;
    valid_from: string;
    valid_to: string | null;
    monthly_amount: string;
  } | null;
};

/** Import preview response (no write yet). */
export type TariffImportPreview = {
  import_id: string;
  tariff_code: string;
  row_count: number;
  valid_rows: number;
  warning_rows: number;
  error_rows: number;
  preview: TariffImportRow[];
  conflicts: TariffImportRow[];
};

/** P-T upcoming progression row. */
export type ProgressionRow = {
  employee_id: string;
  employee_name: string;
  tariff_code: string;
  salary_group: string;
  current_level: number;
  next_level: number;
  months_in_tier: number;
  months_required: number;
  progression_date: string;
  source: "MANUAL" | "AUTO";
  days_until: number;
  current_amount: string;
  next_amount: string;
  delta_monthly: string;
  in_forecast: boolean;
};

// ── Leave & Absence (Area F) ─────────────────────────────────────────────────

export type LeaveTypeValue =
  | "ELTERNZEIT"
  | "MUTTERSCHUTZ"
  | "LANGZEITERKRANKUNG"
  | "OTHER";

export type LeavePeriod = {
  id: string;
  employee_id: string;
  employee_name: string | null;
  leave_type: LeaveTypeValue;
  start_date: string;
  expected_end_date: string | null;
  actual_end_date: string | null;
  replacement_employee_id: string | null;
  replacement_name: string | null;
  funder_notification_required: boolean;
  funder_notification_sent_at: string | null;
  note: string | null;
  status: "ACTIVE" | "ENDED";
  created_at?: string | null;
};

export type PlaceholderEmployee = {
  id: string;
  employee_code: string;
  name: string;
  leave_period_id: string | null;
  status: "ACTIVE" | "CLOSED";
};

// ── Bonuses & Adjustments (Areas G & H) ──────────────────────────────────────

export type BonusTypeValue = "FIXED" | "PERCENT" | "REFERENCE_MONTH";
export type ProrationRuleValue = "FULL" | "HOURS_PRORATED";
export type BonusApplicableToValue = "ALL" | "PROJECT_ONLY" | "OVERHEAD_ONLY";
export type BruttoTypeValue = "EMPLOYER" | "EMPLOYEE" | "NEITHER";
export type AdjustmentTypeValue = "ADDITION" | "DEDUCTION";

export type BonusTemplate = {
  id: string;
  name: string;
  tariff_code: string | null;
  salary_group_min: string | null;
  salary_group_max: string | null;
  applicable_to: BonusApplicableToValue;
  type: BonusTypeValue;
  amount: string;
  brutto_type: BruttoTypeValue;
  proration_rule: ProrationRuleValue;
  reference_month: number | null;
  payment_month: number | null;
  prorate_by_employment_period: boolean;
  period_from: string;
  period_to: string | null;
  matched_count?: number;
};

export type BonusPayment = {
  id: string;
  employee_id: string;
  type: BonusTypeValue;
  amount: string;
  brutto_type: BruttoTypeValue;
  proration_rule: ProrationRuleValue;
  reference_month: number | null;
  payment_month: number | null;
  prorate_by_employment_period: boolean;
  period_from: string;
  period_to: string | null;
  description: string | null;
  source_template_id: string | null;
};

export type SalaryAdjustment = {
  id: string;
  employee_id: string;
  type: AdjustmentTypeValue;
  amount: string;
  brutto_type: BruttoTypeValue;
  proration_rule: ProrationRuleValue;
  period_from: string;
  period_to: string | null;
  description: string | null;
};

export type EligibilityPreview = {
  matched: number;
  total: number;
  rows: {
    employee_id: string;
    employee_name: string;
    tariff_code: string | null;
    salary_group: string | null;
    matched: boolean;
    reason: string | null;
  }[];
};

// ── Audit Trail (Area O) ─────────────────────────────────────────────────────

export type AuditActionTypeValue =
  | "UPDATE"
  | "DELETE"
  | "AUTO_PROMOTION"
  | "LEAVE_START"
  | "LEAVE_END";

export type AuditLogEntry = {
  id: string;
  employee_id: string;
  employee_name: string | null;
  salary_assignment_id: string | null;
  leave_period_id: string | null;
  action_type: AuditActionTypeValue;
  changed_by: string | null;
  changed_at: string | null;
  summary: string;
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
};

/** Result of POST /employees/promotions/run. */
export type PromotionRunResult = {
  promoted_count: number;
  skipped_count: number;
  as_of: string;
  promoted: {
    employee_id: string;
    employee_name: string;
    salary_group: string;
    from_level: number;
    to_level: number;
    promotion_date: string;
    new_amount: string;
  }[];
  skipped: { employee_id: string; employee_name: string; code: string; message: string }[];
};

// ── Stellenplan matrix (Area E.1) ────────────────────────────────────────────

export type StellenplanRow = {
  employee_id: string;
  employee_name: string;
  allocation_method: "ACTUAL_HOURS" | "PLAN_PERCENTAGE";
  unit: "h" | "%";
  capacity: number;
  total_allocated: number;
  status: "OK" | "UNDER" | "OVER";
  cells: Record<string, number>;
};

export type StellenplanMatrix = {
  as_of: string;
  cost_centers: { id: string; code: string; name: string; typ: string }[];
  rows: StellenplanRow[];
};

// ── Payroll period lifecycle (Area I) ────────────────────────────────────────

export type PayrollPeriodStatusValue = "NOT_STARTED" | "CALCULATED" | "LOCKED";

export type PayrollPeriodRow = {
  monat: string;
  label: string;
  status: PayrollPeriodStatusValue;
  employee_count: number;
  total_ag_brutto: string | null;
  error_count: number;
  on_leave_count: number;
  last_run_at: string | null;
  locked_at: string | null;
};

export type PayrollPeriodsOverview = {
  fiscal_year_id: string;
  jahr: number;
  periods: PayrollPeriodRow[];
};

export type PayrollResultRow = {
  payroll_id: string;
  employee_id: string;
  employee_name: string;
  status: string;
  actual_salary: string;
  an_brutto: string;
  ag_brutto: string;
  bav_amount: string;
  fringe_benefits_amount: string;
  allocation_count: number;
  quelle: string;
};

export type PayrollPeriodResults = {
  monat: string;
  label: string;
  locked: boolean;
  summary: {
    employee_count: number;
    total_ag_brutto: string | null;
    total_an_brutto: string | null;
    total_bav: string | null;
    by_status: Record<string, number>;
  };
  rows: PayrollResultRow[];
};

// ── Cost Forecast (Area K) ───────────────────────────────────────────────────

export type ForecastDashboard = {
  fiscal_year_id: string;
  last_run_at: string | null;
  employee_count: number;
  grand_total: string | null;
  by_month: { monat: string; label: string; total: string }[];
  warnings: Record<string, number>;
  has_forecast: boolean;
};

export type ForecastMatrix = {
  months: { monat: string; label: string }[];
  rows: {
    employee_id: string;
    employee_name: string;
    cells: Record<string, string>;
    row_total: string;
    warnings: number;
  }[];
  column_totals: Record<string, string>;
};

export type ForecastWarnings = {
  total: number;
  groups: {
    warning: string;
    count: number;
    rows: { employee_id: string; employee_name: string; monat: string; label: string; total_forecast: string }[];
  }[];
};

export type ForecastDetail = {
  employee_id: string;
  employee_name: string;
  monat: string;
  label: string;
  forecast_level: number | null;
  forecast_salary: string;
  standard_hours: string;
  forecast_hours: string;
  prorated_salary: string;
  an_brutto: string;
  ag_brutto: string;
  bav_amount: string;
  fringe_amount: string;
  total_forecast: string;
  warning: string | null;
  components: { component: string; description: string; amount: string; brutto_type: string }[];
};

export type ForecastRunResult = {
  row_count: number;
  employee_count: number;
  month_count: number;
  warnings: Record<string, number>;
};

// ── Scenario Planner (Area L) ────────────────────────────────────────────────

export type ScenarioHire = {
  name?: string;
  tariff_code?: string;
  salary_group?: string;
  level?: number;
  weekly_hours?: number;
  monthly_amount?: number;
  start_month?: string;
};

export type ScenarioParams = {
  hour_overrides?: { employee_id: string; weekly_hours: number }[];
  level_overrides?: { employee_id: string; level: number }[];
  growth_rate_pct?: number;
  hires?: ScenarioHire[];
};

export type Scenario = {
  id: string;
  fiscal_year_id: string;
  name: string;
  status: "DRAFT" | "COMPUTED" | "PROMOTED";
  params: ScenarioParams;
  baseline_total: string | null;
  scenario_total: string | null;
  delta_total: string | null;
  computed_at: string | null;
};

export type ScenarioResults = {
  scenario: Scenario;
  by_month: { monat: string; label: string; baseline: string; scenario: string; delta: string }[];
  by_employee: { employee_id: string | null; label: string; baseline: string; scenario: string; delta: string }[];
};

// ── Allocation views (Area N) ────────────────────────────────────────────────

export type AllocationOverview = {
  monat: string;
  label: string;
  grand_total: string | null;
  groups: {
    funding_measure_id: string | null;
    funding_measure_name: string;
    total: string | null;
    rows: {
      employee_name: string;
      cost_center: string | null;
      finanzplan_position: string | null;
      betrag_anteil: string | null;
      prozent: string | null;
      payroll_status: string;
    }[];
  }[];
};

export type AllocationPerGrant = {
  funding_measure_id: string;
  funding_measure_name: string | null;
  months: { monat: string; label: string }[];
  rows: { employee_id: string; employee_name: string; cells: Record<string, string>; row_total: string }[];
  column_totals: Record<string, string>;
  grand_total: string | null;
};

// ── VWN report (Area M) ──────────────────────────────────────────────────────

export type VwnConfig = {
  funding_measure_id: string;
  visible_components: string[];
  bav_required: boolean;
  aggregate_label: string;
  hide_zero: boolean;
};

export type VwnPreview = {
  funding_measure_id: string;
  funding_measure_name: string;
  from_month: string;
  to_month: string;
  components: string[];
  aggregate_label: string;
  has_aggregate: boolean;
  rows: { employee_id: string; employee_name: string; cells: Record<string, string>; aggregate: string; total: string }[];
  component_totals: Record<string, string>;
  aggregate_total: string;
  grand_total: string | null;
};

export type FundingMeasureRef = { id: string; name: string };

// ── External payroll import (Area J) ─────────────────────────────────────────

export type ImportSourceTypeValue = "CSV_QUARTERLY" | "DATEV_EXTF" | "PERSONIO" | "DIAMANT_BAB";

export type PayrollImportBatchRow = {
  id: string;
  source_type: ImportSourceTypeValue;
  period_from: string;
  period_to: string;
  note: string | null;
  status: string;
  row_count: number;
  matched_count: number;
  total_gross: string | null;
  processed_at: string | null;
};

export type PayrollImportPreviewRow = {
  external_id: string | null;
  name: string | null;
  matched_employee_id: string | null;
  matched_name: string | null;
  gross: number;
  an_gross: number | null;
  distribution: { monat: string; amount: number }[];
};

export type PayrollImportPreview = {
  source_type: ImportSourceTypeValue;
  period_from: string;
  period_to: string;
  row_count: number;
  matched_count: number;
  unmatched_count: number;
  total_gross: number;
  rows: PayrollImportPreviewRow[];
};

// ── Fristen integration (Area P) ─────────────────────────────────────────────

export type LeaveTask = {
  type: "LEAVE_NOTIFICATION" | "RETURN_CHECK";
  leave_period_id: string;
  employee_name: string;
  title: string;
  due_date: string;
};

export type LeaveTasks = { total: number; tasks: LeaveTask[] };

// ── PCM Settings (Area A) ────────────────────────────────────────────────────

export type PcmSettingsOverview = {
  checklist: {
    tariffs_entered: boolean;
    levels_entered: boolean;
    bav_configured: boolean;
    has_employees: boolean;
    fiscal_year_active: boolean;
  };
  bav_rate_pct: string | null;
  active_fiscal_year: { jahr: number; status: string } | null;
};

export type PcmBavConfig = {
  bav_rate_pct: string | null;
  tariff_overrides: { tariff_code: string; bav_rate_pct: string | null }[];
};

export type PcmExternalId = {
  id: string;
  employee_code: string;
  name: string;
  employee_external_id: string | null;
};

export type PcmApiErrorBody = { error: string; code: string };

/** Flattened active cost center (parent + children) for select inputs. */
export type FlatCostCenter = { id: string; code: string; name: string };
