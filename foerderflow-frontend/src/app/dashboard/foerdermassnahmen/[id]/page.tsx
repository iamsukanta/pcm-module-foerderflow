import Link from "next/link";
import { notFound } from "next/navigation";
import { Pencil, Layers } from "lucide-react";
import { createHash } from "node:crypto";

import { requireOrgSession } from "@/lib/session";
import { ApiError, serverFetch } from "@/lib/serverApi";
import { loadActiveCostCentersForForms } from "@/lib/costCenters";
import { Badge } from "@/components/ui/Badge";
import { AmpelBadge } from "@/components/ui/AmpelBadge";
import type { AmpelStatus } from "@/lib/ampel";
import { SollIstTabelle } from "@/components/ui/SollIstTabelle";
import { PrognoseCard } from "@/components/ui/PrognoseCard";
import { ComplianceBanner } from "@/components/ui/ComplianceBanner";
import { CrossFinanzierungWidget } from "@/components/dashboard/CrossFinanzierungWidget";
import { PageShell } from "@/components/ui/PageShell";
import { EmptyState } from "@/components/ui/EmptyState";
import type {
  FundingMeasureStatus,
  FundingRuleTyp,
  FunderTyp,
} from "@/types/foerdermassnahmen";
import type { FehlbedarfStatusResult } from "@/lib/fehlbedarf-compliance";
import type { PrognoseStatus } from "@/lib/jahresendprognose";
import { FoerdermassnahmeDetailClient } from "./FoerdermassnahmeDetailClient";
import { FinanzplanTab } from "./FinanzplanTab";
import { NachweiseTab, type NachweisRow } from "./NachweiseTab";
import { BescheidTab, type BescheidDokumentMeta } from "./BescheidTab";

type DetailTab = "uebersicht" | "bescheid" | "regeln" | "finanzplan" | "nachweise";
const VALID_TABS: DetailTab[] = ["uebersicht", "bescheid", "regeln", "finanzplan", "nachweise"];

type PageProps = {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tab?: string }>;
};

function formatEuro(value: { toString(): string }): string {
  return new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(
    parseFloat(value.toString()),
  );
}

function formatDate(date: string): string {
  return new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(date));
}

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

const RULE_TYP_LABEL: Record<FundingRuleTyp, string> = {
  KOSTENKATEGORIE_ERLAUBT: "Kostenart erlaubt",
  KOSTENKATEGORIE_VERBOTEN: "Kostenart verboten",
  BELEGPFLICHT_SPEZIAL: "Besondere Belegpflicht",
  EIGENANTEIL_MIN: "Mindest-Eigenanteil",
  VERWENDUNGSFRIST_TAGE: "Verwendungsfrist (Tage)",
  ZWISCHENNACHWEIS_PFLICHT: "Zwischennachweis Pflicht",
  PERSONALKOSTEN_HOECHSTSATZ: "Personalkosten-Höchstsatz",
};

const RULE_TYP_BADGE: Record<
  FundingRuleTyp,
  "success" | "danger" | "warning" | "default" | "muted"
> = {
  KOSTENKATEGORIE_ERLAUBT: "success",
  KOSTENKATEGORIE_VERBOTEN: "danger",
  BELEGPFLICHT_SPEZIAL: "warning",
  EIGENANTEIL_MIN: "default",
  VERWENDUNGSFRIST_TAGE: "default",
  ZWISCHENNACHWEIS_PFLICHT: "muted",
  PERSONALKOSTEN_HOECHSTSATZ: "warning",
};

const VERFAHREN_LABEL: Record<string, string> = {
  ANFORDERUNG: "Anforderungsverfahren",
  ABRUF: "Abrufverfahren",
  ABSCHLAG: "Abschlagszahlungen",
};

type MeasureRule = {
  id: string;
  org_id: string;
  funding_measure_id: string;
  typ: FundingRuleTyp;
  schluessel: string;
  wert: string | null;
  beschreibung: string | null;
  created_at: string;
  updated_at: string;
};

type MeasureCostCenterLink = {
  id: string;
  org_id: string;
  funding_measure_id: string;
  cost_center_id: string;
  created_at: string;
  cost_center: { id: string; name: string; code: string; typ: string; ist_aktiv: boolean };
};

