"use client";

import { useState, type ChangeEvent, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/ToastProvider";
import type { FiscalYearWithMeta } from "@/types/haushaltsjahre";

const CONFIRMATION_WORD = "SCHLIESSEN";

type FiscalYearCloseFormProps = {
  fiscalYear: FiscalYearWithMeta;
};

export function FiscalYearCloseForm({ fiscalYear }: FiscalYearCloseFormProps) {
  const router = useRouter();
  const toast = useToast();

  const [confirmText, setConfirmText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isConfirmed = confirmText === CONFIRMATION_WORD;

  const handleConfirmChange = (e: ChangeEvent<HTMLInputElement>) => {
    setConfirmText(e.target.value);
    if (error) setError(null);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    if (!isConfirmed) {
      setError(`Bitte gib "${CONFIRMATION_WORD}" zur Bestätigung ein.`);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`/api/protected/haushaltsjahre/${fiscalYear.id}/close`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmation: CONFIRMATION_WORD }),
      });

      const json = (await res.json()) as {
        data?: FiscalYearWithMeta;
        message?: string;
        error?: string;
        code?: string;
      };

      if (!res.ok) {
        setError(json.error ?? "Ein Fehler ist aufgetreten. Bitte versuche es erneut.");
        return;
      }

      toast.success(json.message ?? `Haushaltsjahr ${fiscalYear.jahr} wurde geschlossen.`);
      router.push("/dashboard/haushaltsjahre");
      router.refresh();
    } catch {
      setError("Netzwerkfehler. Bitte überprüfe deine Verbindung und versuche es erneut.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section
      id="schliessen"
      aria-labelledby="close-section-heading"
      className="mt-10 rounded-soft border-2 border-soft-crit/30 bg-soft-critSoft p-6"
    >
      {/* Section Header */}
      <div className="flex items-start gap-3 mb-5">
        <div className="flex-shrink-0 rounded-full bg-soft-critSoft p-2">
          <span className="text-xl" aria-hidden="true">
            🔒
          </span>
        </div>
        <div>
          <h2 id="close-section-heading" className="text-lg font-semibold text-soft-crit">
            Haushaltsjahr schließen
          </h2>
          <p className="text-sm text-soft-crit mt-0.5">Diese Aktion ist unwiderruflich.</p>
        </div>
      </div>

      {/* Warning Banner */}
      <div role="alert" className="mb-5 rounded-soft-sm border border-soft-crit/40 bg-white p-4">
        <p className="text-sm font-semibold text-soft-crit mb-2">
          ⚠️ Achtung: Diese Aktion kann nicht rückgängig gemacht werden.
        </p>
        <p className="text-sm text-soft-crit">
          Das Haushaltsjahr <strong>{fiscalYear.jahr}</strong> wird geschlossen. Nach dem Schließen
          sind keine weiteren Buchungen mehr möglich. Das Haushaltsjahr kann nicht wieder geöffnet
          werden.
        </p>
      </div>

      {/* What happens list */}
      <ul className="mb-6 space-y-2">
        {[
          "Keine neuen Buchungen können dem Haushaltsjahr zugeordnet werden.",
          "Bestehende Buchungen und Nachweise bleiben unverändert erhalten.",
          "Das Haushaltsjahr wird dauerhaft als geschlossen markiert.",
          "Datum und Nutzer der Schließung werden im Audit-Trail festgehalten.",
        ].map((item) => (
          <li key={item} className="flex items-start gap-2 text-sm text-soft-crit">
            <span className="mt-0.5 shrink-0 text-soft-crit" aria-hidden="true">
              •
            </span>
            {item}
          </li>
        ))}
      </ul>

      {/* Confirmation form */}
      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div>
          <label htmlFor="close-confirm-input" className="block text-sm font-medium text-soft-crit mb-1">
            Zur Bestätigung bitte{" "}
            <code className="rounded bg-soft-critSoft px-1.5 py-0.5 text-soft-crit font-mono text-xs">
              {CONFIRMATION_WORD}
            </code>{" "}
            eingeben:
          </label>
          <input
            id="close-confirm-input"
            type="text"
            value={confirmText}
            onChange={handleConfirmChange}
            placeholder={CONFIRMATION_WORD}
            autoComplete="off"
            spellCheck={false}
            aria-required="true"
            aria-describedby={error ? "close-confirm-error" : "close-confirm-hint"}
            aria-invalid={!!error}
            className={`w-full rounded-soft-xs border px-3 py-2.5 text-sm font-mono outline-none transition-colors
              focus:ring-2 focus:ring-soft-crit focus:border-soft-crit
              ${
                error
                  ? "border-soft-crit bg-soft-critSoft text-soft-crit"
                  : isConfirmed
                    ? "border-soft-ok bg-soft-okSoft text-soft-ok"
                    : "border-soft-crit/40 bg-white text-soft-ink"
              }`}
          />
          {error ? (
            <p id="close-confirm-error" role="alert" className="mt-1 text-xs text-soft-crit">
              {error}
            </p>
          ) : (
            <p id="close-confirm-hint" className="mt-1 text-xs text-soft-crit">
              Gib &ldquo;SCHLIESSEN&rdquo; ein, um die Schließung zu bestätigen.
            </p>
          )}
        </div>

        <div className="flex items-center justify-end gap-3 pt-1">
          <Button
            type="button"
            variant="secondary"
            onClick={() => router.push("/dashboard/haushaltsjahre")}
            disabled={loading}
          >
            Abbrechen
          </Button>
          <Button
            type="submit"
            variant="danger"
            loading={loading}
            disabled={!isConfirmed || loading}
            aria-describedby={!isConfirmed ? "close-confirm-hint" : undefined}
          >
            🔒 Haushaltsjahr {fiscalYear.jahr} schließen
          </Button>
        </div>
      </form>
    </section>
  );
}
