"use client";

import { useState, useEffect, useCallback } from "react";

type FunderEntry = {
  funder_id: string;
  funder_name: string;
  betrag_abgerufen: string;
  betrag_verwendet: string;
  betrag_offen: string;
  anzahl: number;
};

type Periode = {
  label: string;
  start: string;
  ende: string;
  funder: FunderEntry[];
  gesamt_abgerufen: string;
  gesamt_verwendet: string;
};

type KalenderData = {
  perioden: Periode[];
  haushaltsjahr: { id: string; jahr: number };
};

type Props = {
  haushaltsjahrId: string;
};

type PeriodeTyp = "MONAT" | "QUARTAL";

function formatEur(val: string | number): string {
  return Number(val).toLocaleString("de-DE", { style: "currency", currency: "EUR" });
}

function ausschoepfungProzent(abgerufen: string, verwendet: string): number {
  const a = parseFloat(abgerufen);
  const v = parseFloat(verwendet);
  return a > 0 ? Math.round((v / a) * 100) : 0;
}

function ausschoepfungColor(prozent: number): string {
  if (prozent >= 80) return "bg-soft-ok";
  if (prozent >= 40) return "bg-soft-warn";
  return "bg-soft-crit";
}

function ausschoepfungBadge(prozent: number): string {
  if (prozent >= 80) return "bg-soft-okSoft text-soft-ok border-soft-ok/20";
  if (prozent >= 40) return "bg-soft-warnSoft text-soft-warn border-soft-warn/20";
  return "bg-soft-critSoft text-soft-crit border-soft-crit/20";
}

/**
 * Cashflow-Kalender für Mittelabrufe.
 * Zeigt monatliche/quartalsweise Aggregation per Fördergeber als Grid.
 */
