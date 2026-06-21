"use client";

// D.1 — Tariff Code List. Entry point of the Tariff Registry: one card per
// distinct tariff_code with coverage status, employee count and a validity bar.

import { useMemo, useState } from "react";
import Link from "next/link";
import { Upload, Table2, ChevronRight, Search, AlertTriangle } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { deDate } from "@/lib/pcmFormat";
import type { TariffCodeSummary } from "@/types/pcm";

type StatusFilter = "all" | "active" | "proposed" | "gap";

const STATUS_LABELS: Record<StatusFilter, string> = {
  all: "Alle",
  active: "Aktiv",
  proposed: "Mit Planung",
  gap: "Mit Lücke",
};

function abbrev(code: string): string {
  const letters = code.replace(/[^A-Za-zÄÖÜäöü]/g, "");
  return (letters.slice(0, 2) || code.slice(0, 2)).toUpperCase();
}

export function TariffCodeListClient({ codes }: { codes: TariffCodeSummary[] }) {
  const [status, setStatus] = useState<StatusFilter>("all");
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    return codes.filter((c) => {
      if (query && !c.tariff_code.toLowerCase().includes(query.toLowerCase())) return false;
      if (status === "active") return c.has_current;
      if (status === "proposed") return c.has_proposed;
      if (status === "gap") return c.has_gap;
      return true;
    });
  }, [codes, status, query]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-soft-ink3" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Tarifcode suchen…"
              className="rounded-soft-xs border border-soft-line bg-white pl-9 pr-3 py-2 text-sm
                outline-none focus:ring-2 focus:ring-soft-accent focus:border-soft-accent"
            />
          </div>
          <div className="flex gap-1">
            {(Object.keys(STATUS_LABELS) as StatusFilter[]).map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setStatus(key)}
                className={`px-3 py-1.5 rounded-soft-xs text-xs font-medium transition-colors ${
                  status === key
                    ? "bg-soft-accent text-white"
                    : "bg-soft-line2 text-soft-ink2 hover:bg-soft-ink/5"
                }`}
              >
                {STATUS_LABELS[key]}
              </button>
            ))}
          </div>
        </div>
        <Link href="/dashboard/pcm/tarife/import">
          <Button variant="primary">
            <Upload className="h-4 w-4 mr-1" aria-hidden="true" />
            Neue Tarifvereinbarung importieren
          </Button>
        </Link>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon={Table2}
          title={codes.length === 0 ? "Noch keine Tarifverträge geladen" : "Keine Treffer"}
          description={
            codes.length === 0
              ? "Importiere deine erste Tarifvereinbarung, um Entgelt-Tabellen für Abrechnung und Prognose zu hinterlegen."
              : "Passe Suche oder Filter an."
          }
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {filtered.map((c) => (
            <Link
              key={c.tariff_code}
              href={`/dashboard/pcm/tarife/${encodeURIComponent(c.tariff_code)}`}
              className="group bg-white rounded-soft border border-soft-line p-5 shadow-soft
                hover:border-soft-accent hover:shadow-soft-lg transition-all"
            >
              <div className="flex items-start gap-4">
                <span
                  className="shrink-0 h-11 w-11 rounded-soft-xs bg-soft-accentSoft text-soft-accent
                    flex items-center justify-center font-semibold text-sm"
                  aria-hidden="true"
                >
                  {abbrev(c.tariff_code)}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-soft-ink truncate">{c.tariff_code}</span>
                    <Badge variant="muted">{c.employee_count} MA</Badge>
                  </div>
                  <p className="text-xs text-soft-ink3 mt-0.5">
                    {c.grade_count} Entgeltgruppen
                    {c.standard_hours ? ` · ${c.standard_hours} h/Woche` : ""}
                    {c.bav_rate_pct ? ` · BAV ${c.bav_rate_pct}%` : ""}
                  </p>

                  <div className="flex items-center gap-1.5 mt-3 flex-wrap">
                    {c.has_current && <Badge variant="success">Aktiv</Badge>}
                    {c.has_proposed && <Badge variant="warning">Geplant</Badge>}
                    {c.has_gap && (
                      <Badge variant="danger">
                        <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                        Lücke
                      </Badge>
                    )}
                  </div>

                  <div className="flex items-center justify-between mt-3">
                    <span className="text-[11px] text-soft-ink3">
                      {c.current_valid_from
                        ? `${deDate(c.current_valid_from)} – ${deDate(c.current_valid_to)}`
                        : "Keine aktive Gültigkeit"}
                    </span>
                    <ChevronRight className="h-4 w-4 text-soft-ink3 group-hover:text-soft-accent" />
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
