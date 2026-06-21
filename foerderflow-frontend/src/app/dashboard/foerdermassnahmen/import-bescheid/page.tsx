import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { loadActiveCostCentersForForms } from "@/lib/costCenters";
import { BescheidImportClient } from "./BescheidImportClient";
import { PageShell } from "@/components/ui/PageShell";
import type { FunderTyp } from "@/types/foerdermassnahmen";

type FunderOption = { id: string; name: string; typ: FunderTyp };

export default async function BescheidImportPage() {
  await requireOrgSession();

  const [funders, costCenters] = await Promise.all([
    serverFetch<FunderOption[]>("/protected/funder"),
    loadActiveCostCentersForForms(),
  ]);

  return (
    <PageShell width="content">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-soft-ink">Bescheid importieren</h1>
        <p className="text-sm text-soft-ink3 mt-1">
          PDF-Bescheid hochladen — Felder werden automatisch per OCR extrahiert und zur Prüfung
          vorgelegt.
        </p>
      </div>

      <BescheidImportClient
        funders={funders.map((f) => ({ id: f.id, name: f.name, typ: f.typ }))}
        costCenters={costCenters}
      />
    </PageShell>
  );
}
