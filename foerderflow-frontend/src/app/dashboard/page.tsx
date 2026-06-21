import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle,
  ArrowRight,
  Zap,
  BarChart2,
  Wallet,
  TrendingDown,
  Lock,
  PieChart,
  Calendar,
  AlertCircle,
  FileCheck,
} from "lucide-react";

import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import {
  GettingStartedWidget,
  type OnboardingCounts,
} from "@/components/dashboard/GettingStartedWidget";
import {
  FehlbedarfWidget,
  type FehlbedarfWidgetItem,
} from "@/components/dashboard/FehlbedarfWidget";
import { PageShell } from "@/components/ui/PageShell";

export const dynamic = "force-dynamic";

type Cockpit = {
  onboarding: OnboardingCounts;
  ytd_label: string;
  kpi: {
    gesamtvolumen: number;
    aktive_count: number;
    verbraucht_ytd: number;
    eigenanteil_ytd: number;
    reserviert: number;
    verbrauch_pct: number;
    eigenanteil_quote: number;
  };
  offene_transaktionen: number;
  measures_top: Array<{
    id: string;
    name: string;
    budget_bewilligt: number;
    betrag_ist: number;
    percent: number;
    days_left: number;
  }>;
  dringende_abrufe: Array<{
    id: string;
    betrag: number;
    frist_bis: string;
    measure_name: string;
    days_left: number;
  }>;
  ablaufende_massnahmen: Array<{
    id: string;
    name: string;
    laufzeit_bis: string;
    days_left: number;
  }>;
  dringende_nachweise: Array<{
    id: string;
    frist: string;
    typ: "ZWISCHENNACHWEIS" | "VERWENDUNGSNACHWEIS" | "SACHBERICHT_ONLY";
    measure_name: string;
    days_left: number;
  }>;
  fehlbedarf: FehlbedarfWidgetItem[];
};

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 11) return "Guten Morgen";
  if (hour >= 11 && hour < 17) return "Guten Tag";
  if (hour >= 17 && hour < 22) return "Guten Abend";
  return "Hallo";
}

function formatDate(date: Date): string {
  return new Intl.DateTimeFormat("de-DE", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
}

function formatEuro(value: number): string {
  return new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(value);
}

function formatEuroCompact(value: number): string {
  if (Math.abs(value) >= 1_000_000) {
    return new Intl.NumberFormat("de-DE", {
      style: "currency",
      currency: "EUR",
      maximumFractionDigits: 1,
      notation: "compact",
    }).format(value);
  }
  return new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);
}

function ampelColor(percent: number, daysLeft: number | null): string {
  if (daysLeft !== null && daysLeft < 14) return "bg-soft-crit";
  if (percent > 95) return "bg-soft-crit";
  if (percent >= 80) return "bg-soft-warn";
  return "bg-soft-ok";
}

type FristItem = {
  key: string;
  typ: "REVIEW" | "MITTELABRUF" | "MASSNAHME" | "NACHWEIS";
  titel: string;
  untertitel: string;
  daysLeft: number | null;
  href: string;
  severity: "warn" | "crit" | "info";
};

const NACHWEIS_TYP_LABEL: Record<Cockpit["dringende_nachweise"][number]["typ"], string> = {
  ZWISCHENNACHWEIS: "Zwischennachweis",
  VERWENDUNGSNACHWEIS: "Verwendungsnachweis",
  SACHBERICHT_ONLY: "Sachbericht",
};

