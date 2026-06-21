import Link from "next/link";

import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";
import type { KostenstelleWithChildren } from "@/types/kostenstellen";
import { KostenstellenList } from "./KostenstellenList";

export const metadata = {
  title: "Kostenstellen — FoerderFlow",
};

export default async function KostenstellenPage({
  searchParams,
}: {
  searchParams: Promise<{ filter?: string }>;
}) {
  const { org } = await requireOrgSession();
  const { filter } = await searchParams;
  const activeFilter = filter ?? "alle";

  // Server-side: alle KSTs laden (inkl. inaktive)
  const allKostenstellen = await serverFetch<KostenstelleWithChildren[]>(
    "/protected/kostenstellen?includeInactive=true",
  );

  return (
    <PageShell width="wide">
      {/* Header */}
      <div className="flex items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-soft-ink">Kostenstellen</h1>
          <p className="text-sm text-soft-ink3 mt-1">
            {allKostenstellen.filter((k) => k.ist_aktiv).length} aktiv
            {allKostenstellen.some((k) => !k.ist_aktiv) &&
              `, ${allKostenstellen.filter((k) => !k.ist_aktiv).length} inaktiv`}
          </p>
        </div>
        <Link
          href="/dashboard/kostenstellen/new"
          className="inline-flex items-center justify-center rounded-soft-sm bg-soft-accent px-4 py-2.5 text-sm font-medium text-white
            hover:bg-soft-accentDark active:bg-soft-accentDark transition-colors min-h-[44px] shadow-soft
            focus:outline-none focus:ring-2 focus:ring-soft-accent focus:ring-offset-2"
        >
          + Neue Kostenstelle
        </Link>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-1 mb-6 bg-soft-line2 rounded-soft-sm p-1 w-fit">
        {[
          { value: "alle", label: "Alle" },
          { value: "projekte", label: "Projekte" },
          { value: "overhead", label: "Overhead" },
          { value: "inaktiv", label: "Inaktiv" },
        ].map((tab) => (
          <Link
            key={tab.value}
            href={`/dashboard/kostenstellen?filter=${tab.value}`}
            className={`px-3 py-1.5 rounded-soft-xs text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-soft-accent min-h-[36px] flex items-center
              ${
                activeFilter === tab.value
                  ? "bg-soft-surface text-soft-ink shadow-soft"
                  : "text-soft-ink2 hover:text-soft-ink"
              }`}
          >
            {tab.label}
          </Link>
        ))}
      </div>

      {/* List — interactive part (Client Component) */}
      <KostenstellenList
        kostenstellen={allKostenstellen}
        activeFilter={activeFilter}
        orgId={org.id}
      />
    </PageShell>
  );
}
