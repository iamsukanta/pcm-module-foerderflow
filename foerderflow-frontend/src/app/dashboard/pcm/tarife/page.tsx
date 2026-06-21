import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";
import type { TariffCodeSummary } from "@/types/pcm";
import { TariffCodeListClient } from "./TariffCodeListClient";

export const metadata = {
  title: "Tarif-Register — FoerderFlow",
};

export default async function TarifePage() {
  await requireOrgSession();

  const codes = await serverFetch<TariffCodeSummary[]>("/protected/pcm/tariff-codes");
  const employeesCovered = codes.reduce((sum, c) => sum + c.employee_count, 0);

  return (
    <PageShell width="wide">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-soft-ink">Tarif-Register</h1>
        <p className="text-sm text-soft-ink3 mt-1">
          {codes.length} Tarifverträge · {employeesCovered} Mitarbeitende erfasst.
          Jede Tarifvereinbarung trägt Entgelt-Tabellen mit Gültigkeitsfenstern;
          zwei sich nicht überschneidende Fenster bilden einen unterjährigen
          Tarifwechsel.
        </p>
      </div>

      <TariffCodeListClient codes={codes} />
    </PageShell>
  );
}
