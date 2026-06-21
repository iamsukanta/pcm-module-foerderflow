import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";
import type { FiscalYearWithMeta } from "@/types/haushaltsjahre";
import type { FundingMeasureRef } from "@/types/pcm";
import { AllocationsClient } from "./AllocationsClient";

export const metadata = { title: "Lohnkostenzuordnungen — FoerderFlow" };

export default async function ZuordnungenPage() {
  await requireOrgSession();
  const [fiscalYears, fundingMeasures] = await Promise.all([
    serverFetch<FiscalYearWithMeta[]>("/protected/haushaltsjahre"),
    serverFetch<FundingMeasureRef[]>("/protected/foerdermassnahmen"),
  ]);

  return (
    <PageShell width="wide">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-soft-ink">Lohnkostenzuordnungen</h1>
        <p className="text-sm text-soft-ink3 mt-1">
          Wohin die vom Abrechnungslauf erzeugten Personalkosten geflossen sind —
          je Monat nach Fördermaßnahme, oder je Projekt über alle Monate.
        </p>
      </div>
      <AllocationsClient fiscalYears={fiscalYears} fundingMeasures={fundingMeasures} />
    </PageShell>
  );
}
