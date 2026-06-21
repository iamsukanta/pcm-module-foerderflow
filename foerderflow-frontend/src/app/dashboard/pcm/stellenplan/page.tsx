import Link from "next/link";
import { Settings2 } from "lucide-react";

import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";
import { Button } from "@/components/ui/Button";
import type { StellenplanMatrix } from "@/types/pcm";
import { StellenplanClient } from "./StellenplanClient";

export const metadata = {
  title: "Stellenplan — FoerderFlow",
};

export default async function StellenplanPage() {
  await requireOrgSession();
  const matrix = await serverFetch<StellenplanMatrix>("/protected/pcm/stellenplan/matrix");

  return (
    <PageShell width="full">
      <div className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-soft-ink">Stellenplan</h1>
          <p className="text-sm text-soft-ink3 mt-1">
            Organisationsweite Verteilung der Wochenstunden je Mitarbeiter:in auf
            Kostenstellen und Projekte. Die Doppelförderungs-Ampel zeigt, ob die
            verplanten Stunden zur vertraglich vereinbarten Arbeitszeit passen.
          </p>
        </div>
        <Link href="/dashboard/pcm/wochenstunden">
          <Button variant="secondary">
            <Settings2 className="h-4 w-4 mr-1" aria-hidden="true" /> Zuweisungen verwalten
          </Button>
        </Link>
      </div>
      <StellenplanClient matrix={matrix} />
    </PageShell>
  );
}
