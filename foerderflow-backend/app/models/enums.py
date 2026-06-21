"""Domain enums — 1:1 port of the 24 Prisma enums.

Member NAMES and VALUES are identical to the monolith so DB values, API payloads,
and report output remain byte-compatible. The `@@map` name (PostgreSQL enum type
name) is recorded alongside each enum for use by the SQLAlchemy column definition.
German domain terminology is preserved verbatim (per the no-rename requirement).
"""

from enum import Enum


class _StrEnum(str, Enum):
    """str-backed enum: serializes to its value, compares to plain strings."""

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


class Rechtsform(_StrEnum):
    __pg_name__ = "rechtsform"
    EV = "EV"
    GGMBH = "GGMBH"
    STIFTUNG = "STIFTUNG"
    ANDERE = "ANDERE"


class OrgRole(_StrEnum):
    __pg_name__ = "org_role"
    ADMIN = "ADMIN"
    FINANCE = "FINANCE"
    READONLY = "READONLY"


class CostCenterTyp(_StrEnum):
    __pg_name__ = "cost_center_typ"
    PROJECT = "PROJECT"
    OVERHEAD = "OVERHEAD"


class FunderTyp(_StrEnum):
    __pg_name__ = "funder_typ"
    STIFTUNG = "STIFTUNG"
    KOMMUNE = "KOMMUNE"
    MINISTERIUM = "MINISTERIUM"
    EU = "EU"
    ANDERE = "ANDERE"
    KIRCHE = "KIRCHE"
    PRIVAT = "PRIVAT"


class FinanzierungsartTyp(_StrEnum):
    __pg_name__ = "finanzierungsart_typ"
    ANTEIL = "ANTEIL"
    FEHLBEDARF = "FEHLBEDARF"
    FESTBETRAG = "FESTBETRAG"


class EigenanteilTyp(_StrEnum):
    __pg_name__ = "eigenanteil_typ"
    KOFINANZIERUNG = "KOFINANZIERUNG"
    NICHT_FOERDERFAHIGER_OVERHEAD = "NICHT_FOERDERFAHIGER_OVERHEAD"


class PauschaleTyp(_StrEnum):
    __pg_name__ = "pauschale_typ"
    FIXER_BETRAG = "FIXER_BETRAG"
    PROZENT_GESAMT = "PROZENT_GESAMT"
    PROZENT_PERSONAL = "PROZENT_PERSONAL"
    UMLAGE_KOSTENSTELLEN = "UMLAGE_KOSTENSTELLEN"


class VerwendungsnachweisTyp(_StrEnum):
    __pg_name__ = "verwendungsnachweis_typ"
    ZWISCHENNACHWEIS = "ZWISCHENNACHWEIS"
    VERWENDUNGSNACHWEIS = "VERWENDUNGSNACHWEIS"
    SACHBERICHT_ONLY = "SACHBERICHT_ONLY"


class FristBezug(_StrEnum):
    __pg_name__ = "frist_bezug"
    HHJ_ENDE = "HHJ_ENDE"
    DURCHFUEHRUNG_ENDE = "DURCHFUEHRUNG_ENDE"
    BEWILLIGUNG_ENDE = "BEWILLIGUNG_ENDE"


class VerwendungsnachweisStatus(_StrEnum):
    __pg_name__ = "verwendungsnachweis_status"
    OFFEN = "OFFEN"
    IN_BEARBEITUNG = "IN_BEARBEITUNG"
    EINGEREICHT = "EINGEREICHT"
    ANERKANNT = "ANERKANNT"
    ABGELEHNT = "ABGELEHNT"


class MittelabrufVerfahren(_StrEnum):
    __pg_name__ = "mittelabruf_verfahren"
    ANFORDERUNG = "ANFORDERUNG"
    ABRUF = "ABRUF"
    ABSCHLAG = "ABSCHLAG"


class FundingMeasureStatus(_StrEnum):
    __pg_name__ = "funding_measure_status"
    AKTIV = "AKTIV"
    ABGESCHLOSSEN = "ABGESCHLOSSEN"
    WIDERRUFEN = "WIDERRUFEN"


class AllocationBasis(_StrEnum):
    __pg_name__ = "allocation_basis"
    MITARBEITERZAHL = "MITARBEITERZAHL"
    QUADRATMETER = "QUADRATMETER"
    BUDGET_ANTEIL = "BUDGET_ANTEIL"
    MANUELL = "MANUELL"


class FiscalYearStatus(_StrEnum):
    __pg_name__ = "fiscal_year_status"
    OFFEN = "OFFEN"
    GESCHLOSSEN = "GESCHLOSSEN"


