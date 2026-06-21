import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";
import type { FiscalYearWithMeta } from "@/types/haushaltsjahre";
import type { PcmEmployee, Scenario } from "@/types/pcm";
import { ScenarioClient } from "./ScenarioClient";

export const metadata = {
  title: "Szenario-Planer — FoerderFlow",
};

export default async function SzenarienPage() {
  await requireOrgSession();
  const [scenarios, fiscalYears, employees] = await Promise.all([
    serverFetch<Scenario[]>("/protected/pcm/scenarios"),
    serverFetch<FiscalYearWithMeta[]>("/protected/haushaltsjahre"),
    serverFetch<PcmEmployee[]>("/protected/employees"),
  ]);

  return (
    <PageShell width="wide">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-soft-ink">Szenario-Planer</h1>
        <p className="text-sm text-soft-ink3 mt-1">
          Was-wäre-wenn-Projektionen ohne Festschreibung: Stunden- oder
          Stufenänderungen, Tarifsteigerungen und hypothetische Neueinstellungen
          gegen die aktuelle Prognose vergleichen. Ein Szenario kann übernommen
          werden, um die Ist-Prognose neu zu berechnen.
        </p>
      </div>
      <ScenarioClient scenarios={scenarios} fiscalYears={fiscalYears} employees={employees} />
    </PageShell>
  );
}
