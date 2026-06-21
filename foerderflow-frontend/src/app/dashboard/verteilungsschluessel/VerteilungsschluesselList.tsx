"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { SplitSquareHorizontal } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useToast } from "@/components/ui/ToastProvider";
import {
  ALLOCATION_BASIS_LABELS,
  type AllocationKeyWithPositions,
} from "@/types/verteilungsschluessel";
import { clsx } from "clsx";

type Props = {
  allocationKeys: AllocationKeyWithPositions[];
};

/** Formatiert ein ISO-Datum "YYYY-MM-DD" zu "TT.MM.JJJJ" */
function formatDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}

/** Kurzübersicht der Positionen: "60% SB01 / 30% VW / 10% IT" */
function positionsSummary(positions: AllocationKeyWithPositions["positions"]): string {
  return positions
    .map((p) => {
      const code = p.cost_center?.code ?? p.cost_center_id.slice(0, 6);
      const pct = Number(p.prozent).toFixed(0);
      return `${pct}% ${code}`;
    })
    .join(" / ");
}

export function VerteilungsschluesselList({ allocationKeys }: Props) {
  const router = useRouter();
  const toast = useToast();

  const [deactivateId, setDeactivateId] = useState<string | null>(null);
  const [deactivateName, setDeactivateName] = useState<string>("");
  const [deactivateLoading, setDeactivateLoading] = useState(false);

  const handleDeactivateConfirm = async () => {
    if (!deactivateId) return;
    setDeactivateLoading(true);
    try {
      const res = await fetch(`/api/protected/verteilungsschluessel/${deactivateId}`, {
        method: "DELETE",
      });
      const json = (await res.json()) as { message?: string; error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Fehler beim Deaktivieren.");
      } else {
        toast.success(json.message ?? "Schlüssel deaktiviert.");
        router.refresh();
      }
    } catch {
      toast.error("Netzwerkfehler. Bitte versuche es erneut.");
    } finally {
      setDeactivateLoading(false);
      setDeactivateId(null);
    }
  };

  if (allocationKeys.length === 0) {
    return (
      <EmptyState
        icon={SplitSquareHorizontal}
        title="Noch keine Verteilungsschlüssel"
        description="Ein Verteilungsschlüssel legt fest, wie gemeinsame Kosten auf Ihre Projekte aufgeteilt werden — zum Beispiel Miete, Telefon oder IT. Sie geben an, welcher Anteil (in Prozent) auf welche Kostenstelle entfällt."
        action={{
          label: "Ersten Schlüssel anlegen",
          onClick: () => router.push("/dashboard/verteilungsschluessel/new"),
        }}
      />
    );
  }

  return (
    <>
      <div className="space-y-3">
        {allocationKeys.map((key) => {
          const summary = positionsSummary(key.positions);
          const vonStr = formatDate(key.gueltig_von);
          const bisStr = key.gueltig_bis ? formatDate(key.gueltig_bis) : "unbegrenzt";

          return (
            <div
              key={key.id}
              className={clsx(
                "rounded-soft-sm border bg-soft-surface p-5 transition-shadow hover:shadow-soft",
                key.ist_aktiv ? "border-soft-line" : "border-soft-line2 opacity-70",
              )}
            >
              <div className="flex items-start gap-3 flex-wrap">
                {/* Name + Badges */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <Link
                      href={`/dashboard/verteilungsschluessel/${key.id}`}
                      className="text-base font-semibold text-soft-ink hover:text-soft-accent hover:underline truncate"
                    >
                      {key.name}
                    </Link>
                    {key.ist_aktiv ? (
                      <Badge variant="success">Aktiv</Badge>
                    ) : (
                      <Badge variant="muted">Inaktiv</Badge>
                    )}
                    <Badge variant="default">{ALLOCATION_BASIS_LABELS[key.basis]}</Badge>
                    {key.is_valid === false && <Badge variant="warning">⚠️ Summe ≠ 100%</Badge>}
                  </div>

                  {/* Zeitraum */}
                  <p className="text-xs text-soft-ink3 mb-2">
                    Gültig: {vonStr} – {bisStr}
                  </p>

                  {/* Positions-Summary */}
                  {summary ? (
                    <p className="text-sm text-soft-ink2 font-mono">{summary}</p>
                  ) : (
                    <p className="text-sm text-soft-ink4 italic">Keine Positionen</p>
                  )}
                </div>

                {/* Aktionen */}
                <div className="flex items-center gap-2 shrink-0 flex-wrap">
                  <Link
                    href={`/dashboard/verteilungsschluessel/${key.id}`}
                    className="inline-flex items-center justify-center rounded-soft-xs px-3 py-1.5 text-sm font-medium text-soft-ink2 border border-soft-line hover:bg-soft-line2 transition-colors min-h-[36px]"
                  >
                    Bearbeiten
                  </Link>

                  {key.ist_aktiv && (
                    <Link
                      href={`/dashboard/verteilungsschluessel/${key.id}?action=neue-version`}
                      className="inline-flex items-center justify-center rounded-soft-xs px-3 py-1.5 text-sm font-medium text-soft-accent border border-soft-accent hover:bg-soft-accentWash transition-colors min-h-[36px]"
                    >
                      Neue Version
                    </Link>
                  )}

                  {key.ist_aktiv && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setDeactivateId(key.id);
                        setDeactivateName(key.name);
                      }}
                      className="text-soft-ink3 hover:text-soft-crit"
                    >
                      Deaktivieren
                    </Button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Deactivate Confirm Dialog */}
      <ConfirmDialog
        open={!!deactivateId}
        title="Verteilungsschlüssel deaktivieren"
        description={`Soll „${deactivateName}" wirklich deaktiviert werden? Der Schlüssel bleibt für historische Auswertungen erhalten, kann aber nicht mehr für neue Zuordnungen verwendet werden.`}
        confirmLabel="Deaktivieren"
        onConfirm={handleDeactivateConfirm}
        onCancel={() => setDeactivateId(null)}
        variant="danger"
        loading={deactivateLoading}
      />
    </>
  );
}
