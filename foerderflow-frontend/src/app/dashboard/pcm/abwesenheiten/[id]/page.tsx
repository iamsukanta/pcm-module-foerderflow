import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";
import type { LeavePeriod, PlaceholderEmployee } from "@/types/pcm";
import { LeaveDetailClient } from "./LeaveDetailClient";

export const metadata = {
  title: "Abwesenheit — FoerderFlow",
};

export default async function LeaveDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireOrgSession();
  const { id } = await params;

  const [leave, placeholders] = await Promise.all([
    serverFetch<LeavePeriod>(`/protected/pcm/leave-periods/${id}`),
    serverFetch<PlaceholderEmployee[]>("/protected/pcm/placeholder-employees"),
  ]);

  return (
    <PageShell width="content">
      <div className="mb-6">
        <Link
          href="/dashboard/pcm/abwesenheiten"
          className="inline-flex items-center gap-1 text-sm text-soft-ink3 hover:text-soft-ink mb-2"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          Abwesenheiten
        </Link>
        <h1 className="text-2xl font-bold text-soft-ink">{leave.employee_name}</h1>
      </div>
      <LeaveDetailClient leave={leave} placeholders={placeholders} />
    </PageShell>
  );
}
