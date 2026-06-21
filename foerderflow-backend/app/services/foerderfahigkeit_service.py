"""Förderfähigkeit / compliance checks — port of lib/foerderfahigkeit.ts
(validate_foerderfahigkeit, check_overhead_limit, check_doppelfinanzierung,
check_finanzplan_position_ueberziehung).

Returns (valid, errors, warnings). German messages preserved. Money in messages
formatted de-DE ("1.234,56 €").
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.funding import FundingMeasure, FundingRule
from app.models.master import CostCenter, Kostenbereich
from app.models.finanzplan import FinanzplanPosition
from app.models.transaction import FundAllocation, TransactionSplit
from app.services.allocation_position_resolver import position_ist


@dataclass
class ValidationResult:
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def format_eur(n: float) -> str:
    s = f"{n:,.2f}"  # 1,234.56
    s = s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"{s} €"


def _display_name(db: Session, code: str | None) -> str:
    if not code:
        return "(nicht angegeben)"
    kb = db.execute(
        select(Kostenbereich.bezeichnung).where(Kostenbereich.code == code)
    ).scalar_one_or_none()
    return kb or code


def _display_name_map(db: Session, codes: list[str]) -> dict[str, str]:
    unique = list(set(codes))
    if not unique:
        return {}
    rows = db.execute(
        select(Kostenbereich.code, Kostenbereich.bezeichnung).where(
            Kostenbereich.code.in_(unique)
        )
    ).all()
    return {c: b for c, b in rows}


def validate_foerderfahigkeit(
    db: Session, funding_measure_id: str, kostenbereich_code: str | None, betrag: float
) -> ValidationResult:
    rules = (
        db.execute(
            select(FundingRule).where(
                FundingRule.funding_measure_id == funding_measure_id,
                FundingRule.typ.in_(
                    [
                        "KOSTENKATEGORIE_ERLAUBT",
                        "KOSTENKATEGORIE_VERBOTEN",
                        "PERSONALKOSTEN_HOECHSTSATZ",
                    ]
                ),
            )
        )
        .scalars()
        .all()
    )
    display_name = _display_name(db, kostenbereich_code)
    codes_to_names = _display_name_map(db, [r.schluessel for r in rules])

    errors: list[str] = []
    warnings: list[str] = []

    def _typ(r) -> str:
        return r.typ.value if hasattr(r.typ, "value") else r.typ

    kategorie = [r for r in rules if _typ(r) in ("KOSTENKATEGORIE_ERLAUBT", "KOSTENKATEGORIE_VERBOTEN")]
    hoechstsatz = [r for r in rules if _typ(r) == "PERSONALKOSTEN_HOECHSTSATZ"]
    if not kategorie and not hoechstsatz:
        return ValidationResult()

    erlaubt = [r for r in kategorie if _typ(r) == "KOSTENKATEGORIE_ERLAUBT"]
    verboten = [r for r in kategorie if _typ(r) == "KOSTENKATEGORIE_VERBOTEN"]

    if kostenbereich_code is None:
        if erlaubt:
            warnings.append("Kostenart nicht angegeben — Förderfahigkeit unklar")
        return ValidationResult(True, errors, warnings)

    is_verboten = any(r.schluessel == kostenbereich_code for r in verboten)
    if is_verboten:
        errors.append(
            f'Die Kostenart „{display_name}" ist für diese Fördermassnahme nicht förderfähig.'
        )

    if not is_verboten and erlaubt:
        if not any(r.schluessel == kostenbereich_code for r in erlaubt):
            erlaubt_names = ", ".join(
                f'„{codes_to_names.get(r.schluessel, r.schluessel)}"' for r in erlaubt
            )
            errors.append(
                f'Die Kostenart „{display_name}" ist nicht in der Liste der förderfähigen '
                f"Kostenarten. Erlaubt: {erlaubt_names}."
            )

    if not errors:
        for rule in hoechstsatz:
            if rule.schluessel == kostenbereich_code and rule.wert:
                try:
                    limit = float(rule.wert)
                except ValueError:
                    continue
                if betrag > limit:
                    warnings.append(
                        f"Personalkosten-Höchstsatz überschritten: Betrag {format_eur(betrag)} "
                        f"liegt über dem Limit von {format_eur(limit)} pro Monat/VZÄ für "
                        f'„{display_name}".'
                    )

    return ValidationResult(len(errors) == 0, errors, warnings)


def check_overhead_limit(
    db: Session,
    funding_measure_id: str,
    org_id: str,
    new_betrag_foerderfahig: float,
    cost_center_id: str,
) -> ValidationResult:
    cc = db.execute(
        select(CostCenter).where(CostCenter.id == cost_center_id, CostCenter.org_id == org_id)
    ).scalar_one_or_none()
    typ = (cc.typ.value if cc and hasattr(cc.typ, "value") else (cc.typ if cc else None))
    if not cc or typ != "OVERHEAD":
        return ValidationResult()

    measure = db.execute(
        select(FundingMeasure).where(
            FundingMeasure.id == funding_measure_id, FundingMeasure.org_id == org_id
        )
    ).scalar_one_or_none()
    if not measure or measure.overhead_limit_prozent is None:
        return ValidationResult()

    limit_prozent = float(measure.overhead_limit_prozent)
    budget_gesamt = float(measure.budget_gesamt)
    limit_betrag = budget_gesamt * limit_prozent / 100

    existing = db.execute(
        select(func.coalesce(func.sum(FundAllocation.betrag_foerderfahig * FundAllocation.prozent / 100), 0))
        .select_from(FundAllocation)
        .join(TransactionSplit, FundAllocation.transaction_split_id == TransactionSplit.id)
        .join(CostCenter, CostCenter.id == TransactionSplit.cost_center_id)
        .where(
            FundAllocation.funding_measure_id == funding_measure_id,
            FundAllocation.org_id == org_id,
            CostCenter.typ == "OVERHEAD",
        )
    ).scalar_one()
    existing_overhead = float(existing or 0)
    projected = existing_overhead + new_betrag_foerderfahig

    if projected > limit_betrag:
        return ValidationResult(
            True,
            [],
            [
                f"Gemeinkostendeckel überschritten: Limit {limit_prozent}% "
                f"({format_eur(limit_betrag)}), projiziert {format_eur(projected)} "
                f"({projected / budget_gesamt * 100:.1f}%)."
            ],
        )
    return ValidationResult()


def check_doppelfinanzierung(
    db: Session, transaction_split_id: str, funding_measure_id: str, new_prozent: float = 100
) -> ValidationResult:
    existing = (
        db.execute(
            select(FundAllocation).where(
                FundAllocation.transaction_split_id == transaction_split_id
            )
        )
        .scalars()
        .all()
    )
    same = next((a for a in existing if a.funding_measure_id == funding_measure_id), None)
    if same:
        return ValidationResult(
            False,
            [
                f'Doppelfinanzierung: dieser Split ist bereits der Massnahme '
                f'„{same.funding_measure.name}" zugeordnet (Allocation existiert).'
            ],
            [],
        )

    existing_sum = sum(float(a.prozent) for a in existing)
    projected = existing_sum + new_prozent
    if projected > 100 + 0.001:
        def fmt(n: float) -> str:
            return f"{n:.2f}".rstrip("0").rstrip(".")

        fremd = ", ".join(f"{a.funding_measure.name} ({fmt(float(a.prozent))}%)" for a in existing)
        return ValidationResult(
            False,
            [
                f"Übervergabe: dieser Split ist bereits zu {fmt(existing_sum)}% anderen "
                f"Massnahmen zugeordnet ({fremd}). Neue {fmt(new_prozent)}% würden die "
                f"100%-Grenze überschreiten (Total {fmt(projected)}%)."
            ],
            [],
        )
    return ValidationResult()


def check_finanzplan_position_ueberziehung(
    db: Session, finanzplan_position_id: str, org_id: str, new_betrag_foerderfahig: float
) -> ValidationResult:
    pos = db.execute(
        select(FinanzplanPosition).where(
            FinanzplanPosition.id == finanzplan_position_id,
            FinanzplanPosition.org_id == org_id,
        )
    ).scalar_one_or_none()
    if not pos:
        return ValidationResult()
    if pos.ist_pauschale:
        return ValidationResult()

    bewilligt = float(pos.betrag_bewilligt)
    limit_pct = float(pos.ueberziehung_limit_pct)
    max_erlaubt = bewilligt * (1 + limit_pct / 100)

    ist_bisher = position_ist(db, pos.funding_measure_id, org_id, finanzplan_position_id)
    ist_nach = ist_bisher + new_betrag_foerderfahig
    if ist_nach <= max_erlaubt:
        return ValidationResult()

    nachricht = (
        f'Position „{pos.bezeichnung}": Bewilligt {format_eur(bewilligt)}, '
        f"Limit {limit_pct}% = {format_eur(max_erlaubt)}, "
        f"projiziert {format_eur(ist_nach)} "
        f"(+{format_eur(ist_nach - max_erlaubt)} über Limit)."
    )
    if pos.ueberziehung_genehmigungspflichtig:
        return ValidationResult(
            False,
            [f"Überziehung genehmigungspflichtig — bitte Änderungsbescheid einholen. {nachricht}"],
            [],
        )
    return ValidationResult(
        True,
        [],
        [f"Überziehungswarnung: {nachricht} Prüfen ob Deckungsfähigkeit ausreicht."],
    )
