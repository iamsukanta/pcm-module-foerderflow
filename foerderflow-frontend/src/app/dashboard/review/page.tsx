"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import Link from "next/link";
import { formatEur } from "@/lib/utils";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CheckCircle, Check, Pencil, AlertTriangle } from "lucide-react";
import { PageShell } from "@/components/ui/PageShell";
import { useToast } from "@/components/ui/ToastProvider";

type TransactionForReview = {
  id: string;
  datum: string;
  betrag: string;
  auftraggeber: string | null;
  verwendungszweck: string | null;
  kostenbereich: { id: string; code: string; bezeichnung: string } | null;
  status: string;
  confidence: string | null;
  rule_applications: {
    confidence: string;
    rule_id: string;
    applied_at: string;
    rule?: { id: string; name: string; confidence: string } | null;
  }[];
  splits?: {
    id: string;
    prozent: string;
    cost_center?: { id: string; name: string } | null;
  }[];
  _count?: { splits: number; belege: number };
};

type PositionWahlItem = {
  allocation_id: string;
  transaction: {
    id: string;
    auftraggeber: string | null;
    datum: string;
    betrag: string;
    kostenbereich: { code: string; bezeichnung: string } | null;
  };
  funding_measure: { id: string; name: string };
  betrag_foerderfahig: string;
  candidates: { id: string; positionscode: string; bezeichnung: string }[];
};

