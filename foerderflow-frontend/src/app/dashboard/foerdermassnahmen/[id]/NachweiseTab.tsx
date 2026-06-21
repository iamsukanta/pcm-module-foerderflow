"use client";

import { useMemo, useState, useTransition, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FileText, AlertTriangle, Plus, Trash2, CheckCircle } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { useToast } from "@/components/ui/ToastProvider";

type Preflight = {
  total_tx: number;
  tx_zugeordnet: number;
  tx_unzugeordnet: number;
  tx_orange: number;
  positions_total: number;
  positions_with_ist: number;
  positions_ohne_ist: number;
  ready: boolean;
  drilldowns: { zugeordnet: string; unzugeordnet: string; orange: string };
};

type VerwendungsnachweisTyp =
  | "ZWISCHENNACHWEIS"
  | "VERWENDUNGSNACHWEIS"
  | "SACHBERICHT_ONLY";

type VerwendungsnachweisStatus =
  | "OFFEN"
  | "IN_BEARBEITUNG"
  | "EINGEREICHT"
  | "ANERKANNT"
  | "ABGELEHNT";

export type NachweisRow = {
  id: string;
  typ: VerwendungsnachweisTyp;
  status: VerwendungsnachweisStatus;
  zeitraum_von: string;
  zeitraum_bis: string;
  frist: string;
  fiscal_year_jahr: number;
  notiz: string | null;
};

type FiscalYearOption = {
  id: string;
  jahr: number;
  status: "OFFEN" | "GESCHLOSSEN";
};

type Props = {
  measureId: string;
  canEdit: boolean;
  hasZwischennachweisPflicht: boolean;
  fiscalYears: FiscalYearOption[];
  initialNachweise: NachweisRow[];
};

const TYP_LABEL: Record<VerwendungsnachweisTyp, string> = {
  ZWISCHENNACHWEIS: "Zwischennachweis",
  VERWENDUNGSNACHWEIS: "Verwendungsnachweis",
  SACHBERICHT_ONLY: "Sachbericht",
};

const STATUS_LABEL: Record<VerwendungsnachweisStatus, string> = {
  OFFEN: "Offen",
  IN_BEARBEITUNG: "In Bearbeitung",
  EINGEREICHT: "Eingereicht",
  ANERKANNT: "Anerkannt",
  ABGELEHNT: "Abgelehnt",
};

const STATUS_VARIANT: Record<
  VerwendungsnachweisStatus,
  "default" | "muted" | "warning" | "success" | "danger"
> = {
  OFFEN: "muted",
  IN_BEARBEITUNG: "default",
  EINGEREICHT: "warning",
  ANERKANNT: "success",
  ABGELEHNT: "danger",
};

function formatDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  return new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "UTC",
  }).format(d);
}

