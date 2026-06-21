"""Data access for BankAccount (Bank-/Kassenkonten)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.transaction import BankAccount, OpeningBalance, Transaction
from app.repositories.base import OrgScopedRepository


class BankAccountRepository(OrgScopedRepository[BankAccount]):
    model = BankAccount

    def list_with_opening(
        self, org_id: str, include_inactive: bool
    ) -> list[BankAccount]:
        stmt = (
            select(BankAccount)
            .where(BankAccount.org_id == org_id)
            .options(
                selectinload(BankAccount.opening_balances).selectinload(
                    OpeningBalance.fiscal_year
                )
            )
            .order_by(BankAccount.typ.asc(), BankAccount.code.asc())
        )
        if not include_inactive:
            stmt = stmt.where(BankAccount.ist_aktiv.is_(True))
        return list(self.db.execute(stmt).scalars().all())

    def get_by_code(self, org_id: str, code: str) -> BankAccount | None:
        return self.db.execute(
            select(BankAccount).where(
                BankAccount.org_id == org_id, BankAccount.code == code
            )
        ).scalar_one_or_none()

    def get_by_iban(self, iban: str) -> BankAccount | None:
        return self.db.execute(
            select(BankAccount).where(BankAccount.iban == iban)
        ).scalar_one_or_none()

    def transaction_sums(self, org_id: str) -> dict[str, Decimal]:
        rows = self.db.execute(
            select(Transaction.bank_account_id, func.sum(Transaction.betrag))
            .where(
                Transaction.org_id == org_id,
                Transaction.bank_account_id.is_not(None),
            )
            .group_by(Transaction.bank_account_id)
        ).all()
        return {acc_id: (s or Decimal(0)) for acc_id, s in rows}

    def transaction_count(self, account_id: str) -> int:
        return self.db.execute(
            select(func.count(Transaction.id)).where(
                Transaction.bank_account_id == account_id
            )
        ).scalar_one()

    def opening_balance_count(self, account_id: str) -> int:
        return self.db.execute(
            select(func.count(OpeningBalance.id)).where(
                OpeningBalance.bank_account_id == account_id
            )
        ).scalar_one()
