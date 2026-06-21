import Link from "next/link";

import { requireOrgSession } from "@/lib/session";
import { HaushaltjahrForm } from "@/components/forms/HaushaltjahrForm";
import { PageShell } from "@/components/ui/PageShell";

export const metadata = {
  title: "Neues Haushaltsjahr — FoerderFlow",
};

export default async function NewHaushaltjahrPage() {
  await requireOrgSession();

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
            Neues Haushaltsjahr
          </li>
        </ol>
      </nav>

      <h1 className="text-2xl font-bold text-soft-ink mb-2">Neues Haushaltsjahr anlegen</h1>
      <p className="text-sm text-soft-ink3 mb-8">
        Lege einen neuen Planungs- und Controlling-Zeitraum für deine Organisation an.
      </p>

      <HaushaltjahrForm mode="create" />
    </PageShell>
  );
}
