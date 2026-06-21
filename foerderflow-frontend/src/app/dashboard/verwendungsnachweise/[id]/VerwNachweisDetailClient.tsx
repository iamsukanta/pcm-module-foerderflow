"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Check, X, ArrowRight, Undo2, Send } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useToast } from "@/components/ui/ToastProvider";

type Status = "OFFEN" | "IN_BEARBEITUNG" | "EINGEREICHT" | "ANERKANNT" | "ABGELEHNT";

type Props = {
  id: string;
  status: Status;
  measureId: string;
  fiscalYearClosed: boolean;
};

const VALID_TRANSITIONS: Record<Status, Status[]> = {
  OFFEN: ["IN_BEARBEITUNG"],
  IN_BEARBEITUNG: ["OFFEN", "EINGEREICHT"],
  EINGEREICHT: ["ANERKANNT", "ABGELEHNT"],
  ANERKANNT: [],
  ABGELEHNT: ["IN_BEARBEITUNG"],
};

const TRANSITION_LABEL: Record<Status, string> = {
  OFFEN: "Zurück zu Offen",
  IN_BEARBEITUNG: "In Bearbeitung",
  EINGEREICHT: "Einreichen",
  ANERKANNT: "Als anerkannt markieren",
  ABGELEHNT: "Als abgelehnt markieren",
};

function transitionIcon(target: Status) {
  switch (target) {
    case "OFFEN":
      return Undo2;
    case "IN_BEARBEITUNG":
      return ArrowRight;
    case "EINGEREICHT":
      return Send;
    case "ANERKANNT":
      return Check;
    case "ABGELEHNT":
      return X;
  }
}

function transitionVariant(target: Status): "primary" | "secondary" | "danger" {
  if (target === "ANERKANNT") return "primary";
  if (target === "ABGELEHNT") return "danger";
  if (target === "EINGEREICHT") return "primary";
  return "secondary";
}

export function VerwNachweisDetailClient({ id, status, fiscalYearClosed }: Props) {
  const router = useRouter();
  const toast = useToast();
  const [submitting, setSubmitting] = useState(false);
  const [pendingTarget, setPendingTarget] = useState<Status | null>(null);

  const allowed = VALID_TRANSITIONS[status];

  async function applyTransition(target: Status) {
    setSubmitting(true);
    try {
      // Einreichen → eigener Endpoint, der den Snapshot baut
      if (target === "EINGEREICHT") {
        const res = await fetch(`/api/protected/verwendungsnachweise/${id}/einreichen`, {
          method: "POST",
        });
        const json = (await res.json()) as { error?: string; message?: string };
        if (!res.ok) {
          toast.error(json.error ?? "Einreichen fehlgeschlagen.");
          return;
        }
        toast.success(json.message ?? "Verwendungsnachweis eingereicht.");
      } else {
        const res = await fetch(`/api/protected/verwendungsnachweise/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: target }),
        });
        const json = (await res.json()) as { error?: string };
        if (!res.ok) {
          toast.error(json.error ?? "Statuswechsel fehlgeschlagen.");
          return;
        }
        toast.success(`Status auf "${TRANSITION_LABEL[target]}" gesetzt.`);
      }
      setPendingTarget(null);
      router.refresh();
    } catch {
      toast.error("Netzwerkfehler. Bitte erneut versuchen.");
    } finally {
      setSubmitting(false);
    }
  }

  function requestTransition(target: Status) {
    // Einreichen, Anerkennen und Ablehnen brauchen Bestätigung
    if (["EINGEREICHT", "ANERKANNT", "ABGELEHNT"].includes(target)) {
      setPendingTarget(target);
      return;
    }
    void applyTransition(target);
  }

  return (
    <div className="rounded-soft border border-soft-line bg-white p-5 space-y-3">
      <h2 className="text-sm font-semibold text-soft-ink2 uppercase tracking-wide">
        Status-Workflow
      </h2>

      {fiscalYearClosed && (
        <p className="text-xs text-soft-warn bg-soft-warnSoft border border-soft-warn/30 rounded-soft-xs px-2.5 py-1.5">
          Haushaltsjahr ist geschlossen — Statusänderungen sind eingeschränkt.
        </p>
      )}

      {allowed.length === 0 ? (
        <p className="text-sm text-soft-ink4 italic">
          Endstatus erreicht — keine weiteren Übergänge möglich.
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {allowed.map((target) => {
            const Icon = transitionIcon(target);
            return (
              <Button
                key={target}
                variant={transitionVariant(target)}
                size="sm"
                onClick={() => requestTransition(target)}
                disabled={submitting}
                className="w-full justify-start"
              >
                <Icon className="h-4 w-4 mr-1.5" aria-hidden="true" />
                {TRANSITION_LABEL[target]}
              </Button>
            );
          })}
        </div>
      )}

      <ConfirmDialog
        open={pendingTarget !== null}
        title={
          pendingTarget === "EINGEREICHT"
            ? "Verwendungsnachweis einreichen?"
            : pendingTarget === "ANERKANNT"
              ? "Als anerkannt markieren?"
              : "Als abgelehnt markieren?"
        }
        description={
          pendingTarget === "EINGEREICHT"
            ? "Achtung: Nach dem Einreichen kann der Nachweis nicht mehr geändert werden. Die aktuellen Daten werden als Snapshot gesichert."
            : pendingTarget === "ANERKANNT"
              ? "Der Nachweis wird als anerkannt markiert. Dies ist ein Endstatus."
              : "Der Nachweis wird als abgelehnt markiert. Du kannst ihn später wieder in Bearbeitung nehmen."
        }
        confirmLabel={
          pendingTarget === "EINGEREICHT"
            ? "Jetzt einreichen"
            : pendingTarget === "ANERKANNT"
              ? "Anerkennen"
              : "Ablehnen"
        }
        variant={pendingTarget === "ABGELEHNT" ? "danger" : "default"}
        loading={submitting}
        onConfirm={() => pendingTarget && applyTransition(pendingTarget)}
        onCancel={() => !submitting && setPendingTarget(null)}
      />
    </div>
  );
}
