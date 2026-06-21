import Link from "next/link";

import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { Button } from "@/components/ui/Button";
import { PageShell } from "@/components/ui/PageShell";
import { berechneAmpel } from "@/lib/ampel";
import type { KostenstelleWithChildren } from "@/types/kostenstellen";
import { FoerdermassnahmenClient } from "./FoerdermassnahmenClient";
import type { FundingMeasureStatus } from "@/types/foerdermassnahmen";

const STATUS_TABS: { label: string; value: FundingMeasureStatus | "ALL" }[] = [
  { label: "Alle", value: "ALL" },
  { label: "Aktiv", value: "AKTIV" },
  { label: "Abgeschlossen", value: "ABGESCHLOSSEN" },
  { label: "Widerrufen", value: "WIDERRUFEN" },
];

type MeasureApiRow = {
  id: string;
  name: string;
  status: FundingMeasureStatus;
  budget_gesamt: string;
  foerderquote: string;
  overhead_limit_prozent: string | null;
  laufzeit_von: string;
  laufzeit_bis: string;
  is_expired: boolean;
  days_until_expiry: number | null;
  betrag_ist: number;
  funder: { id: string; name: string; typ: string };
  _count: { rules: number; cost_centers: number };
};

type PageProps = {
  searchParams: Promise<{ status?: string }>;
};

export default async function FoerdermassnahmenPage({ searchParams }: PageProps) {
  await requireOrgSession();
  const sp = await searchParams;
  const statusFilter = sp.status as FundingMeasureStatus | undefined;

  const VALID_STATUS: FundingMeasureStatus[] = ["AKTIV", "ABGESCHLOSSEN", "WIDERRUFEN"];
  const activeFilter = statusFilter && VALID_STATUS.includes(statusFilter) ? statusFilter : undefined;

  const query = activeFilter ? `?status=${activeFilter}` : "";
  const [measures, kstTree] = await Promise.all([
    serverFetch<MeasureApiRow[]>(`/protected/foerdermassnahmen${query}`),
    serverFetch<KostenstelleWithChildren[]>("/protected/kostenstellen?includeInactive=true"),
  ]);

  const kstCount = kstTree.reduce((n, k) => n + 1 + (k.children?.length ?? 0), 0);

  const enriched = measures.map((m) => {
    const budget_gesamt = parseFloat(m.budget_gesamt);
    const foerderquote = parseFloat(m.foerderquote);
    const overhead_limit_prozent = m.overhead_limit_prozent
      ? parseFloat(m.overhead_limit_prozent)
      : null;
    const betrag_ist = m.betrag_ist ?? 0;
    const betrag_bewilligt = (budget_gesamt * foerderquote) / 100;
    const ampel = berechneAmpel({
      betrag_bewilligt,
      betrag_ist,
      laufzeit_von: new Date(m.laufzeit_von),
      laufzeit_bis: new Date(m.laufzeit_bis),
      overhead_limit_prozent,
      overhead_ist_prozent: 0,
    });
    return {
      id: m.id,
      name: m.name,
      status: m.status,
      budget_gesamt,
      foerderquote,
      overhead_limit_prozent,
      laufzeit_von: new Date(m.laufzeit_von),
      laufzeit_bis: new Date(m.laufzeit_bis),
      funder: m.funder,
      _count: m._count,
      is_expired: m.is_expired,
      days_until_expiry: m.days_until_expiry,
      betrag_ist,
      betrag_bewilligt,
      ampelStatus: ampel.status,
      ampelGruende: ampel.gruende,
    };
  });

  const currentTab = activeFilter ?? "ALL";

  return (
    <PageShell width="wide">
      {/* Header */}
      <div className="flex items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-soft-ink">Fördermassnahmen</h1>
          <p className="text-sm text-soft-ink3 mt-1">
            Alle bewilligten Förderprogramme der Organisation
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/dashboard/foerdermassnahmen/import-bescheid">
            <Button variant="secondary">Bescheid importieren</Button>
          </Link>
          <Link href="/dashboard/foerdermassnahmen/new">
            <Button variant="primary">+ Neue Massnahme</Button>
          </Link>
        </div>
      </div>

      {/* Status Tabs */}
      <div className="flex gap-1 mb-6 border-b border-soft-line">
        {STATUS_TABS.map((tab) => {
          const isActive = tab.value === currentTab;
          const href =
            tab.value === "ALL"
              ? "/dashboard/foerdermassnahmen"
              : `/dashboard/foerdermassnahmen?status=${tab.value}`;
          return (
            <Link
              key={tab.value}
              href={href}
              className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px
                ${
                  isActive
                    ? "border-soft-accent text-soft-accent"
                    : "border-transparent text-soft-ink2 hover:text-soft-ink hover:border-soft-line"
                }`}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>

      {/* Client component with search and cards */}
      <FoerdermassnahmenClient
        measures={enriched}
        kstCount={kstCount}
        activeFilter={activeFilter}
      />
    </PageShell>
  );
}
