"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/ToastProvider";
import { formatEur } from "@/lib/utils";

type SplitOption = {
  id: string;
  cost_center: { name: string };
  prozent: number;
  betrag_anteil: string;
};

type MeasureOption = {
  id: string;
  name: string;
  foerderquote: string;
  funder: { name: string };
};

type FinanzplanPositionOption = {
  id: string;
  positionscode: string;
  bezeichnung: string;
  betrag_bewilligt: string;
  foerderfahig_anteil: string;
  cap_betrag: string | null;
};

type Props = {
  transactionId: string;
  splits: SplitOption[];
  transactionKostenbereichId: string | null;
  transactionKostenbereichCode: string | null;
  onSuccess?: () => void;
  onCancel?: () => void;
};

export function FundAllocationForm({
  transactionId,
  splits,
  transactionKostenbereichId,
  transactionKostenbereichCode,
  onSuccess,
  onCancel,
}: Props) {
  const toast = useToast();

  const [splitId, setSplitId] = useState<string>(splits[0]?.id ?? "");
  const [measureId, setMeasureId] = useState<string>("");
  const [positionId, setPositionId] = useState<string>("");
  const [notiz, setNotiz] = useState<string>("");
  const [measures, setMeasures] = useState<MeasureOption[]>([]);
  const [positions, setPositions] = useState<FinanzplanPositionOption[] | null>(null);
  const [loadingMeasures, setLoadingMeasures] = useState(true);
  const [loadingPositions, setLoadingPositions] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    setLoadingMeasures(true);
    fetch("/api/protected/foerdermassnahmen?status=AKTIV")
      .then((r) => r.json())
      .then((json: { data?: MeasureOption[] }) => {
        setMeasures(json.data ?? []);
      })
      .catch(() => {
        toast.error("Fördermassnahmen konnten nicht geladen werden.");
      })
      .finally(() => setLoadingMeasures(false));
  }, [toast]);

  // Lädt Bridge-Match-Positionen für die gewählte Maßnahme + KB der Transaktion
  useEffect(() => {
    setPositions(null);
    setPositionId("");
    if (!measureId || !transactionKostenbereichId) return;

    setLoadingPositions(true);
    fetch(
      `/api/protected/foerdermassnahmen/${measureId}/finanzplan-positionen?kostenbereich_id=${transactionKostenbereichId}`
    )
      .then((r) => r.json())
      .then((json: { data?: FinanzplanPositionOption[] }) => {
        setPositions(json.data ?? []);
      })
      .catch(() => {
        toast.error("Bescheid-Positionen konnten nicht geladen werden.");
        setPositions([]);
      })
      .finally(() => setLoadingPositions(false));
  }, [measureId, transactionKostenbereichId, toast]);

  const selectedSplit = splits.find((s) => s.id === splitId);
  const selectedMeasure = measures.find((m) => m.id === measureId);

  let previewFoerderung: number | null = null;
  let previewEigenanteil: number | null = null;
  if (selectedSplit && selectedMeasure) {
    const betragAbs = Math.abs(parseFloat(selectedSplit.betrag_anteil));
    const foerderquote = parseFloat(selectedMeasure.foerderquote);
    previewFoerderung =
      Math.round((betragAbs * foerderquote) / 100 * 100) / 100;
    previewEigenanteil = Math.round((betragAbs - previewFoerderung) * 100) / 100;
  }

  const positionCount = positions?.length ?? 0;
  const requiresPositionPick = positionCount > 1;
  const positionMissing = positionCount === 0 && !!measureId && !!transactionKostenbereichId;
  const submitBlocked =
    !splitId ||
    !measureId ||
    positionMissing ||
    (requiresPositionPick && !positionId);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitBlocked) return;

    setSubmitting(true);
    setApiError(null);

    try {
      const res = await fetch(
        `/api/protected/transaktionen/${transactionId}/fund-allocation`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            transaction_split_id: splitId,
            funding_measure_id: measureId,
            finanzplan_position_id: positionId || undefined,
            notiz: notiz.trim() || undefined,
          }),
        }
      );

      if (!res.ok) {
        const json = (await res.json()) as {
          error?: string;
          code?: string;
        };
        const code = json.code ?? "";
        if (code === "MULTI_POSITION_MAPPING") {
          setApiError(
            json.error ??
              "Mehrere Bescheid-Positionen möglich — bitte wählen."
          );
        } else if (code === "KB_NOT_IN_BESCHEID") {
          setApiError(json.error ?? "Kostenbereich nicht im Bescheid hinterlegt.");
        } else if (code === "POSITION_NOT_IN_BRIDGE") {
          setApiError(
            json.error ??
              "Position ist nicht mit dem Kostenbereich verbunden."
          );
        } else if (code === "DOPPELFINANZIERUNG") {
          setApiError(
            "Doppelfinanzierung: dieser Split ist bereits einer Fördermassnahme zugeordnet."
          );
        } else {
          setApiError(json.error ?? "Unbekannter Fehler.");
        }
        return;
      }

      toast.success("Förderzuordnung erfolgreich angelegt.");
      onSuccess?.();
    } catch {
      setApiError("Netzwerkfehler — bitte erneut versuchen.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Split-Auswahl */}
      <div>
        <label className="block text-sm font-medium text-soft-ink mb-1">
          Kostenstellen-Split
        </label>
        <select
          value={splitId}
          onChange={(e) => setSplitId(e.target.value)}
          className="w-full rounded-soft-xs border border-soft-line px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
          required
        >
          {splits.map((s) => (
            <option key={s.id} value={s.id}>
              {s.cost_center.name} — {s.prozent.toFixed(1)} % —{" "}
              {formatEur(parseFloat(s.betrag_anteil))}
            </option>
          ))}
        </select>
      </div>

      {/* Fördermassnahme-Auswahl */}
      <div>
        <label className="block text-sm font-medium text-soft-ink mb-1">
          Fördermassnahme
        </label>
        {loadingMeasures ? (
          <p className="text-sm text-soft-ink3">Lädt…</p>
        ) : (
          <select
            value={measureId}
            onChange={(e) => setMeasureId(e.target.value)}
            className="w-full rounded-soft-xs border border-soft-line px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
            required
          >
            <option value="">— Bitte auswählen —</option>
            {measures.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name} ({m.funder.name}, {parseFloat(m.foerderquote).toFixed(0)} %)
              </option>
            ))}
          </select>
        )}
        {!loadingMeasures && measures.length === 0 && (
          <p className="text-xs text-soft-ink3 mt-1">
            Keine aktiven Fördermassnahmen vorhanden.
          </p>
        )}
      </div>

      {/* Bescheid-Position: 0/1/N-Logik */}
      {measureId && transactionKostenbereichId && (
        <div>
          <label className="block text-sm font-medium text-soft-ink mb-1">
            Bescheid-Position
          </label>
          {loadingPositions || positions === null ? (
            <p className="text-sm text-soft-ink3">Lädt…</p>
          ) : positionCount === 0 ? (
            <div className="rounded-soft-xs bg-soft-critSoft border border-soft-crit/20 px-3 py-2 text-sm text-soft-crit">
              <p className="font-medium">
                Kostenbereich
                {transactionKostenbereichCode ? ` „${transactionKostenbereichCode}"` : ""}{" "}
                ist im Bescheid dieser Massnahme nicht hinterlegt.
              </p>
              <p className="mt-1">
                Bitte den{" "}
                <Link
                  href={`/dashboard/foerdermassnahmen/${measureId}`}
                  className="underline hover:no-underline"
                >
                  Bescheid-Wizard öffnen
                </Link>{" "}
                und den Kostenbereich ergänzen oder eine andere Fördermassnahme wählen.
              </p>
            </div>
          ) : positionCount === 1 ? (
            <div className="rounded-soft-xs border border-soft-line bg-soft-surface2 px-3 py-2 text-sm text-soft-ink">
              <span className="text-soft-ink2 text-xs uppercase tracking-wide mr-2">
                Eindeutig aus Bescheid
              </span>
              <span className="font-medium">
                {positions[0].positionscode}
              </span>
              <span className="text-soft-ink2"> — {positions[0].bezeichnung}</span>
            </div>
          ) : (
            <>
              <select
                value={positionId}
                onChange={(e) => setPositionId(e.target.value)}
                className="w-full rounded-soft-xs border border-soft-line px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                required
              >
                <option value="">— Bitte wählen —</option>
                {positions.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.positionscode} — {p.bezeichnung} ({formatEur(parseFloat(p.betrag_bewilligt))})
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-soft-crit">
                {positionCount} Bescheid-Positionen können diesen Kostenbereich tragen
                — bitte wählen, sonst Doppelzählung im Soll-Ist.
              </p>
            </>
          )}
        </div>
      )}

      {/* Vorschau */}
      {previewFoerderung !== null && previewEigenanteil !== null && (
        <div className="rounded-soft-xs bg-soft-accentSoft border border-soft-accent/20 p-3 text-sm">
          <p className="font-medium text-soft-accent mb-1">Vorschau</p>
          <div className="flex justify-between text-soft-ink">
            <span>Förderbetrag (<span className="numeric">{parseFloat(selectedMeasure!.foerderquote).toFixed(0)} %</span>)</span>
            <span className="font-semibold numeric">
              {formatEur(previewFoerderung)}
            </span>
          </div>
          <div className="flex justify-between text-soft-ink2 mt-0.5">
            <span>Eigenanteil</span>
            <span className="numeric">{formatEur(previewEigenanteil)}</span>
          </div>
        </div>
      )}

      {/* Notiz */}
      <div>
        <label className="block text-sm font-medium text-soft-ink mb-1">
          Notiz <span className="text-soft-ink3 font-normal">(optional)</span>
        </label>
        <textarea
          value={notiz}
          onChange={(e) => setNotiz(e.target.value)}
          rows={2}
          className="w-full rounded-soft-xs border border-soft-line px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent resize-none"
          placeholder="z.B. Verwendungsnachweis-Referenz"
        />
      </div>

      {/* Fehlermeldung */}
      {apiError && (
        <p className="rounded-soft-xs bg-soft-critSoft border border-soft-crit/20 px-3 py-2 text-sm text-soft-crit">
          {apiError}
        </p>
      )}

      {/* Buttons */}
      <div className="flex gap-3 justify-end pt-1">
        {onCancel && (
          <Button variant="secondary" size="sm" onClick={onCancel} type="button">
            Abbrechen
          </Button>
        )}
        <Button
          variant="primary"
          size="sm"
          type="submit"
          loading={submitting}
          disabled={submitBlocked}
        >
          Zuordnung speichern
        </Button>
      </div>
    </form>
  );
}
