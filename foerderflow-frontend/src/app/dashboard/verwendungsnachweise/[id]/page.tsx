import Link from "next/link";
import { notFound } from "next/navigation";

import { requireOrgSession } from "@/lib/session";
import { ApiError, serverFetch } from "@/lib/serverApi";
import { Badge } from "@/components/ui/Badge";
import { PageShell } from "@/components/ui/PageShell";
import { VerwNachweisDetailClient } from "./VerwNachweisDetailClient";
import { VerwNachweisVorschau } from "./VerwNachweisVorschau";

type NachweisTyp = "ZWISCHENNACHWEIS" | "VERWENDUNGSNACHWEIS" | "SACHBERICHT_ONLY";
type NachweisStatus = "OFFEN" | "IN_BEARBEITUNG" | "EINGEREICHT" | "ANERKANNT" | "ABGELEHNT";

const TYP_LABEL: Record<NachweisTyp, string> = {
  ZWISCHENNACHWEIS: "Zwischennachweis",
  VERWENDUNGSNACHWEIS: "Verwendungsnachweis",
  SACHBERICHT_ONLY: "Sachbericht",
};

const STATUS_LABEL: Record<NachweisStatus, string> = {
  OFFEN: "Offen",
  IN_BEARBEITUNG: "In Bearbeitung",
  EINGEREICHT: "Eingereicht",
  ANERKANNT: "Anerkannt",
  ABGELEHNT: "Abgelehnt",
};

const STATUS_VARIANT: Record<NachweisStatus, "muted" | "default" | "warning" | "success" | "danger"> =
  {
    OFFEN: "muted",
    IN_BEARBEITUNG: "default",
    EINGEREICHT: "warning",
    ANERKANNT: "success",
    ABGELEHNT: "danger",
  };

type NachweisDetail = {
  id: string;
  funding_measure_id: string;
  fiscal_year_id: string;
  zeitraum_von: string;
  zeitraum_bis: string;
  frist: string;
  typ: NachweisTyp;
  status: NachweisStatus;
  snapshot_json: unknown;
  notiz: string | null;
  eingereicht_am: string | null;
  eingereicht_von: string | null;
  funding_measure: { name: string } | null;
  fiscal_year: { jahr: number; status: string } | null;
};

function formatDate(d: string): string {
  return new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(d));
}

function formatDateTime(d: string): string {
  return new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(d));
}

