// Dashboard-Widget: zeigt für alle Compliance-relevanten Maßnahmen einer Org
// (FEHLBEDARF oder FESTBETRAG+foerderquote=100) den aktuellen Status.
// Sortierung: WARNUNG > HINWEIS > OK. Presentational — Daten kommen vom Cockpit.

import Link from "next/link";
import { AlertOctagon, AlertTriangle, CheckCircle2, Shield } from "lucide-react";
import type { FehlbedarfStatus } from "@/lib/fehlbedarf-compliance";

export type FehlbedarfWidgetItem = {
  id: string;
  name: string;
  funder_name: string;
  status: FehlbedarfStatus;
  zuwendung_hoechstbetrag: number;
  fehlbedarf_zulaessig: number;
  zuwendung_abgerufen: number;
  verbleibend_abrufbar: number;
  nachricht: string | null;
};

function formatEur(n: number): string {
  return new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(n);
}

const STATUS_RANK: Record<FehlbedarfStatus, number> = { WARNUNG: 0, HINWEIS: 1, OK: 2 };

const STATUS_CFG: Record<
  FehlbedarfStatus,
  { icon: typeof AlertTriangle; iconClass: string; pillClass: string; label: string }
> = {
  WARNUNG: {
    icon: AlertOctagon,
    iconClass: "text-soft-crit",
    pillClass: "bg-soft-critSoft text-soft-crit border-soft-crit/20",
    label: "Warnung",
  },
  HINWEIS: {
    icon: AlertTriangle,
    iconClass: "text-soft-warn",
    pillClass: "bg-soft-warnSoft text-soft-warn border-soft-warn/20",
    label: "Hinweis",
  },
  OK: {
    icon: CheckCircle2,
    iconClass: "text-soft-ok",
    pillClass: "bg-soft-okSoft text-soft-ok border-soft-ok/20",
    label: "OK",
  },
};

export function FehlbedarfWidget({ items }: { items: FehlbedarfWidgetItem[] }) {
  if (items.length === 0) return null;

  const filtered = [...items].sort(
    (a, b) => STATUS_RANK[a.status] - STATUS_RANK[b.status] || a.name.localeCompare(b.name),
  );

  return (
    <section
      aria-label="Fehlbedarf-Compliance Übersicht"
      className="rounded-soft-sm border border-soft-line bg-soft-surface p-6 shadow-soft"
    >
      <header className="mb-4 flex items-center justify-between">
        <h2 className="font-semibold text-soft-ink flex items-center gap-2">
          <Shield className="h-4 w-4 text-soft-ink3" aria-hidden="true" />
          Fehlbedarf-Compliance
        </h2>
        <span className="text-xs text-soft-ink4">
          {filtered.length} Maßnahme{filtered.length === 1 ? "" : "n"} (FEHLBEDARF /
          Vollfinanzierung)
        </span>
      </header>

      <ul className="space-y-2">
        {filtered.map((r) => {
          const cfg = STATUS_CFG[r.status];
          const Icon = cfg.icon;
          return (
            <li
              key={r.id}
              className="rounded-soft-xs border border-soft-line2 bg-soft-surfaceAlt p-3"
            >
              <div className="flex items-start gap-3">
                <Icon className={`h-5 w-5 shrink-0 mt-0.5 ${cfg.iconClass}`} aria-hidden />
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline justify-between gap-3 flex-wrap">
                    <Link
                      href={`/dashboard/foerdermassnahmen/${r.id}`}
                      className="text-sm font-medium text-soft-ink hover:text-soft-accent transition-colors truncate"
                    >
                      {r.name}
                    </Link>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full border shrink-0 ${cfg.pillClass}`}
                    >
                      {cfg.label}
                    </span>
                  </div>
                  <p className="text-xs text-soft-ink4 mt-0.5">{r.funder_name}</p>
                  <div className="mt-2 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs text-soft-ink3">
                    <div>
                      <div className="text-soft-ink4">Höchstbetrag</div>
                      <div className="numeric text-soft-ink2">
                        {formatEur(r.zuwendung_hoechstbetrag)}
                      </div>
                    </div>
                    <div>
                      <div className="text-soft-ink4">Zulässig</div>
                      <div className="numeric text-soft-ink2">
                        {formatEur(r.fehlbedarf_zulaessig)}
                      </div>
                    </div>
                    <div>
                      <div className="text-soft-ink4">Abgerufen</div>
                      <div className="numeric text-soft-ink2">
                        {formatEur(r.zuwendung_abgerufen)}
                      </div>
                    </div>
                    <div>
                      <div className="text-soft-ink4">Verbleibend</div>
                      <div
                        className={`numeric font-medium ${
                          r.status === "WARNUNG" ? "text-soft-crit" : "text-soft-ink"
                        }`}
                      >
                        {formatEur(r.verbleibend_abrufbar)}
                      </div>
                    </div>
                  </div>
                  {r.nachricht && <p className={`text-xs mt-2 ${cfg.iconClass}`}>{r.nachricht}</p>}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
