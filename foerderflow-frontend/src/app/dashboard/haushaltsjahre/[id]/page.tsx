import Link from "next/link";
import { notFound } from "next/navigation";
import { Lock } from "lucide-react";

import { requireOrgSession } from "@/lib/session";
import { ApiError, serverFetch } from "@/lib/serverApi";
import { Badge } from "@/components/ui/Badge";
import { HaushaltjahrForm } from "@/components/forms/HaushaltjahrForm";
import { FiscalYearCloseForm } from "@/components/forms/FiscalYearCloseForm";
import type { FiscalYearWithMeta } from "@/types/haushaltsjahre";
import { PageShell } from "@/components/ui/PageShell";

export const metadata = {
  title: "Haushaltsjahr — FoerderFlow",
};

type PageProps = {
  params: Promise<{ id: string }>;
};

function formatDateDE(dateString: string): string {
  return new Date(dateString).toLocaleDateString("de-DE", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export default async function HaushaltjahrDetailPage({ params }: PageProps) {
  await requireOrgSession();
  const { id } = await params;

  let fiscalYear: FiscalYearWithMeta;
  try {
    fiscalYear = await serverFetch<FiscalYearWithMeta>(`/protected/haushaltsjahre/${id}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }

  const isOpen = fiscalYear.status === "OFFEN";

  return (
    <PageShell width="form">
      {/* Breadcrumb */}
      <nav aria-label="Breadcrumb" className="mb-6">
        <ol className="flex items-center gap-2 text-sm text-soft-ink3">
          <li>
            <Link
              href="/dashboard/haushaltsjahre"
              className="hover:text-soft-ink2 focus:outline-none focus:ring-2 focus:ring-soft-accent rounded"
            >
              Haushaltsjahre
            </Link>
          </li>
          <li aria-hidden="true" className="text-soft-ink4">
            /
          </li>
          <li className="text-soft-ink font-medium" aria-current="page">
            {fiscalYear.jahr}
          </li>
        </ol>
      </nav>

      {/* Header */}
      <div className="flex items-center gap-3 mb-2">
        <h1 className="text-2xl font-bold text-soft-ink">Haushaltsjahr {fiscalYear.jahr}</h1>
        {isOpen ? (
          <Badge variant="default">Aktiv</Badge>
        ) : (
          <Badge variant="muted">
            <Lock className="h-3 w-3 mr-1 inline" />
            Geschlossen
          </Badge>
        )}
      </div>
      <p className="text-sm text-soft-ink3 mb-8">
        {formatDateDE(fiscalYear.beginn)} – {formatDateDE(fiscalYear.ende)}
      </p>

      {/* Closed state: audit info */}
      {!isOpen && fiscalYear.geschlossen_am && (
        <div className="mb-8 rounded-soft-sm border border-soft-line bg-soft-line2 p-4" role="status">
          <p className="text-sm text-soft-ink2">
            <span className="font-medium">Geschlossen am:</span>{" "}
            {formatDateDE(fiscalYear.geschlossen_am)}
          </p>
          <p className="text-sm text-soft-ink3 mt-1">
            Keine weiteren Buchungen für dieses Haushaltsjahr möglich.
          </p>
        </div>
      )}

      {/* Edit Form — only for OFFEN years */}
      {isOpen ? (
        <section aria-labelledby="edit-section-heading">
          <h2 id="edit-section-heading" className="text-base font-semibold text-soft-ink mb-4">
            Zeitraum bearbeiten
          </h2>
          <HaushaltjahrForm
            mode="edit"
            fiscalYearId={fiscalYear.id}
            initialValues={{
              jahr: fiscalYear.jahr,
              beginn: fiscalYear.beginn,
              ende: fiscalYear.ende,
            }}
          />
        </section>
      ) : (
        <section
          aria-labelledby="details-section-heading"
          className="rounded-soft-sm border border-soft-line bg-white p-5"
        >
          <h2
            id="details-section-heading"
            className="text-sm font-semibold text-soft-ink3 uppercase tracking-wide mb-3"
          >
            Details
          </h2>
          <dl className="space-y-3">
            <div className="flex justify-between text-sm">
              <dt className="text-soft-ink3">Jahr</dt>
              <dd className="font-medium text-soft-ink">{fiscalYear.jahr}</dd>
            </div>
            <div className="flex justify-between text-sm">
              <dt className="text-soft-ink3">Beginn</dt>
              <dd className="font-medium text-soft-ink">{formatDateDE(fiscalYear.beginn)}</dd>
            </div>
            <div className="flex justify-between text-sm">
              <dt className="text-soft-ink3">Ende</dt>
              <dd className="font-medium text-soft-ink">{formatDateDE(fiscalYear.ende)}</dd>
            </div>
            <div className="flex justify-between text-sm">
              <dt className="text-soft-ink3">Status</dt>
              <dd>
                <Badge variant="muted">
                  <Lock className="h-3 w-3 mr-1 inline" />
                  Geschlossen
                </Badge>
              </dd>
            </div>
          </dl>
        </section>
      )}

      {/* Close Form — only for OFFEN years */}
      {isOpen && <FiscalYearCloseForm fiscalYear={fiscalYear} />}
    </PageShell>
  );
}
