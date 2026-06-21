"""FK-aware org-data reset — port of monolith `scripts/lib/reset-org-data.ts`.

Wipes all data of ONE organization in FK-safe order (leaves → roots), while
keeping (configurably):
  - the Organization record itself (no FK on the table),
  - OrganizationMembership (default: keep — the user stays logged in),
  - AuditLog (default: keep — compliance trail),
  - OrgInvite (default: delete).

Two narrower resets used by the seed CLIs are also provided:
  - reset_transactions(): only Transactions + Splits + FundAllocations +
    ImportBatches + BookingRuleApplications (master data untouched).
  - reset_rules(): only BookingRules (+ Splits/Applications via cascade).

All operations run inside the caller's session and are flushed but NOT committed
here — the caller owns the commit, so a reset + re-seed is one atomic unit.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.allocation import (
    AllocationKey,
    UmlageSourceScope,
)
from app.models.audit import AuditLog
from app.models.auth import OrganizationMembership, OrgInvite
from app.models.booking_rule import BookingRule, BookingRuleApplication
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
from app.models.payroll import (
    Employee,
    EmployeeContract,
    EmployerGrossFactor,
    MonthlyPayroll,
    PayrollAllocation,
    SalaryComponent,
)
from app.models.transaction import (
    BankAccount,
    FundAllocation,
    ImportBatch,
    OpeningBalance,
    Transaction,
    TransactionBeleg,
    TransactionSplit,
)


def _default_log(symbol: str, msg: str) -> None:
    print(f"  {symbol} {msg}")


@dataclass
class ResetOptions:
    keep_memberships: bool = True
    keep_audit_log: bool = True
    keep_invites: bool = False
    log: Callable[[str, str], None] = _default_log


@dataclass
class ResetSummary:
    counts: dict[str, int] = field(default_factory=dict)

    def total(self) -> int:
        return sum(self.counts.values())


def _delete(db: Session, stmt) -> int:
    """Execute a bulk DELETE and return affected rowcount."""
    return db.execute(stmt).rowcount or 0


def reset_org_data(
    db: Session, org_id: str, opts: ResetOptions | None = None
) -> ResetSummary:
    """Delete all data of `org_id` in FK-safe order. Does NOT commit."""
    opts = opts or ResetOptions()
    log = opts.log
    summary = ResetSummary()

    def record(key: str, count: int, symbol: str = "−", note: str = "") -> None:
        summary.counts[key] = count
        if count > 0:
            log(symbol, f"{key}: {count}{note}")

    # ── 1. Transaction subtree ──────────────────────────────────────────
    split_ids = select(TransactionSplit.id).where(TransactionSplit.org_id == org_id)
    record(
        "FundAllocations",
        _delete(
            db,
            delete(FundAllocation).where(
                FundAllocation.transaction_split_id.in_(split_ids)
            ),
        ),
    )
    record(
        "TransactionSplits",
        _delete(db, delete(TransactionSplit).where(TransactionSplit.org_id == org_id)),
    )
    record(
        "TransactionBelege",
        _delete(db, delete(TransactionBeleg).where(TransactionBeleg.org_id == org_id)),
    )
    record(
        "Transactions",
        _delete(db, delete(Transaction).where(Transaction.org_id == org_id)),
    )

    # ── 2. BookingRule subtree (splits + applications cascade in DB) ─────
    record(
        "BookingRuleApplications",
        _delete(
            db,
            delete(BookingRuleApplication).where(
                BookingRuleApplication.org_id == org_id
            ),
        ),
    )
    record(
        "BookingRules",
        _delete(db, delete(BookingRule).where(BookingRule.org_id == org_id)),
        note="  (Splits via Cascade)",
    )

    # ── 3. FundingMeasure subtree ───────────────────────────────────────
    record(
        "Mittelabrufe",
        _delete(db, delete(Mittelabruf).where(Mittelabruf.org_id == org_id)),
    )
    record(
        "Verwendungsnachweise",
        _delete(db, delete(VerwNachweis).where(VerwNachweis.org_id == org_id)),
    )
    record(
        "FunderNachweisFristen",
        _delete(
            db, delete(FunderNachweisFrist).where(FunderNachweisFrist.org_id == org_id)
        ),
    )

    measure_ids = select(FundingMeasure.id).where(FundingMeasure.org_id == org_id)
    record(
        "BescheidDokumente",
        _delete(
            db,
            delete(BescheidDokument).where(
                BescheidDokument.funding_measure_id.in_(measure_ids)
            ),
        ),
    )
    record(
        "FundingRules",
        _delete(
            db, delete(FundingRule).where(FundingRule.funding_measure_id.in_(measure_ids))
        ),
    )
    fp_ids = select(FinanzplanPosition.id).where(FinanzplanPosition.org_id == org_id)
    record(
        "FinanzplanPositionKostenbereiche",
        _delete(
            db,
            delete(FinanzplanPositionKostenbereich).where(
                FinanzplanPositionKostenbereich.finanzplan_position_id.in_(fp_ids)
            ),
        ),
    )
    record(
        "FinanzplanPositionen",
        _delete(
            db, delete(FinanzplanPosition).where(FinanzplanPosition.org_id == org_id)
        ),
    )
    record(
        "FundingMeasureCostCenters",
        _delete(
            db,
            delete(FundingMeasureCostCenter).where(
                FundingMeasureCostCenter.funding_measure_id.in_(measure_ids)
            ),
        ),
    )
    record(
        "FundingMeasures",
        _delete(db, delete(FundingMeasure).where(FundingMeasure.org_id == org_id)),
    )
    record("Funders", _delete(db, delete(Funder).where(Funder.org_id == org_id)))

    # ── 4. Haushaltsplan + Templates ────────────────────────────────────
    record(
        "HaushaltsPlanPosten",
        _delete(db, delete(HaushaltsPlanPosten).where(HaushaltsPlanPosten.org_id == org_id)),
    )
    record(
        "NachweisTemplates",
        _delete(db, delete(NachweisTemplate).where(NachweisTemplate.org_id == org_id)),
    )

    # ── 5. Personal (Payroll → Contracts → Employees) ───────────────────
    record(
        "PayrollAllocations",
        _delete(db, delete(PayrollAllocation).where(PayrollAllocation.org_id == org_id)),
    )
    record(
        "MonthlyPayrolls",
        _delete(db, delete(MonthlyPayroll).where(MonthlyPayroll.org_id == org_id)),
        note="  (Components/Allocations via Cascade)",
    )
    record(
        "SalaryComponents",
        _delete(db, delete(SalaryComponent).where(SalaryComponent.org_id == org_id)),
    )
    emp_ids = select(Employee.id).where(Employee.org_id == org_id)
    record(
        "EmployeeContracts",
        _delete(
            db, delete(EmployeeContract).where(EmployeeContract.employee_id.in_(emp_ids))
        ),
    )
    record("Employees", _delete(db, delete(Employee).where(Employee.org_id == org_id)))
    record(
        "EmployerGrossFactors",
        _delete(
            db, delete(EmployerGrossFactor).where(EmployerGrossFactor.org_id == org_id)
        ),
    )

    # ── 6. AllocationKeys (positions cascade) ───────────────────────────
    record(
        "AllocationKeys",
        _delete(db, delete(AllocationKey).where(AllocationKey.org_id == org_id)),
        note="  (Positions via Cascade)",
    )

    # ── 7. BankAccount + Opening + Import ───────────────────────────────
    bank_ids = select(BankAccount.id).where(BankAccount.org_id == org_id)
    record(
        "OpeningBalances",
        _delete(
            db, delete(OpeningBalance).where(OpeningBalance.bank_account_id.in_(bank_ids))
        ),
    )
    record(
        "ImportBatches",
        _delete(db, delete(ImportBatch).where(ImportBatch.org_id == org_id)),
    )
    record(
        "BankAccounts",
        _delete(db, delete(BankAccount).where(BankAccount.org_id == org_id)),
    )

    # ── 7.5. UmlageSourceScopes (bridge cascade); before CostCenters ────
    record(
        "UmlageSourceScopes",
        _delete(db, delete(UmlageSourceScope).where(UmlageSourceScope.org_id == org_id)),
        note="  (Bridge via Cascade)",
    )

    # ── 8. CostCenters (children first — self-RESTRICT on parent_id) ────
    n_children = _delete(
        db,
        delete(CostCenter).where(
            CostCenter.org_id == org_id, CostCenter.parent_id.isnot(None)
        ),
    )
    n_parents = _delete(db, delete(CostCenter).where(CostCenter.org_id == org_id))
    record(
        "CostCenters",
        n_children + n_parents,
        note=f"  ({n_children} children + {n_parents} parents)",
    )

    # ── 9. FiscalYears ──────────────────────────────────────────────────
    record(
        "FiscalYears",
        _delete(db, delete(FiscalYear).where(FiscalYear.org_id == org_id)),
    )

    # ── 10. Org-specific Kostenbereiche (system ones have org_id=NULL) ──
    record(
        "OrgSubKostenbereiche",
        _delete(db, delete(Kostenbereich).where(Kostenbereich.org_id == org_id)),
    )

    # ── 11. OrgInvites ──────────────────────────────────────────────────
    if not opts.keep_invites:
        record(
            "OrgInvites",
            _delete(db, delete(OrgInvite).where(OrgInvite.org_id == org_id)),
        )

    # ── 12. AuditLog (default: keep) ────────────────────────────────────
    if not opts.keep_audit_log:
        record("AuditLogs", _delete(db, delete(AuditLog).where(AuditLog.org_id == org_id)))

    # ── 13. OrganizationMembership (default: keep) ──────────────────────
    if not opts.keep_memberships:
        record(
            "OrganizationMemberships",
            _delete(
                db,
                delete(OrganizationMembership).where(
                    OrganizationMembership.org_id == org_id
                ),
            ),
        )

    db.flush()
    return summary


def reset_transactions(
    db: Session, org_id: str, log: Callable[[str, str], None] = _default_log
) -> ResetSummary:
    """Delete only Transactions + Splits + FundAllocations + Belege +
    ImportBatches + BookingRuleApplications. Master data untouched."""
    summary = ResetSummary()
    split_ids = select(TransactionSplit.id).where(TransactionSplit.org_id == org_id)

    deletions = [
        ("BookingRuleApplications", delete(BookingRuleApplication).where(BookingRuleApplication.org_id == org_id)),
        ("FundAllocations", delete(FundAllocation).where(FundAllocation.transaction_split_id.in_(split_ids))),
        ("TransactionSplits", delete(TransactionSplit).where(TransactionSplit.org_id == org_id)),
        ("TransactionBelege", delete(TransactionBeleg).where(TransactionBeleg.org_id == org_id)),
        ("Transactions", delete(Transaction).where(Transaction.org_id == org_id)),
        ("ImportBatches", delete(ImportBatch).where(ImportBatch.org_id == org_id)),
    ]
    for key, stmt in deletions:
        n = _delete(db, stmt)
        summary.counts[key] = n
        if n > 0:
            log("−", f"{key}: {n}")

    if summary.total() == 0:
        log("·", "reset-transactions: nothing to delete (org already empty)")
    db.flush()
    return summary


def reset_rules(
    db: Session, org_id: str, log: Callable[[str, str], None] = _default_log
) -> int:
    """Delete all BookingRules of the org (Splits + Applications cascade)."""
    n = _delete(db, delete(BookingRule).where(BookingRule.org_id == org_id))
    if n > 0:
        log("⚠", f"{n} BookingRules deleted (before re-seed)")
    else:
        log("·", "reset-rules: no existing BookingRules in the org")
    db.flush()
    return n
