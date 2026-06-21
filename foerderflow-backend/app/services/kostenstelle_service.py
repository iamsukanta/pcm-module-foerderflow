"""Kostenstellen (CostCenter) business logic — faithful port of
app/api/protected/kostenstellen/* validation, codes and messages.

Authorization parity note: the monolith guards these routes with
`requireOrgSession()` only (NO requireRole), so any org member — including
READONLY — may create/update/deactivate. We preserve that exactly.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.master import CostCenter
from app.repositories.cost_center_repository import CostCenterRepository

CODE_RE = re.compile(r"^[A-Z0-9-]+$")
VALID_TYPES = ("PROJECT", "OVERHEAD")


# ── serialization (matches the monolith's include/select shapes) ─────────────
def _base_cc(cc: CostCenter, fm_count: int) -> dict[str, Any]:
    return {
        "id": cc.id,
        "org_id": cc.org_id,
        "name": cc.name,
        "code": cc.code,
        "typ": cc.typ.value,
        "ist_aktiv": cc.ist_aktiv,
        "parent_id": cc.parent_id,
        "created_at": cc.created_at.isoformat() if cc.created_at else None,
        "updated_at": cc.updated_at.isoformat() if cc.updated_at else None,
        "_count": {"funding_measure_cost_centers": fm_count},
    }


def _parent_brief(cc: CostCenter) -> dict[str, Any] | None:
    p = cc.parent
    return None if p is None else {"id": p.id, "name": p.name, "code": p.code}


class KostenstelleService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CostCenterRepository(db)

    # ── list ────────────────────────────────────────────────────────────────
    def list(self, org_id: str, include_inactive: bool) -> list[dict[str, Any]]:
        items = self.repo.list_with_relations(org_id, include_inactive)
        # collect ids (parents + their children) for one count query
        all_ids: list[str] = []
        for cc in items:
            all_ids.append(cc.id)
            all_ids.extend(c.id for c in cc.children)
        counts = self.repo.funding_measure_counts(all_ids)

        result = []
        for cc in items:
            row = _base_cc(cc, counts.get(cc.id, 0))
            row["parent"] = _parent_brief(cc)
            children = [
                c for c in cc.children if include_inactive or c.ist_aktiv
            ]
            children.sort(key=lambda c: c.name)
            row["children"] = [
                {
                    "id": c.id,
                    "org_id": c.org_id,
                    "name": c.name,
                    "code": c.code,
                    "typ": c.typ.value,
                    "ist_aktiv": c.ist_aktiv,
                    "parent_id": c.parent_id,
                    "_count": {
                        "funding_measure_cost_centers": counts.get(c.id, 0)
                    },
                }
                for c in children
            ]
            result.append(row)
        return result

    def get(self, org_id: str, id_: str) -> dict[str, Any]:
        cc = self.repo.get_with_relations(org_id, id_)
        if cc is None:
            raise APIError(
                status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Kostenstelle nicht gefunden."
            )
        ids = [cc.id, *[c.id for c in cc.children]]
        counts = self.repo.funding_measure_counts(ids)
        row = _base_cc(cc, counts.get(cc.id, 0))
        row["parent"] = _parent_brief(cc)
        children = sorted(cc.children, key=lambda c: c.name)
        row["children"] = [
            {
                "id": c.id,
                "org_id": c.org_id,
                "name": c.name,
                "code": c.code,
                "typ": c.typ.value,
                "ist_aktiv": c.ist_aktiv,
                "parent_id": c.parent_id,
                "_count": {"funding_measure_cost_centers": counts.get(c.id, 0)},
            }
            for c in children
        ]
        # funding_measure_cost_centers with nested funding_measure (detail view)
        links = sorted(
            cc.funding_measure_cost_centers,
            key=lambda l: l.created_at,
            reverse=True,
        )
        row["funding_measure_cost_centers"] = [
            {
                "id": link.id,
                "org_id": link.org_id,
                "funding_measure_id": link.funding_measure_id,
                "cost_center_id": link.cost_center_id,
                "created_at": link.created_at.isoformat(),
                "funding_measure": {
                    "id": link.funding_measure.id,
                    "name": link.funding_measure.name,
                    "status": link.funding_measure.status.value,
                    "laufzeit_von": link.funding_measure.laufzeit_von.isoformat(),
                    "laufzeit_bis": link.funding_measure.laufzeit_bis.isoformat(),
                },
            }
            for link in links
        ]
        return row

    # ── validation helpers (exact codes/messages) ────────────────────────────
    def _validate_name(self, name: Any) -> str:
        if not isinstance(name, str) or not (2 <= len(name.strip()) <= 100):
            raise APIError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "VALIDATION_NAME",
                "Name muss zwischen 2 und 100 Zeichen lang sein.",
            )
        return name.strip()

    def _validate_code(self, code: Any) -> str:
        if (
            not isinstance(code, str)
            or not (2 <= len(code.strip()) <= 10)
            or not CODE_RE.match(code.strip())
        ):
            raise APIError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "VALIDATION_CODE",
                "Kürzel muss 2–10 Zeichen lang sein und darf nur Großbuchstaben, "
                "Ziffern und Bindestriche enthalten.",
            )
        return code.strip().upper()

    def _validate_typ(self, typ: Any) -> str:
        if typ not in VALID_TYPES:
            raise APIError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "VALIDATION_TYP",
                "Ungültiger Typ. Erlaubt: PROJECT, OVERHEAD.",
            )
        return typ

    def _validate_parent(
        self, org_id: str, parent_id: Any, self_id: str | None = None
    ) -> None:
        if not isinstance(parent_id, str):
            raise APIError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "VALIDATION_PARENT_ID",
                "Ungültige parent_id.",
            )
        if self_id is not None and parent_id == self_id:
            raise APIError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "PARENT_SELF_REFERENCE",
                "Eine Kostenstelle kann nicht sich selbst als Eltern haben.",
            )
        parent = self.repo.get(org_id, parent_id)
        if parent is None:
            raise APIError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "PARENT_NOT_FOUND",
                "Die übergeordnete Kostenstelle wurde nicht gefunden oder gehört "
                "nicht zu dieser Organisation.",
            )
        if parent.parent_id is not None:
            raise APIError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "HIERARCHY_TOO_DEEP",
                "Die gewählte übergeordnete Kostenstelle hat selbst bereits eine "
                "übergeordnete KST. Es ist nur eine Hierarchieebene erlaubt.",
            )

    # ── create ───────────────────────────────────────────────────────────────
    def create(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        name = self._validate_name(body.get("name"))
        code = self._validate_code(body.get("code"))
        typ = self._validate_typ(body.get("typ"))

        if self.repo.get_by_code(org_id, code):
            raise APIError(
                status.HTTP_409_CONFLICT,
                "CODE_DUPLICATE",
                f'Das Kürzel „{code}" ist bereits vergeben. Bitte ein anderes wählen.',
            )

        parent_id = body.get("parent_id")
        if parent_id is not None:
            self._validate_parent(org_id, parent_id)

        cc = CostCenter(
            org_id=org_id,
            name=name,
            code=code,
            typ=typ,
            parent_id=parent_id if isinstance(parent_id, str) else None,
        )
        self.repo.add(cc)
        self.db.commit()
        self.db.refresh(cc)
        ids = [cc.id]
        counts = self.repo.funding_measure_counts(ids)
        row = _base_cc(cc, counts.get(cc.id, 0))
        row["parent"] = _parent_brief(cc)
        return row

    # ── update ───────────────────────────────────────────────────────────────
    def update(self, org_id: str, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        cc = self.repo.get(org_id, id_)
        if cc is None:
            raise APIError(
                status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Kostenstelle nicht gefunden."
            )

        if "name" in body and body["name"] is not None:
            cc.name = self._validate_name(body["name"])
        if "code" in body and body["code"] is not None:
            new_code = self._validate_code(body["code"])
            if new_code != cc.code:
                if self.repo.get_by_code(org_id, new_code, exclude_id=id_):
                    raise APIError(
                        status.HTTP_409_CONFLICT,
                        "CODE_DUPLICATE",
                        f'Das Kürzel „{new_code}" ist bereits vergeben.',
                    )
            cc.code = new_code
        if "typ" in body and body["typ"] is not None:
            cc.typ = self._validate_typ(body["typ"])
        if "parent_id" in body:
            if body["parent_id"] is None:
                cc.parent_id = None
            else:
                self._validate_parent(org_id, body["parent_id"], self_id=id_)
                cc.parent_id = body["parent_id"]

        self.db.commit()
        self.db.refresh(cc)
        counts = self.repo.funding_measure_counts([cc.id])
        row = _base_cc(cc, counts.get(cc.id, 0))
        # reload parent brief
        cc2 = self.repo.get_with_relations(org_id, id_)
        row["parent"] = _parent_brief(cc2) if cc2 else None
        return row

    # ── deactivate (soft delete) ──────────────────────────────────────────────
    def deactivate(self, org_id: str, id_: str) -> dict[str, Any]:
        cc = self.repo.get(org_id, id_)
        if cc is None:
            raise APIError(
                status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Kostenstelle nicht gefunden."
            )
        if not cc.ist_aktiv:
            raise APIError(
                status.HTTP_409_CONFLICT,
                "ALREADY_INACTIVE",
                "Diese Kostenstelle ist bereits deaktiviert.",
            )
        active_children = self.repo.active_children(org_id, id_)
        cc.ist_aktiv = False
        for child in active_children:
            child.ist_aktiv = False
        self.db.commit()

        result: dict[str, Any] = {
            "data": {"id": id_, "ist_aktiv": False},
            "message": f'Kostenstelle „{cc.name}" wurde deaktiviert.',
        }
        if active_children:
            names = ", ".join(c.name for c in active_children)
            result["warnings"] = [
                f"{len(active_children)} untergeordnete Kostenstelle(n) wurden "
                f"ebenfalls deaktiviert: {names}."
            ]
        return result
