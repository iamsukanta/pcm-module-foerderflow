import { notFound } from "next/navigation";

import { requireOrgSession } from "@/lib/session";
import { ApiError, serverFetch } from "@/lib/serverApi";
import { loadActiveCostCentersForForms } from "@/lib/costCenters";
import { FoerdermassnahmeWizard } from "@/components/forms/FoerdermassnahmeWizard";
import { PageShell } from "@/components/ui/PageShell";
import type {
  FunderTyp,
  FundingMeasureStatus,
  FundingRuleTyp,
  MittelabrufVerfahren,
} from "@/types/foerdermassnahmen";
import type { FinanzierungsartTyp } from "@/lib/foerdermassnahme-berechnung";

type FunderOption = { id: string; name: string; typ: FunderTyp };

type MeasureFull = {
  id: string;
  funder_id: string;
  name: string;
  antragsnummer: string | null;
  budget_gesamt: string;
  laufzeit_von: string;
  laufzeit_bis: string;
  durchfuehrungs_von: string | null;
  durchfuehrungs_bis: string | null;
  status: FundingMeasureStatus;
  finanzierungsart: FinanzierungsartTyp | null;
  eigenmittel_betrag: string | null;
  drittmittel_betrag: string | null;
  foerderquote: string;
  verwaltungspauschale_erlaubt: boolean;
  verwaltungspauschale_prozent: string | null;
  budget_flexibilitaet_prozent: string;
  overhead_limit_prozent: string | null;
  mittelabruf_verfahren: MittelabrufVerfahren;
  mwst_foerderfahig: boolean;
  mwst_satz_prozent: string;
  rules: Array<{
    typ: FundingRuleTyp;
    schluessel: string;
    wert: string | null;
    beschreibung: string | null;
  }>;
  cost_centers: Array<{ cost_center_id: string }>;
};

type PositionRow = {
  id: string;
  positionscode: string;
  bezeichnung: string;
  betrag_bewilligt: number;
  ueberziehung_limit_pct: number;
  kostenbereiche: Array<{ kostenbereich: { code: string } }>;
  _count: { fund_allocations: number };
  ist_pauschale: boolean;
  pauschale_typ:
    | "FIXER_BETRAG"
    | "PROZENT_GESAMT"
    | "PROZENT_PERSONAL"
    | "UMLAGE_KOSTENSTELLEN"
    | null;
  pauschale_prozent: number | null;
  umlage_allocation_key_id: string | null;
  umlage_ziel_cost_center_id: string | null;
  umlage_source_scope_id: string | null;
};

function isoOrNull(d: string | null): string | null {
  return d ? new Date(d).toISOString() : null;
}

type PageProps = { params: Promise<{ id: string }> };

export default async function EditFoerdermassnahmePage({ params }: PageProps) {
  await requireOrgSession();
  const { id } = await params;

  let measure: MeasureFull;
  try {
    measure = await serverFetch<MeasureFull>(`/protected/foerdermassnahmen/${id}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }

  const [funders, costCenters, positionen] = await Promise.all([
    serverFetch<FunderOption[]>("/protected/funder"),
    loadActiveCostCentersForForms(),
    serverFetch<PositionRow[]>(`/protected/finanzplan-positionen?funding_measure_id=${id}`),
  ]);

  const initialData = {
    id: measure.id,
    funder_id: measure.funder_id,
    name: measure.name,
    antragsnummer: measure.antragsnummer,
    budget_gesamt: measure.budget_gesamt,
    laufzeit_von: new Date(measure.laufzeit_von).toISOString(),
    laufzeit_bis: new Date(measure.laufzeit_bis).toISOString(),
    durchfuehrungs_von: isoOrNull(measure.durchfuehrungs_von),
    durchfuehrungs_bis: isoOrNull(measure.durchfuehrungs_bis),
    status: measure.status,
    finanzierungsart: measure.finanzierungsart,
    eigenmittel_betrag: measure.eigenmittel_betrag,
    drittmittel_betrag: measure.drittmittel_betrag,
    foerderquote: measure.foerderquote,
    verwaltungspauschale_erlaubt: measure.verwaltungspauschale_erlaubt,
    verwaltungspauschale_prozent: measure.verwaltungspauschale_prozent,
    budget_flexibilitaet_prozent: measure.budget_flexibilitaet_prozent,
    overhead_limit_prozent: measure.overhead_limit_prozent,
    mittelabruf_verfahren: measure.mittelabruf_verfahren,
    cost_center_ids: measure.cost_centers.map((cc) => cc.cost_center_id),
    mwst_foerderfahig: measure.mwst_foerderfahig,
    mwst_satz_prozent: measure.mwst_satz_prozent,
    rules: measure.rules.map((r) => ({
      typ: r.typ,
      schluessel: r.schluessel,
      wert: r.wert ?? null,
      beschreibung: r.beschreibung ?? null,
    })),
    positionen: positionen.map((p) => ({
      id: p.id,
      positionscode: p.positionscode,
      bezeichnung: p.bezeichnung,
      betrag_bewilligt: String(p.betrag_bewilligt),
      ueberziehung_limit_pct: String(p.ueberziehung_limit_pct),
      kostenbereich_codes: p.kostenbereiche.map((k) => k.kostenbereich.code),
      allocation_count: p._count.fund_allocations,
      ist_pauschale: p.ist_pauschale,
      pauschale_typ: p.pauschale_typ,
      pauschale_prozent: p.pauschale_prozent != null ? String(p.pauschale_prozent) : "",
      umlage_allocation_key_id: p.umlage_allocation_key_id,
      umlage_ziel_cost_center_id: p.umlage_ziel_cost_center_id,
      umlage_source_scope_id: p.umlage_source_scope_id,
    })),
  };

  return (
    <PageShell width="form">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-soft-ink">Fördermassnahme bearbeiten</h1>
        <p className="text-sm text-soft-ink3 mt-1">{measure.name}</p>
      </div>

      <FoerdermassnahmeWizard
        funders={funders.map((f) => ({ id: f.id, name: f.name, typ: f.typ }))}
        costCenters={costCenters}
        mode="edit"
        initialData={initialData}
      />
    </PageShell>
  );
}
