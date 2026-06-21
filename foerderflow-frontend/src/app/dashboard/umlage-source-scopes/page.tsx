import Link from "next/link";

import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";
import { UmlageSourceScopeList } from "./UmlageSourceScopeList";

export const metadata = {
  title: "Umlage-Pools — FoerderFlow",
};

type ScopeApiRow = {
  id: string;
  name: string;
  beschreibung: string | null;
  position_count: number;
  cost_centers: Array<{
    cost_center_id: string;
    cost_center: { id: string; code: string; name: string; typ: string };
  }>;
};

export default async function UmlageSourceScopesPage() {
  await requireOrgSession();

  const scopes = await serverFetch<ScopeApiRow[]>("/protected/umlage-source-scopes");

  const data = scopes.map((s) => ({
    id: s.id,
    name: s.name,
    beschreibung: s.beschreibung,
    cost_centers: s.cost_centers.map((c) => ({
      cost_center_id: c.cost_center_id,
      code: c.cost_center.code,
      name: c.cost_center.name,
      typ: c.cost_center.typ,
    })),
    position_count: s.position_count,
  }));

  return (
    <PageShell width="wide">
      <div className="flex items-start justify-between mb-8 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-soft-ink">Umlage-Pools</h1>
          <p className="text-sm text-soft-ink3 mt-1 max-w-2xl">
            Pools von Quell-Kostenstellen für Verwaltungspauschalen vom Typ{" "}
            <strong>UMLAGE_KOSTENSTELLEN</strong> (ANBest-P „anteilige Geschäftsstelle nach
            Verteilungsschlüssel&ldquo;). Pro Bescheid einmal pflegen, von n Pauschale-Positionen
            wiederverwendbar.
          </p>
        </div>
        <Link
          href="/dashboard/umlage-source-scopes/new"
          className="inline-flex items-center justify-center rounded-soft-sm bg-soft-accent px-4 py-2.5 text-sm font-medium text-white
            hover:bg-soft-accentDark active:bg-soft-accentDark transition-colors min-h-[44px] shadow-soft
            focus:outline-none focus:ring-2 focus:ring-soft-accent focus:ring-offset-2"
        >
          + Neuer Pool
        </Link>
      </div>

      <UmlageSourceScopeList scopes={data} />
    </PageShell>
  );
}
