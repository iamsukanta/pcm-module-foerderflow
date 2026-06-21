import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";
import type { PcmBavConfig, PcmExternalId, PcmSettingsOverview } from "@/types/pcm";
import { SettingsClient } from "./SettingsClient";

export const metadata = { title: "PCM-Einstellungen — FoerderFlow" };

export default async function PcmSettingsPage() {
  await requireOrgSession();
  const [overview, bav, externalIds] = await Promise.all([
    serverFetch<PcmSettingsOverview>("/protected/pcm/settings/overview"),
    serverFetch<PcmBavConfig>("/protected/pcm/settings/bav"),
    serverFetch<PcmExternalId[]>("/protected/pcm/settings/external-ids"),
  ]);

  return (
    <PageShell width="wide">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-soft-ink">PCM-Einstellungen</h1>
        <p className="text-sm text-soft-ink3 mt-1">
          Grundkonfiguration des Personalkostenmoduls: Einrichtungs-Status,
          org-weiter BAV-Satz und die Zuordnung externer Personalnummern für den
          Lohnimport.
        </p>
      </div>
      <SettingsClient overview={overview} bav={bav} externalIds={externalIds} />
    </PageShell>
  );
}
