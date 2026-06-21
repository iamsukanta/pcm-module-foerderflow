import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";
import type { KostenstelleWithChildren } from "@/types/kostenstellen";
import { BuchungsregelnClient } from "./BuchungsregelnClient";

export const dynamic = "force-dynamic";

type BookingRuleApi = Parameters<typeof BuchungsregelnClient>[0]["initialRules"][number];
type MeasureRow = { id: string; name: string };

export default async function BuchungsregelnPage() {
  await requireOrgSession();

  const [rules, kstTree, measures] = await Promise.all([
    serverFetch<BookingRuleApi[]>("/protected/buchungsregeln"),
    serverFetch<KostenstelleWithChildren[]>("/protected/kostenstellen?includeInactive=true"),
    serverFetch<MeasureRow[]>("/protected/foerdermassnahmen?status=AKTIV"),
  ]);

  // Flat cost-center list (parents + children) for the split dropdowns.
  const costCenters: Array<{ id: string; name: string; code: string }> = [];
  for (const k of kstTree) {
    costCenters.push({ id: k.id, name: k.name, code: k.code });
    for (const c of k.children ?? []) costCenters.push({ id: c.id, name: c.name, code: c.code });
  }
  costCenters.sort((a, b) => a.code.localeCompare(b.code));

  const fundingMeasures = measures.map((m) => ({ id: m.id, name: m.name }));

  return (
    <PageShell width="wide">
      <div className="flex items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-soft-ink">Buchungsregeln</h1>
          <p className="text-sm text-soft-ink3 mt-1">
            Regeln werden beim CSV-Import automatisch angewandt und ersparen manuelle Zuordnung.
          </p>
        </div>
      </div>
      <BuchungsregelnClient
        initialRules={rules}
        costCenters={costCenters}
        fundingMeasures={fundingMeasures}
      />
    </PageShell>
  );
}
