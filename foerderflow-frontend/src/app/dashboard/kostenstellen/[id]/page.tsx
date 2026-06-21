import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeft } from "lucide-react";

import { requireOrgSession } from "@/lib/session";
import { ApiError, serverFetch } from "@/lib/serverApi";
import { KostenstelleForm } from "@/components/forms/KostenstelleForm";
import { Badge } from "@/components/ui/Badge";
import { PageShell } from "@/components/ui/PageShell";
import type { KostenstelleWithChildren } from "@/types/kostenstellen";
import { KostenstelleDeactivateButton } from "./KostenstelleDeactivateButton";

type FundingMeasureBrief = {
  id: string;
  name: string;
  status: "AKTIV" | "ABGESCHLOSSEN" | "WIDERRUFEN" | string;
  laufzeit_von: string;
  laufzeit_bis: string;
};

type KostenstelleDetail = KostenstelleWithChildren & {
  children: Array<KostenstelleWithChildren>;
  funding_measure_cost_centers: Array<{
    id: string;
    funding_measure_id: string;
    funding_measure: FundingMeasureBrief;
  }>;
};

export async function generateMetadata() {
  return { title: `Kostenstelle bearbeiten — FoerderFlow` };
}

export default async function KostenstelleDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireOrgSession();
  const { id } = await params;

  let kst: KostenstelleDetail;
  try {
    kst = await serverFetch<KostenstelleDetail>(`/protected/kostenstellen/${id}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }

  // Mögliche Eltern-KSTs (aktive PROJECT-KSTs ohne parent, außer sich selbst)
  const all = await serverFetch<KostenstelleWithChildren[]>("/protected/kostenstellen");
  const parentOptions = all
    .filter((k) => k.ist_aktiv && k.typ === "PROJECT" && !k.parent_id && k.id !== id)
    .map((k) => ({ id: k.id, name: k.name, code: k.code }));

  const statusVariant = kst.ist_aktiv ? "success" : "muted";

  return (
    <PageShell width="form">
      {/* Back Link */}
      <Link
        href="/dashboard/kostenstellen"
        className="inline-flex items-center gap-1 text-sm text-soft-ink3 hover:text-soft-ink2
          focus:outline-none focus:ring-2 focus:ring-soft-accent rounded"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Zurück zu Kostenstellen
      </Link>

      {/* Header Card */}
      <div className="bg-white rounded-soft border border-soft-line p-6">
        <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
          <div>
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <h1
                className={`text-xl font-bold ${kst.ist_aktiv ? "text-soft-ink" : "text-soft-ink3"}`}
              >
                {kst.name}
              </h1>
              <Badge variant="muted" className="font-mono text-xs">
                {kst.code}
              </Badge>
              <Badge variant={kst.typ === "PROJECT" ? "default" : "warning"}>
                {kst.typ === "PROJECT" ? "Projekt" : "Overhead"}
              </Badge>
              <Badge variant={statusVariant}>{kst.ist_aktiv ? "Aktiv" : "Inaktiv"}</Badge>
            </div>

            {kst.parent && (
              <p className="text-sm text-soft-ink3">
                Untergeordnet:{" "}
                <Link
                  href={`/dashboard/kostenstellen/${kst.parent.id}`}
                  className="text-soft-accent hover:underline focus:ring-2 focus:ring-soft-accent rounded"
                >
                  {kst.parent.name} ({kst.parent.code})
                </Link>
              </p>
            )}
          </div>

          {/* Deactivate button (client component for dialog) */}
          {kst.ist_aktiv && (
            <KostenstelleDeactivateButton
              kstId={kst.id}
              kstName={kst.name}
              kstCode={kst.code}
              activeChildrenCount={kst.children.filter((c) => c.ist_aktiv).length}
            />
          )}
        </div>

        {/* Zugeordnete Fördermassnahmen */}
        {kst.funding_measure_cost_centers.length > 0 && (
          <div className="border-t border-soft-line2 pt-4 mt-4">
            <h2 className="text-sm font-medium text-soft-ink2 mb-3">
              Zugeordnete Fördermassnahmen ({kst.funding_measure_cost_centers.length})
            </h2>
            <ul className="space-y-2">
              {kst.funding_measure_cost_centers.map(({ id: linkId, funding_measure }) => (
                <li
                  key={linkId}
                  className="flex items-center justify-between rounded-soft-xs bg-soft-line2 px-3 py-2 text-sm"
                >
                  <span className="text-soft-ink2">{funding_measure.name}</span>
                  <Badge
                    variant={
                      funding_measure.status === "AKTIV"
                        ? "success"
                        : funding_measure.status === "ABGESCHLOSSEN"
                          ? "muted"
                          : "danger"
                    }
                  >
                    {funding_measure.status === "AKTIV"
                      ? "Aktiv"
                      : funding_measure.status === "ABGESCHLOSSEN"
                        ? "Abgeschlossen"
                        : "Widerrufen"}
                  </Badge>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Edit Form */}
      {kst.ist_aktiv ? (
        <div className="bg-white rounded-soft border border-soft-line p-6 sm:p-8 mt-6">
          <h2 className="text-lg font-semibold text-soft-ink mb-1">Kostenstelle bearbeiten</h2>
          <p className="text-sm text-soft-ink3 mb-6">Änderungen werden sofort gespeichert.</p>

          <KostenstelleForm
            mode="edit"
            kstId={kst.id}
            initialValues={{
              name: kst.name,
              code: kst.code,
              typ: kst.typ,
              parent_id: kst.parent_id,
            }}
            parentOptions={parentOptions}
          />
        </div>
      ) : (
        <div
          role="alert"
          className="rounded-soft-sm bg-soft-warnSoft border border-soft-warn/30 p-4 text-sm text-soft-warn mt-6"
        >
          Diese Kostenstelle ist deaktiviert und kann nicht mehr bearbeitet werden. Historische
          Buchungsdaten bleiben vollständig erhalten.
        </div>
      )}
    </PageShell>
  );
}
