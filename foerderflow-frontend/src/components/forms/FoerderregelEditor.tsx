"use client";

import { useState } from "react";
import { useKostenbereiche } from "@/lib/hooks/useKostenbereiche";
import type { FundingRuleTyp } from "@/types/foerdermassnahmen";

// ─── Datentyp ─────────────────────────────────────────────────────────────────

export type RegelInput = {
  typ: FundingRuleTyp;
  schluessel: string;
  wert: string;
  beschreibung: string;
};

// ─── Kategorisierung ──────────────────────────────────────────────────────────

const FOERDER_TYPEN: FundingRuleTyp[] = [
  "KOSTENKATEGORIE_ERLAUBT",
  "KOSTENKATEGORIE_VERBOTEN",
  "EIGENANTEIL_MIN",
  "PERSONALKOSTEN_HOECHSTSATZ",
];

const NACHWEIS_TYPEN: FundingRuleTyp[] = [
  "BELEGPFLICHT_SPEZIAL",
  "VERWENDUNGSFRIST_TAGE",
  "ZWISCHENNACHWEIS_PFLICHT",
];

// ─── Qualifikationsstufen für PERSONALKOSTEN_HOECHSTSATZ ─────────────────────

const QUALIFIKATIONSSTUFEN = [
  { value: "AKADEMIKER",   label: "Akademiker/in (Hochschulabschluss)" },
  { value: "TECHNIKER",    label: "Techniker/in (Fachausbildung)" },
  { value: "FACHARBEITER", label: "Facharbeiter/in (Ausbildungsabschluss)" },
  { value: "SONSTIGE",     label: "Sonstige (Freitext)" },
];

// ─── Regeltyp-Metadaten ───────────────────────────────────────────────────────

type SchluesselTyp = "kostenbereich" | "freitext" | "fixed" | "qualifikation";
type WertTyp = "number-eur" | "number-pct" | "number-tage" | null;

type RegelMeta = {
  label: string;
  schluesselLabel: string;
  schluesselTyp: SchluesselTyp;
  schluesselFixed?: string;
  wertLabel: string | null;
  wertTyp: WertTyp;
  beschreibungLabel: string;
  hinweis?: string;
};

const REGEL_META: Record<FundingRuleTyp, RegelMeta> = {
  KOSTENKATEGORIE_ERLAUBT: {
    label: "Kostenbereich erlaubt",
    schluesselLabel: "Kostenbereich",
    schluesselTyp: "kostenbereich",
    wertLabel: null,
    wertTyp: null,
    beschreibungLabel: "Hinweis (optional)",
    hinweis: "Welche Kostenbereiche sind laut Bescheid explizit förderfähig?",
  },
  KOSTENKATEGORIE_VERBOTEN: {
    label: "Kostenbereich verboten",
    schluesselLabel: "Kostenbereich",
    schluesselTyp: "kostenbereich",
    wertLabel: null,
    wertTyp: null,
    beschreibungLabel: "Hinweis (optional)",
    hinweis: "Welche Kostenbereiche sind laut Bescheid nicht förderfähig?",
  },
  EIGENANTEIL_MIN: {
    label: "Mindest-Eigenanteil",
    schluesselLabel: "Bezeichnung",
    schluesselTyp: "fixed",
    schluesselFixed: "Eigenanteil",
    wertLabel: "Mindestprozentsatz",
    wertTyp: "number-pct",
    beschreibungLabel: "Hinweis (optional)",
    hinweis: "Prozentualer Mindestanteil der Organisation an den Gesamtkosten.",
  },
  PERSONALKOSTEN_HOECHSTSATZ: {
    label: "Personalkosten-Höchstsatz",
    schluesselLabel: "Qualifikationsstufe",
    schluesselTyp: "qualifikation",
    wertLabel: "Höchstbetrag pro VZÄ-Monat",
    wertTyp: "number-eur",
    beschreibungLabel: "Hinweis (z. B. Tarifgruppe, Stundensatz)",
    hinweis: "Mehrere Stufen als separate Regeln anlegen. z. B. Akademiker/in → 4.500 EUR/Monat.",
  },
  BELEGPFLICHT_SPEZIAL: {
    label: "Besondere Belegpflicht",
    schluesselLabel: "Bezeichnung der Pflicht",
    schluesselTyp: "freitext",
    wertLabel: null,
    wertTyp: null,
    beschreibungLabel: "Details (z. B. ab welchem Betrag, welche Belege)",
    hinweis: "z. B. Stundennachweis Pflicht, Originalbelege über 150 EUR",
  },
  VERWENDUNGSFRIST_TAGE: {
    label: "Mittelverwendungsfrist nach Abruf",
    schluesselLabel: "Bezeichnung",
    schluesselTyp: "fixed",
    schluesselFixed: "Verwendungsfrist",
    wertLabel: "Anzahl Tage",
    wertTyp: "number-tage",
    beschreibungLabel: "Hinweis (optional)",
    hinweis: "Tage nach Mittelabruf bis zur Verausgabung (ANBest-P §1.2, Standard: 42 Tage). Keine VN-Einreichungsfristen hier eintragen.",
  },
  ZWISCHENNACHWEIS_PFLICHT: {
    label: "Zwischennachweis Pflicht",
    schluesselLabel: "Bezeichnung",
    schluesselTyp: "fixed",
    schluesselFixed: "Zwischennachweis",
    wertLabel: null,
    wertTyp: null,
    beschreibungLabel: "Hinweis (z. B. Frist, Turnus)",
    hinweis: "Wird im Verwendungsnachweis-Prozess als Pflichtmeilenstein markiert.",
  },
};

