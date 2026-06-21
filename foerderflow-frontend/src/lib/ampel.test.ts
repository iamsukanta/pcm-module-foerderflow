import { describe, it, expect } from "vitest";
import { berechneAmpel } from "./ampel";

// Laufzeit weit in der Zukunft, damit die Datum-basierten Regeln (Unterausschöpfung
// bei <90 Tagen Restlaufzeit, Tempo-Abweichung) nicht stören und wir die
// Budget-Schwellen isoliert testen.
const FAR_VON = new Date(Date.now() - 30 * 86400_000);
const FAR_BIS = new Date(Date.now() + 365 * 86400_000);

describe("berechneAmpel", () => {
  it("ROT bei Overhead-Limit-Überschreitung", () => {
    const r = berechneAmpel({
      betrag_bewilligt: 100000,
      betrag_ist: 10000,
      laufzeit_von: FAR_VON,
      laufzeit_bis: FAR_BIS,
      overhead_limit_prozent: 20,
      overhead_ist_prozent: 25,
    });
    expect(r.status).toBe("ROT");
  });

  it("ROT bei Ausschöpfung > 95%", () => {
    const r = berechneAmpel({
      betrag_bewilligt: 100000,
      betrag_ist: 96000,
      laufzeit_von: FAR_VON,
      laufzeit_bis: FAR_BIS,
      overhead_limit_prozent: null,
      overhead_ist_prozent: 0,
    });
    expect(r.status).toBe("ROT");
  });

  it("GELB bei Ausschöpfung 80–95%", () => {
    const r = berechneAmpel({
      betrag_bewilligt: 100000,
      betrag_ist: 85000,
      laufzeit_von: FAR_VON,
      laufzeit_bis: FAR_BIS,
      overhead_limit_prozent: null,
      overhead_ist_prozent: 0,
    });
    expect(r.status).toBe("GELB");
  });

  it("ROT bei kritischer Unterausschöpfung kurz vor Ende", () => {
    const r = berechneAmpel({
      betrag_bewilligt: 100000,
      betrag_ist: 10000, // 10%
      laufzeit_von: new Date(Date.now() - 300 * 86400_000),
      laufzeit_bis: new Date(Date.now() + 30 * 86400_000), // <90 Tage Rest
      overhead_limit_prozent: null,
      overhead_ist_prozent: 0,
    });
    expect(r.status).toBe("ROT");
  });

  it("ausschoepfung_prozent korrekt berechnet", () => {
    const r = berechneAmpel({
      betrag_bewilligt: 200000,
      betrag_ist: 50000,
      laufzeit_von: FAR_VON,
      laufzeit_bis: FAR_BIS,
      overhead_limit_prozent: null,
      overhead_ist_prozent: 0,
    });
    expect(r.ausschoepfung_prozent).toBeCloseTo(25, 5);
  });
});
