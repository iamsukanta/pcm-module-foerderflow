import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { requireSuperAdmin } from "@/lib/session";
import { ApiError, serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";
import { OrganisationDetailClient } from "@/components/admin/OrganisationDetailClient";

export const dynamic = "force-dynamic";

type Role = "ADMIN" | "FINANCE" | "READONLY";

type OrgMember = {
  id: string;
  user_id: string;
  email: string;
  vorname: string | null;
  nachname: string | null;
  name: string | null;
  role: Role;
  created_at: string;
};

type OrgInvite = {
  id: string;
  email: string;
  role: Role;
  expires_at: string;
  created_at: string;
  created_by_label: string;
};

type OrgDetail = {
  id: string;
  name: string;
  rechtsform: string;
  regelarbeitszeit_stunden: number;
  counts: { transactions: number; funding_measures: number; cost_centers: number };
  members: OrgMember[];
  invites: OrgInvite[];
};

export default async function AdminOrganisationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireSuperAdmin();
  const { id } = await params;

  let org: OrgDetail;
  try {
    org = await serverFetch<OrgDetail>(`/admin/organisations/${id}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }

  return (
    <PageShell width="wide">
      <div className="mb-6">
        <Link
          href="/admin/organisations"
          className="inline-flex items-center gap-1.5 text-sm text-soft-ink3 hover:text-soft-accent mb-4"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden /> Alle Organisationen
        </Link>
        <h1 className="text-2xl font-bold text-soft-ink">{org.name}</h1>
        <p className="mt-1 text-sm text-soft-ink3">
          {org.members.length} Mitglied{org.members.length === 1 ? "" : "er"} ·{" "}
          {org.counts.transactions} Transaktion{org.counts.transactions === 1 ? "" : "en"} ·{" "}
          {org.counts.funding_measures} Fördermaßnahme{org.counts.funding_measures === 1 ? "" : "n"} ·{" "}
          {org.counts.cost_centers} KST{org.counts.cost_centers === 1 ? "" : "s"}
        </p>
      </div>

      <OrganisationDetailClient
        org={{
          id: org.id,
          name: org.name,
          rechtsform: org.rechtsform,
          regelarbeitszeit_stunden: org.regelarbeitszeit_stunden,
        }}
        members={org.members.map((m) => ({
          id: m.id,
          user_id: m.user_id,
          email: m.email,
          vorname: m.vorname,
          nachname: m.nachname,
          role: m.role,
          created_at: m.created_at,
        }))}
        invites={org.invites.map((i) => ({
          id: i.id,
          email: i.email,
          role: i.role,
          expires_at: i.expires_at,
          created_at: i.created_at,
          created_by_label: i.created_by_label,
        }))}
        counts={{
          transactions: org.counts.transactions,
          funding_measures: org.counts.funding_measures,
          cost_centers: org.counts.cost_centers,
        }}
      />
    </PageShell>
  );
}
