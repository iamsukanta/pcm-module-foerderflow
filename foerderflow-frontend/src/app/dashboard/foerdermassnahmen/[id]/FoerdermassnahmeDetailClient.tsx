"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/ToastProvider";
import { FileDown } from "lucide-react";
import type {
  FundingMeasureStatus,
  FundingRuleTyp,
  FundingRuleBase,
  FundingMeasureCostCenterBase,
} from "@/types/foerdermassnahmen";

// ─── Types ──────────────────────────────────────────────────────

type CostCenterOption = { id: string; name: string; code: string; ist_aktiv: boolean };

type MeasureForClient = {
  id: string;
  name: string;
  status: FundingMeasureStatus;
  funder_id: string;
  funder: { id: string; name: string; typ: string; notizen: string | null };
  budget_gesamt: string;
  foerderquote: string;
  laufzeit_von: string;
  laufzeit_bis: string;
  verwaltungspauschale_erlaubt: boolean;
  verwaltungspauschale_prozent: string | null;
  budget_flexibilitaet_prozent: string;
  overhead_limit_prozent: string | null;
  mittelabruf_verfahren: string;
  rules: FundingRuleBase[];
  cost_centers: (FundingMeasureCostCenterBase & {
    cost_center: { id: string; name: string; code: string; typ: string; ist_aktiv: boolean };
  })[];
};

type FiscalYearOption = { id: string; jahr: number; status: string };

type Props = {
  measure: MeasureForClient;
  costCenters: CostCenterOption[];
  fiscalYears: FiscalYearOption[];
};

const RULE_TYP_OPTIONS: { value: FundingRuleTyp; label: string; hint: string }[] = [
  { value: "KOSTENKATEGORIE_ERLAUBT", label: "Kostenart erlaubt", hint: "z.B. Personalkosten" },
  { value: "KOSTENKATEGORIE_VERBOTEN", label: "Kostenart verboten", hint: "z.B. Reisekosten" },
  { value: "BELEGPFLICHT_SPEZIAL", label: "Besondere Belegpflicht", hint: "Beschreibung" },
  { value: "EIGENANTEIL_MIN", label: "Mindest-Eigenanteil", hint: "Prozent (z.B. 20)" },
  { value: "VERWENDUNGSFRIST_TAGE", label: "Verwendungsfrist (Tage)", hint: "z.B. 42" },
  { value: "ZWISCHENNACHWEIS_PFLICHT", label: "Zwischennachweis Pflicht", hint: "true / false" },
];

// ─────────────────────────────────────────────────────────────────
// Actions panel — revoke, add/remove KST, add/remove rules
// ─────────────────────────────────────────────────────────────────

