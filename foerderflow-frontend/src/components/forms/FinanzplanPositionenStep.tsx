"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight, Plus, Trash2, AlertCircle, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useKostenbereiche } from "@/lib/hooks/useKostenbereiche";

export type PauschaleTypClient = "FIXER_BETRAG" | "PROZENT_GESAMT" | "PROZENT_PERSONAL" | "UMLAGE_KOSTENSTELLEN";

export type WizardPosition = {
  /** Vorhandene DB-ID (Edit-Modus); leer = neu im Wizard */
  id?: string;
  positionscode: string;
  bezeichnung: string;
  betrag_bewilligt: string;          // String — wird beim Submit zu number
  ueberziehung_limit_pct: string;    // String — default "20"
  kostenbereich_codes: string[];     // Multi-Select aus systemweiter Kostenbereich-Taxonomie (DB)
  /** Pro Kostenbereich-Code optionale per-Code-Konfiguration */
  kostenbereich_overrides?: Record<string, { foerderfahig_anteil?: number; cap_betrag?: number | null }>;
  /** Anzahl FundAllocations — verhindert Löschung wenn > 0 */
  allocation_count?: number;
  // Phase J — Verwaltungspauschale
  ist_pauschale?: boolean;
  pauschale_typ?: PauschaleTypClient | null;
  pauschale_prozent?: string;        // String — leer = aus Maßnahmen-Default oder N/A
  // Phase K — UMLAGE_KOSTENSTELLEN-FKs
  umlage_allocation_key_id?: string | null;
  umlage_ziel_cost_center_id?: string | null;
  umlage_source_scope_id?: string | null;
};

/** Phase K — Verteilungsschlüssel-Auswahl-Option für den UMLAGE-Modus. */
export type UmlageAllocationKeyOption = {
  id: string;
  name: string;
  gueltig_von: string;
  gueltig_bis: string | null;
  ist_aktiv: boolean;
  positions: Array<{ cost_center_id: string; cost_center_code: string; cost_center_name: string; prozent: number }>;
};

/** Phase K — Umlage-Source-Scope-Auswahl-Option für den UMLAGE-Modus. */
export type UmlageSourceScopeOption = {
  id: string;
  name: string;
  cost_center_count: number;
};

type Props = {
  positionen: WizardPosition[];
  onChange: (positionen: WizardPosition[]) => void;
  budgetGesamt: number;
  errors?: Record<string, string>;
};

function emptyPosition(): WizardPosition {
  return {
    positionscode: "",
    bezeichnung: "",
    betrag_bewilligt: "",
    ueberziehung_limit_pct: "20",
    kostenbereich_codes: [],
    ist_pauschale: false,
    pauschale_typ: null,
    pauschale_prozent: "",
    umlage_allocation_key_id: null,
    umlage_ziel_cost_center_id: null,
    umlage_source_scope_id: null,
  };
}

