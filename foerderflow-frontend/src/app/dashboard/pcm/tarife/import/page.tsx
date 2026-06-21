import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { requireOrgSession } from "@/lib/session";
import { PageShell } from "@/components/ui/PageShell";
import { ImportWizardClient } from "./ImportWizardClient";

export const metadata = {
  title: "Tarif-Import — FoerderFlow",
};

export default async function TariffImportPage() {
  await requireOrgSession();
  return (
    <PageShell width="wide">
      <div className="mb-6">
        <Link
          href="/dashboard/pcm/tarife"
          className="inline-flex items-center gap-1 text-sm text-soft-ink3 hover:text-soft-ink mb-2"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          Tarif-Register
        </Link>
        <h1 className="text-2xl font-bold text-soft-ink">Tarifvereinbarung importieren</h1>
        <p className="text-sm text-soft-ink3 mt-1">
          Lade eine Entgelt-Tabelle als CSV/Excel hoch oder übertrage sie manuell.
          Der Assistent prüft Überschneidungen, bevor geschrieben wird.
        </p>
      </div>
      <ImportWizardClient />
    </PageShell>
  );
}