export function MittelabrufKalender({ haushaltsjahrId }: Props) {
  const [data, setData] = useState<KalenderData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [periode, setPeriode] = useState<PeriodeTyp>("MONAT");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/protected/mittelabrufe/kalender?haushaltsjahr_id=${encodeURIComponent(
          haushaltsjahrId,
        )}&periode=${periode}`,
        { credentials: "same-origin" },
      );

      const text = await res.text();

      if (!res.ok) {
        let message = `Fehler ${res.status}`;
        if (text) {
          try {
            const parsed = JSON.parse(text) as { error?: string };
            if (parsed.error) message = parsed.error;
          } catch {
            // Kein JSON (z.B. HTML-Login-Seite) — Statuscode reicht.
          }
        }
        throw new Error(message);
      }

      if (!text) {
        throw new Error("Leere Antwort vom Server.");
      }

      const json = JSON.parse(text) as { data?: KalenderData | null };
      setData(json.data ?? null);
    } catch (err) {
      setData(null);
      setError(
        err instanceof Error ? err.message : "Unbekannter Fehler beim Laden des Cashflow-Kalenders.",
      );
    } finally {
      setLoading(false);
    }
  }, [haushaltsjahrId, periode]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div>
      {/* Periode-Toggle */}
      <div className="flex items-center gap-2 mb-6">
        <span className="text-sm text-soft-ink3">Ansicht:</span>
        {(["MONAT", "QUARTAL"] as PeriodeTyp[]).map((p) => (
          <button
            key={p}
            onClick={() => setPeriode(p)}
            className={`px-3 py-1.5 rounded-soft-xs text-sm font-medium transition-colors
              ${
                periode === p
                  ? "bg-soft-accent text-white"
                  : "bg-soft-line2 text-soft-ink2 hover:bg-soft-line"
              }`}
          >
            {p === "MONAT" ? "Monatlich" : "Quartalsweise"}
          </button>
        ))}
      </div>

      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-soft-accent border-t-transparent" />
        </div>
      )}

      {!loading && error && (
        <div className="rounded-soft border border-soft-crit/30 bg-soft-critSoft px-4 py-3 text-sm text-soft-crit flex items-start gap-3">
          <svg
            className="h-4 w-4 shrink-0 mt-0.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
            />
          </svg>
          <div className="flex-1">
            <p className="font-medium">Cashflow-Kalender konnte nicht geladen werden.</p>
            <p className="text-xs text-soft-crit/80 mt-0.5">{error}</p>
          </div>
          <button
            type="button"
            onClick={() => void load()}
            className="text-xs font-medium underline hover:no-underline focus:outline-none focus:ring-2 focus:ring-soft-crit rounded-soft-xs px-1"
          >
            Erneut versuchen
          </button>
        </div>
      )}

      {!loading && !error && data && data.perioden.length === 0 && (
        <div className="flex flex-col items-center py-16 text-center">
          <div className="rounded-full bg-soft-line2 p-4 mb-3">
            <svg
              className="h-7 w-7 text-soft-ink4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"
              />
            </svg>
          </div>
          <p className="text-soft-ink3 text-sm">
            Keine Mittelabrufe für dieses Haushaltsjahr vorhanden.
          </p>
        </div>
      )}

      {!loading && !error && data && data.perioden.length > 0 && (
        <div className="space-y-6 overflow-x-auto">
          {data.perioden.map((p) => {
            const gesamt_prozent = ausschoepfungProzent(p.gesamt_abgerufen, p.gesamt_verwendet);
            return (
              <div
                key={p.start}
                className="rounded-soft border border-soft-line bg-soft-surface overflow-hidden"
              >
                {/* Perioden-Header */}
                <div className="flex items-center justify-between px-5 py-3 bg-soft-line2 border-b border-soft-line">
                  <div>
                    <span className="font-semibold text-soft-ink">{p.label}</span>
                    <span className="ml-3 text-xs text-soft-ink4">
                      {p.start} – {p.ende}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-sm">
                    <span className="text-soft-ink3">
                      Gesamt abgerufen:{" "}
                      <strong className="text-soft-ink">{formatEur(p.gesamt_abgerufen)}</strong>
                    </span>
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${ausschoepfungBadge(gesamt_prozent)}`}
                    >
                      <span
                        className={`inline-block h-1.5 w-1.5 rounded-full ${ausschoepfungColor(gesamt_prozent)}`}
                      />
                      {gesamt_prozent}% verwendet
                    </span>
                  </div>
                </div>

                {/* Fördergeber-Zeilen */}
                <div className="divide-y divide-soft-line2">
                  {p.funder.map((f) => {
                    const pct = ausschoepfungProzent(f.betrag_abgerufen, f.betrag_verwendet);
                    return (
                      <div key={f.funder_id} className="flex items-center gap-4 px-5 py-3">
                        {/* Fördergeber-Name */}
                        <div className="w-48 shrink-0">
                          <span className="text-sm font-medium text-soft-ink2 truncate block">
                            {f.funder_name}
                          </span>
                          <span className="text-xs text-soft-ink4">
                            {f.anzahl} Abruf{f.anzahl !== 1 ? "e" : ""}
                          </span>
                        </div>

                        {/* Fortschrittsbalken */}
                        <div className="flex-1">
                          <div className="flex justify-between text-xs text-soft-ink3 mb-1">
                            <span>{formatEur(f.betrag_verwendet)} verwendet</span>
                            <span>{formatEur(f.betrag_abgerufen)} abgerufen</span>
                          </div>
                          <div className="h-2 w-full rounded-full bg-soft-line2">
                            <div
                              className={`h-full rounded-full transition-all ${ausschoepfungColor(pct)}`}
                              style={{ width: `${Math.min(100, pct)}%` }}
                            />
                          </div>
                        </div>

                        {/* Kennzahlen */}
                        <div className="shrink-0 text-right w-32">
                          <div className="text-sm font-semibold text-soft-ink">{pct}%</div>
                          <div className="text-xs text-soft-ink4">
                            {parseFloat(f.betrag_offen) > 0
                              ? `${formatEur(f.betrag_offen)} offen`
                              : "vollständig"}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
