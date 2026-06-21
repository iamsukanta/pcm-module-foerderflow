import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";
import type { FundingMeasureRef } from "@/types/pcm";
import { VwnClient } from "./VwnClient";

export const metadata = { title: "VWN-Personalkostenbericht — FoerderFlow" };

export default async function VwnPage() {
  await requireOrgSession();
  const fundingMeasures = await serverFetch<FundingMeasureRef[]>("/protected/foerdermassnahmen");

  return (
    <PageShell width="wide">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-soft-ink">VWN-Personalkostenbericht</h1>
        <p className="text-sm text-soft-ink3 mt-1">
          Aufgeschlüsselte Personalkosten je Fördermaßnahme und Berichtszeitraum
          für den Verwendungsnachweis. Die Abrechnungspositionen werden anteilig
          der Förderzuordnung zugeordnet; die Spalten sind je Maßnahme konfigurierbar.
        </p>
      </div>
      <VwnClient fundingMeasures={fundingMeasures} />
    </PageShell>
  );
}
