import Link from "next/link";
import { Building2, UsersRound, ShieldCheck, Plus } from "lucide-react";

import { requireSuperAdmin } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";

export const dynamic = "force-dynamic";

type OrgRow = { id: string; created_at: string };
type UserRow = { id: string; is_super_admin: boolean };

export default async function AdminOverviewPage() {
  await requireSuperAdmin();

  const [orgs, users] = await Promise.all([
    serverFetch<OrgRow[]>("/admin/organisations"),
    serverFetch<UserRow[]>("/admin/users"),
  ]);

  const orgCount = orgs.length;
  const userCount = users.length;
  const superAdminCount = users.filter((u) => u.is_super_admin).length;
  const cutoff = Date.now() - 30 * 24 * 60 * 60 * 1000;
  const neueOrgs30d = orgs.filter((o) => o.created_at && new Date(o.created_at).getTime() >= cutoff)
    .length;

  return (
    <PageShell width="wide">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-soft-ink">Plattform-Übersicht</h1>
        <p className="mt-1 text-sm text-soft-ink3">
          Cross-Org-Sicht für VoluLink Super-Admins. Hier verwaltest du alle Kunden-Organisationen,
          Mitgliedschaften und Plattform-Rollen.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <KpiCard
          label="Organisationen"
          value={orgCount}
          icon={Building2}
          href="/admin/organisations"
        />
        <KpiCard label="Davon neu (30 Tage)" value={neueOrgs30d} icon={Plus} />
        <KpiCard label="User insgesamt" value={userCount} icon={UsersRound} href="/admin/users" />
        <KpiCard label="VoluLink Super-Admins" value={superAdminCount} icon={ShieldCheck} />
      </div>

      <div className="bg-white rounded-soft-sm border border-soft-line p-6">
        <h2 className="text-base font-semibold text-soft-ink mb-3">Schnellaktionen</h2>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/admin/organisations/neu"
            className="inline-flex items-center gap-1.5 bg-soft-accent text-white px-4 py-2 rounded-soft-sm text-sm hover:bg-soft-accentDark"
          >
            <Plus className="h-4 w-4" aria-hidden /> Neue Organisation
          </Link>
          <Link
            href="/admin/organisations"
            className="inline-flex items-center gap-1.5 border border-soft-line bg-white px-4 py-2 rounded-soft-sm text-sm text-soft-ink2 hover:bg-soft-surfaceAlt"
          >
            <Building2 className="h-4 w-4" aria-hidden /> Alle Organisationen
          </Link>
          <Link
            href="/admin/users"
            className="inline-flex items-center gap-1.5 border border-soft-line bg-white px-4 py-2 rounded-soft-sm text-sm text-soft-ink2 hover:bg-soft-surfaceAlt"
          >
            <UsersRound className="h-4 w-4" aria-hidden /> User-Liste
          </Link>
        </div>
      </div>
    </PageShell>
  );
}

function KpiCard({
  label,
  value,
  icon: Icon,
  href,
}: {
  label: string;
  value: number;
  icon: typeof Building2;
  href?: string;
}) {
  const inner = (
    <div className="bg-white rounded-soft-sm border border-soft-line p-4 hover:border-soft-accent transition-colors">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-soft-ink3 uppercase tracking-wide">{label}</span>
        <Icon className="h-4 w-4 text-soft-ink3" aria-hidden />
      </div>
      <p className="text-2xl font-semibold text-soft-ink numeric">{value}</p>
    </div>
  );
  return href ? <Link href={href}>{inner}</Link> : inner;
}
