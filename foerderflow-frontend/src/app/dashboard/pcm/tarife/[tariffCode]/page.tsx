import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";
import type { SalaryLevel, SalaryTariff } from "@/types/pcm";
import { TariffDetailClient } from "./TariffDetailClient";

export const metadata = {
  title: "Tarif-Detail — FoerderFlow",
};

export default async function TariffDetailPage({
  params,
}: {
  params: Promise<{ tariffCode: string }>;
}) {
  await requireOrgSession();
  const { tariffCode } = await params;
  const code = decodeURIComponent(tariffCode);
  const enc = encodeURIComponent(code);

  const [rows, levels] = await Promise.all([
    serverFetch<SalaryTariff[]>(`/protected/pcm/tariff-codes/${enc}/rows`),
    serverFetch<SalaryLevel[]>(`/protected/pcm/tariff-codes/${enc}/levels`),
  ]);

  return (
    <PageShell width="wide">
      <div className="mb-6">
        <Link
          href="/dashboard/pcm/tarife"
          className="inline-flex items-center gap-1 text-sm text-soft-ink3 hover:text-soft-ink mb-2"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          Tarif-Register
        </Link>
        <h1 className="text-2xl font-bold text-soft-ink">{code}</h1>
        <p className="text-sm text-soft-ink3 mt-1">
          Vollständiges Entgeltgitter, Stufen-Progressionsregeln und
          Gültigkeits-Timeline. Eine Zelle bearbeiten öffnet die Tarif-Zeile;
          Überschneidungen werden direkt aufgelöst.
        </p>
      </div>

      <TariffDetailClient tariffCode={code} rows={rows} levels={levels} />
    </PageShell>
  );
}
