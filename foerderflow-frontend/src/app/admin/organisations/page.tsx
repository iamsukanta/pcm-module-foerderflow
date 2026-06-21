import Link from "next/link";
import { Plus, ChevronRight } from "lucide-react";

import { requireSuperAdmin } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";

export const dynamic = "force-dynamic";

const RECHTSFORM_LABEL: Record<string, string> = {
  EV: "e.V.",
  GGMBH: "gGmbH",
  STIFTUNG: "Stiftung",
  ANDERE: "Andere",
};

type OrgRow = {
  id: string;
  name: string;
  rechtsform: string;
  mitglieder_count: number;
  transaction_count: number;
  created_at: string;
};

export default async function AdminOrganisationsPage() {
  await requireSuperAdmin();

  const orgs = await serverFetch<OrgRow[]>("/admin/organisations");

  return (
    <PageShell width="wide">
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-soft-ink">Organisationen</h1>
          <p className="mt-1 text-sm text-soft-ink3">
            {orgs.length} Organisation{orgs.length === 1 ? "" : "en"} insgesamt.
          </p>
        </div>
        <Link
          href="/admin/organisations/neu"
          className="inline-flex items-center gap-1.5 bg-soft-accent text-white px-4 py-2 rounded-soft-sm text-sm hover:bg-soft-accentDark"
        >
          <Plus className="h-4 w-4" aria-hidden /> Neue Organisation
        </Link>
      </div>

      <div className="bg-white rounded-soft-sm border border-soft-line overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-soft-surfaceAlt border-b border-soft-line text-left text-xs uppercase tracking-wide text-soft-ink3">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Rechtsform</th>
              <th className="px-4 py-3 text-right">Mitglieder</th>
              <th className="px-4 py-3 text-right">Transaktionen</th>
              <th className="px-4 py-3">Angelegt</th>
              <th className="px-4 py-3 w-10"></th>
            </tr>
          </thead>
          <tbody>
            {orgs.map((o) => (
              <tr
                key={o.id}
                className="border-b border-soft-line2 last:border-0 hover:bg-soft-surfaceAlt"
              >
                <td className="px-4 py-3">
                  <Link
                    href={`/admin/organisations/${o.id}`}
                    className="font-medium text-soft-ink hover:text-soft-accent"
                  >
                    {o.name}
                  </Link>
                </td>
                <td className="px-4 py-3 text-soft-ink2">
                  {RECHTSFORM_LABEL[o.rechtsform] ?? o.rechtsform}
                </td>
                <td className="px-4 py-3 text-right numeric">{o.mitglieder_count}</td>
                <td className="px-4 py-3 text-right numeric">{o.transaction_count}</td>
                <td className="px-4 py-3 text-soft-ink3 text-xs">
                  {o.created_at ? new Date(o.created_at).toLocaleDateString("de-DE") : "—"}
                </td>
                <td className="px-4 py-3">
                  <Link
                    href={`/admin/organisations/${o.id}`}
                    aria-label={`Details zu ${o.name}`}
                    className="inline-flex p-1.5 rounded-soft-xs hover:bg-soft-line2"
                  >
                    <ChevronRight className="h-4 w-4 text-soft-ink3" aria-hidden />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </PageShell>
  );
}
