import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { KostenstelleForm } from "@/components/forms/KostenstelleForm";
import { PageShell } from "@/components/ui/PageShell";
import type { KostenstelleWithChildren } from "@/types/kostenstellen";

export const metadata = {
  title: "Neue Kostenstelle — FoerderFlow",
};

export default async function NewKostenstellePage() {
  await requireOrgSession();

  // Mögliche Eltern-KSTs: aktive PROJECT-KSTs ohne eigenes parent.
  const all = await serverFetch<KostenstelleWithChildren[]>("/protected/kostenstellen");
  const parentOptions = all
    .filter((k) => k.ist_aktiv && k.typ === "PROJECT" && !k.parent_id)
    .map((k) => ({ id: k.id, name: k.name, code: k.code }));

  return (
    <PageShell width="form">
      {/* Back Link */}
      <Link
        href="/dashboard/kostenstellen"
        className="inline-flex items-center gap-1 text-sm text-soft-ink3 hover:text-soft-ink2 mb-6
          focus:outline-none focus:ring-2 focus:ring-soft-accent rounded"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Zurück zu Kostenstellen
      </Link>

      <div className="bg-white rounded-soft border border-soft-line p-6 sm:p-8">
        <h1 className="text-xl font-bold text-soft-ink mb-1">Neue Kostenstelle</h1>
        <p className="text-sm text-soft-ink3 mb-6">
          Kostenstellen sind die Zurechnungseinheiten für Personalkosten und Sachausgaben.
        </p>

        <KostenstelleForm mode="create" parentOptions={parentOptions} />
      </div>
    </PageShell>
  );
}
