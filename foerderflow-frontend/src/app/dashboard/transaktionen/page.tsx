import Link from "next/link";
import { Upload, CheckCircle2, Circle } from "lucide-react";

import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { TransaktionenClient } from "./TransaktionenClient";
import { PageShell } from "@/components/ui/PageShell";

function PrerequisiteItem({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      {ok ? (
        <CheckCircle2 className="h-4 w-4 text-soft-ok shrink-0" />
      ) : (
        <Circle className="h-4 w-4 text-soft-ink3 shrink-0" />
      )}
      <span className={ok ? "text-soft-ink2" : "text-soft-ink3"}>{label}</span>
    </div>
  );
}

function EmptyTransaktionen({ kstOk, massnahmeOk }: { kstOk: boolean; massnahmeOk: boolean }) {
  return (
    <PageShell width="wide">
      <div className="flex items-center justify-between mb-8 gap-4">
        <h1 className="text-2xl font-bold text-soft-ink">Transaktionen</h1>
      </div>
      <div className="rounded-soft border border-soft-line bg-soft-surface shadow-soft p-10 flex flex-col items-center text-center max-w-lg mx-auto mt-12">
        <div className="rounded-full bg-soft-line2 p-4 mb-4">
          <Upload className="h-8 w-8 text-soft-ink3" />
        </div>
        <h2 className="text-lg font-semibold text-soft-ink mb-2">Noch keine Transaktionen</h2>
        <p className="text-sm text-soft-ink2 mb-6 max-w-sm">
          Importiere deinen Kontoauszug und FoerderFlow ordnet Ausgaben automatisch den richtigen
          Projekten zu.
        </p>
        <Link
          href="/dashboard/transaktionen/import"
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-soft-accent text-white text-sm font-medium rounded-soft-sm hover:bg-soft-accentDark transition-colors mb-6 shadow-soft min-h-[44px]"
        >
          Kontoauszug importieren →
        </Link>
        <div className="w-full border-t border-soft-line pt-4 space-y-2 text-left">
          <p className="text-xs text-soft-ink3 font-medium uppercase tracking-wider mb-2">
            Voraussetzungen
          </p>
          <PrerequisiteItem ok={kstOk} label="Kostenstelle vorhanden" />
          <PrerequisiteItem ok={massnahmeOk} label="Fördermassnahme vorhanden" />
        </div>
      </div>
    </PageShell>
  );
}

export default async function TransaktionenPage() {
  await requireOrgSession();

  const [txSample, kst, massnahmen] = await Promise.all([
    serverFetch<unknown[]>("/protected/transaktionen?limit=1"),
    serverFetch<unknown[]>("/protected/kostenstellen"),
    serverFetch<unknown[]>("/protected/foerdermassnahmen"),
  ]);

  if (txSample.length === 0) {
    return <EmptyTransaktionen kstOk={kst.length > 0} massnahmeOk={massnahmen.length > 0} />;
  }

  return <TransaktionenClient />;
}
