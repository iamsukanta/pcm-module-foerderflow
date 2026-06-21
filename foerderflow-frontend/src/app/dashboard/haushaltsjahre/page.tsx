import Link from "next/link";
import { CalendarDays, Lock } from "lucide-react";

import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import type { FiscalYearWithMeta } from "@/types/haushaltsjahre";
import { PageShell } from "@/components/ui/PageShell";

export const metadata = {
  title: "Haushaltsjahre — FoerderFlow",
};

function formatDateDE(dateString: string): string {
  return new Date(dateString).toLocaleDateString("de-DE", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function FiscalYearCard({ year }: { year: FiscalYearWithMeta }) {
  const isOpen = year.status === "OFFEN";
  const beginnDE = formatDateDE(year.beginn);
  const endeDE = formatDateDE(year.ende);

  return (
    <div
      className={`rounded-soft-sm border p-5 transition-all ${
        isOpen
          ? "border-soft-accent bg-soft-surface shadow-soft ring-2 ring-soft-accentWash"
          : "border-soft-line bg-soft-line2 opacity-70"
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <span className="text-xl font-bold text-soft-ink">{year.jahr}</span>
              {isOpen ? (
                <Badge variant="default">Aktiv</Badge>
              ) : (
                <Badge variant="muted">Geschlossen</Badge>
              )}
            </div>
            <p className="text-sm text-soft-ink3 mt-0.5">
              {beginnDE} – {endeDE}
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 shrink-0">
          {isOpen ? (
            <>
              <Link
                href={`/dashboard/haushaltsjahre/${year.id}`}
                className="inline-flex items-center justify-center rounded-soft-sm border border-soft-line bg-soft-surface px-3 py-2 text-sm font-medium text-soft-ink2
                  hover:bg-soft-line2 active:bg-soft-line transition-colors min-h-[36px] shadow-soft
                  focus:outline-none focus:ring-2 focus:ring-soft-accent focus:ring-offset-2"
              >
                Bearbeiten
              </Link>
              <Link
                href={`/dashboard/haushaltsjahre/${year.id}#schliessen`}
                className="inline-flex items-center justify-center rounded-soft-sm border border-soft-crit/20 bg-soft-critSoft px-3 py-2 text-sm font-medium text-soft-crit
                  hover:bg-soft-crit hover:text-white active:bg-soft-critDark transition-colors min-h-[36px]
                  focus:outline-none focus:ring-2 focus:ring-soft-crit focus:ring-offset-2"
              >
                <Lock className="h-3.5 w-3.5 mr-1" />
                Schließen
              </Link>
            </>
          ) : (
            <Link
              href={`/dashboard/haushaltsjahre/${year.id}`}
              className="inline-flex items-center justify-center rounded-soft-sm border border-soft-line px-3 py-2 text-sm font-medium text-soft-ink3
                hover:bg-soft-line2 transition-colors min-h-[36px]
                focus:outline-none focus:ring-2 focus:ring-soft-accent focus:ring-offset-2"
            >
              Details
            </Link>
          )}
        </div>
      </div>

      {/* Schließungs-Audit-Info */}
      {!isOpen && year.geschlossen_am && (
        <div className="mt-3 pt-3 border-t border-soft-line flex items-center gap-1.5 text-xs text-soft-ink3">
          <Lock className="h-3.5 w-3.5" />
          <span>Geschlossen am {formatDateDE(year.geschlossen_am)}</span>
        </div>
      )}
    </div>
  );
}

export default async function HaushaltsjahreListPage() {
  await requireOrgSession();

  const years = await serverFetch<FiscalYearWithMeta[]>("/protected/haushaltsjahre");

  const openYears = years.filter((y) => y.status === "OFFEN");
  const closedYears = years.filter((y) => y.status === "GESCHLOSSEN");

  return (
    <PageShell width="wide">
      {/* Header */}
      <div className="flex items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-soft-ink">Haushaltsjahre</h1>
          <p className="text-sm text-soft-ink3 mt-1">
            {openYears.length > 0
              ? `${openYears.length} offen, ${closedYears.length} geschlossen`
              : years.length === 0
                ? "Noch kein Haushaltsjahr angelegt"
                : `${closedYears.length} geschlossen`}
          </p>
        </div>
        <Link
          href="/dashboard/haushaltsjahre/new"
          className="inline-flex items-center justify-center rounded-soft-sm bg-soft-accent px-4 py-2.5 text-sm font-medium text-white
            hover:bg-soft-accentDark active:bg-soft-accentDark transition-colors min-h-[44px] shadow-soft
            focus:outline-none focus:ring-2 focus:ring-soft-accent focus:ring-offset-2"
        >
          + Neues Haushaltsjahr
        </Link>
      </div>

      {/* Empty State */}
      {years.length === 0 && (
        <EmptyState
          icon={CalendarDays}
          title="Noch kein Haushaltsjahr angelegt"
          description="Lege dein erstes Haushaltsjahr an, um Buchungen und Fördermittel einem Planungszeitraum zuzuordnen."
          action={{
            label: "Erstes Haushaltsjahr anlegen",
            href: "/dashboard/haushaltsjahre/new",
          }}
        />
      )}

      {/* Open Years — primär oben */}
      {openYears.length > 0 && (
        <section className="mb-8">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-soft-ink3 mb-3">
            Aktives Haushaltsjahr
          </h2>
          <div className="flex flex-col gap-3">
            {openYears.map((year) => (
              <FiscalYearCard key={year.id} year={year} />
            ))}
          </div>
        </section>
      )}

      {/* Closed Years */}
      {closedYears.length > 0 && (
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-wide text-soft-ink3 mb-3">
            Abgeschlossene Haushaltsjahre
          </h2>
          <div className="flex flex-col gap-3">
            {closedYears.map((year) => (
              <FiscalYearCard key={year.id} year={year} />
            ))}
          </div>
        </section>
      )}

      {/* Multiple open years warning */}
      {openYears.length > 1 && (
        <div
          role="alert"
          className="mt-6 rounded-soft-sm border border-soft-warn/20 bg-soft-warnSoft p-4 text-sm text-soft-warn"
        >
          <strong className="font-semibold">Achtung:</strong> Es sind mehrere Haushaltsjahre
          gleichzeitig offen ({openYears.map((y) => y.jahr).join(", ")}). Pro Organisation sollte nur
          ein Haushaltsjahr offen sein.
        </div>
      )}
    </PageShell>
  );
}
