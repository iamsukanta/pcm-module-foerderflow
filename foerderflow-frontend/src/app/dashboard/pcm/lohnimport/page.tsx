import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";
import type { PayrollImportBatchRow } from "@/types/pcm";
import { LohnimportClient } from "./LohnimportClient";

export const metadata = { title: "Lohnimport — FoerderFlow" };

export default async function LohnimportPage() {
  await requireOrgSession();
  const batches = await serverFetch<PayrollImportBatchRow[]>("/protected/pcm/payroll-import/batches");

  return (
    <PageShell width="wide">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-soft-ink">Lohnimport</h1>
        <p className="text-sm text-soft-ink3 mt-1">
          Externe Lohndaten importieren (DATEV, Personio, Quartals-CSV oder
          Diamant-BAB). Beträge werden den Mitarbeitenden zugeordnet, über die
          Monate verteilt und in die Monatsabrechnung übernommen.
        </p>
      </div>
      <LohnimportClient batches={batches} />
    </PageShell>
  );
}