type MeasureFull = {
  id: string;
  name: string;
  status: FundingMeasureStatus;
  funder_id: string;
  funder: { id: string; name: string; typ: FunderTyp; notizen: string | null };
  budget_gesamt: string;
  foerderquote: string;
  laufzeit_von: string;
  laufzeit_bis: string;
  durchfuehrungs_von: string | null;
  durchfuehrungs_bis: string | null;
  antragsnummer: string | null;
  verwaltungspauschale_erlaubt: boolean;
  verwaltungspauschale_prozent: string | null;
  budget_flexibilitaet_prozent: string;
  overhead_limit_prozent: string | null;
  mwst_satz_prozent: string;
  mittelabruf_verfahren: string;
  eigenmittel_betrag: string | null;
  drittmittel_betrag: string | null;
  is_expired: boolean;
  days_until_expiry: number | null;
  rules: MeasureRule[];
  cost_centers: MeasureCostCenterLink[];
  _count: { rules: number; cost_centers: number };
};

type AmpelData = {
  status: AmpelStatus;
  gruende: string[];
  betrag_ist: string;
  betrag_bewilligt: string;
};

type PrognoseData = {
  monatsrate: number;
  betrag_ist_gesamt: number;
  prognose_gesamt: number;
  prognose_prozent: number;
  days_remaining: number;
  status: PrognoseStatus;
  betrag_bewilligt: string;
};

type SollIstRow = {
  id: string;
  kostenart: string;
  beschreibung: string | null;
  betrag_beantragt: string;
  betrag_bewilligt: string;
  betrag_ist: string;
  betrag_geplant: string;
  differenz: string;
  ausschoepfung_prozent: number;
  status: "OK" | "WARNING" | "KRITISCH" | "UEBERSCHRITTEN";
};

type SollIstData = {
  data: SollIstRow[];
  gesamt_beantragt: string;
  gesamt_bewilligt: string;
  gesamt_ist: string;
};

type NachweisApiRow = {
  id: string;
  typ: NachweisRow["typ"];
  status: NachweisRow["status"];
  zeitraum_von: string;
  zeitraum_bis: string;
  frist: string;
  notiz: string | null;
  fiscal_year: { jahr: number } | null;
};

type FiscalYearRow = { id: string; jahr: number; status: "OFFEN" | "GESCHLOSSEN" };

