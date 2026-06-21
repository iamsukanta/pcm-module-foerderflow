import Link from "next/link";

import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { VerteilungsschluesselList } from "./VerteilungsschluesselList";
import type { AllocationKeyWithPositions } from "@/types/verteilungsschluessel";
import { PageShell } from "@/components/ui/PageShell";

export const metadata = {
  title: "Verteilungsschlüssel — FoerderFlow",
};

export default async function VerteilungsschluesselPage() {
  await requireOrgSession();

  // Backend liefert positions+summe_prozent+is_valid und Daten als YYYY-MM-DD direkt.
  const keys = await serverFetch<AllocationKeyWithPositions[]>(
    "/protected/verteilungsschluessel?includeInactive=true",
  );

  const activeCount = keys.filter((k) => k.ist_aktiv).length;
  const inactiveCount = keys.filter((k) => !k.ist_aktiv).length;

  return (
    <PageShell width="wide">
      {/* Header */}
      <div className="flex items-start justify-between mb-8 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-soft-ink">Verteilungsschlüssel</h1>
          <p className="text-sm text-soft-ink3 mt-1">
            {activeCount} aktiv
            {inactiveCount > 0 && `, ${inactiveCount} inaktiv`}
          </p>
        </div>
        <Link
          href="/dashboard/verteilungsschluessel/new"
          className="inline-flex items-center justify-center rounded-soft-sm bg-soft-accent px-4 py-2.5 text-sm font-medium text-white
            hover:bg-soft-accentDark active:bg-soft-accentDark transition-colors min-h-[44px] shadow-soft
            focus:outline-none focus:ring-2 focus:ring-soft-accent focus:ring-offset-2"
        >
          + Neuer Schlüssel
        </Link>
      </div>

      {/* List */}
      <VerteilungsschluesselList allocationKeys={keys} />
    </PageShell>
  );
}
