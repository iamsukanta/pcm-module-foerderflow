import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";
import type { FiscalYearWithMeta } from "@/types/haushaltsjahre";
import { PrognoseClient } from "./PrognoseClient";

export const metadata = {
  title: "Personalkostenprognose — FoerderFlow",
};

export default async function PrognosePage() {
  await requireOrgSession();
  const fiscalYears = await serverFetch<FiscalYearWithMeta[]>("/protected/haushaltsjahre");

  return (
    <PageShell width="full">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-soft-ink">Personalkostenprognose</h1>
        <p className="text-sm text-soft-ink3 mt-1">
          Projiziert die Personalkosten je Mitarbeiter:in und Monat über das
          Haushaltsjahr — inkl. Tarif-Gültigkeitsfenster, Stufenaufstieg, BAV,
          Boni und Anpassungen. Abwesenheiten werden ausgesetzt; Datenlücken
          werden als Warnung markiert.
        </p>
      </div>
      <PrognoseClient fiscalYears={fiscalYears} />
    </PageShell>
  );
}
