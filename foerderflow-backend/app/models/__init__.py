"""models — SQLAlchemy ORM entities (1:1 with the 46 Prisma models) + 24 enums.

Importing this package registers every table on `Base.metadata`, which Alembic's
env.py relies on for autogeneration.
"""

from app.models import enums  # noqa: F401
from app.models.allocation import (
    AllocationKey,
    AllocationKeyPosition,
    UmlageSourceScope,
    UmlageSourceScopeCostCenter,
)
from app.models.audit import AuditLog
from app.models.auth import (
    Account,
    OrganizationMembership,
    OrgInvite,
    Session,
    User,
    VerificationToken,
)
from app.models.booking_rule import (
    BookingRule,
    BookingRuleApplication,
    BookingRuleSplit,
)
from app.models.finanzplan import (
    FinanzplanPosition,
    FinanzplanPositionKostenbereich,
    HaushaltsPlanPosten,
    VerwNachweis,
)
from app.models.funding import (
    BescheidDokument,
    FundingMeasure,
    FundingMeasureCostCenter,
    FundingRule,
    NachweisTemplate,
)
from app.models.master import (
    CostCenter,
    FiscalYear,
    Funder,
    FunderNachweisFrist,
    Kostenbereich,
)
from app.models.mittelabruf import Mittelabruf
from app.models.organization import Organization
from app.models.payroll import (
    Employee,
    EmployeeContract,
    EmployerGrossFactor,
    MonthlyPayroll,
    PayrollAllocation,
    PayrollComponent,
    SalaryComponent,
    TarifTabelle,
)
from app.models.pcm_audit import LogEmployeeSalaryAssignment
from app.models.pcm_bonus import BonusPayment, BonusTemplate, SalaryAdjustment
from app.models.pcm_forecast import PersonalCostForecast
from app.models.pcm_import import PayrollImportBatch
from app.models.pcm_leave import EmployeeLeavePeriod
from app.models.pcm_period import PayrollPeriod
from app.models.pcm_scenario import ForecastScenario, ForecastScenarioRow
from app.models.pcm_vwn import VwnPersonnelConfig
from app.models.pcm_payroll import PayrollDetailLine
from app.models.pcm_personnel import WochenstundenZuweisung
from app.models.pcm_tariff import SalaryLevel, SalaryTariff
from app.models.transaction import (
    BankAccount,
    CsvImportProfile,
    FundAllocation,
    ImportBatch,
    OpeningBalance,
    Transaction,
    TransactionBeleg,
    TransactionSplit,
)

__all__ = [
    "Organization",
    "User",
    "Account",
    "Session",
    "VerificationToken",
    "OrganizationMembership",
    "OrgInvite",
    "CostCenter",
    "Funder",
    "FunderNachweisFrist",
    "FiscalYear",
    "Kostenbereich",
    "FundingMeasure",
    "BescheidDokument",
    "FundingRule",
    "FundingMeasureCostCenter",
    "NachweisTemplate",
    "AllocationKey",
    "AllocationKeyPosition",
    "UmlageSourceScope",
    "UmlageSourceScopeCostCenter",
    "BankAccount",
    "OpeningBalance",
    "CsvImportProfile",
    "ImportBatch",
    "Transaction",
    "TransactionSplit",
    "FundAllocation",
    "TransactionBeleg",
    "BookingRule",
    "BookingRuleSplit",
    "BookingRuleApplication",
    "Mittelabruf",
    "Employee",
    "EmployeeContract",
    "SalaryComponent",
    "EmployerGrossFactor",
    "TarifTabelle",
    "MonthlyPayroll",
    "PayrollComponent",
    "PayrollAllocation",
    "SalaryTariff",
    "SalaryLevel",
    "WochenstundenZuweisung",
    "PayrollDetailLine",
    "EmployeeLeavePeriod",
    "BonusTemplate",
    "BonusPayment",
    "SalaryAdjustment",
    "LogEmployeeSalaryAssignment",
    "PayrollPeriod",
    "PersonalCostForecast",
    "ForecastScenario",
    "ForecastScenarioRow",
    "VwnPersonnelConfig",
    "PayrollImportBatch",
    "FinanzplanPosition",
    "FinanzplanPositionKostenbereich",
    "HaushaltsPlanPosten",
    "VerwNachweis",
    "AuditLog",
]