function tageVerbleibend(frist: string): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const f = new Date(frist);
  f.setHours(0, 0, 0, 0);
  return Math.ceil((f.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
}

type PageProps = { params: Promise<{ id: string }> };

export default async function VerwNachweisDetailPage({ params }: PageProps) {
  await requireOrgSession();
  const { id } = await params;

  let nachweis: NachweisDetail;
  try {
    nachweis = await serverFetch<NachweisDetail>(`/protected/verwendungsnachweise/${id}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }

  const measureId = nachweis.funding_measure_id;
  const measureName = nachweis.funding_measure?.name ?? "—";
  const fiscalYear = nachweis.fiscal_year;
  const tage = tageVerbleibend(nachweis.frist);
  const isOpen = ["OFFEN", "IN_BEARBEITUNG"].includes(nachweis.status);
  const fristKritisch = isOpen && tage <= 14;
  const isReadonly = ["EINGEREICHT", "ANERKANNT", "ABGELEHNT"].includes(nachweis.status);
  const fyClosed = fiscalYear?.status === "GESCHLOSSEN";

  return (
    <PageShell width="content">
      <nav className="flex items-center gap-2 text-sm text-soft-ink4 mb-6">
        <Link href="/dashboard/foerdermassnahmen" className="hover:text-soft-accent transition-colors">
          Fördermassnahmen
        </Link>
        <span>/</span>
        <Link
          href={`/dashboard/foerdermassnahmen/${measureId}?tab=nachweise`}
          className="hover:text-soft-accent transition-colors truncate max-w-xs"
        >
          {measureName}
        </Link>
        <span>/</span>
        <span className="text-soft-ink2">{TYP_LABEL[nachweis.typ]}</span>
      </nav>

      <div className="flex items-start justify-between gap-4 mb-6">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="text-xs font-medium text-soft-ink4 uppercase tracking-wide">
              Haushaltsjahr {fiscalYear?.jahr}
            </span>
            <Badge variant={STATUS_VARIANT[nachweis.status]}>{STATUS_LABEL[nachweis.status]}</Badge>
            {fyClosed && <Badge variant="muted">HHJ geschlossen</Badge>}
          </div>
          <h1 className="text-2xl font-bold text-soft-ink">{TYP_LABEL[nachweis.typ]}</h1>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Kerndaten */}
          <div className="rounded-soft border border-soft-line bg-white p-6">
            <h2 className="text-sm font-semibold text-soft-ink2 uppercase tracking-wide mb-4">
              Kerndaten
            </h2>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4 text-sm">
              <div>
                <dt className="text-soft-ink4 text-xs mb-0.5">Zeitraum von</dt>
                <dd className="numeric font-medium text-soft-ink">
                  {formatDate(nachweis.zeitraum_von)}
                </dd>
              </div>
              <div>
                <dt className="text-soft-ink4 text-xs mb-0.5">Zeitraum bis</dt>
                <dd className="numeric font-medium text-soft-ink">
                  {formatDate(nachweis.zeitraum_bis)}
                </dd>
              </div>
              <div>
                <dt className="text-soft-ink4 text-xs mb-0.5">Einreichfrist</dt>
                <dd
                  className={`numeric font-medium ${fristKritisch ? "text-soft-warn" : "text-soft-ink"}`}
                >
                  {formatDate(nachweis.frist)}
                </dd>
                {isOpen && (
                  <dd
                    className={`text-xs mt-0.5 ${fristKritisch ? "text-soft-warn" : "text-soft-ink4"}`}
                  >
                    {tage < 0
                      ? `${Math.abs(tage)} Tage überfällig`
                      : tage === 0
                        ? "heute fällig"
                        : `noch ${tage} Tage`}
                  </dd>
                )}
              </div>
              <div>
                <dt className="text-soft-ink4 text-xs mb-0.5">Typ</dt>
                <dd className="font-medium text-soft-ink">{TYP_LABEL[nachweis.typ]}</dd>
              </div>
              {nachweis.notiz && (
                <div className="col-span-2">
                  <dt className="text-soft-ink4 text-xs mb-0.5">Notiz</dt>
                  <dd className="text-soft-ink2 whitespace-pre-wrap">{nachweis.notiz}</dd>
                </div>
              )}
            </dl>
          </div>

          {/* Vorschau — nur vor Einreichung sinnvoll */}
          {!isReadonly && <VerwNachweisVorschau measureId={measureId} />}

          {/* Snapshot — nach Einreichung */}
          {isReadonly && nachweis.snapshot_json ? (
            <div className="rounded-soft border border-soft-line bg-white p-6">
              <h2 className="text-sm font-semibold text-soft-ink2 uppercase tracking-wide mb-2">
                Eingereichter Snapshot
              </h2>
              {nachweis.eingereicht_am && (
                <p className="text-xs text-soft-ink4 mb-4">
                  Eingereicht am{" "}
                  <span className="numeric">{formatDateTime(nachweis.eingereicht_am)}</span>
                </p>
              )}
              <SnapshotPreview snapshot={nachweis.snapshot_json} />
            </div>
          ) : null}

          {/* Dokumente */}
          <div className="rounded-soft border border-soft-line bg-white p-6">
            <h2 className="text-sm font-semibold text-soft-ink2 uppercase tracking-wide mb-4">
              Dokumente
            </h2>
            <p className="text-sm text-soft-ink3 mb-3">
              Excel- und DOCX-Export sowie alle Belege werden als ZIP-Paket für die Massnahme +
              Haushaltsjahr {fiscalYear?.jahr} zusammengestellt.
            </p>
            <a
              href={`/api/protected/foerdermassnahmen/${measureId}/verwendungsnachweis?fiscal_year_id=${nachweis.fiscal_year_id}`}
              className="inline-flex items-center justify-center font-medium transition-colors duration-150 outline-none shadow-soft px-4 py-2 text-sm min-h-[44px] rounded-soft-sm bg-soft-accent text-white hover:bg-soft-accentDark focus:ring-2 focus:ring-soft-accent focus:ring-offset-2"
            >
              ZIP herunterladen
            </a>
          </div>
        </div>

        <div className="space-y-6">
          <VerwNachweisDetailClient
            id={nachweis.id}
            status={nachweis.status}
            measureId={measureId}
            fiscalYearClosed={!!fyClosed}
          />
        </div>
      </div>
    </PageShell>
  );
}

// ─────────────────────────────────────────────
// Snapshot-Vorschau (humanized, server-side)
// ─────────────────────────────────────────────

function formatEuro(n: number): string {
  return new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
  }).format(n);
}

function SnapshotPreview({ snapshot }: { snapshot: unknown }) {
  if (!snapshot || typeof snapshot !== "object" || Array.isArray(snapshot)) {
    return <p className="text-sm text-soft-ink4 italic">Keine Snapshot-Daten verfügbar.</p>;
  }
  const s = snapshot as Record<string, unknown>;
  const einnahmen = (s.einnahmen ?? {}) as {
    eigenmittel?: number;
    zuwendung?: number;
    sonstige?: number;
  };
  const ausgaben = Array.isArray(s.ausgaben)
    ? (s.ausgaben as Array<{
        kostenart: string;
        betrag: number;
        belege_count: number;
      }>)
    : [];
  const transaktionen = Array.isArray(s.transaktionen) ? (s.transaktionen as unknown[]) : [];
  const gesamtAusgaben = ausgaben.reduce((sum, a) => sum + (a.betrag ?? 0), 0);
  const gesamtBelege = ausgaben.reduce((sum, a) => sum + (a.belege_count ?? 0), 0);

  return (
    <div className="space-y-4 text-sm">
      <div className="grid grid-cols-3 gap-3">
        <SummaryCard label="Zuwendung" value={formatEuro(einnahmen.zuwendung ?? 0)} />
        <SummaryCard label="Eigenmittel" value={formatEuro(einnahmen.eigenmittel ?? 0)} />
        <SummaryCard
          label="Ausgaben"
          value={formatEuro(gesamtAusgaben)}
          hint={`${transaktionen.length} Transaktionen · ${gesamtBelege} Belege`}
        />
      </div>

      {ausgaben.length > 0 && (
        <div>
          <h3 className="text-xs font-medium text-soft-ink3 uppercase tracking-wide mb-2">
            Ausgaben pro Kostenart
          </h3>
          <div className="rounded-soft-sm border border-soft-line2 overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-soft-surfaceAlt text-soft-ink3">
                <tr>
                  <th className="text-left px-3 py-2 font-medium">Kostenart</th>
                  <th className="text-right px-3 py-2 font-medium">Betrag</th>
                  <th className="text-right px-3 py-2 font-medium">Belege</th>
                </tr>
              </thead>
              <tbody>
                {ausgaben.map((a) => (
                  <tr key={a.kostenart} className="border-t border-soft-line2">
                    <td className="px-3 py-2 text-soft-ink2">{a.kostenart}</td>
                    <td className="px-3 py-2 numeric text-right text-soft-ink">
                      {formatEuro(a.betrag ?? 0)}
                    </td>
                    <td className="px-3 py-2 numeric text-right text-soft-ink3">
                      {a.belege_count ?? 0}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function SummaryCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-soft-sm border border-soft-line2 bg-soft-line2/40 px-3 py-2.5">
      <div className="text-xs text-soft-ink3 uppercase tracking-wide">{label}</div>
      <div className="numeric text-soft-ink font-semibold">{value}</div>
      {hint && <div className="text-xs text-soft-ink4 mt-0.5">{hint}</div>}
    </div>
  );
}
