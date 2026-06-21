"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { formatEur } from "@/lib/utils";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { FundAllocationForm } from "@/components/forms/FundAllocationForm";
import { BelegUploadForm } from "@/components/forms/BelegUploadForm";
import { SplitEditor } from "@/components/forms/SplitEditor";
import { useToast } from "@/components/ui/ToastProvider";
import { FileText, FileImage, Link2 } from "lucide-react";
import { PageShell } from "@/components/ui/PageShell";

type CostCenterOption = { id: string; name: string; code: string };

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────

type FundAllocationData = {
  id: string;
  betrag_foerderung: string;
  betrag_eigenanteil: string;
  status: string;
  notiz: string | null;
  funding_measure: { id: string; name: string };
  transaction_split_id: string;
};

type SplitData = {
  id: string;
  prozent: string;
  betrag_anteil: string;
  cost_center: { id: string; name: string; code: string };
  fund_allocations: FundAllocationData[];
};

type BelegData = {
  id: string;
  datei_name: string | null;
  datei_typ: string | null;
  externe_referenz: string | null;
  retention_until: string;
  created_at: string;
};

type TransactionData = {
  id: string;
  datum: string;
  betrag: string;
  typ: string;
  auftraggeber: string | null;
  verwendungszweck: string | null;
  kostenbereich: { id: string; code: string; bezeichnung: string } | null;
  notiz: string | null;
  status: string;
  splits: SplitData[];
  import_batch: { dateiname: string } | null;
};

// ─────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────

const STATUS_COLORS: Record<string, "muted" | "default" | "success" | "warning"> =
  {
    IMPORTIERT: "muted",
    KATEGORISIERT: "default",
    ZUGEORDNET: "warning",
    ABGESCHLOSSEN: "success",
  };

const STATUS_LABELS: Record<string, string> = {
  IMPORTIERT: "Offen",
  KATEGORISIERT: "Kategorisiert",
  ZUGEORDNET: "Zugeordnet",
  ABGESCHLOSSEN: "Abgeschlossen",
};

const ALLOCATION_STATUS_COLORS: Record<string, "muted" | "default" | "warning"> =
  {
    VORLAEUFIG: "warning",
    BESTAETIGT: "default",
  };

// ─────────────────────────────────────────────
// Page Component
// ─────────────────────────────────────────────

