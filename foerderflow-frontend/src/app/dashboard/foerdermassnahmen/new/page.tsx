import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { loadActiveCostCentersForForms } from "@/lib/costCenters";
import { FoerdermassnahmeWizard } from "@/components/forms/FoerdermassnahmeWizard";
import { PageShell } from "@/components/ui/PageShell";
import type { FunderTyp } from "@/types/foerdermassnahmen";

type FunderOption = { id: string; name: string; typ: FunderTyp };

export default async function NewFoerdermassnahmePage() {
  await requireOrgSession();

  const [funders, costCenters] = await Promise.all([
    serverFetch<FunderOption[]>("/protected/funder"),
    loadActiveCostCentersForForms(),
  ]);

  return (
    <PageShell width="form">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-soft-ink">Neue Fördermassnahme</h1>
        <p className="text-sm text-soft-ink3 mt-1">
          Legen Sie ein neues Förderprogramm mit Budget, Laufzeit und Regeln an.
        </p>
      </div>

      <FoerdermassnahmeWizard
        funders={funders.map((f) => ({ id: f.id, name: f.name, typ: f.typ }))}
        costCenters={costCenters}
      />
    </PageShell>
  );
}
