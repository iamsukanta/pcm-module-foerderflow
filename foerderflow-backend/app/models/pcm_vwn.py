"""Module PCM — VWN personnel-cost report config (Area M).

Per funding measure: which ``payroll_detail_lines`` components appear as named
line items in the Verwendungsnachweis, plus aggregation/display options.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._types import created_at, cuid_pk, updated_at

if TYPE_CHECKING:
    pass


class VwnPersonnelConfig(Base):
    __tablename__ = "vwn_personnel_configs"
    __table_args__ = (
        UniqueConstraint("org_id", "funding_measure_id"),
        Index("ix_vwn_personnel_configs_org_id", "org_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    funding_measure_id: Mapped[str] = mapped_column(
        ForeignKey("funding_measures.id", ondelete="CASCADE"), nullable=False
    )
    # Ordered list of PayrollDetailComponent values shown as named line items.
    visible_components: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    bav_required: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    aggregate_label: Mapped[str] = mapped_column(
        String(80), default="Sonstiges", server_default="Sonstiges", nullable=False
    )
    hide_zero: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    def as_dict(self) -> dict[str, Any]:
        return {
            "funding_measure_id": self.funding_measure_id,
            "visible_components": self.visible_components,
            "bav_required": self.bav_required,
            "aggregate_label": self.aggregate_label,
            "hide_zero": self.hide_zero,
        }