export default function TransaktionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const toast = useToast();

  const [transaction, setTransaction] = useState<TransactionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const [costCenters, setCostCenters] = useState<CostCenterOption[]>([]);
  const [showAllocationForm, setShowAllocationForm] = useState(false);
  const [deletingAlloc, setDeletingAlloc] = useState<{
    splitId: string;
    measureName: string;
  } | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // Belege
  const [belege, setBelege] = useState<BelegData[]>([]);
  const [showBelegForm, setShowBelegForm] = useState(false);
  const [deletingBeleg, setDeletingBeleg] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [deleteBelegLoading, setDeleteBelegLoading] = useState(false);

  const fetchBelege = useCallback(() => {
    fetch(`/api/protected/transaktionen/${id}/belege`)
      .then((r) => r.json())
      .then((json: { data?: BelegData[] }) => {
        if (json.data) setBelege(json.data);
      })
      .catch(() => {
        // Stille Fehlerbehandlung — toast wird bei expliziten Aktionen gezeigt
      });
  }, [id]);

  const fetchTransaction = useCallback(() => {
    setLoading(true);
    fetch(`/api/protected/transaktionen/${id}`)
      .then((r) => {
        if (r.status === 404) {
          setNotFound(true);
          return null;
        }
        return r.json();
      })
      .then((json: { data?: TransactionData } | null) => {
        if (json?.data) setTransaction(json.data);
      })
      .catch(() => {
        toast.error("Transaktion konnte nicht geladen werden.");
      })
      .finally(() => setLoading(false));
  }, [id, toast]);

  useEffect(() => {
    fetchTransaction();
    fetchBelege();
    // Kostenstellen für Split-Editor laden
    fetch("/api/protected/kostenstellen")
      .then((r) => r.json())
      .then((json: { data?: CostCenterOption[] }) => {
        if (json.data) setCostCenters(json.data);
      })
      .catch(() => {});
  }, [fetchTransaction, fetchBelege]);

  async function handleDeleteBeleg(belegId: string) {
    setDeleteBelegLoading(true);
    try {
      const res = await fetch(
        `/api/protected/transaktionen/${id}/belege/${belegId}`,
        { method: "DELETE" }
      );
      const json = (await res.json()) as {
        data?: { message: string };
        warning?: string;
        error?: string;
      };
      if (!res.ok) {
        toast.error(json.error ?? "Löschen fehlgeschlagen.");
        return;
      }
      toast.success(json.data?.message ?? "Beleg gelöscht.");
      if (json.warning) {
        // Kurze Verzögerung damit beide Toasts sichtbar sind
        setTimeout(() => toast.error(`Hinweis: ${json.warning}`), 400);
      }
      setDeletingBeleg(null);
      fetchBelege();
    } catch {
      toast.error("Netzwerkfehler — bitte erneut versuchen.");
    } finally {
      setDeleteBelegLoading(false);
    }
  }

  async function handleDeleteAllocation(splitId: string) {
    setDeleteLoading(true);
    try {
      const res = await fetch(
        `/api/protected/transaktionen/${id}/fund-allocation`,
        {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ transaction_split_id: splitId }),
        }
      );
      if (!res.ok) {
        const json = (await res.json()) as { error?: string };
        toast.error(json.error ?? "Löschen fehlgeschlagen.");
        return;
      }
      toast.success("Förderzuordnung entfernt.");
      setDeletingAlloc(null);
      fetchTransaction();
    } catch {
      toast.error("Netzwerkfehler — bitte erneut versuchen.");
    } finally {
      setDeleteLoading(false);
    }
  }

  // ── Loading / Error states ──────────────────

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto py-16 px-4 text-center text-soft-ink4 text-sm">
        Lädt…
      </div>
    );
  }

  if (notFound || !transaction) {
    return (
      <div className="max-w-2xl mx-auto py-16 px-4 text-center">
        <p className="text-soft-ink3 text-sm">Transaktion nicht gefunden.</p>
        <Link
          href="/dashboard/transaktionen"
          className="mt-4 inline-block text-soft-accent text-sm hover:underline"
        >
          Zurück zur Übersicht
        </Link>
      </div>
    );
  }

  const betrag = parseFloat(transaction.betrag);
  const isAusgabe = betrag < 0;

  // Alle FundAllocations aus allen Splits extrahieren
  const allAllocations = transaction.splits.flatMap((s) =>
    s.fund_allocations.map((a) => ({ ...a, split: s }))
  );

  // Splits ohne bestehende Allocation für das Formular
  const freeSplits = transaction.splits.filter(
    (s) => s.fund_allocations.length === 0
  );

  // Props für FundAllocationForm
  const formSplits = freeSplits.map((s) => ({
    id: s.id,
    cost_center: s.cost_center,
    prozent: parseFloat(s.prozent),
    betrag_anteil: s.betrag_anteil,
  }));

  return (
    <PageShell width="form" className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-soft-ink3">
        <Link href="/dashboard/transaktionen" className="hover:text-soft-accent">
          Transaktionen
        </Link>
        <span>/</span>
        <span className="text-soft-ink truncate max-w-xs">
          {transaction.auftraggeber ?? "Unbekannt"}
        </span>
      </div>

      {/* Header Card */}
      <div className="bg-white rounded-soft-sm border border-soft-line p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-xl font-bold text-soft-ink truncate">
              {transaction.auftraggeber ?? (
                <span className="text-soft-ink4 italic font-normal">
                  Unbekannter Auftraggeber
                </span>
              )}
            </h1>
            <p className="text-sm text-soft-ink3 mt-1">
              {new Date(transaction.datum).toLocaleDateString("de-DE", {
                day: "2-digit",
                month: "long",
                year: "numeric",
              })}
            </p>
          </div>
          <div className="text-right flex-shrink-0">
            <p
              className={`text-2xl font-bold font-mono ${
                isAusgabe ? "text-soft-crit" : "text-soft-ok"
              }`}
            >
              {formatEur(betrag)}
            </p>
            <div className="mt-1">
              <Badge
                variant={STATUS_COLORS[transaction.status] ?? "muted"}
              >
                {STATUS_LABELS[transaction.status] ?? transaction.status}
              </Badge>
            </div>
          </div>
        </div>

        {transaction.verwendungszweck && (
          <p className="mt-4 text-sm text-soft-ink2 bg-soft-surfaceAlt rounded-soft-xs p-3 leading-relaxed">
            {transaction.verwendungszweck}
          </p>
        )}

        <dl className="mt-5 grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-soft-ink3 text-xs uppercase tracking-wide">
              Kostenbereich
            </dt>
            <dd className="font-medium text-soft-ink mt-0.5">
              {transaction.kostenbereich?.bezeichnung ?? (
                <span className="text-soft-ink4">—</span>
              )}
            </dd>
          </div>
          <div>
            <dt className="text-soft-ink3 text-xs uppercase tracking-wide">
              Typ
            </dt>
            <dd className="font-medium text-soft-ink mt-0.5">
              {transaction.typ}
            </dd>
          </div>
          {transaction.import_batch && (
            <div className="col-span-2">
              <dt className="text-soft-ink3 text-xs uppercase tracking-wide">
                Import-Datei
              </dt>
              <dd className="font-medium text-soft-ink mt-0.5 text-xs font-mono">
                {transaction.import_batch.dateiname}
              </dd>
            </div>
          )}
          {transaction.notiz && (
            <div className="col-span-2">
              <dt className="text-soft-ink3 text-xs uppercase tracking-wide">
                Notiz
              </dt>
              <dd className="text-soft-ink2 mt-0.5">{transaction.notiz}</dd>
            </div>
          )}
        </dl>
      </div>

      {/* Kostenstellen-Splits */}
      <div className="bg-white rounded-soft-sm border border-soft-line p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-soft-ink">
            Kostenstellen-Zuordnung
          </h2>
          {transaction.splits.length > 0 && (
            <span className="text-xs text-soft-ink4">
              {transaction.splits.length} KST
              {transaction.splits.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>

        <SplitEditor
          transactionId={transaction.id}
          betrag={Math.abs(parseFloat(transaction.betrag))}
          currentSplits={transaction.splits}
          costCenters={costCenters}
          auftraggeber={transaction.auftraggeber}
          verwendungszweck={transaction.verwendungszweck}
          kostenbereichId={transaction.kostenbereich?.id ?? null}
          kostenbereichBezeichnung={transaction.kostenbereich?.bezeichnung ?? null}
          onSaved={fetchTransaction}
        />
      </div>

      {/* Förderzuordnung */}
      <div className="bg-white rounded-soft-sm border border-soft-line p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-soft-ink">
            Förderzuordnung
          </h2>
          {freeSplits.length > 0 && !showAllocationForm && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowAllocationForm(true)}
            >
              + Zuordnung hinzufügen
            </Button>
          )}
        </div>

        {/* Inline-Formular */}
        {showAllocationForm && formSplits.length > 0 && (
          <div className="mb-5 rounded-soft-xs border border-soft-accent/20 bg-soft-accentSoft/40 p-4">
            <p className="text-sm font-medium text-soft-ink2 mb-3">
              Neue Förderzuordnung
            </p>
            <FundAllocationForm
              transactionId={id}
              splits={formSplits}
              transactionKostenbereichId={transaction.kostenbereich?.id ?? null}
              transactionKostenbereichCode={transaction.kostenbereich?.code ?? null}
              onSuccess={() => {
                setShowAllocationForm(false);
                fetchTransaction();
              }}
              onCancel={() => setShowAllocationForm(false)}
            />
          </div>
        )}

        {/* Bestehende Zuordnungen */}
        {allAllocations.length === 0 && !showAllocationForm ? (
          <div className="text-center py-6">
            <p className="text-sm text-soft-ink3">
              Noch keine Förderzuordnung vorhanden.
            </p>
            {transaction.splits.length === 0 && (
              <p className="text-xs text-soft-ink4 mt-1">
                Zuerst Kostenstellen zuordnen.
              </p>
            )}
          </div>
        ) : (
          allAllocations.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-soft-ink4 uppercase tracking-wide border-b border-soft-line2">
                    <th className="text-left pb-2 font-medium">Massnahme</th>
                    <th className="text-right pb-2 font-medium">Förderbetrag</th>
                    <th className="text-right pb-2 font-medium">Eigenanteil</th>
                    <th className="text-center pb-2 font-medium">Status</th>
                    <th className="pb-2" />
                  </tr>
                </thead>
                <tbody>
                  {allAllocations.map((a) => (
                    <tr
                      key={a.id}
                      className="border-b border-soft-line2 last:border-0"
                    >
                      <td className="py-2 pr-3">
                        <p className="font-medium text-soft-ink">
                          {a.funding_measure.name}
                        </p>
                        <p className="text-xs text-soft-ink4">
                          {a.split.cost_center.name}
                        </p>
                      </td>
                      <td className="py-2 text-right font-mono text-soft-ok font-medium">
                        {formatEur(parseFloat(a.betrag_foerderung))}
                      </td>
                      <td className="py-2 text-right font-mono text-soft-ink2">
                        {formatEur(parseFloat(a.betrag_eigenanteil))}
                      </td>
                      <td className="py-2 text-center">
                        <Badge
                          variant={
                            ALLOCATION_STATUS_COLORS[a.status] ?? "muted"
                          }
                        >
                          {a.status === "VORLAEUFIG"
                            ? "Vorläufig"
                            : a.status}
                        </Badge>
                      </td>
                      <td className="py-2 pl-3">
                        <button
                          onClick={() =>
                            setDeletingAlloc({
                              splitId: a.transaction_split_id,
                              measureName: a.funding_measure.name,
                            })
                          }
                          className="text-xs text-soft-crit hover:text-soft-crit transition-colors"
                        >
                          Entfernen
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
      </div>

      {/* Belege */}
      <div className="bg-white rounded-soft-sm border border-soft-line p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-soft-ink">Belege</h2>
          {!showBelegForm && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowBelegForm(true)}
            >
              + Beleg hinzufügen
            </Button>
          )}
        </div>

        {/* Inline-Formular */}
        {showBelegForm && (
          <div className="mb-5 rounded-soft-xs border border-soft-accent/20 bg-soft-accentSoft/40 p-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-medium text-soft-ink2">Neuer Beleg</p>
              <button
                type="button"
                onClick={() => setShowBelegForm(false)}
                className="text-xs text-soft-ink4 hover:text-soft-ink2"
              >
                Schließen
              </button>
            </div>
            <BelegUploadForm
              transactionId={id}
              onSuccess={() => {
                setShowBelegForm(false);
                fetchBelege();
              }}
            />
          </div>
        )}

        {/* Belege-Liste */}
        {belege.length === 0 ? (
          <div className="text-center py-6">
            <p className="text-sm text-soft-ink3">Noch keine Belege vorhanden.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {belege.map((b) => {
              const retentionDate = new Date(b.retention_until);
              const today = new Date();
              const warnDate = new Date();
              warnDate.setDate(today.getDate() + 30);

              let retentionBadge: { label: string; variant: "warning" | "danger" | "muted" } | null =
                null;
              if (retentionDate < today) {
                retentionBadge = { label: "Frist abgelaufen", variant: "danger" };
              } else if (retentionDate < warnDate) {
                retentionBadge = { label: "Frist bald", variant: "warning" };
              }

              const BelegIcon = b.externe_referenz
                ? Link2
                : b.datei_typ?.startsWith("image/")
                ? FileImage
                : FileText;

              const displayName = b.externe_referenz ?? b.datei_name ?? "Beleg";

              return (
                <div
                  key={b.id}
                  className="flex items-center justify-between gap-3 py-2 border-b border-soft-line2 last:border-0"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <BelegIcon className="h-4 w-4 text-soft-ink4 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-soft-ink truncate">
                        {displayName}
                      </p>
                      <p className="text-xs text-soft-ink4">
                        {new Date(b.created_at).toLocaleDateString("de-DE")}
                        {" · "}
                        Aufbewahrung bis{" "}
                        {retentionDate.toLocaleDateString("de-DE")}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {retentionBadge && (
                      <Badge variant={retentionBadge.variant}>
                        {retentionBadge.label}
                      </Badge>
                    )}
                    <button
                      onClick={() =>
                        setDeletingBeleg({ id: b.id, name: displayName })
                      }
                      className="text-xs text-soft-crit hover:text-soft-crit transition-colors"
                    >
                      Löschen
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Confirm Dialog für Beleg-Löschung */}
      <ConfirmDialog
        open={deletingBeleg !== null}
        title="Beleg löschen"
        description={`Soll der Beleg „${deletingBeleg?.name}" wirklich als gelöscht markiert werden? Die Datei wird nicht physisch entfernt.`}
        confirmLabel="Löschen"
        variant="danger"
        loading={deleteBelegLoading}
        onConfirm={() => {
          if (deletingBeleg) {
            void handleDeleteBeleg(deletingBeleg.id);
          }
        }}
        onCancel={() => setDeletingBeleg(null)}
      />

      {/* Confirm Dialog für Löschung */}
      <ConfirmDialog
        open={deletingAlloc !== null}
        title="Förderzuordnung entfernen"
        description={`Soll die Zuordnung zur Massnahme „${deletingAlloc?.measureName}" wirklich entfernt werden?`}
        confirmLabel="Entfernen"
        variant="danger"
        loading={deleteLoading}
        onConfirm={() => {
          if (deletingAlloc) {
            handleDeleteAllocation(deletingAlloc.splitId);
          }
        }}
        onCancel={() => setDeletingAlloc(null)}
      />
    </PageShell>
  );
}
