import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";
import type { ProgressionRow } from "@/types/pcm";
import { ProgressionsClient } from "./ProgressionsClient";

export const metadata = {
  title: "Anstehende Stufenaufstiege — FoerderFlow",
};

export default async function ProgressionsPage() {
  await requireOrgSession();
  const rows = await serverFetch<ProgressionRow[]>(
    "/protected/pcm/employees/progressions/upcoming?months_ahead=6",
  );
  return (
    <PageShell width="wide">
      <div className="mb-6">
        <Link
          href="/dashboard/pcm/abrechnung"
          className="inline-flex items-center gap-1 text-sm text-soft-ink3 hover:text-soft-ink mb-2"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          PCM-Abrechnung
        </Link>
        <h1 className="text-2xl font-bold text-soft-ink">Anstehende Stufenaufstiege</h1>
        <p className="text-sm text-soft-ink3 mt-1">
          Mitarbeitende, deren automatischer Stufenaufstieg im gewählten Zeitfenster
          fällig wird. Die Höhergruppierung erfolgt automatisch durch den
          Promotion-Job; dieser Überblick dient der Prüfung der Termine und der
          Kostenwirkung.
        </p>
      </div>
      <ProgressionsClient initialRows={rows} />
    </PageShell>
  );
}