export function FinanzplanPositionenStep({
  positionen,
  onChange,
  budgetGesamt,
  errors = {},
}: Props) {
  const [expanded, setExpanded] = useState<Set<number>>(() => new Set([0]));
  const [deleteIdx, setDeleteIdx] = useState<number | null>(null);

  // Phase K — UMLAGE-Optionen laden (Schlüssel + Pools) wenn min. eine Position
  // pauschale_typ=UMLAGE_KOSTENSTELLEN hat oder hat haben könnte. Defensiv immer laden.
  const [umlageKeys, setUmlageKeys] = useState<UmlageAllocationKeyOption[]>([]);
  const [umlageScopes, setUmlageScopes] = useState<UmlageSourceScopeOption[]>([]);
  const [umlageLoaded, setUmlageLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [keysRes, scopesRes] = await Promise.all([
          fetch("/api/protected/verteilungsschluessel"),
          fetch("/api/protected/umlage-source-scopes"),
        ]);
        if (!keysRes.ok || !scopesRes.ok) return;
        const keysJson = (await keysRes.json()) as {
          data: Array<{
            id: string;
            name: string;
            gueltig_von: string;
            gueltig_bis: string | null;
            ist_aktiv: boolean;
            positions: Array<{
              cost_center_id: string;
              prozent: string;
              cost_center?: { code: string; name: string };
            }>;
          }>;
        };
        const scopesJson = (await scopesRes.json()) as {
          data: Array<{ id: string; name: string; cost_center_count: number }>;
        };
        if (cancelled) return;
        setUmlageKeys(
          keysJson.data
            .filter((k) => k.ist_aktiv) // nur aktive Schlüssel zur Auswahl
            .map((k) => ({
              id: k.id,
              name: k.name,
              gueltig_von: k.gueltig_von,
              gueltig_bis: k.gueltig_bis,
              ist_aktiv: k.ist_aktiv,
              positions: k.positions.map((p) => ({
                cost_center_id: p.cost_center_id,
                cost_center_code: p.cost_center?.code ?? "?",
                cost_center_name: p.cost_center?.name ?? "?",
                prozent: parseFloat(p.prozent),
              })),
            }))
        );
        setUmlageScopes(scopesJson.data ?? []);
        setUmlageLoaded(true);
      } catch {
        // Fail-silent: UMLAGE-Modus wird im Form als nicht verfügbar markiert
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const summe = positionen.reduce(
    (s, p) => s + (parseFloat(p.betrag_bewilligt) || 0),
    0
  );
  const ueberzogen = budgetGesamt > 0 && summe > budgetGesamt + 0.005;

  const updatePos = (idx: number, patch: Partial<WizardPosition>) => {
    onChange(positionen.map((p, i) => (i === idx ? { ...p, ...patch } : p)));
  };

  const toggleKostenbereich = (idx: number, code: string) => {
    const pos = positionen[idx];
    const has = pos.kostenbereich_codes.includes(code);
    updatePos(idx, {
      kostenbereich_codes: has
        ? pos.kostenbereich_codes.filter((c) => c !== code)
        : [...pos.kostenbereich_codes, code],
    });
  };

  const toggleExpanded = (idx: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const addPosition = () => {
    const next = positionen.length;
    onChange([...positionen, emptyPosition()]);
    setExpanded((prev) => new Set(prev).add(next));
  };

  const removeAt = (idx: number) => {
    onChange(positionen.filter((_, i) => i !== idx));
    setExpanded((prev) => {
      const next = new Set<number>();
      for (const i of prev) {
        if (i < idx) next.add(i);
        else if (i > idx) next.add(i - 1);
      }
      return next;
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-soft-ink">Finanzplan-Positionen</h2>
        <p className="text-sm text-soft-ink3 mt-1">
          Bewilligte Positionen aus dem Bescheid mit ihren erlaubten Kostenbereichen.
          Diese sind die Grundlage für die monatliche Planung im Finanzplan-Tab.
        </p>
      </div>

      {/* Summe-Indikator */}
      {positionen.length > 0 && (
        <div
          className={`rounded-soft-sm border px-4 py-3 text-sm flex items-center justify-between ${
            ueberzogen
              ? "border-soft-warn/30 bg-soft-warnSoft text-soft-warn"
              : "border-soft-line bg-soft-line2/40 text-soft-ink2"
          }`}
        >
          <span>
            {positionen.length} Position(en) ·{" "}
            <span className="numeric font-semibold">
              {new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(summe)}
            </span>
          </span>
          {budgetGesamt > 0 && (
            <span className="text-xs">
              Budget gesamt:{" "}
              <span className="numeric">
                {new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(budgetGesamt)}
              </span>
            </span>
          )}
        </div>
      )}

      {ueberzogen && (
        <div
          role="alert"
          className="rounded-soft-sm border border-soft-warn/30 bg-soft-warnSoft px-4 py-3 text-sm text-soft-warn flex items-start gap-2"
        >
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" aria-hidden="true" />
          <span>
            Die Summe der Positionen überschreitet das Budget der Massnahme. Das ist erlaubt
            (Warnung im Bescheid), aber bitte prüfe die Eingaben.
          </span>
        </div>
      )}

      {/* Positionen-Liste */}
      {positionen.length === 0 ? (
        <div className="text-center py-12 text-sm text-soft-ink4 italic border border-dashed border-soft-line rounded-soft-sm">
          Noch keine Positionen. Lege deine erste Position an.
        </div>
      ) : (
        <div className="space-y-3">
          {positionen.map((pos, idx) => (
            <PositionCard
              key={idx}
              pos={pos}
              idx={idx}
              expanded={expanded.has(idx)}
              onToggleExpanded={() => toggleExpanded(idx)}
              onUpdate={(patch) => updatePos(idx, patch)}
              onToggleKostenbereich={(code) => toggleKostenbereich(idx, code)}
              onDelete={() => setDeleteIdx(idx)}
              errors={errors}
              umlageKeys={umlageKeys}
              umlageScopes={umlageScopes}
              umlageLoaded={umlageLoaded}
            />
          ))}
        </div>
      )}

      <Button type="button" variant="secondary" onClick={addPosition}>
        <Plus className="h-4 w-4 mr-1.5" aria-hidden="true" />
        Position hinzufügen
      </Button>

      {/* Delete-Confirm */}
      <ConfirmDialog
        open={deleteIdx !== null}
        title="Position löschen?"
        description={
          deleteIdx !== null && positionen[deleteIdx]?.allocation_count
            ? `„${positionen[deleteIdx].bezeichnung || "Unbenannt"}" hat ${positionen[deleteIdx].allocation_count} Mittelzuordnung(en). Löschen ist nicht möglich, solange Allocations bestehen.`
            : `„${deleteIdx !== null ? positionen[deleteIdx]?.bezeichnung || "Unbenannt" : ""}" wird aus dem Finanzplan entfernt.`
        }
        confirmLabel={
          deleteIdx !== null && positionen[deleteIdx]?.allocation_count
            ? "Schließen"
            : "Ja, löschen"
        }
        variant="danger"
        onConfirm={() => {
          if (deleteIdx !== null) {
            const pos = positionen[deleteIdx];
            if (!pos.allocation_count) removeAt(deleteIdx);
            setDeleteIdx(null);
          }
        }}
        onCancel={() => setDeleteIdx(null)}
      />
    </div>
  );
}

// ─────────────────────────────────────────────
// Position-Card mit Inline-Edit + Kostenbereich-Multi-Select
// ─────────────────────────────────────────────

function PositionCard({
  pos,
  idx,
  expanded,
  onToggleExpanded,
  onUpdate,
  onToggleKostenbereich,
  onDelete,
  errors,
  umlageKeys,
  umlageScopes,
  umlageLoaded,
}: {
  pos: WizardPosition;
  idx: number;
  expanded: boolean;
  onToggleExpanded: () => void;
  onUpdate: (patch: Partial<WizardPosition>) => void;
  onToggleKostenbereich: (code: string) => void;
  onDelete: () => void;
  errors: Record<string, string>;
  // Phase K — UMLAGE-Optionen vom Eltern-Component geladen
  umlageKeys: UmlageAllocationKeyOption[];
  umlageScopes: UmlageSourceScopeOption[];
  umlageLoaded: boolean;
}) {
  // Phase K — Aktueller Schlüssel + Ziel-KST-Optionen für den UMLAGE-Modus
  const selectedKey = umlageKeys.find((k) => k.id === pos.umlage_allocation_key_id) ?? null;
  const codeError = errors[`pos_${idx}_positionscode`];
  const bezError = errors[`pos_${idx}_bezeichnung`];
  const betragError = errors[`pos_${idx}_betrag_bewilligt`];
  const { obergruppen } = useKostenbereiche();

  return (
    <div className="rounded-soft-sm border border-soft-line bg-white">
      {/* Kopfzeile */}
      <div className="flex items-start gap-3 p-4">
        <button
          type="button"
          aria-label={expanded ? "Position einklappen" : "Position ausklappen"}
          onClick={onToggleExpanded}
          className="mt-1 p-1 rounded-soft-xs hover:bg-soft-line2 text-soft-ink3 focus:outline-none focus:ring-2 focus:ring-soft-accent"
        >
          {expanded ? (
            <ChevronDown className="h-4 w-4" aria-hidden="true" />
          ) : (
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          )}
        </button>

        <div className="flex-1 grid grid-cols-12 gap-3">
          {/* Positionscode */}
          <div className="col-span-3">
            <label className="block text-xs font-medium text-soft-ink3 mb-1">
              Code <span className="text-soft-crit">*</span>
            </label>
            <input
              type="text"
              value={pos.positionscode}
              onChange={(e) => onUpdate({ positionscode: e.target.value })}
              placeholder="z.B. 1.1"
              maxLength={50}
              aria-invalid={!!codeError}
              className={`w-full rounded-soft-xs border px-2.5 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-soft-accent ${
                codeError ? "border-soft-crit" : "border-soft-line"
              }`}
            />
          </div>

          {/* Bezeichnung */}
          <div className="col-span-5">
            <label className="block text-xs font-medium text-soft-ink3 mb-1">
              Bezeichnung <span className="text-soft-crit">*</span>
              {pos.ist_pauschale && (
                <span
                  className="ml-2 inline-flex items-center rounded-soft-xs bg-soft-accentSoft px-1.5 py-0.5 text-[10px] font-medium text-soft-accent border border-soft-accent/30"
                  title={`Pauschale-Position (${pos.pauschale_typ ?? "FIXER_BETRAG"})`}
                >
                  Pauschale
                  {pos.pauschale_typ === "PROZENT_PERSONAL" && pos.pauschale_prozent && (
                    <span className="ml-1 numeric">{pos.pauschale_prozent}% × Personal</span>
                  )}
                  {pos.pauschale_typ === "PROZENT_GESAMT" && pos.pauschale_prozent && (
                    <span className="ml-1 numeric">{pos.pauschale_prozent}% × Gesamt</span>
                  )}
                  {pos.pauschale_typ === "UMLAGE_KOSTENSTELLEN" && (
                    <span className="ml-1">(Umlage)</span>
                  )}
                  {(pos.pauschale_typ === "FIXER_BETRAG" || !pos.pauschale_typ) && (
                    <span className="ml-1">(fixer Betrag)</span>
                  )}
                </span>
              )}
            </label>
            <input
              type="text"
              value={pos.bezeichnung}
              onChange={(e) => onUpdate({ bezeichnung: e.target.value })}
              placeholder="z.B. Personalkosten 2 VZÄ"
              maxLength={500}
              aria-invalid={!!bezError}
              className={`w-full rounded-soft-xs border px-2.5 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-soft-accent ${
                bezError ? "border-soft-crit" : "border-soft-line"
              }`}
            />
          </div>

          {/* Betrag bewilligt */}
          <div className="col-span-3">
            <label className="block text-xs font-medium text-soft-ink3 mb-1">
              Betrag bewilligt (EUR) <span className="text-soft-crit">*</span>
            </label>
            <div className="relative">
              <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-soft-ink4 text-xs">€</span>
              <input
                type="number"
                min={0}
                step={0.01}
                value={pos.betrag_bewilligt}
                onChange={(e) => onUpdate({ betrag_bewilligt: e.target.value })}
                placeholder="0.00"
                aria-invalid={!!betragError}
                className={`numeric w-full rounded-soft-xs border pl-6 pr-2.5 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-soft-accent ${
                  betragError ? "border-soft-crit" : "border-soft-line"
                }`}
              />
            </div>
          </div>

          {/* Löschen */}
          <div className="col-span-1 flex items-end justify-end">
            <button
              type="button"
              aria-label={`Position ${pos.positionscode || idx + 1} löschen`}
              title="Löschen"
              onClick={onDelete}
              className="p-1.5 rounded-soft-xs text-soft-ink3 hover:text-soft-crit hover:bg-soft-critSoft transition-colors focus:outline-none focus:ring-2 focus:ring-soft-crit"
            >
              <Trash2 className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>

      {/* Fehler-Inline */}
      {(codeError || bezError || betragError) && (
        <div className="px-4 pb-2 text-xs text-soft-crit space-y-0.5">
          {codeError && <p role="alert">{codeError}</p>}
          {bezError && <p role="alert">{bezError}</p>}
          {betragError && <p role="alert">{betragError}</p>}
        </div>
      )}

      {/* Ausgeklappter Bereich: Kostenbereich-Zuordnung + erweiterte Felder */}
      {expanded && (
        <div className="border-t border-soft-line2 px-4 py-4 space-y-4 bg-soft-line2/30">
          {/* Phase J — Verwaltungspauschale */}
          <div className="rounded-soft-sm border border-soft-line bg-white p-3 space-y-3">
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={pos.ist_pauschale ?? false}
                onChange={(e) =>
                  onUpdate({
                    ist_pauschale: e.target.checked,
                    pauschale_typ: e.target.checked ? (pos.pauschale_typ ?? "FIXER_BETRAG") : null,
                    pauschale_prozent: e.target.checked ? (pos.pauschale_prozent ?? "") : "",
                  })
                }
                className="mt-0.5 h-3.5 w-3.5 rounded accent-soft-accent"
              />
              <div>
                <span className="text-sm font-medium text-soft-ink2">Pauschale-Position</span>
                <p className="text-xs text-soft-ink3 mt-0.5">
                  Bescheid-Position OHNE direkte Buchungen — Ist wird aus dem Bescheid-Betrag oder einem Prozentsatz berechnet,
                  nicht aus FundAllocations. Typisch für „anteilig Geschäftsstelle&ldquo;, „Gemeinkostenpauschale&ldquo;, „Verwaltungsumlage&ldquo;.
                </p>
                <p className="text-xs text-soft-ink4 mt-0.5">
                  Nicht zu verwechseln mit dem <strong>Gemeinkostendeckel</strong> (Step 2 → „Gemeinkostendeckel %&ldquo;) — das ist
                  ein Schutz-Limit, KEINE Förder-Ergänzung.
                </p>
              </div>
            </label>

            {pos.ist_pauschale && (
              <div className="space-y-3 pt-2 border-t border-soft-line2">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-soft-ink3 mb-1">Berechnungsmodus</label>
                    <select
                      value={pos.pauschale_typ ?? "FIXER_BETRAG"}
                      onChange={(e) => {
                        const next = e.target.value as PauschaleTypClient;
                        onUpdate({
                          pauschale_typ: next,
                          pauschale_prozent: next === "FIXER_BETRAG" || next === "UMLAGE_KOSTENSTELLEN" ? "" : (pos.pauschale_prozent ?? ""),
                          // UMLAGE-FKs nur erhalten wenn Modus UMLAGE bleibt, sonst zurücksetzen
                          ...(next !== "UMLAGE_KOSTENSTELLEN" && {
                            umlage_allocation_key_id: null,
                            umlage_ziel_cost_center_id: null,
                            umlage_source_scope_id: null,
                          }),
                        });
                      }}
                      className="w-full rounded-soft-xs border border-soft-line bg-white px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                    >
                      <option value="FIXER_BETRAG">Fixer Betrag (Bescheid hat € genannt)</option>
                      <option value="PROZENT_PERSONAL">% × direkte Personalkosten (ESF/BMBF-Standard)</option>
                      <option value="PROZENT_GESAMT">% × Gesamt-direkte-Kosten (institutionell)</option>
                      <option value="UMLAGE_KOSTENSTELLEN">Umlage nach Verteilungsschlüssel (ANBest-P)</option>
                    </select>
                  </div>
                  {pos.pauschale_typ !== "UMLAGE_KOSTENSTELLEN" && (
                    <div>
                      <label className="block text-xs font-medium text-soft-ink3 mb-1">
                        Prozentsatz{" "}
                        {pos.pauschale_typ === "FIXER_BETRAG" && (
                          <span className="text-soft-ink4 font-normal">(nicht relevant)</span>
                        )}
                      </label>
                      <div className="relative">
                        <input
                          type="number"
                          min={0}
                          max={100}
                          step={0.01}
                          disabled={pos.pauschale_typ === "FIXER_BETRAG"}
                          value={pos.pauschale_prozent ?? ""}
                          onChange={(e) => onUpdate({ pauschale_prozent: e.target.value })}
                          placeholder={
                            pos.pauschale_typ === "PROZENT_PERSONAL"
                              ? "z.B. 15"
                              : pos.pauschale_typ === "PROZENT_GESAMT"
                              ? "z.B. 7"
                              : "—"
                          }
                          className="numeric w-full rounded-soft-xs border border-soft-line px-2.5 py-1.5 pr-7 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-soft-accent disabled:bg-soft-line2 disabled:text-soft-ink4"
                        />
                        <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-soft-ink4">%</span>
                      </div>
                      <p className="mt-1 text-xs text-soft-ink4">
                        Leer = Default aus Maßnahmen-Feld „Verwaltungspauschale %&ldquo;.
                      </p>
                    </div>
                  )}
                </div>

                {/* Phase K — UMLAGE_KOSTENSTELLEN Sub-Form */}
                {pos.pauschale_typ === "UMLAGE_KOSTENSTELLEN" && (
                  <div className="rounded-soft-xs border border-soft-accent/20 bg-soft-accentSoft/40 p-3 space-y-3">
                    <p className="text-xs text-soft-ink3">
                      Ist wird dynamisch aus Σ Buchungen auf Quell-KSTs × Schlüssel-Anteil
                      berechnet (versionssensitiv über Schlüssel-Gültigkeit), gecappt auf{" "}
                      <strong className="numeric">{pos.betrag_bewilligt || "?"}</strong> €.
                    </p>

                    <div>
                      <label className="block text-xs font-medium text-soft-ink3 mb-1">
                        Verteilungsschlüssel <span className="text-soft-crit">*</span>
                      </label>
                      <select
                        value={pos.umlage_allocation_key_id ?? ""}
                        onChange={(e) => {
                          const id = e.target.value || null;
                          onUpdate({
                            umlage_allocation_key_id: id,
                            // Ziel-KST zurücksetzen — muss aus dem neuen Schlüssel kommen
                            umlage_ziel_cost_center_id: null,
                          });
                        }}
                        className="w-full rounded-soft-xs border border-soft-line bg-white px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                      >
                        <option value="">— Schlüssel wählen —</option>
                        {umlageKeys.map((k) => (
                          <option key={k.id} value={k.id}>
                            {k.name} (gültig ab {k.gueltig_von})
                          </option>
                        ))}
                      </select>
                      {umlageLoaded && umlageKeys.length === 0 && (
                        <p className="mt-1 text-xs text-soft-warn">
                          Keine aktiven Schlüssel vorhanden.{" "}
                          <Link href="/dashboard/verteilungsschluessel/new" target="_blank" className="underline">
                            Schlüssel anlegen <ExternalLink className="inline h-3 w-3" />
                          </Link>
                        </p>
                      )}
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-soft-ink3 mb-1">
                        Ziel-Kostenstelle <span className="text-soft-crit">*</span>
                        <span className="ml-2 text-[10px] font-normal text-soft-ink4">
                          (welcher Schlüssel-Anteil zählt für diese Position?)
                        </span>
                      </label>
                      <select
                        value={pos.umlage_ziel_cost_center_id ?? ""}
                        onChange={(e) =>
                          onUpdate({ umlage_ziel_cost_center_id: e.target.value || null })
                        }
                        disabled={!selectedKey}
                        className="w-full rounded-soft-xs border border-soft-line bg-white px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent disabled:bg-soft-line2 disabled:text-soft-ink4"
                      >
                        <option value="">— Ziel-KST wählen —</option>
                        {selectedKey?.positions.map((kp) => (
                          <option key={kp.cost_center_id} value={kp.cost_center_id}>
                            {kp.cost_center_code} — {kp.cost_center_name} ({kp.prozent}%)
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-soft-ink3 mb-1">
                        Quell-KST-Pool <span className="text-soft-crit">*</span>
                        <span className="ml-2 text-[10px] font-normal text-soft-ink4">
                          (Buchungen welcher KSTs werden umgelegt?)
                        </span>
                      </label>
                      <select
                        value={pos.umlage_source_scope_id ?? ""}
                        onChange={(e) => onUpdate({ umlage_source_scope_id: e.target.value || null })}
                        className="w-full rounded-soft-xs border border-soft-line bg-white px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                      >
                        <option value="">— Pool wählen —</option>
                        {umlageScopes.map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.name} ({s.cost_center_count} KSTs)
                          </option>
                        ))}
                      </select>
                      {umlageLoaded && umlageScopes.length === 0 && (
                        <p className="mt-1 text-xs text-soft-warn">
                          Keine Pools angelegt.{" "}
                          <Link href="/dashboard/umlage-source-scopes/new" target="_blank" className="underline">
                            Pool anlegen <ExternalLink className="inline h-3 w-3" />
                          </Link>
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          <div>
            <h4 className="text-sm font-semibold text-soft-ink2 mb-2">
              Erlaubte Kostenbereiche
              <span className="ml-2 text-xs font-normal text-soft-ink3">
                ({pos.kostenbereich_codes.length} ausgewählt)
                {pos.ist_pauschale && (
                  <span className="ml-2 text-soft-ink4 italic">— für Pauschale-Positionen nicht nötig</span>
                )}
              </span>
            </h4>
            <p className="text-xs text-soft-ink3 mb-3">
              Buchungen können nur Kostenbereichen zugeordnet werden, die hier markiert sind.
            </p>
            <div className="space-y-3">
              {obergruppen.map((gruppe) => (
                <div key={gruppe.id}>
                  <p className="text-xs font-semibold text-soft-ink3 uppercase tracking-wide mb-1.5">
                    {gruppe.bezeichnung}
                  </p>
                  <div className="grid grid-cols-2 gap-1.5">
                    {gruppe.kinder.map((item) => {
                      const checked = pos.kostenbereich_codes.includes(item.code);
                      return (
                        <label
                          key={item.code}
                          className={`flex items-center gap-2 rounded-soft-xs border px-2.5 py-1.5 text-xs cursor-pointer transition-colors ${
                            checked
                              ? "border-soft-accent bg-soft-accentSoft text-soft-ink"
                              : "border-soft-line bg-white text-soft-ink2 hover:border-soft-line"
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => onToggleKostenbereich(item.code)}
                            className="h-3.5 w-3.5 rounded accent-soft-accent"
                          />
                          <span className="truncate">{item.bezeichnung}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Erweiterte Position-Felder */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-soft-ink3 mb-1">
                Überziehungs-Limit (%)
              </label>
              <input
                type="number"
                min={0}
                max={100}
                step={1}
                value={pos.ueberziehung_limit_pct}
                onChange={(e) => onUpdate({ ueberziehung_limit_pct: e.target.value })}
                className="numeric w-full rounded-soft-xs border border-soft-line px-2.5 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-soft-accent"
              />
              <p className="mt-1 text-xs text-soft-ink4">
                Erlaubte Überziehung ohne Genehmigung (Standard 20%, ANBest-P §1.2)
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
