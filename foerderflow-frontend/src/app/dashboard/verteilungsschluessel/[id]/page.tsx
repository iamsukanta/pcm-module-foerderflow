import Link from "next/link";
import { notFound } from "next/navigation";

import { requireOrgSession } from "@/lib/session";
import { ApiError, serverFetch } from "@/lib/serverApi";
import { loadActiveCostCenters } from "@/lib/costCenters";
import { Badge } from "@/components/ui/Badge";
import { VerteilungsschluesselDetailClient } from "./VerteilungsschluesselDetailClient";
import {
  ALLOCATION_BASIS_LABELS,
  type AllocationKeyWithPositions,
} from "@/types/verteilungsschluessel";
import { PageShell } from "@/components/ui/PageShell";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return { title: `Verteilungsschlüssel ${id} — FoerderFlow` };
}

function formatDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}

export default async function VerteilungsschluesselDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ action?: string }>;
}) {
  await requireOrgSession();
  const { id } = await params;
  const { action } = await searchParams;

  let allocationKey: AllocationKeyWithPositions;
  try {
    allocationKey = await serverFetch<AllocationKeyWithPositions>(
      `/protected/verteilungsschluessel/${id}`,
    );
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }

  // Kostenstellen für neue-version-Formular (aktive PROJECT/OVERHEAD)
  const all = await loadActiveCostCenters();
  const costCenters = all.filter((c) => c.typ === "PROJECT" || c.typ === "OVERHEAD");

  const showNeueVersion = action === "neue-version";

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
        <span className="text-soft-ink font-medium truncate max-w-xs inline-block align-middle">
          {allocationKey.name}
        </span>
      </nav>

      {/* Header */}
      <div className="flex items-start gap-3 mb-8">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-soft-ink truncate">{allocationKey.name}</h1>
            {allocationKey.ist_aktiv ? (
              <Badge variant="success">Aktiv</Badge>
            ) : (
              <Badge variant="muted">Inaktiv</Badge>
            )}
            <Badge variant="default">{ALLOCATION_BASIS_LABELS[allocationKey.basis]}</Badge>
          </div>
          <p className="text-sm text-soft-ink3">
            Gültig: {formatDate(allocationKey.gueltig_von)} –{" "}
            {allocationKey.gueltig_bis ? formatDate(allocationKey.gueltig_bis) : "unbegrenzt"}
          </p>
        </div>
      </div>

      {/* Interactive: edit form + neue-version form */}
      <VerteilungsschluesselDetailClient
        allocationKey={allocationKey}
        availableCostCenters={costCenters}
        initialShowNeueVersion={showNeueVersion}
      />
    </PageShell>
  );
}
