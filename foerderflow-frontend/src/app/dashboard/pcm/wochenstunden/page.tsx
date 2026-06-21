import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";
import type { KostenstelleWithChildren } from "@/types/kostenstellen";
import type { FlatCostCenter, PcmEmployee, WochenstundenZuweisung } from "@/types/pcm";
import { WochenstundenClient } from "./WochenstundenClient";

export const metadata = {
  title: "Wochenstunden — FoerderFlow",
};

function flatten(items: KostenstelleWithChildren[]): FlatCostCenter[] {
  const out: FlatCostCenter[] = [];
  for (const c of items) {
    if (c.ist_aktiv) out.push({ id: c.id, code: c.code, name: c.name });
    for (const child of c.children ?? []) {
      if (child.ist_aktiv) out.push({ id: child.id, code: child.code, name: child.name });
    }
  }
  return out.sort((a, b) => a.code.localeCompare(b.code));
}

export default async function WochenstundenPage() {
  await requireOrgSession();

  const [employees, costCenters, assignments] = await Promise.all([
    serverFetch<PcmEmployee[]>("/protected/employees"),
    serverFetch<KostenstelleWithChildren[]>("/protected/kostenstellen"),
    serverFetch<WochenstundenZuweisung[]>("/protected/pcm/wochenstunden-zuweisungen"),
  ]);

  return (
    <PageShell width="wide">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-soft-ink">Wochenstunden-Zuweisungen</h1>
        <p className="text-sm text-soft-ink3 mt-1">
          Verteilt die vertraglichen Wochenstunden auf Kostenstellen. Die Summe darf
          die vertraglich vereinbarten Stunden nicht überschreiten
          (Doppelförderungs-Sperre).
        </p>
      </div>

      <WochenstundenClient
        employees={employees.filter((e) => e.ist_aktiv)}
        costCenters={flatten(costCenters)}
        assignments={assignments}
      />
    </PageShell>
  );
}
