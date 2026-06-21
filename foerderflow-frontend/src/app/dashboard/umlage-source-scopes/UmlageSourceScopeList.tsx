"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { SplitSquareHorizontal } from "lucide-react";
import { EmptyState } from "@/components/ui/EmptyState";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/ToastProvider";

type ScopeRow = {
  id: string;
  name: string;
  beschreibung: string | null;
  cost_centers: Array<{ cost_center_id: string; code: string; name: string; typ: string }>;
  position_count: number;
};

export function UmlageSourceScopeList({ scopes }: { scopes: ScopeRow[] }) {
  const router = useRouter();
  const toast = useToast();
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (scopes.length === 0) {
    return (
      <EmptyState
        icon={SplitSquareHorizontal}
        title="Noch keine Umlage-Pools angelegt"
        description="Lege einen Pool von Quell-Kostenstellen an, um UMLAGE_KOSTENSTELLEN-Pauschalen einzurichten. Typisch: alle Verwaltungs-KSTs (Z-GF, Z-HR, Z-LK, ...) der Org."
        action={{ href: "/dashboard/umlage-source-scopes/new", label: "Neuen Pool anlegen" }}
      />
    );
  }

  async function handleDelete() {
    if (!deleteId) return;
    setBusy(true);
    try {
      const res = await fetch(`/api/protected/umlage-source-scopes/${deleteId}`, {
        method: "DELETE",
      });
      const json = (await res.json()) as { error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Löschen fehlgeschlagen.");
      } else {
        toast.success("Pool wurde gelöscht.");
        router.refresh();
      }
    } catch (e) {
      toast.error(`Netzwerkfehler: ${String(e)}`);
    } finally {
      setBusy(false);
      setDeleteId(null);
    }
  }

  const deleteScope = scopes.find((s) => s.id === deleteId);

  return (
    <>
      <div className="space-y-3">
        {scopes.map((scope) => (
          <div
            key={scope.id}
            className="rounded-soft border border-soft-line bg-white p-5 hover:border-soft-ink4 transition-colors"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 mb-2 flex-wrap">
                  <h3 className="text-base font-semibold text-soft-ink truncate">{scope.name}</h3>
                  <span className="inline-flex items-center rounded-soft-xs bg-soft-line2 px-1.5 py-0.5 text-[11px] text-soft-ink3">
                    {scope.cost_centers.length} Kostenstelle
                    {scope.cost_centers.length !== 1 ? "n" : ""}
                  </span>
                  {scope.position_count > 0 && (
                    <span className="inline-flex items-center rounded-soft-xs bg-soft-accentSoft px-1.5 py-0.5 text-[11px] text-soft-accent">
                      {scope.position_count} Position{scope.position_count !== 1 ? "en" : ""} verlinkt
                    </span>
                  )}
                </div>
                {scope.beschreibung && (
                  <p className="text-sm text-soft-ink3 mb-3 whitespace-pre-line">
                    {scope.beschreibung}
                  </p>
                )}
                <div className="flex flex-wrap gap-1.5">
                  {scope.cost_centers.map((cc) => (
                    <span
                      key={cc.cost_center_id}
                      className="inline-flex items-center rounded-soft-xs border border-soft-line bg-soft-line2/30 px-2 py-0.5 text-xs text-soft-ink2"
                      title={cc.name}
                    >
                      <span className="numeric font-medium">{cc.code}</span>
                      <span className="ml-1 text-soft-ink4">— {cc.name}</span>
                    </span>
                  ))}
                </div>
              </div>
              <div className="flex flex-col gap-2 shrink-0">
                <Link
                  href={`/dashboard/umlage-source-scopes/${scope.id}`}
                  className="inline-flex items-center justify-center rounded-soft-xs border border-soft-line bg-white px-3 py-1.5 text-xs font-medium text-soft-ink2 hover:bg-soft-line2 transition-colors"
                >
                  Bearbeiten
                </Link>
                <Button
                  type="button"
                  variant="danger"
                  className="!py-1.5 !px-3 !text-xs"
                  onClick={() => setDeleteId(scope.id)}
                  disabled={scope.position_count > 0}
                  title={
                    scope.position_count > 0
                      ? "Pool wird noch von Pauschale-Positionen genutzt"
                      : "Pool löschen"
                  }
                >
                  Löschen
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>

      <ConfirmDialog
        open={deleteId !== null}
        title="Umlage-Pool löschen?"
        description={
          deleteScope
            ? `„${deleteScope.name}" wird unwiderruflich gelöscht. Diese Aktion ist nicht rückgängig zu machen.`
            : ""
        }
        confirmLabel={busy ? "Wird gelöscht …" : "Ja, löschen"}
        variant="danger"
        onConfirm={handleDelete}
        onCancel={() => setDeleteId(null)}
      />
    </>
  );
}
