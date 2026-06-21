import { Clock } from "lucide-react";

import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";
import { deDate } from "@/lib/pcmFormat";
import type { LeavePeriod, LeaveTasks, PcmEmployee, PlaceholderEmployee } from "@/types/pcm";
import { LeaveClient } from "./LeaveClient";

export const metadata = {
  title: "Abwesenheiten — FoerderFlow",
};

export default async function AbwesenheitenPage() {
  await requireOrgSession();

  const [leaves, employees, placeholders, fristen] = await Promise.all([
    serverFetch<LeavePeriod[]>("/protected/pcm/leave-periods"),
    serverFetch<PcmEmployee[]>("/protected/employees"),
    serverFetch<PlaceholderEmployee[]>("/protected/pcm/placeholder-employees"),
    serverFetch<LeaveTasks>("/protected/pcm/fristen/leave-tasks"),
  ]);

  return (
    <PageShell width="wide">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-soft-ink">Abwesenheiten</h1>
        <p className="text-sm text-soft-ink3 mt-1">
          Elternzeit, Mutterschutz und Langzeiterkrankung. Während einer aktiven
          Abwesenheit wird die Abrechnung der betroffenen Person ausgesetzt
          (Status&nbsp;ON_LEAVE, 0&nbsp;€); Vertretungen werden als Platzhalter
          geführt.
        </p>
      </div>

      {fristen.total > 0 && (
        <div className="mb-6 rounded-soft bg-soft-warnSoft border border-soft-warn/30 p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-soft-warn mb-2">
            <Clock className="h-4 w-4" aria-hidden="true" />
            {fristen.total} offene Frist(en) zu Abwesenheiten
          </div>
          <ul className="space-y-1">
            {fristen.tasks.map((t) => (
              <li key={`${t.leave_period_id}-${t.type}`} className="flex items-center justify-between text-xs text-soft-ink2">
                <span>{t.title}</span>
                <span className="numeric text-soft-ink3 ml-3 shrink-0">fällig {deDate(t.due_date)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <LeaveClient leaves={leaves} employees={employees} placeholders={placeholders} />
    </PageShell>
  );
}