function tageVerbleibend(fristIso: string): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const frist = new Date(`${fristIso}T00:00:00Z`);
  frist.setHours(0, 0, 0, 0);
  return Math.ceil((frist.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
}

export function NachweiseTab({
  measureId,
  canEdit,
  hasZwischennachweisPflicht,
  fiscalYears,
  initialNachweise,
}: Props) {
  const router = useRouter();
  const toast = useToast();
  const [pending, startTransition] = useTransition();

  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const offeneFiscalYears = useMemo(
    () => fiscalYears.filter((fy) => fy.status === "OFFEN"),
    [fiscalYears]
  );

  // Form-State
  const [formTyp, setFormTyp] = useState<VerwendungsnachweisTyp>("VERWENDUNGSNACHWEIS");
  const [formZeitraumVon, setFormZeitraumVon] = useState("");
  const [formZeitraumBis, setFormZeitraumBis] = useState("");
  const [formFrist, setFormFrist] = useState("");
  const [formFiscalYearId, setFormFiscalYearId] = useState(
    offeneFiscalYears[0]?.id ?? ""
  );
  const [formNotiz, setFormNotiz] = useState("");

  // Pre-Flight: nachladen sobald Zeitraum komplett ist
  const [preflight, setPreflight] = useState<Preflight | null>(null);
  const [preflightLoading, setPreflightLoading] = useState(false);

  useEffect(() => {
    if (!showCreate || !formZeitraumVon || !formZeitraumBis) {
      setPreflight(null);
      return;
    }
    let cancelled = false;
    setPreflightLoading(true);
    fetch(
      `/api/protected/foerdermassnahmen/${measureId}/preflight?zeitraum_von=${formZeitraumVon}&zeitraum_bis=${formZeitraumBis}`
    )
      .then((r) => r.json())
      .then((json: { data?: Preflight }) => {
        if (!cancelled) setPreflight(json.data ?? null);
      })
      .catch(() => {
        if (!cancelled) setPreflight(null);
      })
      .finally(() => {
        if (!cancelled) setPreflightLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [showCreate, formZeitraumVon, formZeitraumBis, measureId]);

  const hasZwischennachweis = initialNachweise.some(
    (n) => n.typ === "ZWISCHENNACHWEIS"
  );
  const showZwischennachweisHinweis =
    hasZwischennachweisPflicht && !hasZwischennachweis;

  function resetForm() {
    setFormTyp("VERWENDUNGSNACHWEIS");
    setFormZeitraumVon("");
    setFormZeitraumBis("");
    setFormFrist("");
    setFormFiscalYearId(offeneFiscalYears[0]?.id ?? "");
    setFormNotiz("");
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!formFiscalYearId) {
      toast.error("Bitte ein offenes Haushaltsjahr wählen.");
      return;
    }
    if (!formZeitraumVon || !formZeitraumBis || !formFrist) {
      toast.error("Bitte Zeitraum und Frist ausfüllen.");
      return;
    }
    if (formZeitraumVon >= formZeitraumBis) {
      toast.error("Zeitraum-Beginn muss vor dem Ende liegen.");
      return;
    }
    if (formFrist < formZeitraumBis) {
      toast.error("Die Frist darf nicht vor dem Zeitraum-Ende liegen.");
      return;
    }

    setCreating(true);
    try {
      const res = await fetch("/api/protected/verwendungsnachweise", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          funding_measure_id: measureId,
          fiscal_year_id: formFiscalYearId,
          zeitraum_von: formZeitraumVon,
          zeitraum_bis: formZeitraumBis,
          frist: formFrist,
          typ: formTyp,
          notiz: formNotiz.trim() || undefined,
        }),
      });
      const json = (await res.json()) as { error?: string; data?: { id: string } };
      if (!res.ok) {
        toast.error(json.error ?? "Anlegen fehlgeschlagen.");
        return;
      }
      toast.success("Verwendungsnachweis wurde angelegt.");
      setShowCreate(false);
      resetForm();
      startTransition(() => router.refresh());
    } catch {
      toast.error("Netzwerkfehler. Bitte erneut versuchen.");
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete() {
    if (!deleteId) return;
    setDeleting(true);
    try {
      const res = await fetch(`/api/protected/verwendungsnachweise/${deleteId}`, {
        method: "DELETE",
      });
      const json = (await res.json()) as { error?: string; message?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Löschen fehlgeschlagen.");
        return;
      }
      toast.success(json.message ?? "Nachweis gelöscht.");
      setDeleteId(null);
      startTransition(() => router.refresh());
    } catch {
      toast.error("Netzwerkfehler.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="space-y-4">
      {showZwischennachweisHinweis && (
        <div className="flex items-start gap-3 rounded-soft-sm bg-soft-warnSoft border border-soft-warn/30 px-4 py-3 text-sm text-soft-warn">
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" aria-hidden="true" />
          <div>
            <strong>Zwischennachweis erforderlich</strong> — diese Massnahme hat eine
            ZWISCHENNACHWEIS_PFLICHT-Regel, aber es wurde noch kein Zwischennachweis
            angelegt.
          </div>
        </div>
      )}

      <div className="flex items-center justify-between">
        <p className="text-sm text-soft-ink3">
          Formelle Nachweise (Zwischen- / Verwendungsnachweis / Sachbericht) für
          diese Massnahme.
        </p>
        {canEdit && (
          <Button
            variant="primary"
            size="sm"
            onClick={() => {
              resetForm();
              setShowCreate(true);
            }}
          >
            <Plus className="h-4 w-4 mr-1.5" aria-hidden="true" />
            Neuen Nachweis erstellen
          </Button>
        )}
      </div>

      {initialNachweise.length === 0 ? (
        <div className="rounded-soft border border-soft-line bg-white">
          <EmptyState
            icon={FileText}
            title="Noch keine Nachweise"
            description="Lege einen Zwischen- oder Verwendungsnachweis an, um Belege, Soll/Ist und Sachbericht für eine Förderperiode zu bündeln."
            action={
              canEdit
                ? {
                    label: "Nachweis erstellen",
                    onClick: () => {
                      resetForm();
                      setShowCreate(true);
                    },
                  }
                : undefined
            }
          />
        </div>
      ) : (
        <div className="rounded-soft border border-soft-line bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-soft-surfaceAlt text-soft-ink3 text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-4 py-2.5 font-medium">Typ</th>
                <th className="text-left px-4 py-2.5 font-medium">Zeitraum</th>
                <th className="text-left px-4 py-2.5 font-medium">Frist</th>
                <th className="text-left px-4 py-2.5 font-medium">Status</th>
                <th className="text-right px-4 py-2.5 font-medium">Aktionen</th>
              </tr>
            </thead>
            <tbody>
              {initialNachweise.map((n) => {
                const tage = tageVerbleibend(n.frist);
                const isOffen = n.status === "OFFEN";
                const fristKritisch =
                  ["OFFEN", "IN_BEARBEITUNG"].includes(n.status) && tage <= 14;
                return (
                  <tr
                    key={n.id}
                    className="border-t border-soft-line2 hover:bg-soft-surfaceAlt/40 transition-colors"
                  >
                    <td className="px-4 py-3 text-soft-ink">
                      {TYP_LABEL[n.typ]}
                      <span className="text-xs text-soft-ink4 ml-2">
                        HHJ {n.fiscal_year_jahr}
                      </span>
                    </td>
                    <td className="px-4 py-3 numeric text-soft-ink2">
                      {formatDate(n.zeitraum_von)} – {formatDate(n.zeitraum_bis)}
                    </td>
                    <td className="px-4 py-3 text-soft-ink2">
                      <span className="numeric">{formatDate(n.frist)}</span>
                      {["OFFEN", "IN_BEARBEITUNG"].includes(n.status) && (
                        <span
                          className={`block text-xs ${
                            fristKritisch ? "text-soft-warn" : "text-soft-ink4"
                          }`}
                        >
                          {tage < 0
                            ? `${Math.abs(tage)} Tage überfällig`
                            : tage === 0
                            ? "heute fällig"
                            : `noch ${tage} Tage`}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={STATUS_VARIANT[n.status]}>
                        {STATUS_LABEL[n.status]}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <Link href={`/dashboard/verwendungsnachweise/${n.id}`}>
                          <Button variant="ghost" size="sm">
                            Öffnen
                          </Button>
                        </Link>
                        {canEdit && isOffen && (
                          <button
                            type="button"
                            aria-label="Verwendungsnachweis löschen"
                            title="Löschen"
                            onClick={() => setDeleteId(n.id)}
                            className="p-1.5 rounded-soft-xs hover:bg-soft-surfaceAlt text-soft-ink4 hover:text-soft-crit transition-colors focus:outline-none focus:ring-2 focus:ring-soft-crit"
                          >
                            <Trash2 className="h-4 w-4" aria-hidden="true" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Erstellen-Modal */}
      {showCreate && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="nachweis-create-title"
        >
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => !creating && setShowCreate(false)}
            aria-hidden="true"
          />
          <form
            onSubmit={handleCreate}
            className="relative z-10 w-full max-w-lg rounded-soft bg-soft-surface shadow-soft-lg p-6 space-y-4"
          >
            <h2
              id="nachweis-create-title"
              className="text-lg font-semibold text-soft-ink"
            >
              Neuen Nachweis erstellen
            </h2>

            <div>
              <label className="block text-xs font-medium text-soft-ink3 uppercase tracking-wide mb-1">
                Typ
              </label>
              <select
                value={formTyp}
                onChange={(e) => setFormTyp(e.target.value as VerwendungsnachweisTyp)}
                required
                className="w-full px-3 py-2 text-sm rounded-soft-sm border border-soft-line bg-white text-soft-ink focus:outline-none focus:ring-2 focus:ring-soft-accent"
              >
                <option value="ZWISCHENNACHWEIS">Zwischennachweis</option>
                <option value="VERWENDUNGSNACHWEIS">Verwendungsnachweis</option>
                <option value="SACHBERICHT_ONLY">Sachbericht</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-soft-ink3 uppercase tracking-wide mb-1">
                Haushaltsjahr
              </label>
              <select
                value={formFiscalYearId}
                onChange={(e) => setFormFiscalYearId(e.target.value)}
                required
                className="w-full px-3 py-2 text-sm rounded-soft-sm border border-soft-line bg-white text-soft-ink focus:outline-none focus:ring-2 focus:ring-soft-accent"
              >
                {offeneFiscalYears.length === 0 && (
                  <option value="">Kein offenes Haushaltsjahr verfügbar</option>
                )}
                {offeneFiscalYears.map((fy) => (
                  <option key={fy.id} value={fy.id}>
                    {fy.jahr}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-soft-ink3 uppercase tracking-wide mb-1">
                  Zeitraum von
                </label>
                <input
                  type="date"
                  required
                  value={formZeitraumVon}
                  onChange={(e) => setFormZeitraumVon(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-soft-sm border border-soft-line bg-white text-soft-ink numeric focus:outline-none focus:ring-2 focus:ring-soft-accent"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-soft-ink3 uppercase tracking-wide mb-1">
                  Zeitraum bis
                </label>
                <input
                  type="date"
                  required
                  value={formZeitraumBis}
                  onChange={(e) => setFormZeitraumBis(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-soft-sm border border-soft-line bg-white text-soft-ink numeric focus:outline-none focus:ring-2 focus:ring-soft-accent"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-soft-ink3 uppercase tracking-wide mb-1">
                Einreichfrist
              </label>
              <input
                type="date"
                required
                value={formFrist}
                onChange={(e) => setFormFrist(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-soft-sm border border-soft-line bg-white text-soft-ink numeric focus:outline-none focus:ring-2 focus:ring-soft-accent"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-soft-ink3 uppercase tracking-wide mb-1">
                Notiz (optional)
              </label>
              <textarea
                rows={3}
                value={formNotiz}
                onChange={(e) => setFormNotiz(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-soft-sm border border-soft-line bg-white text-soft-ink focus:outline-none focus:ring-2 focus:ring-soft-accent"
              />
            </div>

            {/* Pre-Flight-Check */}
            {preflightLoading && (
              <div className="text-xs text-soft-ink3">Pre-Flight wird geprüft…</div>
            )}
            {preflight && !preflightLoading && (
              <div
                className={`rounded-soft-sm border p-3 text-xs space-y-2 ${
                  preflight.ready
                    ? "border-soft-ok/30 bg-soft-okSoft"
                    : "border-soft-warn/40 bg-soft-warnSoft"
                }`}
              >
                <div className="flex items-center gap-2 font-medium">
                  {preflight.ready ? (
                    <>
                      <CheckCircle className="h-4 w-4 text-soft-ok" />
                      <span className="text-soft-ok">Bereit zur Generierung</span>
                    </>
                  ) : (
                    <>
                      <AlertTriangle className="h-4 w-4 text-soft-warn" />
                      <span className="text-soft-warn">Vor der Generierung prüfen</span>
                    </>
                  )}
                </div>
                <ul className="space-y-0.5 text-soft-ink2">
                  <li>
                    {preflight.tx_zugeordnet}/{preflight.total_tx} Transaktionen auf
                    Maßnahmen-KSTs zugeordnet
                  </li>
                  {preflight.tx_unzugeordnet > 0 && (
                    <li>
                      <Link
                        href={preflight.drilldowns.unzugeordnet}
                        className="text-soft-warn hover:underline"
                        target="_blank"
                      >
                        ⚠ {preflight.tx_unzugeordnet} unzugeordnet →
                      </Link>
                    </li>
                  )}
                  {preflight.tx_orange > 0 && (
                    <li>
                      <Link
                        href={preflight.drilldowns.orange}
                        className="text-soft-warn hover:underline"
                        target="_blank"
                      >
                        ⚠ {preflight.tx_orange} mit Konfidenz ORANGE (Review) →
                      </Link>
                    </li>
                  )}
                  <li>
                    {preflight.positions_with_ist}/{preflight.positions_total}{" "}
                    Finanzplan-Positionen mit Ist-Betrag
                    {preflight.positions_ohne_ist > 0 && (
                      <span className="text-soft-warn">
                        {" "}— {preflight.positions_ohne_ist} ohne Ist
                      </span>
                    )}
                  </li>
                </ul>
              </div>
            )}

            <div className="flex justify-end gap-3 pt-2">
              <Button
                type="button"
                variant="secondary"
                onClick={() => setShowCreate(false)}
                disabled={creating}
              >
                Abbrechen
              </Button>
              <Button type="submit" variant="primary" loading={creating || pending}>
                Erstellen
              </Button>
            </div>
          </form>
        </div>
      )}

      <ConfirmDialog
        open={deleteId !== null}
        title="Nachweis löschen?"
        description="Der Nachweis wird unwiderruflich gelöscht. Eingereichte Nachweise lassen sich nicht löschen."
        confirmLabel="Löschen"
        variant="danger"
        loading={deleting}
        onConfirm={handleDelete}
        onCancel={() => !deleting && setDeleteId(null)}
      />
    </div>
  );
}