function ReviewInboxInner() {
  const toast = useToast();
  const [transactions, setTransactions] = useState<TransactionForReview[]>([]);
  const [positionItems, setPositionItems] = useState<PositionWahlItem[]>([]);
  const [positionChoices, setPositionChoices] = useState<Record<string, string>>({});
  const [savingPosition, setSavingPosition] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState<Set<string>>(new Set());
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkLoading, setBulkLoading] = useState(false);

  const fetchReview = useCallback(async () => {
    setLoading(true);
    try {
      const [orangeRes, positionRes] = await Promise.all([
        fetch("/api/protected/transaktionen?confidence=ORANGE&limit=100"),
        fetch("/api/protected/allocations/position-wahl-ausstehend"),
      ]);
      const orangeJson = (await orangeRes.json()) as { data: TransactionForReview[] };
      const positionJson = (await positionRes.json()) as { data: PositionWahlItem[] };
      setTransactions(orangeJson.data ?? []);
      setPositionItems(positionJson.data ?? []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchReview();
  }, [fetchReview]);

  async function savePositionChoice(item: PositionWahlItem) {
    const positionId = positionChoices[item.allocation_id];
    if (!positionId) return;
    setSavingPosition((prev) => new Set(prev).add(item.allocation_id));
    try {
      const res = await fetch(`/api/protected/transaktionen/${item.transaction.id}/fund-allocation`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          allocation_id: item.allocation_id,
          finanzplan_position_id: positionId,
        }),
      });
      const json = (await res.json()) as { error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Speichern fehlgeschlagen.");
        return;
      }
      toast.success("Position gespeichert.");
      setPositionItems((prev) => prev.filter((p) => p.allocation_id !== item.allocation_id));
    } catch {
      toast.error("Netzwerkfehler.");
    } finally {
      setSavingPosition((prev) => {
        const next = new Set(prev);
        next.delete(item.allocation_id);
        return next;
      });
    }
  }

  async function confirmTransaction(id: string) {
    setConfirming((prev) => new Set(prev).add(id));
    try {
      const res = await fetch(`/api/protected/transaktionen/${id}/confirm`, {
        method: "PATCH",
      });
      if (res.ok) {
        setTransactions((prev) => prev.filter((t) => t.id !== id));
        setSelectedIds((prev) => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
      }
    } finally {
      setConfirming((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }

  async function confirmSelected() {
    if (selectedIds.size === 0) return;
    setBulkLoading(true);
    try {
      const res = await fetch("/api/protected/transaktionen/batch-confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transaction_ids: [...selectedIds] }),
      });
      const json = (await res.json()) as {
        data?: { confirmed: number; skipped: { id: string; reason: string }[] };
        message?: string;
        error?: string;
      };
      if (!res.ok) {
        toast.error(json.error ?? "Fehler beim Bestätigen.");
        return;
      }
      const confirmedCount = json.data?.confirmed ?? 0;
      const skippedCount = json.data?.skipped?.length ?? 0;
      if (confirmedCount > 0) toast.success(`${confirmedCount} Transaktion(en) bestätigt.`);
      if (skippedCount > 0) toast.error(`${skippedCount} übersprungen.`);
      setSelectedIds(new Set());
      void fetchReview();
    } catch {
      toast.error("Netzwerkfehler.");
    } finally {
      setBulkLoading(false);
    }
  }

  const allSelected = transactions.length > 0 && selectedIds.size === transactions.length;
  const toggleAll = () => {
    setSelectedIds(allSelected ? new Set() : new Set(transactions.map((t) => t.id)));
  };

  return (
    <PageShell width="wide">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-soft-ink">Review-Inbox</h1>
          <p className="text-sm text-soft-ink3 mt-1">
            Diese Transaktionen wurden automatisch zugeordnet, aber noch nicht bestätigt.
          </p>
        </div>
        {transactions.length > 0 && (
          <label className="inline-flex items-center gap-2 text-sm text-soft-ink2 select-none cursor-pointer">
            <input
              type="checkbox"
              className="rounded border-soft-line"
              checked={allSelected}
              onChange={toggleAll}
            />
            Alle markieren
          </label>
        )}
      </div>

      {/* Bulk-Action-Bar */}
      {selectedIds.size > 0 && (
        <div className="flex flex-wrap items-center gap-3 rounded-soft-sm bg-soft-accentSoft border border-soft-accent/30 px-4 py-3">
          <span className="text-sm text-soft-accent font-medium">{selectedIds.size} ausgewählt</span>
          <button
            type="button"
            disabled={bulkLoading}
            onClick={() => void confirmSelected()}
            className="rounded-soft-xs bg-soft-ok text-white text-sm px-3 py-1.5 hover:bg-soft-ok/85 disabled:opacity-50 transition-colors inline-flex items-center gap-1.5"
          >
            <Check className="h-4 w-4" />
            {bulkLoading ? "Wird bestätigt…" : "Auswahl bestätigen"}
          </button>
          <button
            type="button"
            onClick={() => setSelectedIds(new Set())}
            className="text-xs text-soft-accent hover:underline ml-auto"
          >
            Auswahl aufheben
          </button>
        </div>
      )}

      {/* Sektion: Position-Wahl ausstehend */}
      {!loading && positionItems.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-soft-crit" />
            <h2 className="text-lg font-semibold text-soft-ink">Position-Wahl ausstehend</h2>
            <Badge variant="warning">{positionItems.length}</Badge>
          </div>
          <p className="text-sm text-soft-ink3">
            Bei diesen Förderzuordnungen kann der Kostenbereich in der Maßnahme auf mehrere
            Bescheid-Positionen wirken. Solange keine Position gewählt ist, wird die Buchung im
            Soll-Ist doppelt gezählt.
          </p>
          {positionItems.map((item) => {
            const datum = new Date(item.transaction.datum);
            const choice = positionChoices[item.allocation_id] ?? "";
            const isSaving = savingPosition.has(item.allocation_id);
            return (
              <div
                key={item.allocation_id}
                className="bg-white rounded-soft-sm border border-soft-crit/30 ring-1 ring-soft-crit/10 p-5 space-y-3"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className="font-semibold text-soft-ink truncate">
                      {item.transaction.auftraggeber ?? (
                        <span className="text-soft-ink4 italic font-normal">Unbekannt</span>
                      )}
                    </p>
                    <p className="text-xs text-soft-ink3 mt-0.5">
                      {datum.toLocaleDateString("de-DE")} · {item.funding_measure.name}
                    </p>
                  </div>
                  <span className="font-mono font-semibold text-sm text-soft-crit whitespace-nowrap">
                    {formatEur(parseFloat(item.transaction.betrag))}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {item.transaction.kostenbereich && (
                    <Badge variant="muted">{item.transaction.kostenbereich.bezeichnung}</Badge>
                  )}
                  <span className="text-xs text-soft-ink3">
                    Förderfähig:{" "}
                    <span className="numeric">{formatEur(parseFloat(item.betrag_foerderfahig))}</span>
                  </span>
                </div>
                <div className="flex flex-wrap gap-2 items-center">
                  <select
                    value={choice}
                    onChange={(e) =>
                      setPositionChoices((prev) => ({
                        ...prev,
                        [item.allocation_id]: e.target.value,
                      }))
                    }
                    className="flex-1 min-w-0 rounded-soft-xs border border-soft-line px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                  >
                    <option value="">— Bescheid-Position wählen —</option>
                    {item.candidates.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.positionscode} — {c.bezeichnung}
                      </option>
                    ))}
                  </select>
                  <Button
                    variant="primary"
                    size="sm"
                    type="button"
                    disabled={!choice || isSaving}
                    loading={isSaving}
                    onClick={() => void savePositionChoice(item)}
                  >
                    Speichern
                  </Button>
                  <Link
                    href={`/dashboard/transaktionen/${item.transaction.id}`}
                    className="text-xs text-soft-accent hover:underline"
                  >
                    Details
                  </Link>
                </div>
              </div>
            );
          })}
        </section>
      )}

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-28 bg-soft-surfaceAlt rounded-soft-sm animate-pulse" />
          ))}
        </div>
      ) : transactions.length === 0 && positionItems.length === 0 ? (
        <div className="rounded-soft-sm bg-soft-okSoft border border-soft-ok/30 px-6 py-10 text-center">
          <p className="text-soft-ok font-medium text-lg flex items-center justify-center gap-2">
            <CheckCircle className="h-5 w-5 text-soft-ok" />
            Alles erledigt! Keine offenen Transaktionen.
          </p>
        </div>
      ) : transactions.length === 0 ? null : (
        <div className="space-y-3">
          {transactions.map((t) => {
            const betrag = parseFloat(t.betrag);
            const isAusgabe = betrag < 0;
            const datum = new Date(t.datum);
            const lastApp = t.rule_applications?.[0];
            const ruleName = lastApp?.rule?.name ?? null;
            const isSelected = selectedIds.has(t.id);

            return (
              <div
                key={t.id}
                className={`bg-white rounded-soft-sm border p-5 space-y-3 transition-colors ${
                  isSelected ? "border-soft-accent ring-1 ring-soft-accent/30" : "border-soft-line"
                }`}
              >
                {/* Zeile 1: Checkbox + Auftraggeber + Datum */}
                <div className="flex items-start justify-between gap-4">
                  <label className="flex items-start gap-3 cursor-pointer flex-1 min-w-0">
                    <input
                      type="checkbox"
                      className="rounded border-soft-line mt-1"
                      checked={isSelected}
                      onChange={(e) => {
                        setSelectedIds((prev) => {
                          const next = new Set(prev);
                          if (e.target.checked) next.add(t.id);
                          else next.delete(t.id);
                          return next;
                        });
                      }}
                    />
                    <p className="font-semibold text-soft-ink truncate">
                      {t.auftraggeber ?? (
                        <span className="text-soft-ink4 italic font-normal">Unbekannt</span>
                      )}
                    </p>
                  </label>
                  <span className="text-xs text-soft-ink4 whitespace-nowrap">
                    {datum.toLocaleDateString("de-DE")}
                  </span>
                </div>

                {/* Zeile 2: Betrag + Badges */}
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`font-mono font-semibold text-sm ${
                      isAusgabe ? "text-soft-crit" : "text-soft-ok"
                    }`}
                  >
                    {formatEur(betrag)}
                  </span>
                  {t.kostenbereich && <Badge variant="muted">{t.kostenbereich.bezeichnung}</Badge>}
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-soft-warnSoft text-soft-warn text-xs font-medium px-2.5 py-0.5">
                    <span className="inline-block h-2 w-2 rounded-full bg-soft-warn" />
                    Erste Zuordnung
                  </span>
                  {ruleName && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-soft-surfaceAlt text-soft-ink2 text-xs px-2.5 py-0.5">
                      Regel: {ruleName}
                    </span>
                  )}
                </div>

                {/* Zeile 3: Verwendungszweck */}
                {t.verwendungszweck && (
                  <p className="text-xs text-soft-ink3 line-clamp-1">{t.verwendungszweck}</p>
                )}

                {/* Buttons */}
                <div className="flex gap-2 pt-1">
                  <button
                    type="button"
                    disabled={confirming.has(t.id)}
                    onClick={() => void confirmTransaction(t.id)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-soft-xs bg-soft-ok text-white text-sm font-medium hover:bg-soft-ok/85 disabled:opacity-50 transition-colors"
                  >
                    {confirming.has(t.id) ? (
                      "Wird gespeichert…"
                    ) : (
                      <>
                        <Check className="h-4 w-4" /> Bestätigen
                      </>
                    )}
                  </button>
                  <Link
                    href={`/dashboard/transaktionen/${t.id}`}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-soft-xs bg-soft-surfaceAlt text-soft-ink2 text-sm font-medium hover:bg-soft-line transition-colors"
                  >
                    <Pencil className="h-4 w-4" /> Bearbeiten
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </PageShell>
  );
}

export default function ReviewPage() {
  return (
    <Suspense
      fallback={
        <PageShell width="wide" className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-28 bg-soft-surfaceAlt rounded-soft-sm animate-pulse" />
          ))}
        </PageShell>
      }
    >
      <ReviewInboxInner />
    </Suspense>
  );
}
