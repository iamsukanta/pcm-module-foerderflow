"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PowerOff } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useToast } from "@/components/ui/ToastProvider";

type KostenstelleDeactivateButtonProps = {
  kstId: string;
  kstName: string;
  kstCode: string;
  activeChildrenCount: number;
};

export function KostenstelleDeactivateButton({
  kstId,
  kstName,
  kstCode,
  activeChildrenCount,
}: KostenstelleDeactivateButtonProps) {
  const router = useRouter();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleConfirm = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/protected/kostenstellen/${kstId}`, {
        method: "DELETE",
      });
      const json = (await res.json()) as {
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
        router.push("/dashboard/kostenstellen");
        router.refresh();
      }
    } catch {
      toast.error("Netzwerkfehler. Bitte versuche es erneut.");
    } finally {
      setLoading(false);
      setOpen(false);
    }
  };

  return (
    <>
      <Button variant="danger" size="sm" onClick={() => setOpen(true)}>
        <PowerOff className="h-4 w-4 mr-1.5" aria-hidden="true" />
        Deaktivieren
      </Button>

      <ConfirmDialog
        open={open}
        variant="danger"
        title="Kostenstelle deaktivieren?"
        description={
          `„${kstName}" (${kstCode}) wird deaktiviert. ` +
          (activeChildrenCount > 0
            ? `Achtung: ${activeChildrenCount} untergeordnete Kostenstelle(n) werden ebenfalls deaktiviert. `
            : "") +
          "Historische Daten bleiben erhalten. Die KST kann nicht reaktiviert werden."
        }
        confirmLabel="Jetzt deaktivieren"
        onConfirm={handleConfirm}
        onCancel={() => setOpen(false)}
        loading={loading}
      />
    </>
  );
}
