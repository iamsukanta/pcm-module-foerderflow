import { notFound } from "next/navigation";

import { requireOrgSession } from "@/lib/session";
import { ApiError, serverFetch } from "@/lib/serverApi";
import { loadActiveCostCenters } from "@/lib/costCenters";
import { PageShell } from "@/components/ui/PageShell";
import { UmlageSourceScopeForm } from "../UmlageSourceScopeForm";

export const metadata = { title: "Umlage-Pool bearbeiten — FoerderFlow" };

type PageProps = { params: Promise<{ id: string }> };

type ScopeDetail = {
  id: string;
  name: string;
  beschreibung: string | null;
  cost_centers: Array<{ cost_center_id: string }>;
};

export default async function EditUmlageSourceScopePage({ params }: PageProps) {
  await requireOrgSession();
  const { id } = await params;

  let scope: ScopeDetail;
  try {
    scope = await serverFetch<ScopeDetail>(`/protected/umlage-source-scopes/${id}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }

  const costCenters = await loadActiveCostCenters();

  return (
    <PageShell width="form">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-soft-ink">Umlage-Pool bearbeiten</h1>
        <p className="text-sm text-soft-ink3 mt-1">{scope.name}</p>
      </div>
      <UmlageSourceScopeForm
        costCenters={costCenters}
        initial={{
          id: scope.id,
          name: scope.name,
          beschreibung: scope.beschreibung,
          cost_center_ids: scope.cost_centers.map((c) => c.cost_center_id),
        }}
      />
    </PageShell>
  );
}
