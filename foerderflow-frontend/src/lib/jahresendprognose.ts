// Client-safe types for the Jahresendprognose. The computation runs in the
// backend (GET /foerdermassnahmen/{id}/prognose); the frontend only needs the
// result shape consumed by PrognoseCard.

export type PrognoseStatus = "UNTERAUSSCHOEPFUNG" | "OK" | "UEBERSCHREITUNG";

export type PrognoseResult = {
  monatsrate: number; // durchschnittliche monatliche Ausgaben der letzten 90 Tage
  betrag_ist_gesamt: number; // gesamte bisherige Ausgaben
  prognose_gesamt: number; // projizierte Gesamtausgaben bis Laufzeitende
  prognose_prozent: number; // prognose_gesamt / betrag_bewilligt * 100
  days_remaining: number; // verbleibende Tage bis laufzeit_bis
  status: PrognoseStatus;
};