function BudgetProgressBar({ used, total }: { used: number; total: number }) {
  const percent = total > 0 ? Math.min(100, (used / total) * 100) : 0;
  return (
    <div className="mt-1">
      <div className="flex justify-between text-xs text-soft-ink3 mb-1.5">
        <span>Mittelverwendung</span>
        <span className="numeric">
          {formatEuro({ toString: () => used.toString() })} von{" "}
          {formatEuro({ toString: () => total.toString() })} ({percent.toFixed(0)}%)
        </span>
      </div>
      <div
        className="h-2 w-full rounded-full bg-soft-surfaceAlt"
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

export default async function FoerdermassnahmeDetailPage({ params, searchParams }: PageProps) {
  await requireOrgSession();
  const { id } = await params;
  const sp = await searchParams;
  const activeTab: DetailTab =
    sp.tab && VALID_TABS.includes(sp.tab as DetailTab) ? (sp.tab as DetailTab) : "uebersicht";

  let measure: MeasureFull;
  try {
    measure = await serverFetch<MeasureFull>(`/protected/foerdermassnahmen/${id}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }

  const [ampel, prognose, sollIst, compliance, nachweise, bescheidMeta, fiscalYears, costCenters] =
    await Promise.all([
      serverFetch<AmpelData>(`/protected/foerdermassnahmen/${id}/ampel`),
      serverFetch<PrognoseData>(`/protected/foerdermassnahmen/${id}/prognose`),
      serverFetch<SollIstData>(`/protected/foerdermassnahmen/${id}/soll-ist-position`),
      serverFetch<FehlbedarfStatusResult | null>(
        `/protected/foerdermassnahmen/${id}/compliance-status`,
      ),
      serverFetch<NachweisApiRow[]>(`/protected/verwendungsnachweise?funding_measure_id=${id}`),
      serverFetch<BescheidDokumentMeta | null>(`/protected/foerdermassnahmen/${id}/bescheid/meta`),
      serverFetch<FiscalYearRow[]>("/protected/haushaltsjahre"),
      loadActiveCostCentersForForms(),
    ]);

  const { is_expired, days_until_expiry } = measure;
  const isExpiringSoon = !is_expired && days_until_expiry !== null && days_until_expiry <= 30;

  const betrag_ist = parseFloat(ampel.betrag_ist);
  const betrag_bewilligt = parseFloat(ampel.betrag_bewilligt);
  const eigenanteilPct = Math.max(0, 100 - parseFloat(measure.foerderquote));

  // Compliance dismiss-hash (stable across identical states). Dismissal-state
  // tracking lives client-side via the dismiss endpoint; SSR starts undismissed.
  let complianceAlertHash: string | null = null;
  if (compliance && compliance.status !== "OK") {
    const hashInput = JSON.stringify({
      measureId: measure.id,
      status: compliance.status,
      eigenmittel_ist: Math.round(compliance.eigenmittel_ist * 100),
      drittmittel_ist: Math.round(compliance.drittmittel_ist * 100),
      zuwendung_abgerufen: Math.round(compliance.zuwendung_abgerufen * 100),
    });
    complianceAlertHash = createHash("sha256").update(hashInput).digest("hex").slice(0, 16);
  }

  const serializedMeasure = {
    id: measure.id,
    name: measure.name,
    status: measure.status,
    funder_id: measure.funder_id,
    funder: {
      id: measure.funder.id,
      name: measure.funder.name,
      typ: measure.funder.typ,
      notizen: measure.funder.notizen ?? null,
    },
    budget_gesamt: measure.budget_gesamt,
    foerderquote: measure.foerderquote,
    verwaltungspauschale_erlaubt: measure.verwaltungspauschale_erlaubt,
    verwaltungspauschale_prozent: measure.verwaltungspauschale_prozent,
    budget_flexibilitaet_prozent: measure.budget_flexibilitaet_prozent,
    overhead_limit_prozent: measure.overhead_limit_prozent,
    mwst_satz_prozent: measure.mwst_satz_prozent,
    eigenmittel_betrag: measure.eigenmittel_betrag,
    drittmittel_betrag: measure.drittmittel_betrag,
    laufzeit_von: measure.laufzeit_von,
    laufzeit_bis: measure.laufzeit_bis,
    mittelabruf_verfahren: measure.mittelabruf_verfahren,
    rules: measure.rules.map((r) => ({
      ...r,
      created_at: new Date(r.created_at),
      updated_at: new Date(r.updated_at),
    })),
    cost_centers: measure.cost_centers.map((cc) => ({
      ...cc,
      created_at: new Date(cc.created_at),
    })),
    _count: measure._count,
    is_expired,
    days_until_expiry,
  };

  return (
    <PageShell width="content">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-soft-ink4 mb-6">
        <Link
          href="/dashboard/foerdermassnahmen"
          className="hover:text-soft-accent transition-colors"
        >
          Fördermassnahmen
        </Link>
        <span>/</span>
        <span className="text-soft-ink2 truncate max-w-xs">{measure.name}</span>
      </nav>

      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="text-xs font-medium text-soft-ink4 uppercase tracking-wide">
              {measure.funder.name}
            </span>
            {is_expired && <Badge variant="danger">Abgelaufen</Badge>}
            <Badge variant={STATUS_BADGE_VARIANT[measure.status]}>
              {STATUS_LABEL[measure.status]}
            </Badge>
            {measure.status === "AKTIV" && (
              <AmpelBadge status={ampel.status} gruende={ampel.gruende} size="md" />
            )}
          </div>
          <h1 className="text-2xl font-bold text-soft-ink">{measure.name}</h1>
        </div>
        {measure.status !== "WIDERRUFEN" && (
          <Link href={`/dashboard/foerdermassnahmen/${id}/edit`}>
            <button
              type="button"
              aria-label="Fördermassnahme bearbeiten"
              title="Bearbeiten"
              className="p-1.5 rounded-soft-xs hover:bg-soft-surfaceAlt text-soft-ink4 hover:text-soft-ink2 transition-colors focus:outline-none focus:ring-2 focus:ring-soft-accent"
            >
              <Pencil className="h-5 w-5" aria-hidden="true" />
            </button>
          </Link>
        )}
      </div>

      {/* Expiry warning */}
      {isExpiringSoon && !is_expired && (
        <div className="mb-6 flex items-center gap-2 rounded-soft-sm bg-soft-warnSoft border border-soft-warn/30 px-4 py-3 text-sm text-soft-warn">
          <svg
            className="h-4 w-4 shrink-0"
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
          <span>
            <strong>
              Läuft in {days_until_expiry} {days_until_expiry === 1 ? "Tag" : "Tagen"} ab
            </strong>{" "}
            — bitte rechtzeitig Verwendungsnachweis einreichen.
          </span>
        </div>
      )}

      {/* Compliance-Banner */}
      {compliance && compliance.status !== "OK" && complianceAlertHash && (
        <ComplianceBanner
          variant={compliance.status}
          title={
            compliance.status === "WARNUNG"
              ? "Compliance-Warnung — Zuwendung zu hoch abgerufen"
              : "Compliance-Hinweis — Meldepflicht gegenüber Fördergeber"
          }
          message={compliance.nachricht ?? ""}
          alertHash={complianceAlertHash}
          initiallyDismissed={false}
          dismissEndpoint="/api/protected/compliance/dismiss"
        />
      )}

      {/* Cross-Finanzierungs-Widget */}
      {compliance && (
        <CrossFinanzierungWidget
          status={compliance.status}
          gesamtausgabenPlan={compliance.gesamtausgaben_plan}
          eigenmittelPlan={compliance.eigenmittel_plan}
          eigenmittelIst={compliance.eigenmittel_ist}
          drittmittelPlan={compliance.drittmittel_plan}
          drittmittelIst={compliance.drittmittel_ist}
          zuwendungHoechstbetrag={compliance.zuwendung_hoechstbetrag}
          zuwendungAbgerufen={compliance.zuwendung_abgerufen}
          fehlbedarfZulaessig={compliance.fehlbedarf_zulaessig}
          verbleibendAbrufbar={compliance.verbleibend_abrufbar}
          andereMassnahmen={compliance.andere_fundingmeasures_ueberlappend}
        />
      )}

      {/* Tab-Navigation */}
      <div
        className="flex gap-1 mb-6 border-b border-soft-line"
        role="tablist"
        aria-label="Massnahme-Ansicht"
      >
        {(["uebersicht", "bescheid", "regeln", "finanzplan", "nachweise"] as const).map((tab) => {
          const isActive = activeTab === tab;
          const label =
            tab === "uebersicht"
              ? "Übersicht"
              : tab === "bescheid"
                ? "Zuwendungsbescheid"
                : tab === "regeln"
                  ? `Förderregeln (${measure._count.rules})`
                  : tab === "finanzplan"
                    ? "Finanzplan"
                    : "Nachweise";
          const href =
            tab === "uebersicht"
              ? `/dashboard/foerdermassnahmen/${id}`
              : `/dashboard/foerdermassnahmen/${id}?tab=${tab}`;
          return (
            <Link
              key={tab}
              href={href}
              role="tab"
              aria-selected={isActive}
              className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px focus:outline-none focus:ring-2 focus:ring-soft-accent rounded-t
                ${
                  isActive
                    ? "border-soft-accent text-soft-accent"
                    : "border-transparent text-soft-ink2 hover:text-soft-ink hover:border-soft-line"
                }`}
            >
              {label}
            </Link>
          );
        })}
      </div>

      {/* Zuwendungsbescheid-Tab */}
      <div className={activeTab === "bescheid" ? "block" : "hidden"}>
        <BescheidTab
          measureId={id}
          canEdit={measure.status !== "WIDERRUFEN"}
          initialDokument={bescheidMeta}
        />
      </div>

      {/* Förderregeln-Tab */}
      <div className={activeTab === "regeln" ? "block" : "hidden"}>
        <div className="rounded-soft border border-soft-line bg-white p-6">
          <div className="flex items-baseline justify-between gap-4 mb-4">
            <h2 className="text-sm font-semibold text-soft-ink2 uppercase tracking-wide">
              Förderregeln ({measure._count.rules})
            </h2>
            <p className="text-xs text-soft-ink3">
              Förderfähigkeitsregeln aus dem Zuwendungsbescheid
            </p>
          </div>
          {measure.rules.length === 0 ? (
            <p className="text-sm text-soft-ink4 italic">Keine Förderregeln hinterlegt.</p>
          ) : (
            <div className="space-y-3">
              {measure.rules.map((rule) => (
                <div
                  key={rule.id}
                  className="flex items-start gap-3 rounded-soft-sm border border-soft-line2 bg-soft-line2 p-3"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <Badge variant={RULE_TYP_BADGE[rule.typ]}>{RULE_TYP_LABEL[rule.typ]}</Badge>
                    </div>
                    <div className="text-sm font-medium text-soft-ink">{rule.schluessel}</div>
                    {rule.wert && (
                      <div className="text-xs text-soft-ink3 mt-0.5">Wert: {rule.wert}</div>
                    )}
                    {rule.beschreibung && (
                      <div className="text-xs text-soft-ink4 mt-0.5">{rule.beschreibung}</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Finanzplan-Tab (self-loads via useEffect) */}
      <div className={activeTab === "finanzplan" ? "block" : "hidden"}>
        <p className="text-sm text-soft-ink3 mb-4">Monatliche Verteilung der bewilligten Mittel</p>
        <FinanzplanTab measureId={id} canEdit={measure.status !== "WIDERRUFEN"} />
      </div>

      {/* Nachweise-Tab */}
      <div className={activeTab === "nachweise" ? "block" : "hidden"}>
        <NachweiseTab
          measureId={id}
          canEdit={measure.status !== "WIDERRUFEN"}
          hasZwischennachweisPflicht={measure.rules.some(
            (r) => r.typ === "ZWISCHENNACHWEIS_PFLICHT",
          )}
          fiscalYears={fiscalYears.map((f) => ({ id: f.id, jahr: f.jahr, status: f.status }))}
          initialNachweise={nachweise.map((n) => ({
            id: n.id,
            typ: n.typ,
            status: n.status,
            zeitraum_von: n.zeitraum_von,
            zeitraum_bis: n.zeitraum_bis,
            frist: n.frist,
            fiscal_year_jahr: n.fiscal_year?.jahr ?? 0,
            notiz: n.notiz,
          }))}
        />
      </div>

      {/* Übersicht-Tab */}
      <div
        className={activeTab === "uebersicht" ? "grid grid-cols-1 lg:grid-cols-3 gap-6" : "hidden"}
      >
        {/* Left column */}
        <div className="lg:col-span-2 space-y-6">
          {/* Budget Overview */}
          <div className="rounded-soft border border-soft-line bg-white p-6">
            <h2 className="text-sm font-semibold text-soft-ink2 uppercase tracking-wide mb-4">
              Budget
            </h2>
            <div className="numeric text-3xl font-bold text-soft-ink mb-1">
              {formatEuro(measure.budget_gesamt)}
            </div>
            <div className="text-sm text-soft-ink3 mb-4">
              Förderquote{" "}
              <span className="numeric">{parseFloat(measure.foerderquote).toFixed(0)}%</span> ·
              Eigenanteil <span className="numeric">{eigenanteilPct.toFixed(0)}%</span>
            </div>
            <BudgetProgressBar used={betrag_ist} total={betrag_bewilligt} />
          </div>

          {/* Kerndaten */}
          <div className="rounded-soft border border-soft-line bg-white p-6">
            <h2 className="text-sm font-semibold text-soft-ink2 uppercase tracking-wide mb-4">
              Kerndaten
            </h2>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4 text-sm">
              <div>
                <dt className="text-soft-ink4 text-xs mb-0.5">Bewilligung von</dt>
                <dd className="font-medium text-soft-ink">{formatDate(measure.laufzeit_von)}</dd>
              </div>
              <div>
                <dt className="text-soft-ink4 text-xs mb-0.5">Bewilligung bis</dt>
                <dd
                  className={`font-medium ${is_expired ? "text-soft-crit" : isExpiringSoon ? "text-soft-warn" : "text-soft-ink"}`}
                >
                  {formatDate(measure.laufzeit_bis)}
                </dd>
              </div>
              {measure.durchfuehrungs_von && measure.durchfuehrungs_bis && (
                <>
                  <div>
                    <dt className="text-soft-ink4 text-xs mb-0.5">Durchführung von</dt>
                    <dd className="font-medium text-soft-ink">
                      {formatDate(measure.durchfuehrungs_von)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-soft-ink4 text-xs mb-0.5">Durchführung bis</dt>
                    <dd className="font-medium text-soft-ink">
                      {formatDate(measure.durchfuehrungs_bis)}
                    </dd>
                  </div>
                </>
              )}
              {measure.antragsnummer && (
                <div className="col-span-2">
                  <dt className="text-soft-ink4 text-xs mb-0.5">Antragsnummer</dt>
                  <dd className="font-medium text-soft-ink numeric">{measure.antragsnummer}</dd>
                </div>
              )}
              <div>
                <dt className="text-soft-ink4 text-xs mb-0.5">Mittelabruf-Verfahren</dt>
                <dd className="font-medium text-soft-ink">
                  {VERFAHREN_LABEL[measure.mittelabruf_verfahren] ?? measure.mittelabruf_verfahren}
                </dd>
              </div>
              <div>
                <dt className="text-soft-ink4 text-xs mb-0.5">Budget-Flexibilität</dt>
                <dd className="numeric font-medium text-soft-ink">
                  {parseFloat(measure.budget_flexibilitaet_prozent).toFixed(0)}%
                </dd>
              </div>
              {measure.verwaltungspauschale_erlaubt && (
                <div>
                  <dt className="text-soft-ink4 text-xs mb-0.5">Verwaltungspauschale</dt>
                  <dd className="font-medium text-soft-ink">
                    {measure.verwaltungspauschale_prozent ? (
                      <span className="numeric">
                        {parseFloat(measure.verwaltungspauschale_prozent).toFixed(0)}%
                      </span>
                    ) : (
                      "Erlaubt (kein Satz gesetzt)"
                    )}
                  </dd>
                </div>
              )}
              <div>
                <dt className="text-soft-ink4 text-xs mb-0.5">Gemeinkostendeckel</dt>
                <dd className="font-medium text-soft-ink">
                  {measure.overhead_limit_prozent ? (
                    <span className="numeric">
                      {parseFloat(measure.overhead_limit_prozent).toFixed(1)}%
                    </span>
                  ) : (
                    <span className="text-soft-ink4 font-normal">Kein Limit</span>
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-soft-ink4 text-xs mb-0.5">Fördergeber-Typ</dt>
                <dd className="font-medium text-soft-ink">{measure.funder.typ}</dd>
              </div>
            </dl>

            {measure.funder.notizen && (
              <div className="mt-4 rounded-soft-xs bg-soft-line2 border border-soft-line2 p-3 text-xs text-soft-ink2">
                <span className="font-medium">Notizen Fördergeber: </span>
                {measure.funder.notizen}
              </div>
            )}
          </div>

          {/* Soll-Ist-Vergleich pro Finanzplan-Position */}
          <div className="rounded-soft border border-soft-line bg-white p-6">
            <div className="flex items-baseline justify-between gap-4 mb-4">
              <h2 className="text-sm font-semibold text-soft-ink2 uppercase tracking-wide">
                Soll/Ist pro Finanzplan-Position
              </h2>
              {sollIst.data.length > 0 && (
                <p className="text-xs text-soft-ink3">
                  Bewilligt vs. tatsächlich verbucht (Mittelzuordnungen)
                </p>
              )}
            </div>
            {sollIst.data.length === 0 ? (
              <EmptyState
                icon={Layers}
                title="Noch keine Finanzplan-Positionen"
                description="Lege Positionen an, um den Soll/Ist-Vergleich pro Bescheid-Position zu sehen."
                action={{
                  label: "Finanzplan-Positionen anlegen",
                  href: `/dashboard/foerdermassnahmen/${id}/edit?step=4`,
                }}
              />
            ) : (
              <SollIstTabelle
                data={sollIst.data}
                gesamt_beantragt={sollIst.gesamt_bewilligt}
                gesamt_bewilligt={sollIst.gesamt_bewilligt}
                gesamt_ist={sollIst.gesamt_ist}
                titleColumn="Position"
                measureId={id}
              />
            )}
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-6">
          {/* Kostenstellen */}
          <div className="rounded-soft border border-soft-line bg-white p-5">
            <h2 className="text-sm font-semibold text-soft-ink2 uppercase tracking-wide mb-3">
              Kostenstellen ({measure._count.cost_centers})
            </h2>
            {measure.cost_centers.length === 0 ? (
              <p className="text-sm text-soft-ink4 italic">Keine Kostenstellen zugeordnet.</p>
            ) : (
              <div className="space-y-2">
                {measure.cost_centers.map((cc) => (
                  <div
                    key={cc.id}
                    className="flex items-center gap-2 rounded-soft-xs bg-soft-line2 border border-soft-line2 px-3 py-2"
                  >
                    <span className="font-mono text-xs bg-soft-line text-soft-ink2 rounded px-1.5 py-0.5">
                      {cc.cost_center.code}
                    </span>
                    <span className="text-sm text-soft-ink2 truncate">{cc.cost_center.name}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Jahresendprognose */}
          <PrognoseCard data={prognose} />

          {/* Actions card — client component */}
          <FoerdermassnahmeDetailClient
            measure={serializedMeasure}
            costCenters={costCenters}
            fiscalYears={fiscalYears}
          />
        </div>
      </div>
    </PageShell>
  );
}
