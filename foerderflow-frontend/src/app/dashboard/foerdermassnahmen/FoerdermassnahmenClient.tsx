"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { AmpelBadge } from "@/components/ui/AmpelBadge";
import { SearchInput } from "@/components/ui/SearchInput";
import { useDebounce } from "@/lib/hooks/useDebounce";
import { FoerdermassnahmeDeleteButton } from "@/components/forms/FoerdermassnahmeDeleteButton";
import type { FundingMeasureStatus } from "@/types/foerdermassnahmen";
import { Landmark, CheckCircle2, Circle, Eye, Pencil } from "lucide-react";

type EnrichedMeasure = {
  id: string;
  name: string;
  status: FundingMeasureStatus;
  budget_gesamt: number;
  foerderquote: number;
  laufzeit_von: Date;
  laufzeit_bis: Date;
  overhead_limit_prozent: number | null;
  is_expired: boolean;
  days_until_expiry: number | null;
  betrag_ist: number;
  betrag_bewilligt: number;
  ampelStatus: "GRUEN" | "GELB" | "ROT";
  ampelGruende: string[];
  funder: { id: string; name: string; typ: string };
  _count: { rules: number; cost_centers: number };
};

type Props = {
  measures: EnrichedMeasure[];
  kstCount: number;
  activeFilter?: FundingMeasureStatus;
};

const STATUS_BADGE_VARIANT: Record<FundingMeasureStatus, "success" | "muted" | "danger"> = {
  AKTIV: "success",
  ABGESCHLOSSEN: "muted",
  WIDERRUFEN: "danger",
};

const STATUS_LABEL: Record<FundingMeasureStatus, string> = {
  AKTIV: "Aktiv",
  ABGESCHLOSSEN: "Abgeschlossen",
  WIDERRUFEN: "Widerrufen",
};

function formatEuro(value: number): string {
  return new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(value);
}

function formatDate(date: Date): string {
  return new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(date));
}

