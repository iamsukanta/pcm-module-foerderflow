import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";
import type { PcmEmployee } from "@/types/pcm";
import { ZulagenClient } from "./ZulagenClient";

export const metadata = {
  title: "Zulagen & Boni — FoerderFlow",
};

export default async function ZulagenPage() {
  await requireOrgSession();
  const employees = await serverFetch<PcmEmployee[]>("/protected/employees");

  return (
    <PageShell width="wide">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-soft-ink">Zulagen &amp; Boni</h1>
        <p className="text-sm text-soft-ink3 mt-1">
          Individuelle Boni und Gehaltsanpassungen je Mitarbeiter:in
          (Münchenzulage, Jobticket, Prämien, Abzüge). Diese fließen direkt in die
          Abrechnung ein; ein individueller Eintrag hat Vorrang vor einer Bonusvorlage.
        </p>
      </div>
      <ZulagenClient employees={employees} />
    </PageShell>
  );
}
