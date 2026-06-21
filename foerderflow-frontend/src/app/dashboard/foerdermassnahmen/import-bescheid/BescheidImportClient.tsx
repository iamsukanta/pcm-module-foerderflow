"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/ToastProvider";
import { FoerdermassnahmeWizard } from "@/components/forms/FoerdermassnahmeWizard";
import { FunderForm } from "@/components/forms/FunderForm";
import { FoerderregelEditor, type RegelInput } from "@/components/forms/FoerderregelEditor";
import type { BescheidExtraktion } from "@/lib/bescheid/extraction-prompt";
import type { FunderTyp, MittelabrufVerfahren } from "@/types/foerdermassnahmen";
import { useKostenbereiche } from "@/lib/hooks/useKostenbereiche";

// ─── Props ────────────────────────────────────────────────────────────────────

type FunderOption = { id: string; name: string; typ: FunderTyp };
type CostCenterOption = { id: string; name: string; code: string; ist_aktiv: boolean };

type Props = {
  funders: FunderOption[];
  costCenters: CostCenterOption[];
};

// ─── Hilfsfunktionen ──────────────────────────────────────────────────────────

function ConfidenceBadge({ confidence }: { confidence: BescheidExtraktion["confidence"] }) {
  const dots = confidence === "HIGH" ? 3 : confidence === "MEDIUM" ? 2 : 1;
  const color =
    confidence === "HIGH" ? "text-soft-ok"
    : confidence === "MEDIUM" ? "text-soft-warn"
    : "text-soft-crit";
  const label = confidence === "HIGH" ? "Hoch" : confidence === "MEDIUM" ? "Mittel" : "Niedrig";
  return (
    <div className="flex items-center gap-2">
      <span className={`font-semibold text-sm ${color}`}>{label}</span>
      <span className={`text-lg tracking-widest ${color}`}>
        {"●".repeat(dots)}{"○".repeat(3 - dots)}
      </span>
    </div>
  );
}

// Styling für Felder je nach Confidence und ob null
function fieldCls(isNull: boolean, confidence: BescheidExtraktion["confidence"] | undefined) {
  if (isNull)
    return "w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors focus:ring-2 focus:ring-soft-accent focus:border-soft-accent bg-soft-line2 border-soft-line text-soft-ink4 placeholder:text-soft-ink4";
  if (confidence !== "HIGH")
    return "w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors focus:ring-2 focus:ring-soft-accent focus:border-soft-accent bg-soft-warnSoft border-soft-warn/40";
  return "w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors focus:ring-2 focus:ring-soft-accent focus:border-soft-accent bg-white border-soft-line";
}

function WarningLabel() {
  return <span className="ml-2 text-xs text-soft-warn font-normal">⚠ Bitte prüfen</span>;
}

// ─── EditPosition ─────────────────────────────────────────────────────────────

type EditPosition = {
  positionscode: string;
  bezeichnung: string;
  betrag_bewilligt: string;
  ueberziehung_limit_pct: string;
  kostenbereich_code: string;
  // Phase J — Verwaltungspauschale
  ist_pauschale: boolean;
  pauschale_typ: "FIXER_BETRAG" | "PROZENT_GESAMT" | "PROZENT_PERSONAL" | "UMLAGE_KOSTENSTELLEN" | null;
  pauschale_prozent: string;
};

// ─── Hauptkomponente ──────────────────────────────────────────────────────────