function BudgetProgressBar({ used, total }: { used: number; total: number }) {
  const percent = total > 0 ? Math.min(100, (used / total) * 100) : 0;
  return (
    <div className="mt-3">
      <div className="flex justify-between text-xs text-soft-ink3 mb-1">
        <span>Mittelverwendung</span>
        <span className="numeric">{percent.toFixed(0)}%</span>
      </div>
      <div
        className="h-1.5 w-full rounded-full bg-soft-surfaceAlt"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Mittelverwendung"
      >
        <div
          className="h-full rounded-full bg-soft-accent transition-all"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

export function FoerdermassnahmenClient({ measures, kstCount, activeFilter }: Props) {
  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearch = useDebounce(searchQuery, 300);

  const filteredMeasures = useMemo(() => {
    if (!debouncedSearch.trim()) return measures;

    const query = debouncedSearch.toLowerCase();
    return measures.filter(
      (m) => m.name.toLowerCase().includes(query) || m.funder.name.toLowerCase().includes(query),
    );
  }, [measures, debouncedSearch]);

  return (
    <>
      {/* Search input */}
      {measures.length > 0 && (
        <SearchInput
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="Suche nach Massnahme oder Fördergeber..."
          className="mb-6"
        />
      )}

      {/* Empty State */}
      {measures.length === 0 && (
        <div className="flex flex-col items-center justify-center text-center mt-8">
          <div className="rounded-soft border border-soft-line bg-white p-10 max-w-lg w-full">
            <div className="rounded-full bg-soft-surfaceAlt p-4 mb-4 inline-flex">
              <Landmark className="h-8 w-8 text-soft-ink4" />
            </div>
            <h3 className="text-lg font-semibold text-soft-ink mb-2">
              {activeFilter
                ? `Keine Massnahmen mit Status „${STATUS_LABEL[activeFilter]}"`
                : "Noch keine Fördermassnahmen"}
            </h3>
            <p className="text-sm text-soft-ink3 max-w-sm mx-auto mb-6">
              {activeFilter
                ? "Wechsle den Filter oder lege eine neue Massnahme an."
                : "Lege deine erste Fördermassnahme an und verknüpfe sie mit Kostenstellen und Budgetpositionen."}
            </p>
            {!activeFilter && (
              <Link href="/dashboard/foerdermassnahmen/new">
                <Button variant="primary">Fördermassnahme anlegen →</Button>
              </Link>
            )}
            {!activeFilter && (
              <div className="mt-6 border-t border-soft-line2 pt-4 space-y-2 text-left">
                <p className="text-xs text-soft-ink4 font-medium uppercase tracking-wider mb-2">
                  Voraussetzungen
                </p>
                <div className="flex items-center gap-2 text-sm">
                  {kstCount > 0 ? (
                    <CheckCircle2 className="h-4 w-4 text-soft-ok shrink-0" aria-hidden="true" />
                  ) : (
                    <Circle className="h-4 w-4 text-soft-ink4 shrink-0" />
                  )}
                  <span className={kstCount > 0 ? "text-soft-ink2" : "text-soft-ink4"}>
                    Kostenstelle vorhanden
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* No search results */}
      {measures.length > 0 && filteredMeasures.length === 0 && (
        <div className="text-center py-12 text-soft-ink4 text-sm">
          Keine Fördermassnahmen gefunden für „{searchQuery}&ldquo;.
        </div>
      )}

      {/* Cards Grid */}
      {filteredMeasures.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filteredMeasures.map((measure) => {
            const isExpired = measure.is_expired;
            const daysLeft = measure.days_until_expiry;
            const isExpiringSoon = !isExpired && daysLeft !== null && daysLeft <= 30;

            return (
              <div
                key={measure.id}
                className={`rounded-soft border bg-white p-5 shadow-soft
                  ${isExpired ? "opacity-60" : ""}
                  ${measure.status === "WIDERRUFEN" ? "opacity-50" : ""}`}
              >
                {/* Funder name (small, top) */}
                <div className="flex items-start justify-between gap-2 mb-2">
                  <span className="text-xs font-medium text-soft-ink4 uppercase tracking-wide truncate">
                    {measure.funder.name}
                  </span>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {isExpired && <Badge variant="danger">Abgelaufen</Badge>}
                    <Badge variant={STATUS_BADGE_VARIANT[measure.status]}>
                      {STATUS_LABEL[measure.status]}
                    </Badge>
                    {measure.status === "AKTIV" && (
                      <AmpelBadge status={measure.ampelStatus} gruende={measure.ampelGruende} />
                    )}
                  </div>
                </div>

                {/* Measure name */}
                <h2 className="text-base font-semibold text-soft-ink leading-snug mb-3 line-clamp-2">
                  {measure.name}
                </h2>

                {/* Metrics row */}
                <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                  <div>
                    <span className="block text-xs text-soft-ink4">Budget</span>
                    <span className="numeric font-semibold text-soft-ink">
                      {formatEuro(measure.budget_gesamt)}
                    </span>
                  </div>
                  <div>
                    <span className="block text-xs text-soft-ink4">Förderquote</span>
                    <span className="numeric font-semibold text-soft-ink">
                      {measure.foerderquote.toFixed(0)}%
                    </span>
                  </div>
                  <div>
                    <span className="block text-xs text-soft-ink4">Laufzeit von</span>
                    <span className="text-soft-ink2">{formatDate(measure.laufzeit_von)}</span>
                  </div>
                  <div>
                    <span className="block text-xs text-soft-ink4">Laufzeit bis</span>
                    <span
                      className={`${isExpiringSoon ? "text-soft-warn font-medium" : isExpired ? "text-soft-crit" : "text-soft-ink2"}`}
                    >
                      {formatDate(measure.laufzeit_bis)}
                    </span>
                  </div>
                </div>

                {/* Expiry warning */}
                {isExpiringSoon && !isExpired && (
                  <div className="mt-3 flex items-center gap-1.5 rounded-soft-xs bg-soft-warnSoft border border-soft-warn/30 px-3 py-2 text-xs text-soft-warn">
                    <svg
                      className="h-3.5 w-3.5 shrink-0"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                      />
                    </svg>
                    Läuft in {daysLeft} {daysLeft === 1 ? "Tag" : "Tagen"} ab
                  </div>
                )}

                {/* Budget Progress Bar */}
                <BudgetProgressBar used={measure.betrag_ist} total={measure.betrag_bewilligt} />

                {/* Footer: meta + action buttons */}
                <div className="mt-3 flex items-center justify-between gap-3 text-xs text-soft-ink4 border-t border-soft-line2 pt-3">
                  <div className="flex items-center gap-3">
                    <span>{measure._count.cost_centers} KST</span>
                    <span>·</span>
                    <span>{measure._count.rules} Regeln</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Link href={`/dashboard/foerdermassnahmen/${measure.id}`}>
                      <button
                        type="button"
                        aria-label={`Detailansicht ${measure.name}`}
                        title="Detailansicht"
                        className="p-1.5 rounded-soft-xs hover:bg-soft-surfaceAlt text-soft-ink4 hover:text-soft-ink2 transition-colors focus:outline-none focus:ring-2 focus:ring-soft-accent"
                      >
                        <Eye className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </Link>
                    <Link href={`/dashboard/foerdermassnahmen/${measure.id}/edit`}>
                      <button
                        type="button"
                        aria-label={`Bearbeiten ${measure.name}`}
                        title="Bearbeiten"
                        className="p-1.5 rounded-soft-xs hover:bg-soft-surfaceAlt text-soft-ink4 hover:text-soft-ink2 transition-colors focus:outline-none focus:ring-2 focus:ring-soft-accent"
                      >
                        <Pencil className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </Link>
                    <FoerdermassnahmeDeleteButton
                      massnahmeId={measure.id}
                      massnahmeName={measure.name}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
