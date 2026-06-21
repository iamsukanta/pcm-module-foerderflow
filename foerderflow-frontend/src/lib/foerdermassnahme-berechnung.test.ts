import { describe, it, expect } from "vitest";
import { berechneZuwendung, validiereFehlbedarf } from "./foerdermassnahme-berechnung";

describe("berechneZuwendung", () => {
  it("ANTEIL: gesamt × quote/100", () => {
    const r = berechneZuwendung({
      finanzierungsart: "ANTEIL",
      gesamtausgaben: 50000,
      foerderquoteInput: 80,
    });
    expect(r.zuwendung).toBe(40000);
    expect(r.foerderquote).toBe(80);
  });

  it("FEHLBEDARF: gesamt − eigen − dritt, abgeleitete Quote", () => {
    const r = berechneZuwendung({
      finanzierungsart: "FEHLBEDARF",
      gesamtausgaben: 66447.22,
      eigenmittel: 34509.49,
      drittmittel: 0,
    });
    expect(r.zuwendung).toBeCloseTo(31937.73, 2);
    expect(r.foerderquote).toBeCloseTo(48.06, 2);
  });

  it("FESTBETRAG: zuwendung = gesamt, quote 0", () => {
    const r = berechneZuwendung({ finanzierungsart: "FESTBETRAG", gesamtausgaben: 12000 });
    expect(r.zuwendung).toBe(12000);
    expect(r.foerderquote).toBe(0);
  });
});

describe("validiereFehlbedarf", () => {
  it("rejects negative Eigenmittel", () => {
    const r = validiereFehlbedarf({ gesamtausgaben: 100, eigenmittel: -1, drittmittel: 0 });
    expect(r.valid).toBe(false);
  });

  it("rejects when eigen+dritt exceed gesamt", () => {
    const r = validiereFehlbedarf({ gesamtausgaben: 100, eigenmittel: 80, drittmittel: 40 });
    expect(r.valid).toBe(false);
  });

  it("warns when computed Fehlbedarf exceeds Höchstbetrag", () => {
    const r = validiereFehlbedarf({
      gesamtausgaben: 100000,
      eigenmittel: 10000,
      drittmittel: 0,
      zuwendungHoechstbetrag: 50000,
    });
    expect(r.valid).toBe(true);
    expect(r.warning).toBeTruthy();
  });

  it("ok within Höchstbetrag", () => {
    const r = validiereFehlbedarf({
      gesamtausgaben: 100000,
      eigenmittel: 60000,
      drittmittel: 0,
      zuwendungHoechstbetrag: 50000,
    });
    expect(r.valid).toBe(true);
    expect(r.warning).toBeUndefined();
  });
});
