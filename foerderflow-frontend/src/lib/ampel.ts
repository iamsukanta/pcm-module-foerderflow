/**
 * Ampel-Warnsystem für Fördermassnahmen.
 * Pure Berechnungslogik ohne DB-Zugriff — alle Eingaben werden als Zahlen übergeben.
 */

export type AmpelStatus = "GRUEN" | "GELB" | "ROT";

export type AmpelInput = {
  betrag_bewilligt: number; // genehmigtes Förderbudget (budget_gesamt * foerderquote/100)
  betrag_ist: number; // tatsächlich ausgegebene Fördermittel bisher
  laufzeit_von: Date; // Startdatum der Maßnahme
  laufzeit_bis: Date; // Enddatum der Maßnahme
  overhead_limit_prozent: number | null; // konfiguriertes Gemeinkostendeckel (%)
  overhead_ist_prozent: number; // tatsächlicher Gemeinkosten-Anteil in % des betrag_ist
};

export type AmpelResult = {
  status: AmpelStatus;
  ausschoepfung_prozent: number; // betrag_ist / betrag_bewilligt * 100
  gruende: string[]; // deutsche Erklärungen für die Bewertung
};

/**
 * Berechnet den Ampel-Status einer Fördermassnahme.
 * Priorität: ROT > GELB > GRUEN. Erste zutreffende Regel gewinnt.
 */
export function berechneAmpel(input: AmpelInput): AmpelResult {
  const {
    betrag_bewilligt,
    betrag_ist,
    laufzeit_von,
    laufzeit_bis,
    overhead_limit_prozent,
    overhead_ist_prozent,
  } = input;

  const ausschoepfung_prozent = betrag_bewilligt > 0 ? (betrag_ist / betrag_bewilligt) * 100 : 0;

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const bis = new Date(laufzeit_bis);
  bis.setHours(0, 0, 0, 0);
  const von = new Date(laufzeit_von);
  von.setHours(0, 0, 0, 0);

  const days_until_expiry = Math.ceil((bis.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  const total_days = Math.max(
    1,
    Math.ceil((bis.getTime() - von.getTime()) / (1000 * 60 * 60 * 24)),
  );
  const days_elapsed = Math.max(
    0,
    Math.ceil((today.getTime() - von.getTime()) / (1000 * 60 * 60 * 24)),
  );

  // Lineares Soll-Tempo: nach X% der Laufzeit sollte X% des Budgets ausgeschöpft sein
  const soll_ausschoepfung = Math.min(100, (days_elapsed / total_days) * 100);
  const tempo_abweichung = Math.abs(ausschoepfung_prozent - soll_ausschoepfung);

  const gruende: string[] = [];

  // ── ROT-Kriterien ────────────────────────────────────────────────

  // Overhead-Limit überschritten
  if (overhead_limit_prozent !== null && overhead_ist_prozent > overhead_limit_prozent) {
    gruende.push(
      `Gemeinkostendeckel überschritten: ${overhead_ist_prozent.toFixed(1)}% (Limit: ${overhead_limit_prozent}%)`,
    );
    return { status: "ROT", ausschoepfung_prozent, gruende };
  }

  // Budgetüberschreitung
  if (ausschoepfung_prozent > 95) {
    gruende.push(`Ausschöpfung bei ${ausschoepfung_prozent.toFixed(1)}% — Budgetüberlauf droht`);
    return { status: "ROT", ausschoepfung_prozent, gruende };
  }

  // Kritische Unterausschöpfung: weniger als 40% ausgegeben, weniger als 90 Tage Restlaufzeit
  if (ausschoepfung_prozent < 40 && days_until_expiry < 90 && days_until_expiry >= 0) {
    gruende.push(
      `Nur ${ausschoepfung_prozent.toFixed(1)}% ausgeschöpft bei ${days_until_expiry} verbleibenden Tagen — Unterausschöpfung kritisch`,
    );
    return { status: "ROT", ausschoepfung_prozent, gruende };
  }

  // ── GELB-Kriterien ───────────────────────────────────────────────

  // Ausschöpfung im Warnbereich (80–95%)
  if (ausschoepfung_prozent >= 80) {
    gruende.push(`Ausschöpfung bei ${ausschoepfung_prozent.toFixed(1)}% — Budget wird knapp`);
    return { status: "GELB", ausschoepfung_prozent, gruende };
  }

  // Tempo-Abweichung >10% vom linearen Soll
  if (tempo_abweichung > 10 && days_elapsed > 0) {
    gruende.push(
      `Ausgabentempo weicht ${tempo_abweichung.toFixed(1)}% vom Soll-Kurs ab ` +
        `(Soll: ${soll_ausschoepfung.toFixed(1)}%, Ist: ${ausschoepfung_prozent.toFixed(1)}%)`,
    );
    return { status: "GELB", ausschoepfung_prozent, gruende };
  }

  // ── GRUEN ────────────────────────────────────────────────────────
  gruende.push(`Ausschöpfung ${ausschoepfung_prozent.toFixed(1)}% — im Zielkorridor`);
  return { status: "GRUEN", ausschoepfung_prozent, gruende };
}