export function BescheidImportClient({ funders: initialFunders, costCenters }: Props) {
  const { obergruppen: kostenbereichGruppen } = useKostenbereiche();
  const router = useRouter();
  const toast = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);

  type Phase = "upload" | "processing" | "review" | "wizard";
  const [phase, setPhase] = useState<Phase>("upload");
  const [dragging, setDragging] = useState(false);

  // Processing-Fortschrittstext
  const processingTexts = [
    "Dokument wird gelesen…",
    "Förderregeln werden extrahiert…",
    "Prüfe Kostenpositionen…",
  ];
  const [processingTextIdx, setProcessingTextIdx] = useState(0);

  // OCR-Ergebnis für Confidence-Anzeige
  const [extraktion, setExtraktion] = useState<BescheidExtraktion | null>(null);

  // Hochgeladenes PDF im Speicher halten, damit es nach Anlage der Maßnahme
  // an den Bescheid-Endpoint persistiert werden kann (BescheidDokument).
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);

  // Funder-State (kann inline erweitert werden)
  const [funders, setFunders] = useState<FunderOption[]>(initialFunders);
  const [showNewFunderForm, setShowNewFunderForm] = useState(false);

  // Review-Felder
  const [reviewName, setReviewName] = useState("");
  const [reviewFunderId, setReviewFunderId] = useState("");
  const [reviewFunderName, setReviewFunderName] = useState("");
  const [reviewBudget, setReviewBudget] = useState("");
  const [reviewFoerderquote, setReviewFoerderquote] = useState("");
  const [reviewFinanzierungsart, setReviewFinanzierungsart] = useState("");
  const [reviewEigenmittel, setReviewEigenmittel] = useState("");
  const [reviewDrittmittel, setReviewDrittmittel] = useState("");
  const [reviewZuwendungsbetrag, setReviewZuwendungsbetrag] = useState("");
  const [reviewLaufzeitVon, setReviewLaufzeitVon] = useState("");
  const [reviewLaufzeitBis, setReviewLaufzeitBis] = useState("");
  const [reviewMittelabruf, setReviewMittelabruf] = useState("");
  const [reviewVerwaltungspauschale, setReviewVerwaltungspauschale] = useState(false);
  const [reviewVerwaltungspauschaleP, setReviewVerwaltungspauschaleP] = useState("");
  const [reviewBudgetFlex, setReviewBudgetFlex] = useState("");
  const [reviewMwstFoerderfahig, setReviewMwstFoerderfahig] = useState(true);
  const [reviewPositionen, setReviewPositionen] = useState<EditPosition[]>([]);
  const [reviewRegeln, setReviewRegeln] = useState<RegelInput[]>([]);

  // ── Processing-Timer ──────────────────────────────────────────────────────
  useEffect(() => {
    if (phase !== "processing") return;
    const t1 = setTimeout(() => setProcessingTextIdx(1), 2000);
    const t2 = setTimeout(() => setProcessingTextIdx(2), 5000);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [phase]);

  // ── Extraktion → Review-State ─────────────────────────────────────────────
  const populateReview = useCallback(
    (data: BescheidExtraktion, funderList: FunderOption[]) => {
      setExtraktion(data);
      setReviewName(data.name ?? "");
      setReviewFunderName(data.funder_name ?? "");

      // Funder-Matching: case-insensitive Substring
      const needle = (data.funder_name ?? "").toLowerCase();
      const match = needle
        ? funderList.find(
            (f) =>
              f.name.toLowerCase().includes(needle) ||
              needle.includes(f.name.toLowerCase())
          )
        : undefined;
      setReviewFunderId(match?.id ?? "");

      setReviewBudget(data.budget_gesamt != null ? String(data.budget_gesamt) : "");
      setReviewFoerderquote(data.foerderquote != null ? String(data.foerderquote) : "");
      setReviewFinanzierungsart(data.finanzierungsart ?? "");
      setReviewEigenmittel(data.eigenmittel != null ? String(data.eigenmittel) : "");
      setReviewDrittmittel(data.drittmittel != null ? String(data.drittmittel) : "");
      setReviewZuwendungsbetrag(
        data.zuwendungsbetrag != null ? String(data.zuwendungsbetrag) : ""
      );
      setReviewLaufzeitVon(data.laufzeit_von ?? "");
      setReviewLaufzeitBis(data.laufzeit_bis ?? "");
      setReviewMittelabruf(data.mittelabruf_verfahren ?? "");
      setReviewVerwaltungspauschale(data.verwaltungspauschale_erlaubt ?? false);
      setReviewVerwaltungspauschaleP(
        data.verwaltungspauschale_prozent != null ? String(data.verwaltungspauschale_prozent) : ""
      );
      setReviewBudgetFlex(
        data.budget_flexibilitaet_prozent != null ? String(data.budget_flexibilitaet_prozent) : ""
      );
      setReviewMwstFoerderfahig(!data.mwst_nicht_foerderfahig);
      setReviewPositionen(
        data.finanzplan_positionen.map((p) => ({
          positionscode: p.positionscode,
          bezeichnung: p.bezeichnung,
          betrag_bewilligt: String(p.betrag_bewilligt),
          ueberziehung_limit_pct:
            p.ueberziehung_limit_pct != null ? String(p.ueberziehung_limit_pct) : "",
          kostenbereich_code: p.kostenbereich_code ?? "",
          // Phase J — OCR-Heuristik liefert direkt ist_pauschale + typ + prozent
          ist_pauschale: p.ist_pauschale === true,
          pauschale_typ: p.pauschale_typ ?? null,
          pauschale_prozent: p.pauschale_prozent != null ? String(p.pauschale_prozent) : "",
        }))
      );
      // Regeln aus OCR → RegelInput (wert als String erzwingen — Mistral gibt manchmal Zahlen zurück)
      setReviewRegeln(
        data.rules.map((r) => ({
          typ: r.typ,
          schluessel: r.schluessel,
          wert: r.wert != null ? String(r.wert) : "",
          beschreibung: r.beschreibung ?? "",
        }))
      );
    },
    []
  );

  // ── Upload & Verarbeitung ─────────────────────────────────────────────────
  const handleFile = useCallback(
    async (file: File) => {
      if (file.type !== "application/pdf") {
        toast.error("Nur PDF-Dateien werden unterstützt.");
        return;
      }
      if (file.size > 10 * 1024 * 1024) {
        toast.error("Datei ist zu groß (max. 10 MB).");
        return;
      }

      setProcessingTextIdx(0);
      setPhase("processing");

      const formData = new FormData();
      formData.append("file", file);

      // Harter Client-Timeout (380s) — etwas länger als die zwei Server-Timeouts
      // à 180s, damit der Server bei Mistral-Hang erst selbst 504 liefert (mit
      // sprechendem JSON-Body) bevor der Browser abbricht. Mehrseitige Bescheide
      // (HsdV-SLO hat 11 Seiten) brauchen Mistral mehrere Minuten — kürzere
      // Timeouts haben in 130s abgebrochen während das Backend noch lief.
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 380_000);

      try {
        const res = await fetch("/api/protected/foerdermassnahmen/import-bescheid", {
          method: "POST",
          body: formData,
          signal: controller.signal,
        });

        // Defensive: erst Text lesen, dann JSON parsen — damit ein leerer Body
        // (Server-Crash/Timeout/Reload) eine sprechende Fehlermeldung gibt
        // statt eines maskierten "Netzwerkfehler".
        const text = await res.text();
        let json: { data?: BescheidExtraktion; error?: string; code?: string } = {};
        if (text) {
          try {
            json = JSON.parse(text) as typeof json;
          } catch {
            // Kein gültiges JSON (z.B. HTML-Login-Redirect, Server-Crash-HTML)
            json = {};
          }
        }

        if (!res.ok) {
          const msg =
            json.code === "OCR_TIMEOUT"
              ? "Die OCR-Verarbeitung hat zu lange gedauert. Bitte erneut versuchen."
              : json.code === "EXTRACTION_FAILED"
              ? "Mistral konnte den Bescheid nicht verarbeiten. Bitte in einer Minute erneut versuchen."
              : (json.error ?? `Server antwortete mit Status ${res.status}.`);
          toast.error(msg);
          setPhase("upload");
          return;
        }

        if (!json.data) {
          toast.error(
            text
              ? "Unerwartete Server-Antwort beim OCR-Import."
              : "Leere Antwort vom Server — der OCR-Lauf wurde vermutlich abgebrochen."
          );
          setPhase("upload");
          return;
        }

        populateReview(json.data, funders);
        setUploadedFile(file);
        setPhase("review");
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          toast.error(
            "Die Verarbeitung hat zu lange gedauert (>380 s). Bitte mit kleinerer PDF erneut versuchen oder später wiederholen."
          );
        } else {
          const detail =
            err instanceof Error && err.message ? `: ${err.message}` : "";
          toast.error(`Netzwerkfehler beim OCR-Import${detail}`);
        }
        setPhase("upload");
      } finally {
        clearTimeout(timeout);
      }
    },
    [toast, populateReview, funders]
  );

  // ── Drag & Drop ───────────────────────────────────────────────────────────
  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  // ── Funder inline anlegen ─────────────────────────────────────────────────
  const handleFunderCreated = (funder: { id: string; name: string; typ: FunderTyp }) => {
    setFunders((prev) => [...prev, funder].sort((a, b) => a.name.localeCompare(b.name)));
    setReviewFunderId(funder.id);
    setShowNewFunderForm(false);
  };

  // ── Weiter zum Wizard ─────────────────────────────────────────────────────
  const handleWeiterZumWizard = () => {
    if (!reviewFunderId) {
      toast.error("Bitte einen Fördergeber auswählen oder anlegen.");
      return;
    }
    setPhase("wizard");
  };

  // ── Nach Wizard-Submit: Bescheid-PDF anheften, dann redirect ─────────────
  // Positionen werden vom Wizard selbst via syncPositionen() persistiert
  // (initialData.positionen → step4Positionen → POST im Diff-Pfad).
  const handleWizardSuccess = useCallback(
    async (measureId: string) => {
      // Bescheid-PDF an die neu angelegte Maßnahme heften (best-effort).
      // Schlägt das fehl, ist die Maßnahme trotzdem angelegt — User kann
      // im Tab "Zuwendungsbescheid" nachträglich hochladen.
      if (uploadedFile) {
        try {
          const fd = new FormData();
          fd.append("file", uploadedFile);
          fd.append("quelle", "OCR_IMPORT");
          const res = await fetch(
            `/api/protected/foerdermassnahmen/${measureId}/bescheid`,
            { method: "POST", body: fd }
          );
          if (!res.ok) {
            toast.error(
              "Bescheid-PDF konnte nicht gespeichert werden — bitte im Tab „Zuwendungsbescheid“ nachträglich hochladen."
            );
          }
        } catch {
          toast.error(
            "Bescheid-PDF konnte nicht gespeichert werden — bitte im Tab „Zuwendungsbescheid“ nachträglich hochladen."
          );
        }
      }

      router.push(`/dashboard/foerdermassnahmen/${measureId}?tab=bescheid`);
    },
    [router, toast, uploadedFile]
  );

  // ── Wizard initialData ────────────────────────────────────────────────────
  // Phase B.4 wird OCR-Extraktion um durchfuehrungs_*/antragsnummer erweitern.
  // Aktuell: leer übergeben, User füllt im Wizard manuell falls nötig.
  const wizardInitialData = {
    id: "",
    funder_id: reviewFunderId,
    name: reviewName,
    antragsnummer: null,
    budget_gesamt: reviewBudget,
    laufzeit_von: reviewLaufzeitVon,
    laufzeit_bis: reviewLaufzeitBis,
    durchfuehrungs_von: null,
    durchfuehrungs_bis: null,
    status: "AKTIV" as const,
    // Ticket 01 — Finanzierungsart + Fehlbedarf-Felder
    finanzierungsart: (reviewFinanzierungsart as "ANTEIL" | "FEHLBEDARF" | "FESTBETRAG") || null,
    eigenmittel_betrag: reviewEigenmittel || null,
    drittmittel_betrag: reviewDrittmittel || null,
    foerderquote: reviewFoerderquote || "80",
    verwaltungspauschale_erlaubt: reviewVerwaltungspauschale,
    verwaltungspauschale_prozent: reviewVerwaltungspauschaleP || null,
    budget_flexibilitaet_prozent: reviewBudgetFlex || "20",
    overhead_limit_prozent: null,
    mwst_foerderfahig: reviewMwstFoerderfahig,
    mwst_satz_prozent: "19",
    mittelabruf_verfahren: (reviewMittelabruf as MittelabrufVerfahren) || "ANFORDERUNG",
    cost_center_ids: [],
    rules: reviewRegeln.map((r) => ({
      typ: r.typ,
      schluessel: r.schluessel,
      wert: r.wert || null,
      beschreibung: r.beschreibung || null,
    })),
    positionen: reviewPositionen.map((p) => ({
      // id bewusst weggelassen — Draft-Positionen aus OCR sind noch nicht
      // persistiert. Leerer String triggert im Wizard-Sync sonst einen
      // DELETE auf die ID-lose Collection-URL → 405.
      positionscode: p.positionscode,
      bezeichnung: p.bezeichnung,
      betrag_bewilligt: p.betrag_bewilligt,
      ueberziehung_limit_pct: p.ueberziehung_limit_pct,
      kostenbereich_codes: p.kostenbereich_code ? [p.kostenbereich_code] : [],
      allocation_count: 0,
      ist_pauschale: p.ist_pauschale,
      pauschale_typ: p.pauschale_typ,
      pauschale_prozent: p.pauschale_prozent,
    })),
  };

  const confidence = extraktion?.confidence;

  // ─── Render ───────────────────────────────────────────────────────────────

  // Phase: Wizard
  if (phase === "wizard") {
    return (
      <div>
        <div className="mb-6 rounded-soft-sm border border-soft-accent/20 bg-soft-accentSoft px-4 py-3 text-sm text-soft-accent">
          Felder aus dem Bescheid sind vorausgefüllt. Bitte prüfen und ggf. anpassen.
        </div>
        <FoerdermassnahmeWizard
          funders={funders}
          costCenters={costCenters}
          mode="create"
          initialData={wizardInitialData}
          onSuccess={handleWizardSuccess}
        />
      </div>
    );
  }

  // Phase: Upload
  if (phase === "upload") {
    return (
      <div
        className={`rounded-soft border-2 border-dashed transition-colors flex flex-col items-center justify-center gap-4 p-16 text-center cursor-pointer
          ${dragging ? "border-soft-accent bg-soft-accentSoft" : "border-soft-line hover:border-soft-ink4 hover:bg-soft-line2"}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <div className="rounded-full bg-soft-surfaceAlt p-4">
          <svg className="h-8 w-8 text-soft-ink4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
          </svg>
        </div>
        <div>
          <p className="text-base font-medium text-soft-ink2">PDF-Bescheid hierher ziehen oder klicken</p>
          <p className="text-sm text-soft-ink4 mt-1">Nur PDF-Dateien, max. 10 MB</p>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,application/pdf"
          className="sr-only"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
            e.target.value = "";
          }}
        />
      </div>
    );
  }

  // Phase: Processing
  if (phase === "processing") {
    return (
      <div className="flex flex-col items-center justify-center gap-6 py-24">
        <div className="h-10 w-10 rounded-full border-4 border-soft-accent/30 border-t-blue-600 animate-spin" />
        <p className="text-base text-soft-ink2 font-medium">{processingTexts[processingTextIdx]}</p>
      </div>
    );
  }

  // Phase: Review
  return (
    <div className="space-y-8">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

        {/* Linke Spalte — editierbare Felder */}
        <div className="lg:col-span-2 space-y-5">
          <h2 className="text-base font-semibold text-soft-ink">Extrahierte Felder prüfen</h2>

          {/* Bezeichnung */}
          <div>
            <label className="block text-sm font-medium text-soft-ink2 mb-1">
              Bezeichnung der Maßnahme
              {confidence !== "HIGH" && reviewName && <WarningLabel />}
            </label>
            <input
              type="text"
              value={reviewName}
              onChange={(e) => setReviewName(e.target.value)}
              placeholder="Nicht gefunden — bitte ergänzen"
              className={fieldCls(!reviewName, confidence)}
            />
          </div>

          {/* Fördergeber */}
          <div>
            <label className="block text-sm font-medium text-soft-ink2 mb-1">
              Fördergeber <span className="text-soft-crit">*</span>
            </label>

            {!showNewFunderForm ? (
              <>
                <div className="flex gap-2">
                  <select
                    value={reviewFunderId}
                    onChange={(e) => setReviewFunderId(e.target.value)}
                    className="flex-1 rounded-soft-xs border border-soft-line bg-white px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-soft-accent"
                  >
                    <option value="">— Fördergeber wählen —</option>
                    {funders.map((f) => (
                      <option key={f.id} value={f.id}>{f.name}</option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() => setShowNewFunderForm(true)}
                    className="shrink-0 rounded-soft-xs border border-soft-line bg-white px-3 py-2 text-sm text-soft-ink2 hover:bg-soft-line2 transition-colors whitespace-nowrap"
                  >
                    + Neu anlegen
                  </button>
                </div>
                {reviewFunderName && !reviewFunderId && (
                  <p className="mt-1 text-xs text-soft-warn">
                    Aus Bescheid erkannt: <strong>{reviewFunderName}</strong> — bitte oben zuordnen oder neu anlegen.
                  </p>
                )}
                {!reviewFunderName && (
                  <p className="mt-1 text-xs text-soft-ink4">
                    Kein Fördergeber im Bescheid erkannt — bitte manuell wählen.
                  </p>
                )}
              </>
            ) : (
              <div className="rounded-soft-sm border border-soft-line bg-soft-line2 p-4">
                <p className="text-xs font-semibold text-soft-ink2 mb-3">
                  Neuen Fördergeber anlegen
                  {reviewFunderName && (
                    <span className="ml-1 font-normal text-soft-ink4">
                      (aus Bescheid: {reviewFunderName})
                    </span>
                  )}
                </p>
                <FunderForm
                  inline
                  defaultName={reviewFunderName}
                  onSuccess={handleFunderCreated}
                  onCancel={() => setShowNewFunderForm(false)}
                />
              </div>
            )}
          </div>

          {/* Budget + Förderquote */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-soft-ink2 mb-1">
                Zuwendungsfähige Gesamtausgaben (EUR)
                {confidence !== "HIGH" && reviewBudget && <WarningLabel />}
              </label>
              <input
                type="number"
                value={reviewBudget}
                onChange={(e) => setReviewBudget(e.target.value)}
                placeholder="Nicht gefunden"
                className={fieldCls(!reviewBudget, confidence)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-soft-ink2 mb-1">
                Förderquote (%)
                {confidence !== "HIGH" && reviewFoerderquote && <WarningLabel />}
              </label>
              <input
                type="number"
                min={0}
                max={100}
                value={reviewFoerderquote}
                onChange={(e) => setReviewFoerderquote(e.target.value)}
                placeholder="Nicht gefunden"
                className={fieldCls(!reviewFoerderquote, confidence)}
              />
            </div>
          </div>

          {/* Finanzierungsart */}
          <div>
            <label className="block text-sm font-medium text-soft-ink2 mb-1">Finanzierungsart</label>
            <select
              value={reviewFinanzierungsart}
              onChange={(e) => setReviewFinanzierungsart(e.target.value)}
              className={`w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-soft-accent ${
                !reviewFinanzierungsart ? "bg-soft-line2 border-soft-line text-soft-ink4" : "bg-white border-soft-line"
              }`}
            >
              <option value="">— Nicht erkannt —</option>
              <option value="ANTEIL">Anteilsfinanzierung</option>
              <option value="FEHLBEDARF">Fehlbedarfsfinanzierung</option>
              <option value="FESTBETRAG">Festbetragsfinanzierung</option>
            </select>
          </div>

          {/* Fehlbedarf-spezifische Felder (Eigenmittel / Drittmittel / Höchstbetrag) */}
          {reviewFinanzierungsart === "FEHLBEDARF" && (
            <div className="rounded-soft-sm border border-soft-line bg-soft-surfaceAlt p-4 space-y-3">
              <p className="text-xs text-soft-ink3">
                Fehlbedarfsfinanzierung: aus dem Finanzierungsplan-Anhang extrahiert. Bitte prüfen.
              </p>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-soft-ink2 mb-1">
                    Eigenmittel (EUR)
                    {confidence !== "HIGH" && reviewEigenmittel && <WarningLabel />}
                  </label>
                  <input
                    type="number"
                    value={reviewEigenmittel}
                    onChange={(e) => setReviewEigenmittel(e.target.value)}
                    placeholder="Nicht gefunden"
                    className={fieldCls(!reviewEigenmittel, confidence)}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-soft-ink2 mb-1">
                    Drittmittel (EUR)
                  </label>
                  <input
                    type="number"
                    value={reviewDrittmittel}
                    onChange={(e) => setReviewDrittmittel(e.target.value)}
                    placeholder="0"
                    className={fieldCls(false, confidence)}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-soft-ink2 mb-1">
                    Höchstbetrag (EUR)
                    {confidence !== "HIGH" && reviewZuwendungsbetrag && <WarningLabel />}
                  </label>
                  <input
                    type="number"
                    value={reviewZuwendungsbetrag}
                    onChange={(e) => setReviewZuwendungsbetrag(e.target.value)}
                    placeholder="Nicht gefunden"
                    className={fieldCls(!reviewZuwendungsbetrag, confidence)}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Laufzeit */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-soft-ink2 mb-1">
                Laufzeit von
                {confidence !== "HIGH" && reviewLaufzeitVon && <WarningLabel />}
              </label>
              <input
                type="date"
                value={reviewLaufzeitVon}
                onChange={(e) => setReviewLaufzeitVon(e.target.value)}
                className={fieldCls(!reviewLaufzeitVon, confidence)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-soft-ink2 mb-1">
                Laufzeit bis
                {confidence !== "HIGH" && reviewLaufzeitBis && <WarningLabel />}
              </label>
              <input
                type="date"
                value={reviewLaufzeitBis}
                onChange={(e) => setReviewLaufzeitBis(e.target.value)}
                className={fieldCls(!reviewLaufzeitBis, confidence)}
              />
            </div>
          </div>

          {/* Mittelabruf */}
          <div>
            <label className="block text-sm font-medium text-soft-ink2 mb-1">Mittelabruf-Verfahren</label>
            <select
              value={reviewMittelabruf}
              onChange={(e) => setReviewMittelabruf(e.target.value)}
              className={`w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-soft-accent ${
                !reviewMittelabruf ? "bg-soft-line2 border-soft-line text-soft-ink4" : "bg-white border-soft-line"
              }`}
            >
              <option value="">— Nicht erkannt —</option>
              <option value="ANFORDERUNG">Anforderungsverfahren</option>
              <option value="ABRUF">Abrufverfahren</option>
              <option value="ABSCHLAG">Abschlagszahlungen</option>
            </select>
          </div>

          {/* Verwaltungspauschale + Budget-Flex */}
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-soft-sm border border-soft-line p-3 space-y-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <div
                  className={`relative inline-flex h-5 w-9 rounded-full transition-colors ${reviewVerwaltungspauschale ? "bg-soft-accent" : "bg-soft-line"}`}
                  onClick={() => setReviewVerwaltungspauschale((v) => !v)}
                >
                  <span className={`absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${reviewVerwaltungspauschale ? "translate-x-4" : ""}`} />
                </div>
                <span className="text-sm font-medium text-soft-ink2">Verwaltungspauschale</span>
              </label>
              {reviewVerwaltungspauschale && (
                <div className="relative w-full">
                  <input
                    type="number"
                    value={reviewVerwaltungspauschaleP}
                    onChange={(e) => setReviewVerwaltungspauschaleP(e.target.value)}
                    placeholder="z.B. 15"
                    className="w-full rounded-soft-xs border border-soft-line px-2.5 py-1.5 text-sm pr-8 outline-none focus:ring-2 focus:ring-soft-accent"
                  />
                  <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-soft-ink4">%</span>
                </div>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-soft-ink2 mb-1">Budget-Flexibilität (%)</label>
              <input
                type="number"
                value={reviewBudgetFlex}
                onChange={(e) => setReviewBudgetFlex(e.target.value)}
                placeholder="Standard: 20"
                className={fieldCls(!reviewBudgetFlex, confidence)}
              />
            </div>
          </div>

          {/* MwSt */}
          <label className="flex items-center gap-3 cursor-pointer rounded-soft-sm border border-soft-line p-3">
            <div
              className={`relative inline-flex h-5 w-9 rounded-full transition-colors ${reviewMwstFoerderfahig ? "bg-soft-accent" : "bg-soft-line"}`}
              onClick={() => setReviewMwstFoerderfahig((v) => !v)}
            >
              <span className={`absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${reviewMwstFoerderfahig ? "translate-x-4" : ""}`} />
            </div>
            <div>
              <span className="text-sm font-medium text-soft-ink2">MwSt ist förderfähig</span>
              <p className="text-xs text-soft-ink3">Für Vereine und gGmbH ohne Vorsteuerabzugsberechtigung typischerweise aktiviert</p>
            </div>
          </label>
        </div>

        {/* Rechte Spalte — Qualitätskontrolle */}
        <div className="space-y-4">
          <h2 className="text-base font-semibold text-soft-ink">Qualitätskontrolle</h2>

          <div className="rounded-soft-sm border border-soft-line p-4 space-y-4">
            <div>
              <p className="text-xs font-medium text-soft-ink3 uppercase tracking-wide mb-1">Erkennungs-Confidence</p>
              {extraktion && <ConfidenceBadge confidence={extraktion.confidence} />}
            </div>

            {extraktion && extraktion.raw_hinweise.length > 0 && (
              <div>
                <p className="text-xs font-medium text-soft-ink3 uppercase tracking-wide mb-2">Hinweise zur manuellen Prüfung</p>
                <ul className="space-y-1.5">
                  {extraktion.raw_hinweise.map((h, i) => (
                    <li key={i} className="text-xs text-soft-warn bg-soft-warnSoft rounded px-2 py-1.5 border border-soft-warn/30">
                      {h}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {confidence !== "HIGH" && (
              <p className="text-xs text-soft-warn bg-soft-warnSoft rounded p-2 border border-soft-warn/30">
                Gelb markierte Felder wurden mit mittlerer oder niedriger Sicherheit erkannt — bitte besonders prüfen.
              </p>
            )}

            <p className="text-xs text-soft-ink4">
              Kein Datenbankschreiben bis zum Speichern im Wizard-Schritt.
            </p>
          </div>
        </div>
      </div>

      {/* Finanzplan-Positionen */}
      <div>
        <h2 className="text-base font-semibold text-soft-ink mb-3">
          Finanzplan-Positionen
          <span className="ml-2 text-xs font-normal text-soft-ink4">({reviewPositionen.length} erkannt)</span>
        </h2>
        <div className="rounded-soft-sm border border-soft-line overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-soft-line2 border-b border-soft-line">
              <tr>
                <th className="px-3 py-2.5 text-left text-xs font-medium text-soft-ink3 w-20">Pos.</th>
                <th className="px-3 py-2.5 text-left text-xs font-medium text-soft-ink3">Bezeichnung</th>
                <th className="px-3 py-2.5 text-left text-xs font-medium text-soft-ink3 w-32">Betrag (EUR)</th>
                <th className="px-3 py-2.5 text-left text-xs font-medium text-soft-ink3 w-44">Kostenbereich</th>
                <th className="px-3 py-2.5 text-left text-xs font-medium text-soft-ink3 w-24">Überz. %</th>
                <th
                  className="px-3 py-2.5 text-left text-xs font-medium text-soft-ink3 w-48"
                  title="Pauschale-Position: Ist wird nicht aus Buchungen summiert, sondern direkt aus dem Bescheid-Betrag (FIXER_BETRAG) oder einem Prozentsatz berechnet."
                >
                  Pauschale
                </th>
                <th className="px-2 py-2.5 w-8" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {reviewPositionen.map((pos, idx) => (
                <tr key={idx} className="hover:bg-soft-line2">
                  <td className="px-3 py-2">
                    <input
                      type="text"
                      value={pos.positionscode}
                      onChange={(e) =>
                        setReviewPositionen((prev) =>
                          prev.map((p, i) => i === idx ? { ...p, positionscode: e.target.value } : p)
                        )
                      }
                      className="w-full rounded border border-soft-line px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-soft-accent"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="text"
                      value={pos.bezeichnung}
                      onChange={(e) =>
                        setReviewPositionen((prev) =>
                          prev.map((p, i) => i === idx ? { ...p, bezeichnung: e.target.value } : p)
                        )
                      }
                      className="w-full rounded border border-soft-line px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-soft-accent"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      value={pos.betrag_bewilligt}
                      onChange={(e) =>
                        setReviewPositionen((prev) =>
                          prev.map((p, i) => i === idx ? { ...p, betrag_bewilligt: e.target.value } : p)
                        )
                      }
                      className="w-full rounded border border-soft-line px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-soft-accent"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <select
                      value={pos.kostenbereich_code}
                      onChange={(e) =>
                        setReviewPositionen((prev) =>
                          prev.map((p, i) => i === idx ? { ...p, kostenbereich_code: e.target.value } : p)
                        )
                      }
                      className="w-full rounded border border-soft-line bg-white px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-soft-accent"
                    >
                      <option value="">— wählen —</option>
                      {kostenbereichGruppen.map((gruppe) => (
                        <optgroup key={gruppe.id} label={gruppe.bezeichnung}>
                          {gruppe.kinder.map((item) => (
                            <option key={item.code} value={item.code}>{item.bezeichnung}</option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      value={pos.ueberziehung_limit_pct}
                      onChange={(e) =>
                        setReviewPositionen((prev) =>
                          prev.map((p, i) => i === idx ? { ...p, ueberziehung_limit_pct: e.target.value } : p)
                        )
                      }
                      placeholder="20"
                      className="w-full rounded border border-soft-line px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-soft-accent"
                    />
                  </td>
                  {/* Phase J — Pauschale-Spalte */}
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1.5">
                      <label
                        className="flex items-center gap-1 cursor-pointer shrink-0"
                        title="Pauschale-Position (Ist = Bescheid-Betrag oder %-berechnet)"
                      >
                        <input
                          type="checkbox"
                          checked={pos.ist_pauschale}
                          onChange={(e) =>
                            setReviewPositionen((prev) =>
                              prev.map((p, i) =>
                                i === idx
                                  ? {
                                      ...p,
                                      ist_pauschale: e.target.checked,
                                      pauschale_typ: e.target.checked
                                        ? p.pauschale_typ ?? "FIXER_BETRAG"
                                        : null,
                                    }
                                  : p
                              )
                            )
                          }
                          className="h-3.5 w-3.5 rounded accent-soft-accent"
                        />
                      </label>
                      {pos.ist_pauschale && (
                        <>
                          <select
                            value={pos.pauschale_typ ?? "FIXER_BETRAG"}
                            onChange={(e) =>
                              setReviewPositionen((prev) =>
                                prev.map((p, i) =>
                                  i === idx
                                    ? {
                                        ...p,
                                        pauschale_typ: e.target.value as EditPosition["pauschale_typ"],
                                        pauschale_prozent:
                                          e.target.value === "FIXER_BETRAG" ? "" : p.pauschale_prozent,
                                      }
                                    : p
                                )
                              )
                            }
                            className="flex-1 rounded border border-soft-line bg-white px-1 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-soft-accent"
                            title="Berechnungsmodus"
                          >
                            <option value="FIXER_BETRAG">Fix €</option>
                            <option value="PROZENT_PERSONAL">% Personal</option>
                            <option value="PROZENT_GESAMT">% Gesamt</option>
                          </select>
                          {pos.pauschale_typ !== "FIXER_BETRAG" && (
                            <input
                              type="number"
                              min={0}
                              max={100}
                              value={pos.pauschale_prozent}
                              onChange={(e) =>
                                setReviewPositionen((prev) =>
                                  prev.map((p, i) =>
                                    i === idx ? { ...p, pauschale_prozent: e.target.value } : p
                                  )
                                )
                              }
                              placeholder="%"
                              className="numeric w-12 rounded border border-soft-line px-1 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-soft-accent"
                              title="Prozentsatz"
                            />
                          )}
                        </>
                      )}
                    </div>
                  </td>
                  <td className="px-2 py-2">
                    <button
                      type="button"
                      onClick={() => setReviewPositionen((prev) => prev.filter((_, i) => i !== idx))}
                      className="rounded p-1 text-soft-ink4 hover:text-soft-crit hover:bg-soft-critSoft transition-colors"
                      aria-label="Position entfernen"
                    >
                      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </td>
                </tr>
              ))}
              {reviewPositionen.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-3 py-4 text-center text-xs text-soft-ink4 italic">
                    Keine Positionen erkannt
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <button
          type="button"
          onClick={() =>
            setReviewPositionen((prev) => [
              ...prev,
              {
                positionscode: String(prev.length + 1),
                bezeichnung: "",
                betrag_bewilligt: "",
                ueberziehung_limit_pct: "",
                kostenbereich_code: "",
                ist_pauschale: false,
                pauschale_typ: null,
                pauschale_prozent: "",
              },
            ])
          }
          className="mt-2 text-xs text-soft-accent hover:text-soft-accent hover:underline"
        >
          + Position hinzufügen
        </button>
      </div>

      {/* Förderregeln */}
      <div>
        <h2 className="text-base font-semibold text-soft-ink mb-3">
          Förderregeln
          <span className="ml-2 text-xs font-normal text-soft-ink4">({reviewRegeln.length} erkannt)</span>
        </h2>
        <FoerderregelEditor regeln={reviewRegeln} onChange={setReviewRegeln} />
      </div>

      {/* Aktionen */}
      <div className="flex items-center justify-between border-t border-soft-line2 pt-6">
        <Button type="button" variant="secondary" onClick={() => setPhase("upload")}>
          ← Anderes PDF laden
        </Button>
        <Button type="button" variant="primary" onClick={handleWeiterZumWizard}>
          Weiter zum Wizard →
        </Button>
      </div>
    </div>
  );
}