class FundingRuleTyp(_StrEnum):
    __pg_name__ = "funding_rule_typ"
    KOSTENKATEGORIE_ERLAUBT = "KOSTENKATEGORIE_ERLAUBT"
    KOSTENKATEGORIE_VERBOTEN = "KOSTENKATEGORIE_VERBOTEN"
    BELEGPFLICHT_SPEZIAL = "BELEGPFLICHT_SPEZIAL"
    EIGENANTEIL_MIN = "EIGENANTEIL_MIN"
    VERWENDUNGSFRIST_TAGE = "VERWENDUNGSFRIST_TAGE"
    ZWISCHENNACHWEIS_PFLICHT = "ZWISCHENNACHWEIS_PFLICHT"
    PERSONALKOSTEN_HOECHSTSATZ = "PERSONALKOSTEN_HOECHSTSATZ"


class BescheidQuelle(_StrEnum):
    __pg_name__ = "bescheid_quelle"
    OCR_IMPORT = "OCR_IMPORT"
    MANUAL_UPLOAD = "MANUAL_UPLOAD"


class TransactionTyp(_StrEnum):
    __pg_name__ = "transaction_typ"
    AUSGABE = "AUSGABE"
    EINNAHME = "EINNAHME"
    INTERNE_UMBUCHUNG = "INTERNE_UMBUCHUNG"


class TransactionStatus(_StrEnum):
    __pg_name__ = "transaction_status"
    IMPORTIERT = "IMPORTIERT"
    KATEGORISIERT = "KATEGORISIERT"
    ZUGEORDNET = "ZUGEORDNET"
    ABGESCHLOSSEN = "ABGESCHLOSSEN"


class ImportFormat(_StrEnum):
    __pg_name__ = "import_format"
    GENERIC_CSV = "GENERIC_CSV"
    FINOM_CSV = "FINOM_CSV"
    SPARKASSE_CSV = "SPARKASSE_CSV"
    CAMT_053 = "CAMT_053"
    DATEV_CSV = "DATEV_CSV"
    MANUELL = "MANUELL"


class AccountTyp(_StrEnum):
    __pg_name__ = "account_typ"
    BANK = "BANK"
    KASSE = "KASSE"
    ONLINE_WALLET = "ONLINE_WALLET"


class MittelabrufStatus(_StrEnum):
    __pg_name__ = "mittelabruf_status"
    ABGERUFEN = "ABGERUFEN"
    VERWENDET = "VERWENDET"
    ABGELAUFEN = "ABGELAUFEN"
    ZURUECKGEZAHLT = "ZURUECKGEZAHLT"


class Vertragsart(_StrEnum):
    __pg_name__ = "vertragsart"
    FESTANSTELLUNG = "FESTANSTELLUNG"
    MINIJOB = "MINIJOB"
    WERKVERTRAG = "WERKVERTRAG"
    EHRENAMT = "EHRENAMT"


class Tarifwerk(_StrEnum):
    __pg_name__ = "tarifwerk"
    TVOEDD = "TVOEDD"
    TVOEL = "TVOEL"
    AVR_CARITAS = "AVR_CARITAS"
    AVR_DD = "AVR_DD"
    INDIVIDUELL = "INDIVIDUELL"


class SalaryComponentTyp(_StrEnum):
    __pg_name__ = "salary_component_typ"
    FESTBEZUG = "FESTBEZUG"
    VWL_AG_ZUSCHUSS = "VWL_AG_ZUSCHUSS"
    JOBTICKET_SACHBEZUG = "JOBTICKET_SACHBEZUG"
    SALARY_ADJUSTMENT = "SALARY_ADJUSTMENT"
    SONSTIGES = "SONSTIGES"


# ─────────────────────────────────────────────────────────────────────
# Module PCM (Personal Cost Management) — Phase 1 additions.
# New native enum types; existing enums above are left untouched.
# ─────────────────────────────────────────────────────────────────────


class EmployeeType(_StrEnum):
    """REGULAR staff vs. PLACEHOLDER (virtual replacement during leave)."""

    __pg_name__ = "employee_type"
    REGULAR = "REGULAR"
    PLACEHOLDER = "PLACEHOLDER"


class AllocationMethod(_StrEnum):
    """How a salary assignment attributes cost to grants.

    ACTUAL_HOURS is the §4 ANBest-P Dreisatz default; PLAN_PERCENTAGE is only
    permitted when the linked funding measure has allows_plan_based_allocation.
    """

    __pg_name__ = "allocation_method"
    ACTUAL_HOURS = "ACTUAL_HOURS"
    PLAN_PERCENTAGE = "PLAN_PERCENTAGE"


class PayrollStatus(_StrEnum):
    """Lifecycle of a MonthlyPayroll row. ON_LEAVE = absent, gross 0."""

    __pg_name__ = "payroll_status"
    CALCULATED = "CALCULATED"
    ERROR = "ERROR"
    ON_LEAVE = "ON_LEAVE"


