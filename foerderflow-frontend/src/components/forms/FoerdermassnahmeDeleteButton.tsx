"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useToast } from "@/components/ui/ToastProvider";

type Props = {
  massnahmeId: string;
  massnahmeName: string;
};

export function FoerdermassnahmeDeleteButton({ massnahmeId, massnahmeName }: Props) {
  const router = useRouter();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [blocker, setBlocker] = useState<string | null>(null);

  const handleDelete = async () => {
    setLoading(true);
    setBlocker(null);
    try {
      const res = await fetch(`/api/protected/foerdermassnahmen/${massnahmeId}?hard=true`, {
        method: "DELETE",
      });
      const json = (await res.json()) as { message?: string; error?: string };

      if (res.status === 409) {
        setBlocker(json.error ?? "Löschen nicht möglich.");
        setOpen(false);
        return;
      }

      if (!res.ok) {
        toast.error(json.error ?? "Fehler beim Löschen.");
        setOpen(false);
        return;
      }

      toast.success(json.message ?? "Fördermassnahme gelöscht.");
      setOpen(false);
      router.refresh();
    } catch {
      toast.error("Netzwerkfehler beim Löschen.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {blocker && <p className="text-xs text-soft-crit mt-1">{blocker}</p>}
      <button
        type="button"
        aria-label={`Fördermassnahme „${massnahmeName}" löschen`}
        title="Fördermassnahme löschen"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setBlocker(null);
          setOpen(true);
        }}
        className="p-1.5 rounded-soft-xs hover:bg-soft-critSoft text-soft-ink3 hover:text-soft-crit transition-colors focus:outline-none focus:ring-2 focus:ring-soft-crit"
      >
        <Trash2 className="h-4 w-4" aria-hidden="true" />
      </button>

      <ConfirmDialog
        open={open}
        title="Fördermassnahme löschen"
        description={`„${massnahmeName}" wird vollständig und unwiderruflich gelöscht — inklusive aller Regeln, Kostenstellen-Zuordnungen und Budget-Positionen. Förderzuordnungen und Mittelabrufe müssen vorher entfernt werden.`}
        confirmLabel={loading ? "Wird gelöscht…" : "Ja, endgültig löschen"}
        variant="danger"
        onConfirm={handleDelete}
        onCancel={() => setOpen(false)}
      />
    </>
  );
}
