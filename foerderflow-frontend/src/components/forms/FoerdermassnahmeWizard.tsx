"use client";

import { useState, useCallback, useEffect, Fragment, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/ToastProvider";
import { FunderForm } from "@/components/forms/FunderForm";
import { FoerderregelEditor, type RegelInput } from "@/components/forms/FoerderregelEditor";
import { FinanzplanPositionenStep, type WizardPosition } from "@/components/forms/FinanzplanPositionenStep";
import type {
  FunderTyp,
  FundingMeasureStatus,
  MittelabrufVerfahren,
  FundingRuleTyp,
} from "@/types/foerdermassnahmen";
import type { FinanzierungsartTyp } from "@/lib/foerdermassnahme-berechnung";
import {
  berechneZuwendung,
  validiereFehlbedarf,
} from "@/lib/foerdermassnahme-berechnung";

// ─── Data shapes ────────────────────────────────────────────────

type FunderOption = { id: string; name: string; typ: FunderTyp };
type CostCenterOption = { id: string; name: string; code: string; ist_aktiv: boolean };

type WizardInitialData = {
  id: string;
  funder_id: string;
  name: string;
  budget_gesamt: string;
  laufzeit_von: string;
  laufzeit_bis: string;
  durchfuehrungs_von: string | null;
  durchfuehrungs_bis: string | null;
  antragsnummer: string | null;
  status: FundingMeasureStatus;
  /// Finanzierungsart steuert die UI in Step 2 (ANTEIL/FEHLBEDARF/FESTBETRAG).
  /// Bei null wird ANTEIL als Default angenommen.
  finanzierungsart: FinanzierungsartTyp | null;
  /// Bei FEHLBEDARF: Eigenmittel-Plansumme der Org in EUR.
  eigenmittel_betrag: string | null;
  /// Bei FEHLBEDARF: Drittmittel-Plansumme in EUR (default 0).
  drittmittel_betrag: string | null;
  foerderquote: string;
  verwaltungspauschale_erlaubt: boolean;
  verwaltungspauschale_prozent: string | null;
  budget_flexibilitaet_prozent: string;
  overhead_limit_prozent: string | null;
  mwst_foerderfahig: boolean;
  mwst_satz_prozent: string;
  mittelabruf_verfahren: MittelabrufVerfahren;
  cost_center_ids: string[];
  rules: Array<{
    typ: FundingRuleTyp;
    schluessel: string;
    wert: string | null;
    beschreibung: string | null;
  }>;
  /** Optional — wenn vorhanden, lädt der Wizard die FinanzplanPositionen in Step 4 */
  positionen?: Array<{
    /** Persisted DB-ID (Edit-Modus). Im Create-Modus mit vorausgefüllten
     *  Draft-Positionen (z.B. OCR-Bescheid-Import) weglassen — nicht "". */
    id?: string;
    positionscode: string;
    bezeichnung: string;
    betrag_bewilligt: string;
    ueberziehung_limit_pct: string;
    kostenbereich_codes: string[];
    allocation_count: number;
    // Phase J — Verwaltungspauschale
    ist_pauschale?: boolean;
    pauschale_typ?: "FIXER_BETRAG" | "PROZENT_GESAMT" | "PROZENT_PERSONAL" | "UMLAGE_KOSTENSTELLEN" | null;
    pauschale_prozent?: string;
    // Phase K — UMLAGE_KOSTENSTELLEN-FKs
    umlage_allocation_key_id?: string | null;
    umlage_ziel_cost_center_id?: string | null;
    umlage_source_scope_id?: string | null;
  }>;
};

type WizardProps = {
  funders: FunderOption[];
  costCenters: CostCenterOption[];
  mode?: "create" | "edit";
  initialData?: WizardInitialData;
  onSuccess?: (id: string) => Promise<void>;
};

function toDateInput(str: string): string {
  if (!str) return "";
  try { return new Date(str).toISOString().slice(0, 10); } catch { return ""; }
}

// ─── Step 1 State ────────────────────────────────────────────────

type Step1 = {
  funder_id: string;
  name: string;
  antragsnummer: string;
  budget_gesamt: string;
  /// Bewilligungszeitraum (verpflichtend)
  laufzeit_von: string;
  laufzeit_bis: string;
  /// Optionaler engerer Durchführungszeitraum
  durchfuehrungs_von: string;
  durchfuehrungs_bis: string;
  status: FundingMeasureStatus;
};

// ─── Step 2 State ────────────────────────────────────────────────

type Step2 = {
  /// ANTEIL = prozentual, FEHLBEDARF = Fehlbedarf-Berechnung, FESTBETRAG = fix.
  /// Default ANTEIL für neue Maßnahmen.
  finanzierungsart: FinanzierungsartTyp;
  foerderquote: string;
  /// Nur bei FEHLBEDARF Pflicht-Eingabe.
  eigenmittel_betrag: string;
  /// Nur bei FEHLBEDARF (optional, default 0).
  drittmittel_betrag: string;
  verwaltungspauschale_erlaubt: boolean;
  verwaltungspauschale_prozent: string;
  budget_flexibilitaet_prozent: string;
  overhead_limit_prozent: string;
  mwst_foerderfahig: boolean;
  mwst_satz_prozent: string;
  mittelabruf_verfahren: MittelabrufVerfahren;
};

// ─── Step 3 State ────────────────────────────────────────────────

type Step3 = {
  cost_center_ids: string[];
  rules: RegelInput[];
};

// ─── Mittelabruf descriptions ────────────────────────────────────

const MITTELABRUF_OPTIONS: { value: MittelabrufVerfahren; label: string; description: string }[] = [
  {
    value: "ANFORDERUNG",
    label: "Anforderungsverfahren",
    description: "Mittel werden vor den Ausgaben angefordert. Verwendungsfrist: max. 6 Wochen (42 Tage).",
  },
  {
    value: "ABRUF",
    label: "Abrufverfahren",
    description: "Tagesgenaue Auszahlung — nur bei tatsächlich fälliger Zahlung. Strikt.",
  },
  {
    value: "ABSCHLAG",
    label: "Abschlagszahlungen",
    description: "Regelmäßige Abschläge nach Zeitplan, unabhängig vom tatsächlichen Mittelabfluss.",
  },
];


const STATUS_OPTIONS: { value: FundingMeasureStatus; label: string }[] = [
  { value: "AKTIV", label: "Aktiv" },
  { value: "ABGESCHLOSSEN", label: "Abgeschlossen" },
  { value: "WIDERRUFEN", label: "Widerrufen" },
];

const TOTAL_STEPS = 4;

// ─── Step Indicator ──────────────────────────────────────────────
// Grid-Layout statt Flex+last:flex-none → deterministische Geometrie:
// [circle][1fr connector][circle][1fr connector][circle][1fr connector][circle]
// Connectoren liegen vertikal mittig auf Höhe der Kreis-Mitte (mt-4 = 18px-ish).

const STEP_LABELS = [
  "Grunddaten",
  "Konditionen",
  "Kostenstellen & Regeln",
  "Finanzplan-Positionen",
] as const;

function StepIndicator({ current }: { current: number }) {
  // Dynamische Grid-Spalten: pro Step ein "auto" + zwischen Steps ein "1fr" Connector
  const gridTemplate = STEP_LABELS.map((_, i) =>
    i === 0 ? "auto" : "1fr auto"
  ).join(" ");

  return (
    <div
      role="progressbar"
      aria-valuemin={1}
      aria-valuemax={STEP_LABELS.length}
      aria-valuenow={current}
      aria-label={`Schritt ${current} von ${STEP_LABELS.length}`}
      className="grid items-start mb-8"
      style={{ gridTemplateColumns: gridTemplate }}
    >
      {STEP_LABELS.map((label, i) => {
        const stepNum = i + 1;
        const isDone = stepNum < current;
        const isActive = stepNum === current;
        const prevDone = stepNum - 1 < current;

        return (
          <Fragment key={label}>
            {/* Connector links vom Kreis (außer beim ersten) */}
            {i > 0 && (
              <div
                aria-hidden="true"
                className={`h-0.5 mt-[18px] mx-1 transition-colors
                  ${prevDone ? "bg-soft-ok" : "bg-soft-line"}`}
              />
            )}
            {/* Step-Kreis + Label */}
            <div className="flex flex-col items-center">
              <div
                className={`h-9 w-9 rounded-full flex items-center justify-center text-sm font-semibold border-2 transition-colors
                  ${isDone
                    ? "bg-soft-ok border-soft-ok text-white"
                    : isActive
                    ? "bg-soft-accent border-soft-accent text-white"
                    : "bg-white border-soft-line text-soft-ink4"
                  }`}
              >
                {isDone ? (
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3} aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  stepNum
                )}
              </div>
              <span
                className={`mt-1.5 text-xs font-medium text-center
                  ${isActive ? "text-soft-accent" : isDone ? "text-soft-ok" : "text-soft-ink4"}`}
              >
                {label}
              </span>
            </div>
          </Fragment>
        );
      })}
    </div>
  );
}

