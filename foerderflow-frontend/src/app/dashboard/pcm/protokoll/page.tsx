import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";
import type { AuditLogEntry } from "@/types/pcm";
import { AuditLogClient } from "./AuditLogClient";

export const metadata = {
  title: "Protokoll — FoerderFlow",
};

export default async function ProtokollPage() {
  await requireOrgSession();
  const entries = await serverFetch<AuditLogEntry[]>("/protected/pcm/audit-log");

  return (
    <PageShell width="wide">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-soft-ink">Protokoll</h1>
        <p className="text-sm text-soft-ink3 mt-1">
          Revisionssicheres Protokoll aller Vertragsänderungen, automatischen
          Stufenaufstiege und Abwesenheitsereignisse — für Prüfungen der
          Fördergeberin.
        </p>
      </div>
      <AuditLogClient entries={entries} />
    </PageShell>
  );
}
