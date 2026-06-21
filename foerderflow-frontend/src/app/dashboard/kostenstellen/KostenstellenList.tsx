"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Pencil, PowerOff, FolderOpen, LayoutGrid, Building2 } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useToast } from "@/components/ui/ToastProvider";
import { clsx } from "clsx";
import type { KostenstelleWithChildren } from "@/types/kostenstellen";

type CostCenterRow = KostenstelleWithChildren & {
  children?: Array<
    Omit<KostenstelleWithChildren, "children"> & {
      _count?: { funding_measure_cost_centers: number };
    }
  >;
};

type KostenstellenListProps = {
  kostenstellen: CostCenterRow[];
  activeFilter: string;
  orgId: string;
};

function filterKostenstellen(list: CostCenterRow[], filter: string): CostCenterRow[] {
  switch (filter) {
    case "projekte":
      return list.filter((k) => k.typ === "PROJECT" && k.ist_aktiv);
    case "overhead":
      return list.filter((k) => k.typ === "OVERHEAD" && k.ist_aktiv);
    case "inaktiv":
      return list.filter((k) => !k.ist_aktiv);
    default:
      // "alle": zeige nur top-level (kein parent), inaktive auch
      return list.filter((k) => !k.parent_id);
  }
}

function TypBadge({ typ }: { typ: "PROJECT" | "OVERHEAD" }) {
  return (
    <Badge variant={typ === "PROJECT" ? "default" : "warning"}>
      {typ === "PROJECT" ? "Projekt" : "Overhead"}
    </Badge>
  );
}

type KstCardProps = {
  kst: CostCenterRow;
  indented?: boolean;
  onDeactivate: (kst: CostCenterRow) => void;
};

