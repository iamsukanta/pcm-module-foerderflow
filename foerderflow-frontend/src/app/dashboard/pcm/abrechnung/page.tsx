import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";
import type { FiscalYearWithMeta } from "@/types/haushaltsjahre";
import type { PcmEmployee } from "@/types/pcm";
import { AbrechnungClient } from "./AbrechnungClient";
import { PeriodsOverview } from "./PeriodsOverview";

export const metadata = {
  title: "PCM-Abrechnung — FoerderFlow",
};

export default async function AbrechnungPage() {
  await requireOrgSession();

  const [fiscalYears, employees] = await Promise.all([
    serverFetch<FiscalYearWithMeta[]>("/protected/haushaltsjahre"),
    serverFetch<PcmEmployee[]>("/protected/employees"),
  ]);

  return (
    <PageShell width="wide">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-soft-ink">PCM-Abrechnung</h1>
        <p className="text-sm text-soft-ink3 mt-1">
          Berechnet die Personalkosten eines Monats für alle Mitarbeitenden mit
          aktiver Stundenzuweisung — inkl. Tarif-Gültigkeitsfenster, BAV und
          Förderzuordnung (origin&nbsp;=&nbsp;PCM).
        </p>
      </div>

      <div className="space-y-6">
        <PeriodsOverview fiscalYears={fiscalYears} />
        <AbrechnungClient fiscalYears={fiscalYears} employees={employees} />
      </div>
    </PageShell>
  );
}
