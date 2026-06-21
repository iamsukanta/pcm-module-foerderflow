import Link from "next/link";

import { requireOrgSession } from "@/lib/session";
import { loadActiveCostCenters } from "@/lib/costCenters";
import { VerteilungsschluesselForm } from "@/components/forms/VerteilungsschluesselForm";
import { PageShell } from "@/components/ui/PageShell";

export const metadata = {
  title: "Neuer Verteilungsschlüssel — FoerderFlow",
};

export default async function NeuerVerteilungsschluesselPage() {
  await requireOrgSession();

  // Nur aktive PROJECT- und OVERHEAD-KSTs anbieten
  const all = await loadActiveCostCenters();
  const costCenters = all.filter((c) => c.typ === "PROJECT" || c.typ === "OVERHEAD");

  return (
    <PageShell width="form">
      {/* Breadcrumb */}
      <nav aria-label="Breadcrumb" className="mb-6 text-sm text-soft-ink3">
        <Link href="/dashboard/verteilungsschluessel" className="hover:text-soft-ink2 hover:underline">
          Verteilungsschlüssel
        </Link>
        <span className="mx-2" aria-hidden="true">
          ›
        </span>
        <span className="text-soft-ink font-medium">Neuer Schlüssel</span>
      </nav>

      <h1 className="text-2xl font-bold text-soft-ink mb-2">Neuen Verteilungsschlüssel anlegen</h1>
      <p className="text-sm text-soft-ink3 mb-8">
        Ein Verteilungsschlüssel legt fest, wie gemeinsame Kosten auf Ihre Kostenstellen aufgeteilt
        werden — zum Beispiel Miete, Telefon oder IT. Die Summe der Anteile muss exakt 100&nbsp;%
        ergeben.
      </p>

      <VerteilungsschluesselForm mode="create" availableCostCenters={costCenters} />
    </PageShell>
  );
}