export const REGEL_TYP_OPTIONEN = Object.entries(REGEL_META).map(([value, meta]) => ({
  value: value as FundingRuleTyp,
  label: meta.label,
}));

// ─── Leere Regel für einen Typ ────────────────────────────────────────────────

function leereRegelFuer(typ: FundingRuleTyp): RegelInput {
  const meta = REGEL_META[typ];
  return {
    typ,
    schluessel: meta.schluesselFixed ?? "",
    wert: "",
    beschreibung: "",
  };
}

// ─── Einzel-Regel-Formular ────────────────────────────────────────────────────

type RegelFormularProps = {
  regel: RegelInput;
  onUpdate: (next: RegelInput) => void;
  onRemove?: () => void;
  showRemove?: boolean;
  allowedTypen?: FundingRuleTyp[];
};

export function RegelFormular({
  regel,
  onUpdate,
  onRemove,
  showRemove = true,
  allowedTypen,
}: RegelFormularProps) {
  const meta = REGEL_META[regel.typ];
  const { obergruppen: kostenbereichGruppen } = useKostenbereiche();
  const [sonstigeSchluessel, setSonstigeSchluessel] = useState(
    regel.typ === "PERSONALKOSTEN_HOECHSTSATZ" &&
    !QUALIFIKATIONSSTUFEN.slice(0, -1).some((q) => q.value === regel.schluessel)
      ? regel.schluessel
      : ""
  );

  const update = (partial: Partial<RegelInput>) => onUpdate({ ...regel, ...partial });

  const handleTypChange = (newTyp: FundingRuleTyp) => {
    onUpdate(leereRegelFuer(newTyp));
    setSonstigeSchluessel("");
  };

  const wertSuffix =
    meta.wertTyp === "number-eur" ? "EUR"
    : meta.wertTyp === "number-pct" ? "%"
    : meta.wertTyp === "number-tage" ? "Tage"
    : null;

  const typOptionen = allowedTypen
    ? REGEL_TYP_OPTIONEN.filter((o) => allowedTypen.includes(o.value))
    : REGEL_TYP_OPTIONEN;

  // Qualifikationsstufe: erkennen ob aktueller Schlüssel "SONSTIGE" ist
  const istSonstigeQualifikation =
    regel.typ === "PERSONALKOSTEN_HOECHSTSATZ" &&
    !QUALIFIKATIONSSTUFEN.slice(0, -1).some((q) => q.value === regel.schluessel);

  const handleQualifikationChange = (val: string) => {
    if (val === "SONSTIGE") {
      update({ schluessel: sonstigeSchluessel });
    } else {
      setSonstigeSchluessel("");
      update({ schluessel: val });
    }
  };

  const qualifikationsSelectValue = istSonstigeQualifikation ? "SONSTIGE" : regel.schluessel;

  return (
    <div className="rounded-soft-sm border border-soft-line bg-soft-line2 p-4 space-y-3">
      <div className="flex items-start gap-2">
        {/* Regeltyp */}
        <div className="flex-1">
          <label className="block text-xs font-medium text-soft-ink3 mb-1">Regeltyp</label>
          <select
            value={regel.typ}
            onChange={(e) => handleTypChange(e.target.value as FundingRuleTyp)}
            className="w-full rounded-soft-xs border border-soft-line bg-white px-2.5 py-2 text-sm outline-none focus:ring-2 focus:ring-soft-accent focus:border-soft-accent"
          >
            {typOptionen.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          {meta.hinweis && (
            <p className="mt-1 text-xs text-soft-ink4">{meta.hinweis}</p>
          )}
        </div>

        {showRemove && onRemove && (
          <button
            type="button"
            onClick={onRemove}
            className="shrink-0 mt-5 rounded-soft-xs p-1.5 text-soft-ink4 hover:text-soft-crit hover:bg-soft-critSoft transition-colors"
            aria-label="Regel entfernen"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {/* Schlüssel / Kostenbereich / Qualifikationsstufe */}
        <div>
          <label className="block text-xs font-medium text-soft-ink2 mb-1">
            {meta.schluesselLabel}
            {meta.schluesselTyp !== "fixed" && <span className="text-soft-crit ml-0.5">*</span>}
          </label>

          {meta.schluesselTyp === "kostenbereich" ? (
            <select
              value={regel.schluessel}
              onChange={(e) => update({ schluessel: e.target.value })}
              className="w-full rounded-soft-xs border border-soft-line bg-white px-2.5 py-2 text-sm outline-none focus:ring-2 focus:ring-soft-accent focus:border-soft-accent"
            >
              <option value="">— Kostenbereich wählen —</option>
              {kostenbereichGruppen.map((gruppe) => (
                <optgroup key={gruppe.id} label={gruppe.bezeichnung}>
                  {gruppe.kinder.map((item) => (
                    <option key={item.code} value={item.code}>{item.bezeichnung}</option>
                  ))}
                </optgroup>
              ))}
            </select>
          ) : meta.schluesselTyp === "qualifikation" ? (
            <div className="space-y-2">
              <select
                value={qualifikationsSelectValue}
                onChange={(e) => handleQualifikationChange(e.target.value)}
                className="w-full rounded-soft-xs border border-soft-line bg-white px-2.5 py-2 text-sm outline-none focus:ring-2 focus:ring-soft-accent focus:border-soft-accent"
              >
                <option value="">— Stufe wählen —</option>
                {QUALIFIKATIONSSTUFEN.map((q) => (
                  <option key={q.value} value={q.value}>{q.label}</option>
                ))}
              </select>
              {istSonstigeQualifikation && (
                <input
                  type="text"
                  value={sonstigeSchluessel}
                  onChange={(e) => {
                    setSonstigeSchluessel(e.target.value);
                    update({ schluessel: e.target.value });
                  }}
                  placeholder="Bezeichnung eingeben"
                  className="w-full rounded-soft-xs border border-soft-line bg-white px-2.5 py-2 text-sm outline-none focus:ring-2 focus:ring-soft-accent focus:border-soft-accent"
                />
              )}
            </div>
          ) : meta.schluesselTyp === "fixed" ? (
            <input
              type="text"
              value={meta.schluesselFixed ?? ""}
              disabled
              className="w-full rounded-soft-xs border border-soft-line bg-soft-surfaceAlt px-2.5 py-2 text-sm text-soft-ink3 cursor-not-allowed"
            />
          ) : (
            <input
              type="text"
              value={regel.schluessel}
              onChange={(e) => update({ schluessel: e.target.value })}
              placeholder={meta.schluesselLabel}
              className="w-full rounded-soft-xs border border-soft-line bg-white px-2.5 py-2 text-sm outline-none focus:ring-2 focus:ring-soft-accent focus:border-soft-accent"
            />
          )}
        </div>

        {/* Wert */}
        {meta.wertLabel !== null && meta.wertTyp !== null && (
          <div>
            <label className="block text-xs font-medium text-soft-ink2 mb-1">
              {meta.wertLabel}
            </label>
            <div className="relative">
              <input
                type="number"
                min={0}
                value={regel.wert}
                onChange={(e) => update({ wert: e.target.value })}
                placeholder={meta.wertTyp === "number-eur" ? "0.00" : "0"}
                step={meta.wertTyp === "number-eur" ? "0.01" : "1"}
                className="w-full rounded-soft-xs border border-soft-line bg-white px-2.5 py-2 text-sm outline-none focus:ring-2 focus:ring-soft-accent focus:border-soft-accent pr-14"
              />
              {wertSuffix && (
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-soft-ink4 pointer-events-none">
                  {wertSuffix}
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Beschreibung/Hinweis */}
      <div>
        <label className="block text-xs font-medium text-soft-ink2 mb-1">
          {meta.beschreibungLabel}
        </label>
        <input
          type="text"
          value={regel.beschreibung}
          onChange={(e) => update({ beschreibung: e.target.value })}
          placeholder={meta.beschreibungLabel}
          className="w-full rounded-soft-xs border border-soft-line bg-white px-2.5 py-2 text-sm outline-none focus:ring-2 focus:ring-soft-accent focus:border-soft-accent"
        />
      </div>
    </div>
  );
}

// ─── Sektions-Editor ──────────────────────────────────────────────────────────

type SektionsEditorProps = {
  titel: string;
  beschreibung: string;
  regeln: RegelInput[];
  allowedTypen: FundingRuleTyp[];
  defaultTyp: FundingRuleTyp;
  onChange: (regeln: RegelInput[]) => void;
};

function SektionsEditor({
  titel,
  beschreibung,
  regeln,
  allowedTypen,
  defaultTyp,
  onChange,
}: SektionsEditorProps) {
  const [entwurf, setEntwurf] = useState<RegelInput>(leereRegelFuer(defaultTyp));

  const handleUpdate = (index: number, next: RegelInput) =>
    onChange(regeln.map((r, i) => (i === index ? next : r)));

  const handleRemove = (index: number) =>
    onChange(regeln.filter((_, i) => i !== index));

  const handleAdd = () => {
    const meta = REGEL_META[entwurf.typ];
    const finalSchluessel =
      meta.schluesselTyp === "fixed" ? (meta.schluesselFixed ?? "") : entwurf.schluessel;
    if (!finalSchluessel.trim()) return;
    onChange([...regeln, { ...entwurf, schluessel: finalSchluessel }]);
    setEntwurf(leereRegelFuer(defaultTyp));
  };

  return (
    <div className="space-y-3">
      <div>
        <p className="text-xs font-semibold text-soft-ink2 uppercase tracking-wide">{titel}</p>
        <p className="text-xs text-soft-ink4 mt-0.5">{beschreibung}</p>
      </div>

      {regeln.map((r, i) => (
        <RegelFormular
          key={i}
          regel={r}
          allowedTypen={allowedTypen}
          onUpdate={(next) => handleUpdate(i, next)}
          onRemove={() => handleRemove(i)}
        />
      ))}

      {regeln.length === 0 && (
        <p className="text-sm text-soft-ink4 italic">Keine Regeln angelegt.</p>
      )}

      <div className="rounded-soft-sm border border-dashed border-soft-line p-4 space-y-3">
        <p className="text-xs font-semibold text-soft-ink3 uppercase tracking-wide">Regel hinzufügen</p>
        <RegelFormular
          regel={entwurf}
          onUpdate={setEntwurf}
          allowedTypen={allowedTypen}
          showRemove={false}
        />
        <button
          type="button"
          onClick={handleAdd}
          className="text-sm font-medium text-soft-accent hover:text-soft-accent"
        >
          + Hinzufügen
        </button>
      </div>
    </div>
  );
}

// ─── Haupt-Editor ─────────────────────────────────────────────────────────────

type FoerderregelEditorProps = {
  regeln: RegelInput[];
  onChange: (regeln: RegelInput[]) => void;
};

export function FoerderregelEditor({ regeln, onChange }: FoerderregelEditorProps) {
  const foerderRegeln = regeln.filter((r) => FOERDER_TYPEN.includes(r.typ));
  const nachweisRegeln = regeln.filter((r) => NACHWEIS_TYPEN.includes(r.typ));

  const handleFoerderChange = (neu: RegelInput[]) => onChange([...neu, ...nachweisRegeln]);
  const handleNachweisChange = (neu: RegelInput[]) => onChange([...foerderRegeln, ...neu]);

  return (
    <div className="space-y-8">
      <SektionsEditor
        titel="Förder- & Mittelverteilungsregeln"
        beschreibung="Regeln die bestimmen, welche Kosten förderfähig sind und wie Mittel verteilt werden."
        regeln={foerderRegeln}
        allowedTypen={FOERDER_TYPEN}
        defaultTyp="KOSTENKATEGORIE_ERLAUBT"
        onChange={handleFoerderChange}
      />

      <div className="border-t border-soft-line" />

      <SektionsEditor
        titel="Prüf- & Nachweishinweise"
        beschreibung="Interne Transparenz: Belegpflichten, Fristen und Nachweisanforderungen aus dem Bescheid."
        regeln={nachweisRegeln}
        allowedTypen={NACHWEIS_TYPEN}
        defaultTyp="BELEGPFLICHT_SPEZIAL"
        onChange={handleNachweisChange}
      />
    </div>
  );
}