export function FoerdermassnahmeDetailClient({ measure, costCenters, fiscalYears }: Props) {
  const router = useRouter();
  const toast = useToast();

  const [revoking, setRevoking] = useState(false);
  const [showRevokeConfirm, setShowRevokeConfirm] = useState(false);

  // KST management
  const [addingKst, setAddingKst] = useState(false);
  const [selectedKstToAdd, setSelectedKstToAdd] = useState("");
  const [removingKstId, setRemovingKstId] = useState<string | null>(null);

  // Rule management
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [newRuleTyp, setNewRuleTyp] = useState<FundingRuleTyp>("KOSTENKATEGORIE_ERLAUBT");
  const [newRuleSchluessel, setNewRuleSchluessel] = useState("");
  const [newRuleWert, setNewRuleWert] = useState("");
  const [newRuleBeschreibung, setNewRuleBeschreibung] = useState("");
  const [addingRule, setAddingRule] = useState(false);
  const [removingRuleId, setRemovingRuleId] = useState<string | null>(null);

  // Verwendungsnachweis
  const [nachweisJahrId, setNachweisJahrId] = useState("");
  const [nachweisLoading, setNachweisLoading] = useState(false);

  const isRevoked = measure.status === "WIDERRUFEN";

  // Current assigned KST IDs
  const assignedKstIds = new Set(measure.cost_centers.map((cc) => cc.cost_center_id));
  const availableKstsToAdd = costCenters.filter((cc) => !assignedKstIds.has(cc.id));

  // ── Revoke ────────────────────────────────────
  const handleRevoke = async () => {
    setRevoking(true);
    try {
      const res = await fetch(`/api/protected/foerdermassnahmen/${measure.id}`, {
        method: "DELETE",
      });
      const json = await res.json() as { message?: string; error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Widerruf fehlgeschlagen.");
        return;
      }
      toast.success(json.message ?? "Fördermassnahme wurde widerrufen.");
      router.refresh();
    } catch {
      toast.error("Netzwerkfehler. Bitte versuche es erneut.");
    } finally {
      setRevoking(false);
      setShowRevokeConfirm(false);
    }
  };

  // ── Add KST ───────────────────────────────────
  const handleAddKst = async () => {
    if (!selectedKstToAdd) return;
    setAddingKst(true);
    try {
      const res = await fetch(`/api/protected/foerdermassnahmen/${measure.id}/kostenstellen`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cost_center_id: selectedKstToAdd }),
      });
      const json = await res.json() as { message?: string; error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Kostenstelle konnte nicht hinzugefügt werden.");
        return;
      }
      toast.success(json.message ?? "Kostenstelle wurde zugeordnet.");
      setSelectedKstToAdd("");
      router.refresh();
    } catch {
      toast.error("Netzwerkfehler.");
    } finally {
      setAddingKst(false);
    }
  };

  // ── Remove KST ────────────────────────────────
  const handleRemoveKst = async (costCenterId: string) => {
    setRemovingKstId(costCenterId);
    try {
      const res = await fetch(`/api/protected/foerdermassnahmen/${measure.id}/kostenstellen`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cost_center_id: costCenterId }),
      });
      const json = await res.json() as { message?: string; error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Kostenstelle konnte nicht entfernt werden.");
        return;
      }
      toast.success(json.message ?? "Kostenstelle wurde entfernt.");
      router.refresh();
    } catch {
      toast.error("Netzwerkfehler.");
    } finally {
      setRemovingKstId(null);
    }
  };

  // ── Add Rule ──────────────────────────────────
  const handleAddRule = async () => {
    if (!newRuleSchluessel.trim()) {
      toast.error("Schlüssel ist erforderlich.");
      return;
    }
    setAddingRule(true);
    try {
      const res = await fetch(`/api/protected/foerdermassnahmen/${measure.id}/regeln`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          typ: newRuleTyp,
          schluessel: newRuleSchluessel.trim(),
          wert: newRuleWert.trim() || null,
          beschreibung: newRuleBeschreibung.trim() || null,
        }),
      });
      const json = await res.json() as { message?: string; error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Regel konnte nicht hinzugefügt werden.");
        return;
      }
      toast.success(json.message ?? "Regel wurde hinzugefügt.");
      setNewRuleSchluessel("");
      setNewRuleWert("");
      setNewRuleBeschreibung("");
      setShowRuleForm(false);
      router.refresh();
    } catch {
      toast.error("Netzwerkfehler.");
    } finally {
      setAddingRule(false);
    }
  };

  // ── Verwendungsnachweis Download ──────────────
  const handleDownloadNachweis = async () => {
    if (!nachweisJahrId) return;
    setNachweisLoading(true);
    try {
      const res = await fetch(
        `/api/protected/foerdermassnahmen/${measure.id}/verwendungsnachweis?fiscal_year_id=${nachweisJahrId}`
      );
      if (!res.ok) {
        const json = await res.json() as { error?: string };
        toast.error(json.error ?? "Fehler beim Generieren des Verwendungsnachweises.");
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = res.headers.get("X-Filename") ?? "verwendungsnachweis.zip";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Netzwerkfehler beim Download.");
    } finally {
      setNachweisLoading(false);
    }
  };

  // ── Remove Rule ───────────────────────────────
  const handleRemoveRule = async (ruleId: string) => {
    setRemovingRuleId(ruleId);
    try {
      const res = await fetch(`/api/protected/foerdermassnahmen/${measure.id}/regeln/${ruleId}`, {
        method: "DELETE",
      });
      const json = await res.json() as { message?: string; error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Regel konnte nicht entfernt werden.");
        return;
      }
      toast.success(json.message ?? "Regel wurde entfernt.");
      router.refresh();
    } catch {
      toast.error("Netzwerkfehler.");
    } finally {
      setRemovingRuleId(null);
    }
  };

  // ─────────────────────────────────────────────
  return (
    <div className="space-y-4">
      {/* ── Aktionen ────────────────────── */}
      {!isRevoked && (
        <div className="rounded-soft border border-soft-line bg-white p-5">
          <h2 className="text-sm font-semibold text-soft-ink2 uppercase tracking-wide mb-3">Aktionen</h2>

          <div className="space-y-2">
            {!showRevokeConfirm ? (
              <Button
                variant="danger"
                size="sm"
                className="w-full"
                onClick={() => setShowRevokeConfirm(true)}
              >
                Massnahme widerrufen
              </Button>
            ) : (
              <div className="rounded-soft-sm border border-soft-crit/30 bg-soft-critSoft p-3 space-y-3">
                <p className="text-sm text-soft-crit">
                  <strong>Wirklich widerrufen?</strong> Dieser Status kann nicht rückgängig gemacht werden.
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setShowRevokeConfirm(false)}
                    disabled={revoking}
                  >
                    Abbrechen
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    loading={revoking}
                    onClick={handleRevoke}
                  >
                    Ja, widerrufen
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── KST-Verwaltung ──────────────── */}
      {!isRevoked && (
        <div className="rounded-soft border border-soft-line bg-white p-5">
          <h2 className="text-sm font-semibold text-soft-ink2 uppercase tracking-wide mb-3">
            Kostenstellen verwalten
          </h2>

          {/* Existing assignments with remove */}
          {measure.cost_centers.length > 0 && (
            <div className="space-y-1.5 mb-3">
              {measure.cost_centers.map((cc) => (
                <div
                  key={cc.id}
                  className="flex items-center justify-between gap-2 rounded-soft-xs bg-soft-line2 border border-soft-line2 px-3 py-2"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="font-mono text-xs bg-soft-line text-soft-ink2 rounded px-1.5 py-0.5 shrink-0">
                      {cc.cost_center.code}
                    </span>
                    <span className="text-xs text-soft-ink2 truncate">{cc.cost_center.name}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRemoveKst(cc.cost_center_id)}
                    disabled={removingKstId === cc.cost_center_id}
                    className="shrink-0 text-soft-ink4 hover:text-soft-crit transition-colors disabled:opacity-50"
                    aria-label="Kostenstelle entfernen"
                  >
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Add KST */}
          {availableKstsToAdd.length > 0 && (
            <div className="flex gap-2">
              <select
                value={selectedKstToAdd}
                onChange={(e) => setSelectedKstToAdd(e.target.value)}
                className="flex-1 rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-xs outline-none
                  focus:ring-2 focus:ring-soft-accent focus:border-soft-accent"
              >
                <option value="">KST hinzufügen …</option>
                {availableKstsToAdd.map((cc) => (
                  <option key={cc.id} value={cc.id}>
                    {cc.code} – {cc.name}
                  </option>
                ))}
              </select>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleAddKst}
                loading={addingKst}
                disabled={!selectedKstToAdd}
              >
                +
              </Button>
            </div>
          )}

          {availableKstsToAdd.length === 0 && measure.cost_centers.length === 0 && (
            <p className="text-xs text-soft-ink4 italic">Keine aktiven Kostenstellen verfügbar.</p>
          )}

          {availableKstsToAdd.length === 0 && measure.cost_centers.length > 0 && (
            <p className="text-xs text-soft-ink4 mt-2">Alle aktiven Kostenstellen sind bereits zugeordnet.</p>
          )}
        </div>
      )}

      {/* ── Regeleditor ─────────────────── */}
      {!isRevoked && (
        <div className="rounded-soft border border-soft-line bg-white p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-soft-ink2 uppercase tracking-wide">
              Regeln verwalten
            </h2>
            {!showRuleForm && (
              <button
                type="button"
                onClick={() => setShowRuleForm(true)}
                className="text-xs text-soft-accent hover:text-soft-accent font-medium"
              >
                + Regel hinzufügen
              </button>
            )}
          </div>

          {/* Existing rules with remove */}
          {measure.rules.length > 0 && (
            <div className="space-y-2 mb-3">
              {measure.rules.map((rule) => {
                const typOpt = RULE_TYP_OPTIONS.find((o) => o.value === rule.typ);
                return (
                  <div
                    key={rule.id}
                    className="flex items-start justify-between gap-2 rounded-soft-xs bg-soft-line2 border border-soft-line2 px-3 py-2"
                  >
                    <div className="flex-1 min-w-0">
                      <span className="text-xs font-medium text-soft-ink3">{typOpt?.label ?? rule.typ}</span>
                      <div className="text-xs font-semibold text-soft-ink truncate">{rule.schluessel}</div>
                      {rule.wert && (
                        <div className="text-xs text-soft-ink4 truncate">→ {rule.wert}</div>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveRule(rule.id)}
                      disabled={removingRuleId === rule.id}
                      className="shrink-0 text-soft-ink4 hover:text-soft-crit transition-colors disabled:opacity-50 mt-0.5"
                      aria-label="Regel entfernen"
                    >
                      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {/* New rule form */}
          {showRuleForm && (
            <div className="rounded-soft-sm border border-dashed border-soft-accent/40 bg-soft-accentSoft p-3 space-y-3">
              <div>
                <label className="block text-xs font-medium text-soft-ink2 mb-1">Regeltyp</label>
                <select
                  value={newRuleTyp}
                  onChange={(e) => setNewRuleTyp(e.target.value as FundingRuleTyp)}
                  className="w-full rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-xs outline-none
                    focus:ring-2 focus:ring-soft-accent"
                >
                  {RULE_TYP_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-soft-ink2 mb-1">Schlüssel *</label>
                <input
                  type="text"
                  value={newRuleSchluessel}
                  onChange={(e) => setNewRuleSchluessel(e.target.value)}
                  placeholder={RULE_TYP_OPTIONS.find((o) => o.value === newRuleTyp)?.hint ?? ""}
                  className="w-full rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-xs outline-none
                    focus:ring-2 focus:ring-soft-accent"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-soft-ink2 mb-1">Wert (optional)</label>
                <input
                  type="text"
                  value={newRuleWert}
                  onChange={(e) => setNewRuleWert(e.target.value)}
                  className="w-full rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-xs outline-none
                    focus:ring-2 focus:ring-soft-accent"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-soft-ink2 mb-1">Beschreibung (optional)</label>
                <input
                  type="text"
                  value={newRuleBeschreibung}
                  onChange={(e) => setNewRuleBeschreibung(e.target.value)}
                  placeholder="Hinweis aus dem Bescheid"
                  className="w-full rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-xs outline-none
                    focus:ring-2 focus:ring-soft-accent"
                />
              </div>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => { setShowRuleForm(false); setNewRuleSchluessel(""); setNewRuleWert(""); setNewRuleBeschreibung(""); }}
                  disabled={addingRule}
                >
                  Abbrechen
                </Button>
                <Button
                  type="button"
                  variant="primary"
                  size="sm"
                  loading={addingRule}
                  onClick={handleAddRule}
                >
                  Regel speichern
                </Button>
              </div>
            </div>
          )}

          {measure.rules.length === 0 && !showRuleForm && (
            <p className="text-xs text-soft-ink4 italic">Keine Förderregeln hinterlegt.</p>
          )}
        </div>
      )}

      {/* ── Verwendungsnachweis ─────────────── */}
      <div className="rounded-soft border border-soft-line bg-white p-5">
        <h2 className="text-sm font-semibold text-soft-ink2 uppercase tracking-wide mb-3">
          Verwendungsnachweis
        </h2>

        {/* Generate section */}
        {fiscalYears.length === 0 ? (
          <p className="text-xs text-soft-ink4 italic">Keine Haushaltsjahre vorhanden.</p>
        ) : (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-soft-ink2 mb-1">
                Haushaltsjahr
              </label>
              <select
                value={nachweisJahrId}
                onChange={(e) => setNachweisJahrId(e.target.value)}
                className="w-full rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-xs outline-none
                  focus:ring-2 focus:ring-soft-accent focus:border-soft-accent"
              >
                <option value="">Jahr auswählen …</option>
                {fiscalYears.map((fy) => (
                  <option key={fy.id} value={fy.id}>
                    {fy.jahr} {fy.status === "GESCHLOSSEN" ? "(abgeschlossen)" : "(offen)"}
                  </option>
                ))}
              </select>
            </div>

            <button
              type="button"
              onClick={handleDownloadNachweis}
              disabled={!nachweisJahrId || nachweisLoading}
              className="flex items-center justify-center gap-2 w-full rounded-soft-xs bg-soft-accent px-3 py-2.5
                text-sm font-medium text-white hover:bg-soft-accentDark transition-colors
                disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <FileDown className="h-4 w-4" />
              {nachweisLoading ? "Paket wird generiert …" : "Verwendungsnachweis generieren"}
            </button>

            <p className="text-xs text-soft-ink4">
              ZIP-Paket: Excel (ANBest), Belegliste, Soll/Ist-Vergleich und ggf. ausgefülltes Formulartemplate.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
