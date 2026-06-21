"use client";

import { useState } from "react";
import { useKostenbereiche } from "@/lib/hooks/useKostenbereiche";

type KostenbereichSelectProps = {
  transactionId: string;
  currentKostenbereichId: string | null;
  onSuccess?: () => void;
};

/**
 * Inline-Select für `Transaction.kostenbereich_id`. Lädt Optionen dynamisch aus
 * der systemweiten Kostenbereich-Taxonomie (Server Source of Truth).
 *
 * Optgroup nach Obergruppe. Speichert per PATCH /api/protected/transaktionen/[id].
 */
export function KostenbereichSelect({
  transactionId,
  currentKostenbereichId,
  onSuccess,
}: KostenbereichSelectProps) {
  const [value, setValue] = useState(currentKostenbereichId ?? "");
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<"ok" | "error" | null>(null);
  const { obergruppen, loading: optionsLoading, error } = useKostenbereiche();

  const handleChange = async (newValue: string) => {
    setValue(newValue);
    setLoading(true);
    setFeedback(null);

    try {
      const res = await fetch(`/api/protected/transaktionen/${transactionId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kostenbereich_id: newValue || null }),
      });

      if (res.ok) {
        setFeedback("ok");
        setTimeout(() => setFeedback(null), 2000);
        onSuccess?.();
      } else {
        setFeedback("error");
        setTimeout(() => setFeedback(null), 3000);
        setValue(currentKostenbereichId ?? "");
      }
    } catch {
      setFeedback("error");
      setTimeout(() => setFeedback(null), 3000);
      setValue(currentKostenbereichId ?? "");
    } finally {
      setLoading(false);
    }
  };

  const disabled = loading || optionsLoading;

  return (
    <div className="flex items-center gap-1.5">
      <select
        value={value}
        onChange={(e) => void handleChange(e.target.value)}
        disabled={disabled}
        className={`text-xs rounded-full px-2 py-0.5 border transition-colors focus:outline-none focus:ring-1 focus:ring-soft-accent ${
          disabled
            ? "opacity-50 cursor-not-allowed bg-soft-line2 border-soft-line text-soft-ink3"
            : "bg-soft-line2 border-soft-line text-soft-ink2 hover:bg-soft-line cursor-pointer"
        }`}
        aria-label="Kostenbereich wählen"
      >
        <option value="">— Kostenbereich wählen</option>
        {obergruppen.map((gruppe) => (
          <optgroup key={gruppe.id} label={gruppe.bezeichnung}>
            {gruppe.kinder.map((k) => (
              <option key={k.id} value={k.id}>
                {k.bezeichnung}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
      {feedback === "ok" && (
        <span className="text-xs text-soft-ok font-medium">✓</span>
      )}
      {feedback === "error" && (
        <span className="text-xs text-soft-crit">✗ Fehler</span>
      )}
      {error && (
        <span className="text-xs text-soft-crit" title={error}>⚠ lädt nicht</span>
      )}
    </div>
  );
}