function KstCard({ kst, indented = false, onDeactivate }: KstCardProps) {
  const isInactive = !kst.ist_aktiv;

  return (
    <div
      className={clsx(
        "rounded-soft-sm border bg-soft-surface p-4 transition-colors",
        indented ? "ml-6 border-soft-line" : "border-soft-line",
        isInactive && "opacity-50",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span
              className={clsx(
                "font-semibold text-soft-ink truncate",
                isInactive && "text-soft-ink3",
              )}
            >
              {kst.name}
            </span>
            <Badge variant="muted" className="font-mono text-xs">
              {kst.code}
            </Badge>
            <TypBadge typ={kst.typ} />
            {isInactive && <Badge variant="muted">Inaktiv</Badge>}
          </div>

          <p className="text-xs text-soft-ink3">
            {kst._count?.funding_measure_cost_centers ?? 0} Fördermassnahme
            {(kst._count?.funding_measure_cost_centers ?? 0) !== 1 ? "n" : ""}
          </p>

          {/* Children count hint */}
          {!indented && kst.children && kst.children.length > 0 && (
            <p className="text-xs text-soft-ink4 mt-0.5">
              {kst.children.length} untergeordnete KST
              {kst.children.length !== 1 ? "s" : ""}
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 shrink-0">
          <Link
            href={`/dashboard/kostenstellen/${kst.id}`}
            className="p-2 rounded-soft-xs text-soft-ink3 hover:text-soft-accent hover:bg-soft-accentWash transition-colors
              focus:outline-none focus:ring-2 focus:ring-soft-accent min-h-[44px] min-w-[44px] flex items-center justify-center"
            title={`${kst.name} bearbeiten`}
            aria-label={`${kst.name} bearbeiten`}
          >
            <Pencil className="h-4 w-4" aria-hidden="true" />
          </Link>

          {!isInactive && (
            <button
              onClick={() => onDeactivate(kst)}
              className="p-2 rounded-soft-xs text-soft-ink3 hover:text-soft-crit hover:bg-soft-critSoft transition-colors
                focus:outline-none focus:ring-2 focus:ring-soft-accent min-h-[44px] min-w-[44px] flex items-center justify-center"
              title={`${kst.name} deaktivieren`}
              aria-label={`${kst.name} deaktivieren`}
            >
              <PowerOff className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function KostenstellenList({
  kostenstellen,
  activeFilter,
  orgId: _orgId,
}: KostenstellenListProps) {
  const router = useRouter();
  const toast = useToast();

  const [deactivateTarget, setDeactivateTarget] = useState<CostCenterRow | null>(null);
  const [deactivating, setDeactivating] = useState(false);

  const handleDeactivate = useCallback((kst: CostCenterRow) => {
    setDeactivateTarget(kst);
  }, []);

  const confirmDeactivate = useCallback(async () => {
    if (!deactivateTarget) return;
    setDeactivating(true);

    try {
      const res = await fetch(`/api/protected/kostenstellen/${deactivateTarget.id}`, {
        method: "DELETE",
      });

      const json = (await res.json()) as {
        data?: unknown;
        message?: string;
        warnings?: string[];
        error?: string;
      };

      if (!res.ok) {
        toast.error(json.error ?? "Deaktivierung fehlgeschlagen.");
      } else {
        toast.success(json.message ?? "Kostenstelle deaktiviert.");
        if (json.warnings?.length) {
          json.warnings.forEach((w) => toast.error(`Hinweis: ${w}`));
        }
        router.refresh();
      }
    } catch {
      toast.error("Netzwerkfehler. Bitte versuche es erneut.");
    } finally {
      setDeactivating(false);
      setDeactivateTarget(null);
    }
  }, [deactivateTarget, toast, router]);

  const filtered = filterKostenstellen(kostenstellen, activeFilter);

  // Empty state
  if (filtered.length === 0) {
    const isGlobalEmpty = activeFilter === "alle" && kostenstellen.length === 0;

    if (isGlobalEmpty) {
      return (
        <>
          <EmptyState
            icon={FolderOpen}
            title="Noch keine Kostenstellen"
            description="Kostenstellen sind die Zurechnungseinheiten für Personalkosten und Sachausgaben. Leg jetzt deine erste an."
            action={{
              label: "Erste Kostenstelle anlegen",
              onClick: () => router.push("/dashboard/kostenstellen/new"),
            }}
          />
          <ConfirmDialog
            open={false}
            title=""
            description=""
            confirmLabel=""
            onConfirm={() => {}}
            onCancel={() => {}}
          />
        </>
      );
    }

    return (
      <EmptyState
        icon={activeFilter === "overhead" ? Building2 : LayoutGrid}
        title="Keine Einträge gefunden"
        description={
          activeFilter === "inaktiv"
            ? "Alle Kostenstellen sind aktiv."
            : `Keine ${
                activeFilter === "projekte" ? "Projektkostenstellen" : "Overhead-Kostenstellen"
              } vorhanden.`
        }
      />
    );
  }

  // When filter is not "alle", we show flat list (no hierarchy rendering)
  const showHierarchy = activeFilter === "alle";

  return (
    <>
      <div className="space-y-3">
        {filtered.map((kst) => (
          <div key={kst.id}>
            <KstCard kst={kst} onDeactivate={handleDeactivate} />
            {/* Render children indented, only in "alle" view */}
            {showHierarchy && kst.children && kst.children.length > 0 && (
              <div className="mt-2 space-y-2">
                {kst.children.map((child) => (
                  <KstCard
                    key={child.id}
                    kst={child as CostCenterRow}
                    indented
                    onDeactivate={handleDeactivate}
                  />
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Confirm Deactivate Dialog */}
      <ConfirmDialog
        open={deactivateTarget !== null}
        variant="danger"
        title="Kostenstelle deaktivieren?"
        description={
          deactivateTarget
            ? `„${deactivateTarget.name}" (${deactivateTarget.code}) wird deaktiviert. ` +
              (deactivateTarget.children && deactivateTarget.children.length > 0
                ? `Achtung: ${deactivateTarget.children.length} untergeordnete Kostenstelle(n) werden ebenfalls deaktiviert. `
                : "") +
              "Historische Daten bleiben erhalten. Die KST kann nicht reaktiviert werden."
            : ""
        }
        confirmLabel="Jetzt deaktivieren"
        onConfirm={confirmDeactivate}
        onCancel={() => setDeactivateTarget(null)}
        loading={deactivating}
      />
    </>
  );
}
