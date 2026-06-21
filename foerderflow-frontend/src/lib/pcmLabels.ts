// German labels for Module PCM bonus/adjustment enums (Areas G & H).

import type {
  AdjustmentTypeValue,
  BonusApplicableToValue,
  BonusTypeValue,
  BruttoTypeValue,
  ProrationRuleValue,
} from "@/types/pcm";

export const BONUS_TYPE_LABELS: Record<BonusTypeValue, string> = {
  FIXED: "Fixbetrag (€)",
  PERCENT: "Prozent (% vom Gehalt)",
  REFERENCE_MONTH: "Referenzmonat (JSZ)",
};

export const BRUTTO_TYPE_LABELS: Record<BruttoTypeValue, string> = {
  EMPLOYER: "AG-Brutto",
  EMPLOYEE: "AN-Brutto",
  NEITHER: "Sachbezug (kein Brutto)",
};

export const PRORATION_LABELS: Record<ProrationRuleValue, string> = {
  FULL: "Voll",
  HOURS_PRORATED: "Stundenanteilig",
};

export const APPLICABLE_TO_LABELS: Record<BonusApplicableToValue, string> = {
  ALL: "Alle",
  PROJECT_ONLY: "Nur Projekt",
  OVERHEAD_ONLY: "Nur Overhead",
};

export const ADJUSTMENT_TYPE_LABELS: Record<AdjustmentTypeValue, string> = {
  ADDITION: "Zuschlag",
  DEDUCTION: "Abzug",
};