// ─── Main Wizard ─────────────────────────────────────────────────

export function FoerdermassnahmeWizard({ funders: initialFunders, costCenters, mode = "create", initialData, onSuccess }: WizardProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();

  // URL-Anchor: ?step=N → springt zu Step N (1–4); ungültige Werte fallen auf 1
  const initialStep = (() => {
    const raw = searchParams?.get("step");
    const n = raw ? parseInt(raw, 10) : 1;
    return Number.isFinite(n) && n >= 1 && n <= TOTAL_STEPS ? n : 1;
  })();

  const [currentStep, setCurrentStep] = useState(initialStep);
  const [justNavigated, setJustNavigated] = useState(false);
  const [funders, setFunders] = useState<FunderOption[]>(initialFunders);
  const [showNewFunderForm, setShowNewFunderForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // searchParams.step hat Vorrang nur beim ersten Mount; spätere Änderungen ignorieren
  useEffect(() => {
    // intentionally one-shot
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Step states — initialized from initialData in edit mode
  const [step1, setStep1] = useState<Step1>({
    funder_id: initialData?.funder_id ?? "",
    name: initialData?.name ?? "",
    antragsnummer: initialData?.antragsnummer ?? "",
    budget_gesamt: initialData?.budget_gesamt ?? "",
    laufzeit_von: initialData ? toDateInput(initialData.laufzeit_von) : "",
    laufzeit_bis: initialData ? toDateInput(initialData.laufzeit_bis) : "",
    durchfuehrungs_von: initialData?.durchfuehrungs_von ? toDateInput(initialData.durchfuehrungs_von) : "",
    durchfuehrungs_bis: initialData?.durchfuehrungs_bis ? toDateInput(initialData.durchfuehrungs_bis) : "",
    status: initialData?.status ?? "AKTIV",
  });

  const [step2, setStep2] = useState<Step2>({
    finanzierungsart: initialData?.finanzierungsart ?? "ANTEIL",
    foerderquote: initialData?.foerderquote ?? "80",
    eigenmittel_betrag: initialData?.eigenmittel_betrag ?? "",
    drittmittel_betrag: initialData?.drittmittel_betrag ?? "",
    verwaltungspauschale_erlaubt: initialData?.verwaltungspauschale_erlaubt ?? false,
    verwaltungspauschale_prozent: initialData?.verwaltungspauschale_prozent ?? "",
    budget_flexibilitaet_prozent: initialData?.budget_flexibilitaet_prozent ?? "20",
    overhead_limit_prozent: initialData?.overhead_limit_prozent ?? "",
    mwst_foerderfahig: initialData?.mwst_foerderfahig ?? true,
    mwst_satz_prozent: initialData?.mwst_satz_prozent ?? "19",
    mittelabruf_verfahren: initialData?.mittelabruf_verfahren ?? "ANFORDERUNG",
  });

  const [step3, setStep3] = useState<Step3>({
    cost_center_ids: initialData?.cost_center_ids ?? [],
    rules: (initialData?.rules ?? []).map((r) => ({
      typ: r.typ,
      schluessel: r.schluessel,
      wert: r.wert ?? "",
      beschreibung: r.beschreibung ?? "",
    })),
  });

  const [step4Positionen, setStep4Positionen] = useState<WizardPosition[]>(
    (initialData?.positionen ?? []).map((p) => ({
      id: p.id,
      positionscode: p.positionscode,
      bezeichnung: p.bezeichnung,
      betrag_bewilligt: p.betrag_bewilligt,
      ueberziehung_limit_pct: p.ueberziehung_limit_pct,
      kostenbereich_codes: p.kostenbereich_codes,
      allocation_count: p.allocation_count,
      ist_pauschale: p.ist_pauschale ?? false,
      pauschale_typ: p.pauschale_typ ?? null,
      pauschale_prozent: p.pauschale_prozent ?? "",
      // Phase K — UMLAGE-FKs aus initial laden (Edit-Modus)
      umlage_allocation_key_id: p.umlage_allocation_key_id ?? null,
      umlage_ziel_cost_center_id: p.umlage_ziel_cost_center_id ?? null,
      umlage_source_scope_id: p.umlage_source_scope_id ?? null,
    }))
  );

  const [errors, setErrors] = useState<Record<string, string>>({});

  // ── Step 1 validation ────────────────────────
  const validateStep1 = useCallback((): boolean => {
    const errs: Record<string, string> = {};
    if (!step1.funder_id) errs.funder_id = "Fördergeber ist erforderlich.";
    if (!step1.name.trim() || step1.name.trim().length < 2) errs.name = "Name ist erforderlich (min. 2 Zeichen).";
    const budget = parseFloat(step1.budget_gesamt);
    if (!step1.budget_gesamt || !Number.isFinite(budget) || budget <= 0) {
      errs.budget_gesamt = "Budget muss eine positive Zahl sein.";
    }
    if (!step1.laufzeit_von) errs.laufzeit_von = "Startdatum ist erforderlich.";
    if (!step1.laufzeit_bis) errs.laufzeit_bis = "Enddatum ist erforderlich.";
    if (step1.laufzeit_von && step1.laufzeit_bis && step1.laufzeit_von >= step1.laufzeit_bis) {
      errs.laufzeit_bis = "Enddatum muss nach dem Startdatum liegen.";
    }
    // Durchführungszeitraum: beide oder keiner; muss innerhalb Bewilligung liegen
    const dvon = step1.durchfuehrungs_von;
    const dbis = step1.durchfuehrungs_bis;
    if (Boolean(dvon) !== Boolean(dbis)) {
      errs.durchfuehrungs_von = "Bitte beide Daten angeben oder beide leer lassen.";
    } else if (dvon && dbis) {
      if (dvon >= dbis) {
        errs.durchfuehrungs_bis = "Enddatum der Durchführung muss nach dem Startdatum liegen.";
      } else if (step1.laufzeit_von && step1.laufzeit_bis && (dvon < step1.laufzeit_von || dbis > step1.laufzeit_bis)) {
        errs.durchfuehrungs_bis = "Durchführungszeitraum muss innerhalb des Bewilligungszeitraums liegen.";
      }
    }
    if (step1.antragsnummer.trim().length > 100) {
      errs.antragsnummer = "Antragsnummer darf maximal 100 Zeichen lang sein.";
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }, [step1]);

  // ── Step 2 validation ────────────────────────
  const validateStep2 = useCallback((): boolean => {
    const errs: Record<string, string> = {};

    // Finanzierungsart-spezifische Validierung
    if (step2.finanzierungsart === "ANTEIL") {
      const fq = parseFloat(step2.foerderquote);
      if (!step2.foerderquote || !Number.isFinite(fq) || fq < 0 || fq > 100) {
        errs.foerderquote = "Förderquote muss zwischen 0 und 100 liegen.";
      }
    } else if (step2.finanzierungsart === "FEHLBEDARF") {
      const gesamt = parseFloat(step1.budget_gesamt);
      const eigen = parseFloat(step2.eigenmittel_betrag);
      const dritt = step2.drittmittel_betrag ? parseFloat(step2.drittmittel_betrag) : 0;
      if (!step2.eigenmittel_betrag || !Number.isFinite(eigen)) {
        errs.eigenmittel_betrag = "Eigenmittel sind bei Fehlbedarfsfinanzierung Pflicht.";
      } else if (Number.isFinite(gesamt)) {
        const validation = validiereFehlbedarf({
          gesamtausgaben: gesamt,
          eigenmittel: eigen,
          drittmittel: Number.isFinite(dritt) ? dritt : 0,
        });
        if (!validation.valid && validation.error) {
          errs.eigenmittel_betrag = validation.error;
        }
      }
    }
    // FESTBETRAG: keine zusätzliche Validierung — budget_gesamt aus Step 1 ist alles

    if (step2.verwaltungspauschale_erlaubt && step2.verwaltungspauschale_prozent) {
      const p = parseFloat(step2.verwaltungspauschale_prozent);
      if (!Number.isFinite(p) || p < 0 || p > 100) {
        errs.verwaltungspauschale_prozent = "Verwaltungspauschale muss zwischen 0 und 100 liegen.";
      }
    }
    const flex = parseFloat(step2.budget_flexibilitaet_prozent);
    if (!Number.isFinite(flex) || flex < 0 || flex > 100) {
      errs.budget_flexibilitaet_prozent = "Budget-Flexibilität muss zwischen 0 und 100 liegen.";
    }
    if (step2.overhead_limit_prozent) {
      const overhead = parseFloat(step2.overhead_limit_prozent);
      if (!Number.isFinite(overhead) || overhead < 0 || overhead > 100) {
        errs.overhead_limit_prozent = "Gemeinkostendeckel muss zwischen 0 und 100 liegen.";
      }
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }, [step1, step2]);

  // ── Step 4 validation ────────────────────────
  const validateStep4 = useCallback((): boolean => {
    const errs: Record<string, string> = {};
    step4Positionen.forEach((pos, idx) => {
      if (!pos.positionscode.trim()) {
        errs[`pos_${idx}_positionscode`] = "Code ist erforderlich.";
      }
      if (!pos.bezeichnung.trim()) {
        errs[`pos_${idx}_bezeichnung`] = "Bezeichnung ist erforderlich.";
      }
      const betrag = parseFloat(pos.betrag_bewilligt);
      if (pos.betrag_bewilligt.trim() === "" || !Number.isFinite(betrag) || betrag < 0) {
        errs[`pos_${idx}_betrag_bewilligt`] = "Betrag muss ≥ 0 sein.";
      }
    });
    // Eindeutigkeit positionscode
    const codes = step4Positionen.map((p) => p.positionscode.trim()).filter(Boolean);
    const dupes = codes.filter((c, i) => codes.indexOf(c) !== i);
    if (dupes.length > 0) {
      step4Positionen.forEach((pos, idx) => {
        if (dupes.includes(pos.positionscode.trim())) {
          errs[`pos_${idx}_positionscode`] = "Code muss eindeutig sein.";
        }
      });
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }, [step4Positionen]);

  // ── Navigation ───────────────────────────────
  const handleNext = () => {
    if (currentStep === 1 && !validateStep1()) return;
    if (currentStep === 2 && !validateStep2()) return;
    setErrors({});
    // Blur aktiven Button vor Step-Wechsel — verhindert ungewollten Submit
    (document.activeElement as HTMLElement)?.blur();
    setJustNavigated(true);
    setCurrentStep((s) => Math.min(s + 1, TOTAL_STEPS));
    // Nach 500ms wieder aktivieren
    setTimeout(() => setJustNavigated(false), 500);
  };

  const handleBack = () => {
    setErrors({});
    setCurrentStep((s) => Math.max(s - 1, 1));
  };

  // ── Funder created inline ────────────────────
  const handleFunderCreated = (funder: { id: string; name: string; typ: FunderTyp }) => {
    setFunders((prev) => [...prev, funder].sort((a, b) => a.name.localeCompare(b.name)));
    setStep1((prev) => ({ ...prev, funder_id: funder.id }));
    setShowNewFunderForm(false);
    if (errors.funder_id) setErrors((p) => ({ ...p, funder_id: undefined as unknown as string }));
  };

  // ── Cost center toggle ───────────────────────
  const toggleCostCenter = (id: string) => {
    setStep3((prev) => ({
      ...prev,
      cost_center_ids: prev.cost_center_ids.includes(id)
        ? prev.cost_center_ids.filter((c) => c !== id)
        : [...prev.cost_center_ids, id],
    }));
  };


  // ── Sync der Finanzplan-Positionen (nach Massnahme-Save) ─────
  // Diff zwischen step4Positionen und initialData?.positionen:
  // - Mit id + in step4: PATCH (immer, da kostenbereiche replace)
  // - Ohne id: POST (neu)
  // - In initial aber nicht mehr in step4: DELETE
  const syncPositionen = useCallback(
    async (measureId: string): Promise<void> => {
      // filter(Boolean) symmetrisch zu currentIds: falsy IDs (leerer String/null/undefined)
      // dürfen nicht in toDelete landen, sonst wird `DELETE /api/protected/finanzplan-positionen/`
      // gesendet → Next.js matched die Collection-Route (kein DELETE-Handler) → 405.
      const initialIds = new Set(
        (initialData?.positionen ?? []).map((p) => p.id).filter(Boolean) as string[]
      );
      const currentIds = new Set(step4Positionen.map((p) => p.id).filter(Boolean) as string[]);
      const toDelete = [...initialIds].filter((id) => !currentIds.has(id));

      const tasks: Promise<Response>[] = [];

      for (const id of toDelete) {
        tasks.push(fetch(`/api/protected/finanzplan-positionen/${id}`, { method: "DELETE" }));
      }

      step4Positionen.forEach((pos, idx) => {
        const pauschaleProzent =
          pos.pauschale_prozent && pos.pauschale_prozent.trim()
            ? parseFloat(pos.pauschale_prozent)
            : null;
        const isUmlage = pos.ist_pauschale === true && pos.pauschale_typ === "UMLAGE_KOSTENSTELLEN";
        const payload = {
          positionscode: pos.positionscode.trim(),
          bezeichnung: pos.bezeichnung.trim(),
          betrag_bewilligt: parseFloat(pos.betrag_bewilligt),
          ueberziehung_limit_pct: parseFloat(pos.ueberziehung_limit_pct) || 20,
          sort_order: idx,
          kostenbereiche: pos.kostenbereich_codes.map((code) => ({ kostenbereich_code: code })),
          // Phase J — Pauschale-Felder. Für ist_pauschale=false werden alle Pauschale-Werte
          // serverseitig auf null normalisiert (siehe POST-/PATCH-Route).
          ist_pauschale: pos.ist_pauschale === true,
          pauschale_typ: pos.ist_pauschale ? pos.pauschale_typ ?? "FIXER_BETRAG" : null,
          pauschale_prozent:
            pos.ist_pauschale && Number.isFinite(pauschaleProzent as number) ? pauschaleProzent : null,
          // Phase K — UMLAGE-FKs. Server-CHECK-Constraint erzwingt Konsistenz.
          umlage_allocation_key_id: isUmlage ? pos.umlage_allocation_key_id ?? null : null,
          umlage_ziel_cost_center_id: isUmlage ? pos.umlage_ziel_cost_center_id ?? null : null,
          umlage_source_scope_id: isUmlage ? pos.umlage_source_scope_id ?? null : null,
        };
        if (pos.id) {
          tasks.push(
            fetch(`/api/protected/finanzplan-positionen/${pos.id}`, {
              method: "PATCH",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payload),
            })
          );
        } else {
          tasks.push(
            fetch(`/api/protected/finanzplan-positionen`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ ...payload, funding_measure_id: measureId }),
            })
          );
        }
      });

      const results = await Promise.allSettled(tasks);
      const failures = results.filter((r) => r.status === "rejected" || (r.status === "fulfilled" && !r.value.ok));
      if (failures.length > 0) {
        throw new Error(`${failures.length} Positions-Sync fehlgeschlagen`);
      }
    },
    [initialData, step4Positionen]
  );

  // ── Final submit ─────────────────────────────
  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    // Wenn nicht auf letztem Schritt: weiternavigieren statt speichern
    if (currentStep < TOTAL_STEPS) {
      handleNext();
      return;
    }

    if (!validateStep2()) return;
    if (!validateStep4()) {
      toast.error("Bitte korrigiere die Fehler in den Finanzplan-Positionen.");
      return;
    }

    // Förderquote je nach Finanzierungsart: bei ANTEIL Eingabe, bei FEHLBEDARF
    // abgeleitet aus berechneZuwendung(), bei FESTBETRAG 0.
    const gesamtNum = parseFloat(step1.budget_gesamt);
    const eigenmittelNum = step2.eigenmittel_betrag ? parseFloat(step2.eigenmittel_betrag) : 0;
    const drittmittelNum = step2.drittmittel_betrag ? parseFloat(step2.drittmittel_betrag) : 0;
    const berechnung = berechneZuwendung({
      finanzierungsart: step2.finanzierungsart,
      gesamtausgaben: gesamtNum,
      foerderquoteInput: parseFloat(step2.foerderquote),
      eigenmittel: eigenmittelNum,
      drittmittel: drittmittelNum,
    });

    const payload = {
      funder_id: step1.funder_id,
      name: step1.name.trim(),
      antragsnummer: step1.antragsnummer.trim() || null,
      budget_gesamt: gesamtNum,
      laufzeit_von: step1.laufzeit_von,
      laufzeit_bis: step1.laufzeit_bis,
      durchfuehrungs_von: step1.durchfuehrungs_von || null,
      durchfuehrungs_bis: step1.durchfuehrungs_bis || null,
      status: step1.status,
      finanzierungsart: step2.finanzierungsart,
      eigenmittel_betrag: step2.finanzierungsart === "FEHLBEDARF" ? eigenmittelNum : null,
      drittmittel_betrag: step2.finanzierungsart === "FEHLBEDARF" ? drittmittelNum : null,
      foerderquote: berechnung.foerderquote,
      verwaltungspauschale_erlaubt: step2.verwaltungspauschale_erlaubt,
      verwaltungspauschale_prozent: step2.verwaltungspauschale_erlaubt && step2.verwaltungspauschale_prozent
        ? parseFloat(step2.verwaltungspauschale_prozent)
        : null,
      budget_flexibilitaet_prozent: parseFloat(step2.budget_flexibilitaet_prozent),
      overhead_limit_prozent: step2.overhead_limit_prozent
        ? parseFloat(step2.overhead_limit_prozent)
        : null,
      mwst_foerderfahig: step2.mwst_foerderfahig,
      mwst_satz_prozent: step2.mwst_foerderfahig ? 19 : (parseFloat(step2.mwst_satz_prozent) || 19),
      mittelabruf_verfahren: step2.mittelabruf_verfahren,
      rules: step3.rules.map((r) => ({
        typ: r.typ,
        schluessel: r.schluessel,
        wert: r.wert || null,
        beschreibung: r.beschreibung || null,
      })),
      cost_center_ids: step3.cost_center_ids,
    };

    setSubmitting(true);
    try {
      const url = mode === "edit" && initialData
        ? `/api/protected/foerdermassnahmen/${initialData.id}`
        : "/api/protected/foerdermassnahmen";
      const method = mode === "edit" ? "PATCH" : "POST";

      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const json = await res.json() as { data?: { id: string }; error?: string; message?: string };

      if (!res.ok) {
        toast.error(json.error ?? "Fördermassnahme konnte nicht gespeichert werden.");
        return;
      }

      const targetId = mode === "edit" ? initialData?.id : json.data?.id;

      // Step 4: Finanzplan-Positionen synchronisieren
      if (targetId) {
        try {
          await syncPositionen(targetId);
        } catch {
          toast.error("Massnahme gespeichert, aber Positionen-Sync fehlgeschlagen. Bitte erneut versuchen.");
          return;
        }
      }

      toast.success(json.message ?? "Fördermassnahme wurde gespeichert.");
      if (onSuccess && targetId) {
        await onSuccess(targetId);
      } else {
        router.push(targetId ? `/dashboard/foerdermassnahmen/${targetId}` : "/dashboard/foerdermassnahmen");
        router.refresh();
      }
    } catch {
      toast.error("Netzwerkfehler. Bitte versuche es erneut.");
    } finally {
      setSubmitting(false);
    }
  };

  // ─── Derived values ────────────────────────────────────────────
  const foerderquoteNum = parseFloat(step2.foerderquote) || 0;
  const eigenanteil = Math.max(0, 100 - foerderquoteNum).toFixed(1);

  // Live-Berechnung Zuwendung + abgeleitete Förderquote je Finanzierungsart.
  // Wird in Step 2 als read-only-Anzeige genutzt.
  const gesamtausgabenNum = parseFloat(step1.budget_gesamt) || 0;
  const eigenmittelNum = parseFloat(step2.eigenmittel_betrag) || 0;
  const drittmittelNum = parseFloat(step2.drittmittel_betrag) || 0;
  const liveBerechnung = berechneZuwendung({
    finanzierungsart: step2.finanzierungsart,
    gesamtausgaben: gesamtausgabenNum,
    foerderquoteInput: foerderquoteNum,
    eigenmittel: eigenmittelNum,
    drittmittel: drittmittelNum,
  });
  const fehlbedarfValidation =
    step2.finanzierungsart === "FEHLBEDARF" && gesamtausgabenNum > 0 && step2.eigenmittel_betrag
      ? validiereFehlbedarf({
          gesamtausgaben: gesamtausgabenNum,
          eigenmittel: eigenmittelNum,
          drittmittel: drittmittelNum,
        })
      : null;

  // ─── Render ───────────────────────────────────────────────────

  return (
    <div className="w-full min-h-[640px]">
      <StepIndicator current={currentStep} />

      <form onSubmit={handleSubmit} noValidate>
        {/* ── STEP 1: Grunddaten ─────────────────────────── */}
        {currentStep === 1 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-soft-ink">Grunddaten</h2>
              <p className="text-sm text-soft-ink3 mt-1">Fördergeber, Programmname, Budget und Laufzeit.</p>
            </div>

            {/* Fördergeber */}
            <div>
              <label htmlFor="funder-select" className="block text-sm font-medium text-soft-ink2 mb-1">
                Fördergeber <span className="text-soft-crit">*</span>
              </label>

              {!showNewFunderForm ? (
                <div className="flex gap-2">
                  <select
                    id="funder-select"
                    value={step1.funder_id}
                    onChange={(e) => {
                      const val = e.target.value;
                      if (val === "__new__") {
                        setShowNewFunderForm(true);
                        setStep1((p) => ({ ...p, funder_id: "" }));
                      } else {
                        setStep1((p) => ({ ...p, funder_id: val }));
                        if (errors.funder_id) setErrors((p) => ({ ...p, funder_id: "" }));
                      }
                    }}
                    aria-invalid={!!errors.funder_id}
                    className={`flex-1 rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors bg-white
                      focus:ring-2 focus:ring-soft-accent focus:border-soft-accent
                      ${errors.funder_id ? "border-soft-crit" : "border-soft-line"}`}
                  >
                    <option value="">— Fördergeber wählen —</option>
                    {funders.map((f) => (
                      <option key={f.id} value={f.id}>{f.name}</option>
                    ))}
                    <option value="__new__">+ Neuen Fördergeber anlegen</option>
                  </select>
                </div>
              ) : (
                <FunderForm
                  inline
                  onSuccess={handleFunderCreated}
                  onCancel={() => setShowNewFunderForm(false)}
                />
              )}

              {errors.funder_id && (
                <p role="alert" className="mt-1 text-xs text-soft-crit">{errors.funder_id}</p>
              )}
            </div>

            {/* Name */}
            <div>
              <label htmlFor="measure-name" className="block text-sm font-medium text-soft-ink2 mb-1">
                Name der Massnahme <span className="text-soft-crit">*</span>
              </label>
              <input
                id="measure-name"
                type="text"
                value={step1.name}
                onChange={(e) => {
                  setStep1((p) => ({ ...p, name: e.target.value }));
                  if (errors.name) setErrors((p) => ({ ...p, name: "" }));
                }}
                placeholder="z.B. Integrationsförderung Hamburg 2026–2027"
                maxLength={300}
                aria-invalid={!!errors.name}
                className={`w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors
                  focus:ring-2 focus:ring-soft-accent focus:border-soft-accent
                  ${errors.name ? "border-soft-crit bg-soft-critSoft" : "border-soft-line bg-white"}`}
              />
              {errors.name && <p role="alert" className="mt-1 text-xs text-soft-crit">{errors.name}</p>}
            </div>

            {/* Budget */}
            <div>
              <label htmlFor="budget" className="block text-sm font-medium text-soft-ink2 mb-1">
                Zuwendungsfähige Gesamtausgaben (EUR) <span className="text-soft-crit">*</span>
              </label>
              <p className="text-xs text-soft-ink3 mb-1.5">
                Bei Fehlbedarfsfinanzierung: Summe aus Finanzierungsplan-Anhang
                („AUSGABEN insgesamt&ldquo;). Bei Festbetrag: gleich der Zuwendung.
              </p>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-soft-ink4 text-sm">€</span>
                <input
                  id="budget"
                  type="number"
                  min={0.01}
                  step={0.01}
                  value={step1.budget_gesamt}
                  onChange={(e) => {
                    setStep1((p) => ({ ...p, budget_gesamt: e.target.value }));
                    if (errors.budget_gesamt) setErrors((p) => ({ ...p, budget_gesamt: "" }));
                  }}
                  placeholder="80000.00"
                  aria-invalid={!!errors.budget_gesamt}
                  className={`w-full rounded-soft-xs border pl-7 pr-3 py-2.5 text-sm outline-none transition-colors
                    focus:ring-2 focus:ring-soft-accent focus:border-soft-accent
                    ${errors.budget_gesamt ? "border-soft-crit bg-soft-critSoft" : "border-soft-line bg-white"}`}
                />
              </div>
              {errors.budget_gesamt && (
                <p role="alert" className="mt-1 text-xs text-soft-crit">{errors.budget_gesamt}</p>
              )}
            </div>

            {/* Antragsnummer */}
            <div>
              <label htmlFor="antragsnummer" className="block text-sm font-medium text-soft-ink2 mb-1">
                Antragsnummer
              </label>
              <input
                id="antragsnummer"
                type="text"
                value={step1.antragsnummer}
                onChange={(e) => {
                  setStep1((p) => ({ ...p, antragsnummer: e.target.value }));
                  if (errors.antragsnummer) setErrors((p) => ({ ...p, antragsnummer: "" }));
                }}
                placeholder="z.B. ISP/2025/P 081, 100738705"
                maxLength={100}
                aria-invalid={!!errors.antragsnummer}
                className={`w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors
                  focus:ring-2 focus:ring-soft-accent focus:border-soft-accent
                  ${errors.antragsnummer ? "border-soft-crit bg-soft-critSoft" : "border-soft-line bg-white"}`}
              />
              <p className="mt-1 text-xs text-soft-ink3">
                Beim Fördergeber registrierte Antragsnummer (separat vom Förderkennzeichen).
              </p>
              {errors.antragsnummer && (
                <p role="alert" className="mt-1 text-xs text-soft-crit">{errors.antragsnummer}</p>
              )}
            </div>

            {/* Bewilligungszeitraum */}
            <div>
              <label className="block text-sm font-medium text-soft-ink2 mb-1">
                Bewilligungszeitraum <span className="text-soft-crit">*</span>
              </label>
              <p className="mb-2 text-xs text-soft-ink3">
                Der vom Fördergeber bewilligte Rahmen — innerhalb dessen müssen alle Ausgaben anfallen.
              </p>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <input
                    id="laufzeit-von"
                    type="date"
                    value={step1.laufzeit_von}
                    onChange={(e) => {
                      setStep1((p) => ({ ...p, laufzeit_von: e.target.value }));
                      if (errors.laufzeit_von) setErrors((p) => ({ ...p, laufzeit_von: "" }));
                    }}
                    aria-label="Bewilligung von"
                    aria-invalid={!!errors.laufzeit_von}
                    className={`w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors
                      focus:ring-2 focus:ring-soft-accent focus:border-soft-accent
                      ${errors.laufzeit_von ? "border-soft-crit bg-soft-critSoft" : "border-soft-line bg-white"}`}
                  />
                  {errors.laufzeit_von && (
                    <p role="alert" className="mt-1 text-xs text-soft-crit">{errors.laufzeit_von}</p>
                  )}
                </div>
                <div>
                  <input
                    id="laufzeit-bis"
                    type="date"
                    value={step1.laufzeit_bis}
                    onChange={(e) => {
                      setStep1((p) => ({ ...p, laufzeit_bis: e.target.value }));
                      if (errors.laufzeit_bis) setErrors((p) => ({ ...p, laufzeit_bis: "" }));
                    }}
                    aria-label="Bewilligung bis"
                    aria-invalid={!!errors.laufzeit_bis}
                    className={`w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors
                      focus:ring-2 focus:ring-soft-accent focus:border-soft-accent
                      ${errors.laufzeit_bis ? "border-soft-crit bg-soft-critSoft" : "border-soft-line bg-white"}`}
                  />
                  {errors.laufzeit_bis && (
                    <p role="alert" className="mt-1 text-xs text-soft-crit">{errors.laufzeit_bis}</p>
                  )}
                </div>
              </div>
            </div>

            {/* Durchführungszeitraum (optional) */}
            <div>
              <label className="block text-sm font-medium text-soft-ink2 mb-1">
                Durchführungszeitraum <span className="text-soft-ink3 font-normal">(optional)</span>
              </label>
              <p className="mb-2 text-xs text-soft-ink3">
                Engerer Zeitraum für die tatsächliche Durchführung. Wenn leer = identisch zum Bewilligungszeitraum. Beispiel SAB: Bewilligung 26.09.2024–31.01.2027, Durchführung 01.01.2025–31.12.2026.
              </p>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <input
                    id="durchfuehrungs-von"
                    type="date"
                    value={step1.durchfuehrungs_von}
                    onChange={(e) => {
                      setStep1((p) => ({ ...p, durchfuehrungs_von: e.target.value }));
                      if (errors.durchfuehrungs_von) setErrors((p) => ({ ...p, durchfuehrungs_von: "" }));
                      if (errors.durchfuehrungs_bis) setErrors((p) => ({ ...p, durchfuehrungs_bis: "" }));
                    }}
                    aria-label="Durchführung von"
                    aria-invalid={!!errors.durchfuehrungs_von}
                    className={`w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors
                      focus:ring-2 focus:ring-soft-accent focus:border-soft-accent
                      ${errors.durchfuehrungs_von ? "border-soft-crit bg-soft-critSoft" : "border-soft-line bg-white"}`}
                  />
                  {errors.durchfuehrungs_von && (
                    <p role="alert" className="mt-1 text-xs text-soft-crit">{errors.durchfuehrungs_von}</p>
                  )}
                </div>
                <div>
                  <input
                    id="durchfuehrungs-bis"
                    type="date"
                    value={step1.durchfuehrungs_bis}
                    onChange={(e) => {
                      setStep1((p) => ({ ...p, durchfuehrungs_bis: e.target.value }));
                      if (errors.durchfuehrungs_von) setErrors((p) => ({ ...p, durchfuehrungs_von: "" }));
                      if (errors.durchfuehrungs_bis) setErrors((p) => ({ ...p, durchfuehrungs_bis: "" }));
                    }}
                    aria-label="Durchführung bis"
                    aria-invalid={!!errors.durchfuehrungs_bis}
                    className={`w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors
                      focus:ring-2 focus:ring-soft-accent focus:border-soft-accent
                      ${errors.durchfuehrungs_bis ? "border-soft-crit bg-soft-critSoft" : "border-soft-line bg-white"}`}
                  />
                  {errors.durchfuehrungs_bis && (
                    <p role="alert" className="mt-1 text-xs text-soft-crit">{errors.durchfuehrungs_bis}</p>
                  )}
                </div>
              </div>
            </div>

            {/* Status */}
            <fieldset>
              <legend className="block text-sm font-medium text-soft-ink2 mb-2">Status</legend>
              <div className="flex gap-3">
                {STATUS_OPTIONS.map((opt) => (
                  <label
                    key={opt.value}
                    className={`flex items-center gap-2 rounded-soft-xs border px-4 py-2 cursor-pointer text-sm transition-colors
                      ${step1.status === opt.value
                        ? "border-soft-accent bg-soft-accentSoft text-soft-accent"
                        : "border-soft-line hover:border-soft-line text-soft-ink2"
                      }`}
                  >
                    <input
                      type="radio"
                      name="measure-status"
                      value={opt.value}
                      checked={step1.status === opt.value}
                      onChange={() => setStep1((p) => ({ ...p, status: opt.value }))}
                      className="h-3.5 w-3.5 accent-soft-accent"
                    />
                    {opt.label}
                  </label>
                ))}
              </div>
            </fieldset>
          </div>
        )}

        {/* ── STEP 2: Konditionen ────────────────────────── */}
        {currentStep === 2 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-soft-ink">Konditionen</h2>
              <p className="text-sm text-soft-ink3 mt-1">Förderquote, Pauschalen, Mittelabruf und Budget-Flexibilität.</p>
            </div>

            {/* Finanzierungsart — steuert die folgenden Felder dynamisch */}
            <div>
              <label htmlFor="finanzierungsart" className="block text-sm font-medium text-soft-ink2 mb-1">
                Finanzierungsart <span className="text-soft-crit">*</span>
              </label>
              <select
                id="finanzierungsart"
                value={step2.finanzierungsart}
                onChange={(e) =>
                  setStep2((p) => ({
                    ...p,
                    finanzierungsart: e.target.value as FinanzierungsartTyp,
                  }))
                }
                className="w-full rounded-soft-xs border border-soft-line bg-white px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-soft-accent focus:border-soft-accent"
              >
                <option value="ANTEIL">Anteilsfinanzierung (prozentualer Zuschuss)</option>
                <option value="FEHLBEDARF">Fehlbedarfsfinanzierung (Deckung der Lücke)</option>
                <option value="FESTBETRAG">Festbetragsfinanzierung (fixer Betrag)</option>
              </select>
              <p className="mt-1 text-xs text-soft-ink4">
                {step2.finanzierungsart === "ANTEIL" &&
                  "Fördergeber übernimmt einen prozentualen Anteil der Gesamtausgaben."}
                {step2.finanzierungsart === "FEHLBEDARF" &&
                  "Zuwendung = Gesamtausgaben − Eigenmittel − Drittmittel. Förderquote wird abgeleitet."}
                {step2.finanzierungsart === "FESTBETRAG" &&
                  "Fixer Förderbetrag unabhängig von tatsächlichen Ausgaben."}
              </p>
            </div>

            {/* ─── ANTEIL: Förderquote-Eingabe ─── */}
            {step2.finanzierungsart === "ANTEIL" && (
              <div>
                <label htmlFor="foerderquote" className="block text-sm font-medium text-soft-ink2 mb-1">
                  Förderquote (%) <span className="text-soft-crit">*</span>
                </label>
                <div className="flex items-center gap-3">
                  <div className="relative flex-1">
                    <input
                      id="foerderquote"
                      type="number"
                      min={0}
                      max={100}
                      step={0.01}
                      value={step2.foerderquote}
                      onChange={(e) => {
                        setStep2((p) => ({ ...p, foerderquote: e.target.value }));
                        if (errors.foerderquote) setErrors((p) => ({ ...p, foerderquote: "" }));
                      }}
                      aria-invalid={!!errors.foerderquote}
                      className={`w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors
                        focus:ring-2 focus:ring-soft-accent focus:border-soft-accent
                        ${errors.foerderquote ? "border-soft-crit bg-soft-critSoft" : "border-soft-line bg-white"}`}
                    />
                  </div>
                  <div className="rounded-soft-xs bg-soft-warnSoft border border-soft-warn/30 px-3 py-2 text-sm text-soft-warn whitespace-nowrap">
                    Eigenanteil: <strong className="numeric">{eigenanteil}%</strong>
                  </div>
                </div>
                <div className="mt-2 text-xs text-soft-ink3">
                  Berechnete Zuwendung:{" "}
                  <strong className="numeric">
                    {liveBerechnung.zuwendung.toLocaleString("de-DE", {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}{" "}
                    €
                  </strong>
                </div>
                {errors.foerderquote && (
                  <p role="alert" className="mt-1 text-xs text-soft-crit">{errors.foerderquote}</p>
                )}
              </div>
            )}

            {/* ─── FEHLBEDARF: Eigenmittel + Drittmittel ─── */}
            {step2.finanzierungsart === "FEHLBEDARF" && (
              <div className="rounded-soft-sm border border-soft-line bg-soft-surfaceAlt p-4 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="eigenmittel" className="block text-sm font-medium text-soft-ink2 mb-1">
                      Eigenmittel (EUR) <span className="text-soft-crit">*</span>
                    </label>
                    <input
                      id="eigenmittel"
                      type="number"
                      min={0}
                      step={0.01}
                      value={step2.eigenmittel_betrag}
                      onChange={(e) => {
                        setStep2((p) => ({ ...p, eigenmittel_betrag: e.target.value }));
                        if (errors.eigenmittel_betrag)
                          setErrors((p) => ({ ...p, eigenmittel_betrag: "" }));
                      }}
                      aria-invalid={!!errors.eigenmittel_betrag}
                      className={`w-full rounded-soft-xs border px-3 py-2.5 text-sm numeric outline-none focus:ring-2 focus:ring-soft-accent focus:border-soft-accent ${
                        errors.eigenmittel_betrag ? "border-soft-crit bg-soft-critSoft" : "border-soft-line bg-white"
                      }`}
                    />
                  </div>
                  <div>
                    <label htmlFor="drittmittel" className="block text-sm font-medium text-soft-ink2 mb-1">
                      Drittmittel (EUR)
                    </label>
                    <input
                      id="drittmittel"
                      type="number"
                      min={0}
                      step={0.01}
                      placeholder="0,00"
                      value={step2.drittmittel_betrag}
                      onChange={(e) => setStep2((p) => ({ ...p, drittmittel_betrag: e.target.value }))}
                      className="w-full rounded-soft-xs border border-soft-line bg-white px-3 py-2.5 text-sm numeric outline-none focus:ring-2 focus:ring-soft-accent focus:border-soft-accent"
                    />
                    <p className="mt-1 text-xs text-soft-ink4">Zuwendungen anderer + sonstige</p>
                  </div>
                </div>

                {/* Live-Berechnung Anzeige */}
                <div className="grid grid-cols-2 gap-4 pt-2 border-t border-soft-line2">
                  <div>
                    <p className="text-xs text-soft-ink3 uppercase tracking-wide mb-0.5">
                      Fehlbedarf / Zuwendung
                    </p>
                    <p className="text-lg font-semibold numeric text-soft-ink">
                      {liveBerechnung.zuwendung.toLocaleString("de-DE", {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}{" "}
                      €
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-soft-ink3 uppercase tracking-wide mb-0.5">
                      Förderquote (abgeleitet)
                    </p>
                    <p className="text-lg font-semibold numeric text-soft-ink">
                      {liveBerechnung.foerderquote.toFixed(2)} %
                    </p>
                  </div>
                </div>

                {errors.eigenmittel_betrag && (
                  <p role="alert" className="text-xs text-soft-crit">{errors.eigenmittel_betrag}</p>
                )}
                {fehlbedarfValidation?.warning && (
                  <p className="text-xs text-soft-warn bg-soft-warnSoft border border-soft-warn/30 rounded-soft-xs px-2 py-1.5">
                    ⚠ {fehlbedarfValidation.warning}
                  </p>
                )}
              </div>
            )}

            {/* ─── FESTBETRAG: Hinweis ─── */}
            {step2.finanzierungsart === "FESTBETRAG" && (
              <div className="rounded-soft-xs border border-soft-accent/30 bg-soft-accentSoft px-3 py-2.5 text-sm text-soft-accent">
                Festbetragsfinanzierung: Die in Step 1 eingegebene Zuwendungsfähige Gesamtausgaben (
                <strong className="numeric">
                  {gesamtausgabenNum.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €
                </strong>
                ) sind direkt der Zuwendungsbetrag. Förderquote, Eigenmittel und Drittmittel sind nicht relevant.
              </div>
            )}

            {/* ─── Sektion: Pauschale (Förder-Erweiterung) ─────────────────── */}
            <div className="space-y-3 border-t border-soft-line2 pt-5">
              <div>
                <h3 className="text-xs font-semibold text-soft-ink2 uppercase tracking-wide">
                  Pauschale (Förder-Erweiterung)
                </h3>
                <p className="mt-0.5 text-xs text-soft-ink3">
                  Erlaubt es, zusätzlich zu den direkten Kosten einen pauschalen Verwaltungsanteil
                  als virtuelle Position abzurechnen — ohne Einzelbelege.
                </p>
              </div>

              {/* Verwaltungspauschale */}
              <div className="rounded-soft-sm border border-soft-line p-4 space-y-3">
                <label className="flex items-center gap-3 cursor-pointer">
                  <div
                    className={`relative inline-flex h-5 w-9 rounded-full transition-colors
                      ${step2.verwaltungspauschale_erlaubt ? "bg-soft-accent" : "bg-soft-line"}`}
                    onClick={() =>
                      setStep2((p) => ({
                        ...p,
                        verwaltungspauschale_erlaubt: !p.verwaltungspauschale_erlaubt,
                        verwaltungspauschale_prozent: "",
                      }))
                    }
                  >
                    <span
                      className={`absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform
                        ${step2.verwaltungspauschale_erlaubt ? "translate-x-4" : "translate-x-0"}`}
                    />
                  </div>
                  <input
                    type="checkbox"
                    className="sr-only"
                    checked={step2.verwaltungspauschale_erlaubt}
                    onChange={(e) =>
                      setStep2((p) => ({
                        ...p,
                        verwaltungspauschale_erlaubt: e.target.checked,
                        verwaltungspauschale_prozent: "",
                      }))
                    }
                  />
                  <span className="text-sm font-medium text-soft-ink2">
                    Verwaltungspauschale (Maßnahmen-Default)
                  </span>
                </label>

                <p className="text-xs text-soft-ink3">
                  Default-Prozentsatz für <strong>PROZENT_PERSONAL</strong>- und{" "}
                  <strong>PROZENT_GESAMT</strong>-Pauschale-Positionen in Step 4. Wird nur verwendet,
                  wenn die Position selbst keinen Prozent-Wert hat. Für <strong>FIXER_BETRAG</strong>-
                  Pauschalen nicht relevant — die konkrete Pauschale-Konfiguration findet pro
                  Bescheid-Position in Step 4 statt.
                </p>

                {step2.verwaltungspauschale_erlaubt && (
                  <div>
                    <label htmlFor="pauschale-prozent" className="block text-xs font-medium text-soft-ink2 mb-1">
                      Pauschale in %
                    </label>
                    <div className="relative w-40">
                      <input
                        id="pauschale-prozent"
                        type="number"
                        min={0}
                        max={100}
                        step={0.01}
                        value={step2.verwaltungspauschale_prozent}
                        onChange={(e) => {
                          setStep2((p) => ({ ...p, verwaltungspauschale_prozent: e.target.value }));
                          if (errors.verwaltungspauschale_prozent)
                            setErrors((p) => ({ ...p, verwaltungspauschale_prozent: "" }));
                        }}
                        placeholder="15"
                        aria-invalid={!!errors.verwaltungspauschale_prozent}
                        className={`w-full rounded-soft-xs border px-3 py-2 text-sm outline-none transition-colors
                          focus:ring-2 focus:ring-soft-accent focus:border-soft-accent
                          ${errors.verwaltungspauschale_prozent ? "border-soft-crit bg-soft-critSoft" : "border-soft-line bg-white"}`}
                      />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-soft-ink4 text-sm">%</span>
                    </div>
                    {errors.verwaltungspauschale_prozent && (
                      <p role="alert" className="mt-1 text-xs text-soft-crit">{errors.verwaltungspauschale_prozent}</p>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* ─── Sektion: Schutz-Limits (begrenzen Förderung) ─────────────── */}
            <div className="space-y-4 border-t border-soft-line2 pt-5">
              <div>
                <h3 className="text-xs font-semibold text-soft-ink2 uppercase tracking-wide">
                  Schutz-Limits (begrenzen Förderung)
                </h3>
                <p className="mt-0.5 text-xs text-soft-ink3">
                  Setzen Grenzen für echte Buchungen — andere Mechanik als die Pauschale oben.
                </p>
              </div>

              {/* Budget-Flexibilität */}
              <div>
                <label htmlFor="budget-flex" className="block text-sm font-medium text-soft-ink2 mb-1">
                  Budget-Flexibilität (%)
                </label>
                <div className="relative w-40">
                  <input
                    id="budget-flex"
                    type="number"
                    min={0}
                    max={100}
                    step={0.01}
                    value={step2.budget_flexibilitaet_prozent}
                    onChange={(e) => {
                      setStep2((p) => ({ ...p, budget_flexibilitaet_prozent: e.target.value }));
                      if (errors.budget_flexibilitaet_prozent) setErrors((p) => ({ ...p, budget_flexibilitaet_prozent: "" }));
                    }}
                    aria-invalid={!!errors.budget_flexibilitaet_prozent}
                    className={`w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors
                      focus:ring-2 focus:ring-soft-accent focus:border-soft-accent
                      ${errors.budget_flexibilitaet_prozent ? "border-soft-crit bg-soft-critSoft" : "border-soft-line bg-white"}`}
                  />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-soft-ink4 text-sm">%</span>
                </div>
                <p className="mt-1 text-xs text-soft-ink3">
                  ANBest-P Standard: 20 % — erlaubte Abweichung je Kostenposition ohne Genehmigung.
                </p>
                {errors.budget_flexibilitaet_prozent && (
                  <p role="alert" className="mt-1 text-xs text-soft-crit">{errors.budget_flexibilitaet_prozent}</p>
                )}
              </div>

              {/* Gemeinkostendeckel */}
              <div>
                <label htmlFor="overhead-limit" className="block text-sm font-medium text-soft-ink2 mb-1">
                  Gemeinkostendeckel (%)
                  <span className="ml-2 text-xs font-normal text-soft-ink4">Optional</span>
                </label>
                <div className="relative w-40">
                  <input
                    id="overhead-limit"
                    type="number"
                    min={0}
                    max={100}
                    step={0.01}
                    value={step2.overhead_limit_prozent}
                    onChange={(e) => {
                      setStep2((p) => ({ ...p, overhead_limit_prozent: e.target.value }));
                      if (errors.overhead_limit_prozent) setErrors((p) => ({ ...p, overhead_limit_prozent: "" }));
                    }}
                    placeholder="z.B. 15"
                    aria-invalid={!!errors.overhead_limit_prozent}
                    className={`w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors
                      focus:ring-2 focus:ring-soft-accent focus:border-soft-accent
                      ${errors.overhead_limit_prozent ? "border-soft-crit bg-soft-critSoft" : "border-soft-line bg-white"}`}
                  />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-soft-ink4 text-sm">%</span>
                </div>
                <p className="mt-1 text-xs text-soft-ink3">
                  <strong>Schutz-Limit, KEINE Förder-Ergänzung.</strong> Begrenzt den Anteil der
                  tatsächlich gebuchten OVERHEAD-Kostenstellen an den Sach-Ausgaben. Bei Überschreitung
                  erscheint beim Zuordnen eine Warnung (nicht blockierend). Nicht zu verwechseln mit
                  der Verwaltungspauschale oben — das ist ein anderer Mechanismus.
                </p>
                {errors.overhead_limit_prozent && (
                  <p role="alert" className="mt-1 text-xs text-soft-crit">{errors.overhead_limit_prozent}</p>
                )}
              </div>
            </div>

            {/* MwSt / Vorsteuerabzug */}
            <div className="rounded-soft-sm border border-soft-line p-4 space-y-3">
              <label className="flex items-center gap-3 cursor-pointer">
                <div
                  className={`relative inline-flex h-5 w-9 rounded-full transition-colors
                    ${step2.mwst_foerderfahig ? "bg-soft-accent" : "bg-soft-line"}`}
                  onClick={() => setStep2((p) => ({ ...p, mwst_foerderfahig: !p.mwst_foerderfahig }))}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform
                      ${step2.mwst_foerderfahig ? "translate-x-4" : "translate-x-0"}`}
                  />
                </div>
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={step2.mwst_foerderfahig}
                  onChange={(e) => setStep2((p) => ({ ...p, mwst_foerderfahig: e.target.checked }))}
                />
                <div>
                  <span className="text-sm font-medium text-soft-ink2">Mehrwertsteuer ist förderfähig</span>
                  <p className="text-xs text-soft-ink3 mt-0.5">
                    Deaktivieren wenn die Organisation für diese Maßnahme vorsteuerabzugsberechtigt ist.
                  </p>
                </div>
              </label>
              {!step2.mwst_foerderfahig && (
                <div>
                  <label className="block text-xs font-medium text-soft-ink2 mb-1">
                    MwSt-Satz (%)
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    step="0.1"
                    value={step2.mwst_satz_prozent}
                    onChange={(e) => setStep2((p) => ({ ...p, mwst_satz_prozent: e.target.value }))}
                    className="w-28 rounded-soft-xs border border-soft-line px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                  />
                  <p className="text-xs text-soft-ink3 mt-1">
                    Standard: 19 % (z. B. 7 % für ermäßigte Sätze)
                  </p>
                </div>
              )}
            </div>

            {/* Mittelabruf-Verfahren */}
            <fieldset>
              <legend className="block text-sm font-medium text-soft-ink2 mb-2">
                Mittelabruf-Verfahren <span className="text-soft-crit">*</span>
              </legend>
              <div className="space-y-3">
                {MITTELABRUF_OPTIONS.map((opt) => (
                  <label
                    key={opt.value}
                    className={`flex items-start gap-3 rounded-soft-sm border p-4 cursor-pointer transition-colors
                      ${step2.mittelabruf_verfahren === opt.value
                        ? "border-soft-accent bg-soft-accentSoft"
                        : "border-soft-line hover:border-soft-line hover:bg-soft-line2"
                      }`}
                  >
                    <input
                      type="radio"
                      name="mittelabruf"
                      value={opt.value}
                      checked={step2.mittelabruf_verfahren === opt.value}
                      onChange={() => setStep2((p) => ({ ...p, mittelabruf_verfahren: opt.value }))}
                      className="mt-0.5 h-4 w-4 accent-soft-accent"
                    />
                    <div>
                      <div className="text-sm font-medium text-soft-ink">{opt.label}</div>
                      <div className="text-xs text-soft-ink3 mt-0.5">{opt.description}</div>
                    </div>
                  </label>
                ))}
              </div>
            </fieldset>
          </div>
        )}

        {/* ── STEP 3: Kostenstellen & Regeln ────────────── */}
        {currentStep === 3 && (
          <div className="space-y-8">
            <div>
              <h2 className="text-lg font-semibold text-soft-ink">Kostenstellen & Regeln</h2>
              <p className="text-sm text-soft-ink3 mt-1">
                Welche Kostenstellen sind dieser Massnahme zugeordnet? Welche Förderregeln gelten?
              </p>
            </div>

            {/* Kostenstellen Multi-Select */}
            <div>
              <h3 className="text-sm font-semibold text-soft-ink2 mb-3">
                Kostenstellen zuordnen
                <span className="ml-2 text-xs font-normal text-soft-ink3">(optional)</span>
              </h3>
              {costCenters.length === 0 ? (
                <p className="text-sm text-soft-ink4 italic">Keine aktiven Kostenstellen vorhanden.</p>
              ) : (
                <div className="space-y-2 max-h-64 overflow-y-auto pr-1 border border-soft-line rounded-soft-sm p-3">
                  {costCenters.map((cc) => (
                    <label
                      key={cc.id}
                      className={`flex items-center gap-3 rounded-soft-xs border p-3 cursor-pointer transition-colors
                        ${step3.cost_center_ids.includes(cc.id)
                          ? "border-soft-accent bg-soft-accentSoft"
                          : "border-soft-line hover:border-soft-line"
                        }`}
                    >
                      <input
                        type="checkbox"
                        checked={step3.cost_center_ids.includes(cc.id)}
                        onChange={() => toggleCostCenter(cc.id)}
                        className="h-4 w-4 rounded accent-soft-accent"
                      />
                      <span className="font-mono text-xs bg-soft-surfaceAlt text-soft-ink2 rounded px-1.5 py-0.5">
                        {cc.code}
                      </span>
                      <span className="text-sm text-soft-ink2">{cc.name}</span>
                    </label>
                  ))}
                </div>
              )}
              <p className="mt-1.5 text-xs text-soft-ink3">
                {step3.cost_center_ids.length} Kostenstelle(n) ausgewählt
              </p>
            </div>

            {/* Förderregeln */}
            <div>
              <h3 className="text-sm font-semibold text-soft-ink2 mb-3">
                Förderregeln
                <span className="ml-2 text-xs font-normal text-soft-ink3">(optional)</span>
              </h3>
              <FoerderregelEditor
                regeln={step3.rules}
                onChange={(regeln) => setStep3((p) => ({ ...p, rules: regeln }))}
              />
            </div>
          </div>
        )}

        {/* Vorsteuerabzug-Hinweis auf Step 3 */}
        {currentStep === 3 && !step2.mwst_foerderfahig && (
          <div className="mt-6 rounded-soft-sm border border-soft-warn/30 bg-soft-warnSoft px-4 py-3 text-sm text-soft-warn">
            Diese Maßnahme ist vorsteuerabzugsberechtigt. Bei der Fördermittelzuordnung werden nur Nettobeträge als förderfähige Ausgaben gewertet.
          </div>
        )}

        {/* ── STEP 4: Finanzplan-Positionen ──────────── */}
        {currentStep === 4 && (
          <FinanzplanPositionenStep
            positionen={step4Positionen}
            onChange={setStep4Positionen}
            budgetGesamt={parseFloat(step1.budget_gesamt) || 0}
            errors={errors}
          />
        )}

        {/* ── Navigation ─────────────────────────────────── */}
        <div className="mt-8 flex items-center justify-between border-t border-soft-line2 pt-6">
          <div>
            {currentStep > 1 && (
              <Button
                type="button"
                variant="secondary"
                onClick={handleBack}
                disabled={submitting}
              >
                ← Zurück
              </Button>
            )}
          </div>

          <div className="flex gap-3">
            <Button
              type="button"
              variant="ghost"
              onClick={() => router.push("/dashboard/foerdermassnahmen")}
              disabled={submitting}
            >
              Abbrechen
            </Button>

            {currentStep < TOTAL_STEPS ? (
              <Button type="button" variant="primary" onClick={handleNext}>
                Weiter →
              </Button>
            ) : (
              <Button type="submit" variant="primary" loading={submitting} disabled={justNavigated}>
                {mode === "edit" ? "Änderungen speichern" : "Massnahme speichern"}
              </Button>
            )}
          </div>
        </div>
      </form>
    </div>
  );
}