export default async function DashboardPage() {
  const { user } = await requireOrgSession();
  const cockpit = await serverFetch<Cockpit>("/protected/dashboard/cockpit");

  const greeting = getGreeting();
  const userName = user.name ? user.name.split(" ")[0] : (user.email ?? "");

  const { kpi, ytd_label: ytdLabel } = cockpit;

  // ── Nächste Fristen (aus den Cockpit-Teillisten zusammensetzen) ──
  const fristen: FristItem[] = [];

  if (cockpit.offene_transaktionen > 0) {
    fristen.push({
      key: "review",
      typ: "REVIEW",
      titel: `${cockpit.offene_transaktionen} Transaktion${cockpit.offene_transaktionen === 1 ? "" : "en"} im Review`,
      untertitel: "Zuordnung erforderlich",
      daysLeft: null,
      href: "/dashboard/review",
      severity: "warn",
    });
  }

  for (const a of cockpit.dringende_abrufe) {
    fristen.push({
      key: `abruf-${a.id}`,
      typ: "MITTELABRUF",
      titel: `Mittelabruf · ${formatEuroCompact(a.betrag)}`,
      untertitel: a.measure_name,
      daysLeft: a.days_left,
      href: "/dashboard/mittelabrufe",
      severity: a.days_left < 7 ? "crit" : "warn",
    });
  }

  for (const m of cockpit.ablaufende_massnahmen) {
    fristen.push({
      key: `massnahme-${m.id}`,
      typ: "MASSNAHME",
      titel: "Massnahme läuft ab",
      untertitel: m.name,
      daysLeft: m.days_left,
      href: `/dashboard/foerdermassnahmen/${m.id}`,
      severity: m.days_left < 30 ? "warn" : "info",
    });
  }

  for (const n of cockpit.dringende_nachweise) {
    fristen.push({
      key: `nachweis-${n.id}`,
      typ: "NACHWEIS",
      titel: NACHWEIS_TYP_LABEL[n.typ],
      untertitel: n.measure_name,
      daysLeft: n.days_left,
      href: `/dashboard/verwendungsnachweise/${n.id}`,
      severity: n.days_left < 7 ? "crit" : "warn",
    });
  }

  fristen.sort((a, b) => {
    if (a.daysLeft === null && b.daysLeft !== null) return -1;
    if (a.daysLeft !== null && b.daysLeft === null) return 1;
    return (a.daysLeft ?? 0) - (b.daysLeft ?? 0);
  });

  return (
    <PageShell width="full">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-soft-ink">
          {greeting}, {userName}.
        </h1>
        <p className="text-soft-ink2 mt-1">{formatDate(new Date())}</p>
      </div>

      {/* Getting Started Widget */}
      <GettingStartedWidget onboarding={cockpit.onboarding} />

      {/* KPI-Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <KpiCard
          label="Gesamtvolumen"
          value={formatEuroCompact(kpi.gesamtvolumen)}
          icon={Wallet}
          sublabel={`${kpi.aktive_count} aktive Massnahme${kpi.aktive_count === 1 ? "" : "n"}`}
        />
        <KpiCard
          label={`Verbraucht ${ytdLabel}`}
          value={formatEuroCompact(kpi.verbraucht_ytd)}
          icon={TrendingDown}
          sublabel={
            kpi.gesamtvolumen > 0
              ? `${kpi.verbrauch_pct.toFixed(0)} % vom Volumen`
              : "Noch keine Buchungen"
          }
        />
        <KpiCard
          label="Reserviert"
          value={formatEuroCompact(kpi.reserviert)}
          icon={Lock}
          sublabel="Offene Mittelabrufe"
        />
        <KpiCard
          label={`Eigenanteil ${ytdLabel}`}
          value={formatEuroCompact(kpi.eigenanteil_ytd)}
          icon={PieChart}
          sublabel={
            kpi.eigenanteil_ytd > 0
              ? `${kpi.eigenanteil_quote.toFixed(0)} % der gebuchten Ausgaben`
              : "Entsteht durch Transaktionszuordnung"
          }
          accent
        />
      </div>

      {/* Hauptgrid */}
      <div className="grid grid-cols-12 gap-6 mb-6">
        {/* Aktive Massnahmen */}
        <div className="col-span-12 lg:col-span-7 bg-soft-surface border border-soft-line rounded-soft-sm p-6 shadow-soft">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-soft-ink flex items-center gap-2">
              <BarChart2 className="h-4 w-4 text-soft-ink3" aria-hidden="true" />
              Aktive Massnahmen
            </h2>
            <Link
              href="/dashboard/foerdermassnahmen"
              className="text-xs text-soft-accent hover:underline inline-flex items-center gap-1"
            >
              Alle anzeigen <ArrowRight className="h-3 w-3" aria-hidden="true" />
            </Link>
          </div>

          {cockpit.measures_top.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <p className="text-soft-ink2 text-sm">Noch keine aktiven Fördermassnahmen</p>
              <Link
                href="/dashboard/foerdermassnahmen/new"
                className="mt-3 text-xs text-soft-accent hover:underline"
              >
                Erste Massnahme anlegen →
              </Link>
            </div>
          ) : (
            <div className="space-y-4">
              {cockpit.measures_top.map((m) => (
                <Link
                  key={m.id}
                  href={`/dashboard/foerdermassnahmen/${m.id}`}
                  className="block group"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-soft-ink group-hover:text-soft-accent transition-colors font-medium truncate max-w-[60%]">
                      {m.name}
                    </span>
                    <span className="text-xs text-soft-ink3 numeric">{m.percent.toFixed(0)}%</span>
                  </div>
                  <div className="h-1.5 w-full bg-soft-line2 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${ampelColor(m.percent, m.days_left)}`}
                      style={{ width: `${m.percent}%` }}
                    />
                  </div>
                  <p className="text-xs text-soft-ink3 mt-1 numeric">
                    {formatEuro(m.betrag_ist)} <span className="font-sans">von</span>{" "}
                    {formatEuro(m.budget_bewilligt)}
                    {m.days_left < 14 && (
                      <span className="ml-2 text-soft-crit font-medium">
                        ·{" "}
                        <span className="font-sans">
                          {m.days_left <= 0 ? "Abgelaufen" : `${m.days_left}d verbleibend`}
                        </span>
                      </span>
                    )}
                  </p>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Nächste Fristen */}
        <div className="col-span-12 lg:col-span-5 bg-soft-surface border border-soft-line rounded-soft-sm p-6 shadow-soft">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-soft-ink flex items-center gap-2">
              <Calendar className="h-4 w-4 text-soft-ink3" aria-hidden="true" />
              Nächste Fristen
            </h2>
            <Link
              href="/dashboard/fristen"
              className="text-xs text-soft-accent hover:underline inline-flex items-center gap-1"
            >
              Alle anzeigen <ArrowRight className="h-3 w-3" aria-hidden="true" />
            </Link>
          </div>

          {fristen.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <CheckCircle className="h-8 w-8 text-soft-ok mb-2" aria-hidden="true" />
              <p className="text-soft-ink2 font-medium text-sm">Keine offenen Fristen</p>
              <p className="text-xs text-soft-ink3 mt-1">Alles im grünen Bereich.</p>
            </div>
          ) : (
            <ul className="space-y-2">
              {fristen.slice(0, 8).map((f) => (
                <li key={f.key}>
                  <Link
                    href={f.href}
                    className="flex items-start gap-3 p-3 rounded-soft-xs hover:bg-soft-line2/40 transition-colors group"
                  >
                    <FristIcon severity={f.severity} typ={f.typ} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-soft-ink group-hover:text-soft-accent transition-colors truncate">
                        {f.titel}
                      </p>
                      <p className="text-xs text-soft-ink3 truncate mt-0.5">{f.untertitel}</p>
                    </div>
                    {f.daysLeft !== null && <FristBadge daysLeft={f.daysLeft} severity={f.severity} />}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Fehlbedarf-Compliance Widget */}
      <FehlbedarfWidget items={cockpit.fehlbedarf} />
    </PageShell>
  );
}

function KpiCard({
  label,
  value,
  icon: Icon,
  sublabel,
  accent = false,
}: {
  label: string;
  value: string;
  icon: typeof Wallet;
  sublabel: string;
  accent?: boolean;
}) {
  return (
    <div className="bg-soft-surface border border-soft-line rounded-soft-sm p-5 shadow-soft">
      <div className="flex items-start justify-between gap-3 mb-2">
        <span className="text-xs font-medium text-soft-ink3 uppercase tracking-wide">{label}</span>
        <Icon
          className={`h-4 w-4 shrink-0 ${accent ? "text-soft-accent" : "text-soft-ink4"}`}
          aria-hidden="true"
        />
      </div>
      <p className={`numeric text-2xl font-bold ${accent ? "text-soft-accent" : "text-soft-ink"}`}>
        {value}
      </p>
      <p className="text-xs text-soft-ink3 mt-1">{sublabel}</p>
    </div>
  );
}

function FristIcon({
  severity,
  typ,
}: {
  severity: "warn" | "crit" | "info";
  typ: "REVIEW" | "MITTELABRUF" | "MASSNAHME" | "NACHWEIS";
}) {
  const colorClass =
    severity === "crit"
      ? "text-soft-crit bg-soft-critSoft"
      : severity === "warn"
        ? "text-soft-warn bg-soft-warnSoft"
        : "text-soft-ink3 bg-soft-line2";
  const Icon =
    typ === "REVIEW"
      ? Zap
      : typ === "MITTELABRUF"
        ? AlertCircle
        : typ === "NACHWEIS"
          ? FileCheck
          : AlertTriangle;
  return (
    <div className={`p-1.5 rounded-soft-xs shrink-0 ${colorClass}`}>
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
    </div>
  );
}

function FristBadge({
  daysLeft,
  severity,
}: {
  daysLeft: number;
  severity: "warn" | "crit" | "info";
}) {
  const colorClass =
    severity === "crit"
      ? "bg-soft-critSoft text-soft-crit"
      : severity === "warn"
        ? "bg-soft-warnSoft text-soft-warn"
        : "bg-soft-line2 text-soft-ink2";
  const label = daysLeft <= 0 ? "Heute" : daysLeft === 1 ? "1 Tag" : `${daysLeft} Tage`;
  return (
    <span
      className={`numeric text-xs font-semibold px-2 py-0.5 rounded-soft-xs whitespace-nowrap shrink-0 self-center ${colorClass}`}
    >
      {label}
    </span>
  );
}