class BruttoType(_StrEnum):
    """AN/AG-Brutto classification for payroll components.

    EMPLOYER = AG-cost only · EMPLOYEE = taxable AN-wage · NEITHER = fringe
    benefit (e.g. Jobticket), in neither brutto.
    """

    __pg_name__ = "brutto_type"
    EMPLOYER = "EMPLOYER"
    EMPLOYEE = "EMPLOYEE"
    NEITHER = "NEITHER"


class PayrollDetailComponent(_StrEnum):
    """Itemized payroll line component for VWN breakdown."""

    __pg_name__ = "payroll_detail_component"
    BASE = "BASE"
    ZULAGE = "ZULAGE"
    BONUS = "BONUS"
    JSZ = "JSZ"
    WEIHNACHTSGELD = "WEIHNACHTSGELD"
    BAV = "BAV"
    ADJUST_ADD = "ADJUST_ADD"
    ADJUST_DED = "ADJUST_DED"
    FRINGE = "FRINGE"


class AllocationOrigin(_StrEnum):
    """Provenance scope for payroll_allocations rows.

    PCM rows are deleted/rewritten on each payroll re-run; MANUELL rows
    (pre-PCM manual attributions) are never touched.
    """

    __pg_name__ = "allocation_origin"
    MANUELL = "MANUELL"
    PCM = "PCM"


class LeaveType(_StrEnum):
    """Type of employee absence (Abwesenheit) — drives payroll suppression and
    funder-notification tasks."""

    __pg_name__ = "leave_type"
    ELTERNZEIT = "ELTERNZEIT"
    MUTTERSCHUTZ = "MUTTERSCHUTZ"
    LANGZEITERKRANKUNG = "LANGZEITERKRANKUNG"
    OTHER = "OTHER"


class BonusType(_StrEnum):
    """How a bonus amount is interpreted. FIXED = € value; PERCENT = % of actual
    salary; REFERENCE_MONTH = % of a reference month's salary, paid in a payment
    month (Jahressonderzahlung pattern)."""

    __pg_name__ = "bonus_type"
    FIXED = "FIXED"
    PERCENT = "PERCENT"
    REFERENCE_MONTH = "REFERENCE_MONTH"


class ProrationRule(_StrEnum):
    """FULL = amount as-is; HOURS_PRORATED = amount × project_hours / standard
    hours (e.g. Münchenzulage scales with project FTE)."""

    __pg_name__ = "proration_rule"
    FULL = "FULL"
    HOURS_PRORATED = "HOURS_PRORATED"


class BonusApplicableTo(_StrEnum):
    """Which employees a bonus template applies to, by cost-centre type."""

    __pg_name__ = "bonus_applicable_to"
    ALL = "ALL"
    PROJECT_ONLY = "PROJECT_ONLY"
    OVERHEAD_ONLY = "OVERHEAD_ONLY"


class AdjustmentType(_StrEnum):
    """Per-employee salary adjustment direction."""

    __pg_name__ = "adjustment_type"
    ADDITION = "ADDITION"
    DEDUCTION = "DEDUCTION"


class AuditActionType(_StrEnum):
    """Action recorded in the employee salary-assignment audit log (Area O)."""

    __pg_name__ = "audit_action_type"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    AUTO_PROMOTION = "AUTO_PROMOTION"
    LEAVE_START = "LEAVE_START"
    LEAVE_END = "LEAVE_END"


class PayrollPeriodStatus(_StrEnum):
    """Lock state of a monthly payroll period (Area I). OPEN allows run/re-run;
    LOCKED freezes the period as the legal payroll record."""

    __pg_name__ = "payroll_period_status"
    OPEN = "OPEN"
    LOCKED = "LOCKED"


class ScenarioStatus(_StrEnum):
    """Lifecycle of a forecast scenario (Area L)."""

    __pg_name__ = "scenario_status"
    DRAFT = "DRAFT"
    COMPUTED = "COMPUTED"
    PROMOTED = "PROMOTED"


class ImportSourceType(_StrEnum):
    """External payroll import source (Area J)."""

    __pg_name__ = "import_source_type"
    CSV_QUARTERLY = "CSV_QUARTERLY"
    DATEV_EXTF = "DATEV_EXTF"
    PERSONIO = "PERSONIO"
    DIAMANT_BAB = "DIAMANT_BAB"


class PayrollImportStatus(_StrEnum):
    """Lifecycle of a payroll import batch (Area J)."""

    __pg_name__ = "payroll_import_status"
    PENDING = "PENDING"
    MAPPED = "MAPPED"
    CONFIRMED = "CONFIRMED"
    PROCESSED = "PROCESSED"
    ERROR = "ERROR"
