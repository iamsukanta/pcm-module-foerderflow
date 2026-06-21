import { requireOrgSession } from "@/lib/session";
import { loadActiveCostCenters } from "@/lib/costCenters";
import { PageShell } from "@/components/ui/PageShell";
import { UmlageSourceScopeForm } from "../UmlageSourceScopeForm";

export const metadata = { title: "Neuer Umlage-Pool — FoerderFlow" };

export default async function NewUmlageSourceScopePage() {
  await requireOrgSession();

  const costCenters = await loadActiveCostCenters();

  return (
    <PageShell width="form">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-soft-ink">Neuer Umlage-Pool</h1>
        <p className="text-sm text-soft-ink3 mt-1">
          Gruppe von Quell-Kostenstellen, die bei UMLAGE_KOSTENSTELLEN-Pauschalen gemeinsam umgelegt
          werden.
        </p>
      </div>
      <UmlageSourceScopeForm costCenters={costCenters} />
    </PageShell>
  );
}
