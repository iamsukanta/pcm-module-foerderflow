"""Umlage-Source-Scopes (UmlageSourceScope) — port of
app/api/protected/umlage-source-scopes/*. Pools of source cost-centers for
UMLAGE_KOSTENSTELLEN pauschalen. Name unique per org. Delete blocked while
referenced by Finanzplan positions.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import APIError
from app.models.allocation import UmlageSourceScope, UmlageSourceScopeCostCenter
from app.models.finanzplan import FinanzplanPosition
from app.models.master import CostCenter


def _ev(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _scope_scalars(s: UmlageSourceScope) -> dict[str, Any]:
    return {
        "id": s.id,
        "org_id": s.org_id,
        "name": s.name,
        "beschreibung": s.beschreibung,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _cc_link(link: UmlageSourceScopeCostCenter, with_typ: bool) -> dict[str, Any]:
    cc = link.cost_center
    cc_ser: dict[str, Any] = {"id": cc.id, "code": cc.code, "name": cc.name}
    if with_typ:
        cc_ser["typ"] = _ev(cc.typ)
    return {
        "id": link.id,
        "org_id": link.org_id,
        "umlage_source_scope_id": link.umlage_source_scope_id,
        "cost_center_id": link.cost_center_id,
        "cost_center": cc_ser,
    }


class UmlageScopeService:
    def __init__(self, db: Session):
        self.db = db

    def _position_count(self, scope_id: str) -> int:
        return self.db.execute(
            select(func.count(FinanzplanPosition.id)).where(
                FinanzplanPosition.umlage_source_scope_id == scope_id
            )
        ).scalar_one()

    def _validate_ccs(self, org_id: str, cost_center_ids: Any) -> list[str]:
        if not isinstance(cost_center_ids, list) or len(cost_center_ids) == 0:
            raise APIError(
                422, "VALIDATION_KSTS", "Mindestens eine Quell-Kostenstelle erforderlich."
            )
        kst_ids = [c for c in cost_center_ids if isinstance(c, str)]
        if len(kst_ids) != len(cost_center_ids):
            raise APIError(422, "VALIDATION_KSTS", "Ungültige Kostenstellen-ID.")
        valid = self.db.execute(
            select(CostCenter.id).where(
                CostCenter.id.in_(kst_ids), CostCenter.org_id == org_id
            )
        ).all()
        if len({r[0] for r in valid}) != len(set(kst_ids)):
            raise APIError(
                422,
                "VALIDATION_KSTS",
                "Eine oder mehrere Kostenstellen gehören nicht zur Organisation oder "
                "existieren nicht.",
            )
        return kst_ids

    def _name_taken(self, org_id: str, name: str, exclude_id: str | None = None) -> bool:
        stmt = select(UmlageSourceScope.id).where(
            UmlageSourceScope.org_id == org_id, UmlageSourceScope.name == name
        )
        if exclude_id:
            stmt = stmt.where(UmlageSourceScope.id != exclude_id)
        return self.db.execute(stmt).scalar_one_or_none() is not None

    # ── list / get ────────────────────────────────────────────────────────────
    def list(self, org_id: str) -> list[dict[str, Any]]:
        scopes = (
            self.db.execute(
                select(UmlageSourceScope)
                .where(UmlageSourceScope.org_id == org_id)
                .options(
                    selectinload(UmlageSourceScope.cost_centers).selectinload(
                        UmlageSourceScopeCostCenter.cost_center
                    )
                )
                .order_by(UmlageSourceScope.name.asc())
            )
            .scalars()
            .all()
        )
        rows = []
        for s in scopes:
            row = _scope_scalars(s)
            row["cost_centers"] = [_cc_link(c, with_typ=True) for c in s.cost_centers]
            row["cost_center_count"] = len(s.cost_centers)
            row["position_count"] = self._position_count(s.id)
            rows.append(row)
        return rows

    def get(self, org_id: str, id_: str) -> dict[str, Any]:
        s = self.db.execute(
            select(UmlageSourceScope)
            .where(UmlageSourceScope.id == id_, UmlageSourceScope.org_id == org_id)
            .options(
                selectinload(UmlageSourceScope.cost_centers).selectinload(
                    UmlageSourceScopeCostCenter.cost_center
                )
            )
        ).scalar_one_or_none()
        if s is None:
            raise APIError(404, "NOT_FOUND", "Umlage-Pool nicht gefunden.")
        row = _scope_scalars(s)
        row["cost_centers"] = [_cc_link(c, with_typ=True) for c in s.cost_centers]
        row["position_count"] = self._position_count(s.id)
        return row

    # ── create ────────────────────────────────────────────────────────────────
    def create(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        name = body.get("name")
        if not isinstance(name, str) or not name.strip():
            raise APIError(422, "VALIDATION_NAME", "Name ist erforderlich.")
        kst_ids = self._validate_ccs(org_id, body.get("cost_center_ids"))
        if self._name_taken(org_id, name.strip()):
            raise APIError(
                409, "DUPLICATE_NAME", f'Ein Pool mit dem Namen „{name}" existiert bereits.'
            )
        beschreibung = body.get("beschreibung")
        scope = UmlageSourceScope(
            org_id=org_id,
            name=name.strip(),
            beschreibung=beschreibung.strip() if isinstance(beschreibung, str) and beschreibung.strip() else None,
        )
        self.db.add(scope)
        self.db.flush()
        for cc_id in kst_ids:
            self.db.add(
                UmlageSourceScopeCostCenter(
                    org_id=org_id, umlage_source_scope_id=scope.id, cost_center_id=cc_id
                )
            )
        self.db.commit()
        scope = self.db.execute(
            select(UmlageSourceScope)
            .where(UmlageSourceScope.id == scope.id)
            .options(
                selectinload(UmlageSourceScope.cost_centers).selectinload(
                    UmlageSourceScopeCostCenter.cost_center
                )
            )
        ).scalar_one()
        row = _scope_scalars(scope)
        row["cost_centers"] = [_cc_link(c, with_typ=False) for c in scope.cost_centers]
        return row

    # ── update ────────────────────────────────────────────────────────────────
    def update(self, org_id: str, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        scope = self.db.execute(
            select(UmlageSourceScope).where(
                UmlageSourceScope.id == id_, UmlageSourceScope.org_id == org_id
            )
        ).scalar_one_or_none()
        if scope is None:
            raise APIError(404, "NOT_FOUND", "Umlage-Pool nicht gefunden.")

        if "name" in body:
            name = body["name"]
            if not isinstance(name, str) or not name.strip():
                raise APIError(422, "VALIDATION_NAME", "Name ist erforderlich.")
            if self._name_taken(org_id, name.strip(), exclude_id=id_):
                raise APIError(
                    409,
                    "DUPLICATE_NAME",
                    f'Ein Pool mit dem Namen „{name}" existiert bereits.',
                )
            scope.name = name.strip()
        if "beschreibung" in body:
            b = body["beschreibung"]
            scope.beschreibung = b.strip() if isinstance(b, str) and b.strip() else None

        if "cost_center_ids" in body:
            kst_ids = self._validate_ccs(org_id, body["cost_center_ids"])
            self.db.query(UmlageSourceScopeCostCenter).filter(
                UmlageSourceScopeCostCenter.umlage_source_scope_id == id_
            ).delete(synchronize_session=False)
            for cc_id in kst_ids:
                self.db.add(
                    UmlageSourceScopeCostCenter(
                        org_id=org_id, umlage_source_scope_id=id_, cost_center_id=cc_id
                    )
                )
        self.db.commit()
        self.db.refresh(scope)
        return _scope_scalars(scope)

    # ── delete ────────────────────────────────────────────────────────────────
    def delete(self, org_id: str, id_: str) -> dict[str, Any]:
        scope = self.db.execute(
            select(UmlageSourceScope).where(
                UmlageSourceScope.id == id_, UmlageSourceScope.org_id == org_id
            )
        ).scalar_one_or_none()
        if scope is None:
            raise APIError(404, "NOT_FOUND", "Umlage-Pool nicht gefunden.")
        n = self._position_count(id_)
        if n > 0:
            raise APIError(
                409,
                "HAS_REFERENCES",
                f"Pool wird von {n} Pauschale-Position(en) genutzt — löschen nicht möglich.",
            )
        self.db.delete(scope)
        self.db.commit()
        return {"data": {"id": id_}, "message": "Pool wurde gelöscht."}
