"use client";

import { useState, useEffect } from "react";
import { formatEur } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/ToastProvider";

type CostCenter = { id: string; name: string; code: string };
type AllocationKey = { id: string; name: string; positions: { cost_center_id: string; prozent: number }[] };

type CurrentSplit = {
  id: string;
  cost_center: CostCenter;
  prozent: string;
  betrag_anteil: string;
};

type SplitEditorProps = {
  transactionId: string;
  betrag: number;
  currentSplits: CurrentSplit[];
  costCenters: CostCenter[];
  auftraggeber: string | null;
  verwendungszweck: string | null;
  kostenbereichId: string | null;
  kostenbereichBezeichnung: string | null;
  onSaved: () => void;
};

type EditSplit = {
  cost_center_id: string;
  prozent: number;
};

export function SplitEditor({
  transactionId,
  betrag,
  currentSplits,
  costCenters,
  auftraggeber,
  verwendungszweck,
  kostenbereichId,
  kostenbereichBezeichnung,
  onSaved,
}: SplitEditorProps) {
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [splits, setSplits] = useState<EditSplit[]>([]);
  const [allocationKeys, setAllocationKeys] = useState<AllocationKey[]>([]);
  const [saveAsRule, setSaveAsRule] = useState(false);
  const [ruleName, setRuleName] = useState("");
  const [ruleMatchAuftraggeber, setRuleMatchAuftraggeber] = useState(auftraggeber ?? "");

  useEffect(() => {
    if (editing) {
      // Aktuelle Splits als Ausgangsbasis
      setSplits(
        currentSplits.length > 0
          ? currentSplits.map((s) => ({
              cost_center_id: s.cost_center.id,
              prozent: parseFloat(s.prozent),
            }))
          : [{ cost_center_id: costCenters[0]?.id ?? "", prozent: 100 }]
      );

      // Verteilungsschlüssel laden
      fetch("/api/protected/verteilungsschluessel")
        .then((r) => r.json())
        .then((json: { data?: AllocationKey[] }) => setAllocationKeys(json.data ?? []))
        .catch(() => {});
    }
  }, [editing, currentSplits, costCenters]);

  const summe = splits.reduce((a, s) => a + (s.prozent || 0), 0);
  const summeOk = Math.abs(summe - 100) <= 0.01;

  function applyAllocationKey(keyId: string) {
    const key = allocationKeys.find((k) => k.id === keyId);
    if (!key) return;
    setSplits(key.positions.map((p) => ({ cost_center_id: p.cost_center_id, prozent: p.prozent })));
  }

  function addRow() {
    const remaining = Math.max(0, 100 - summe);
    setSplits((prev) => [
      ...prev,
      { cost_center_id: costCenters[0]?.id ?? "", prozent: parseFloat(remaining.toFixed(3)) },
    ]);
  }

  function removeRow(i: number) {
    setSplits((prev) => prev.filter((_, idx) => idx !== i));
  }

  function updateSplit(i: number, field: keyof EditSplit, value: string | number) {
    setSplits((prev) => {
      const next = [...prev];
      next[i] = { ...next[i], [field]: field === "prozent" ? Number(value) : value };
      return next;
    });
  }

  async function handleSave() {
    if (!summeOk) {
      toast.error(`Prozent-Summe muss 100% ergeben (aktuell ${summe.toFixed(1)}%).`);
      return;
    }
    if (saveAsRule && !ruleName.trim()) {
      toast.error("Bitte einen Namen für die Buchungsregel eingeben.");
      return;
    }

    setLoading(true);
    try {
      const body: {
        splits: EditSplit[];
        save_as_rule?: { name: string; match_auftraggeber?: string; match_kostenbereich_id?: string };
      } = { splits };

      if (saveAsRule && ruleName.trim()) {
        body.save_as_rule = {
          name: ruleName.trim(),
          match_auftraggeber: ruleMatchAuftraggeber.trim() || undefined,
          match_kostenbereich_id: kostenbereichId || undefined,
        };
      }

      const res = await fetch(`/api/protected/transaktionen/${transactionId}/splits`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const json = await res.json() as { message?: string; error?: string };

      if (!res.ok) {
        toast.error(json.error ?? "Fehler beim Speichern.");
        return;
      }

      toast.success(saveAsRule ? "Gespeichert und Buchungsregel angelegt." : (json.message ?? "Gespeichert."));
      setEditing(false);
      setSaveAsRule(false);
      setRuleName("");
      onSaved();
    } catch {
      toast.error("Netzwerkfehler beim Speichern.");
    } finally {
      setLoading(false);
    }
  }

  // ── Lese-Modus ───────────────────────────────────────────────
  if (!editing) {
    return (
      <div>
        {currentSplits.length === 0 ? (
          <div className="text-center py-6">
            <p className="text-sm text-soft-ink2 mb-3">Noch keine Kostenstelle zugeordnet.</p>
            <Button variant="primary" size="sm" onClick={() => setEditing(true)}>
              Kostenstelle zuordnen →
            </Button>
          </div>
        ) : (
          <>
            <div className="space-y-2 mb-4">
              {currentSplits.map((s) => {
                const betragAnteil = parseFloat(s.betrag_anteil);
                const prozent = parseFloat(s.prozent);
                return (
                  <div key={s.id} className="flex items-center justify-between py-2 border-b border-soft-line2 last:border-0">
                    <div>
                      <p className="text-sm font-medium text-soft-ink">{s.cost_center.name}</p>
                      <p className="text-xs text-soft-ink3">{s.cost_center.code}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-semibold text-soft-ink numeric">{formatEur(betragAnteil)}</p>
                      <p className="text-xs text-soft-ink3 numeric">{prozent.toFixed(1)} %</p>
                    </div>
                  </div>
                );
              })}
            </div>
            <Button variant="secondary" size="sm" onClick={() => setEditing(true)}>
              Bearbeiten
            </Button>
          </>
        )}
      </div>
    );
  }

  // ── Bearbeiten-Modus ─────────────────────────────────────────
  return (
    <div className="space-y-4">
      {/* Verteilungsschlüssel-Schnellauswahl */}
      {allocationKeys.length > 0 && (
        <div>
          <label className="block text-xs text-soft-ink2 mb-1">Verteilungsschlüssel anwenden</label>
          <select
            className="w-full rounded-soft-xs border border-soft-line bg-soft-surface px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
            defaultValue=""
            onChange={(e) => { if (e.target.value) applyAllocationKey(e.target.value); }}
          >
            <option value="">— Manuell eingeben —</option>
            {allocationKeys.map((k) => (
              <option key={k.id} value={k.id}>{k.name}</option>
            ))}
          </select>
        </div>
      )}

      {/* Split-Zeilen */}
      <div className="space-y-2">
        {splits.map((s, i) => (
          <div key={i} className="flex items-center gap-2">
            <select
              className="flex-1 rounded-soft-xs border border-soft-line bg-soft-surface px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
              value={s.cost_center_id}
              onChange={(e) => updateSplit(i, "cost_center_id", e.target.value)}
            >
              {costCenters.map((cc) => (
                <option key={cc.id} value={cc.id}>{cc.name} ({cc.code})</option>
              ))}
            </select>
            <div className="relative w-24">
              <input
                type="number"
                min={0}
                max={100}
                step={0.1}
                className="w-full rounded-soft-xs border border-soft-line bg-soft-surface px-3 py-2 text-sm pr-7 numeric focus:outline-none focus:ring-2 focus:ring-soft-accent"
                value={s.prozent}
                onChange={(e) => updateSplit(i, "prozent", e.target.value)}
              />
              <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-soft-ink3 font-sans">%</span>
            </div>
            <span className="text-xs text-soft-ink3 w-20 text-right shrink-0 numeric">
              {formatEur(Math.round(betrag * (s.prozent || 0) / 100 * 100) / 100)}
            </span>
            <button
              type="button"
              onClick={() => removeRow(i)}
              className="text-soft-ink4 hover:text-soft-crit transition-colors"
              disabled={splits.length <= 1}
            >
              ×
            </button>
          </div>
        ))}
      </div>

      {/* Summenbalken */}
      <div>
        <div className="flex justify-between text-xs mb-1">
          <span className={`font-medium numeric ${summeOk ? "text-soft-ok" : "text-soft-crit"}`}>
            {summe.toFixed(1)} % <span className="font-sans">von</span> 100 %
          </span>
          {!summeOk && (
            <span className="text-soft-crit numeric">
              {summe > 100 ? `${(summe - 100).toFixed(1)} % ` : `${(100 - summe).toFixed(1)} % `}
              <span className="font-sans">{summe > 100 ? 'zu viel' : 'fehlen'}</span>
            </span>
          )}
        </div>
        <div className="h-1.5 rounded-full bg-soft-line2 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${summeOk ? "bg-soft-ok" : summe > 100 ? "bg-soft-crit" : "bg-soft-warn"}`}
            style={{ width: `${Math.min(summe, 100)}%` }}
          />
        </div>
      </div>

      <button
        type="button"
        onClick={addRow}
        className="text-xs text-soft-accent hover:text-soft-accentDark hover:underline"
        disabled={costCenters.length === 0}
      >
        + Weitere Kostenstelle
      </button>

      {/* Als Buchungsregel speichern */}
      <div className="rounded-soft-xs border border-soft-line bg-soft-line2 p-3 space-y-2">
        <label className="flex items-center gap-2 text-sm text-soft-ink cursor-pointer">
          <input
            type="checkbox"
            checked={saveAsRule}
            onChange={(e) => setSaveAsRule(e.target.checked)}
            className="rounded border-soft-line"
          />
          Als Buchungsregel speichern (für künftige Importe)
        </label>
        {saveAsRule && (
          <div className="space-y-2 pl-6">
            <input
              type="text"
              placeholder="Name der Regel (z. B. Miete Büro)"
              className="w-full rounded-soft-xs border border-soft-line bg-soft-surface px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
              value={ruleName}
              onChange={(e) => setRuleName(e.target.value)}
            />
            <input
              type="text"
              placeholder={`Auftraggeber enthält… (z. B. "${auftraggeber ?? ""}")`}
              className="w-full rounded-soft-xs border border-soft-line bg-soft-surface px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
              value={ruleMatchAuftraggeber}
              onChange={(e) => setRuleMatchAuftraggeber(e.target.value)}
            />
            <p className="text-xs text-soft-ink3">Der Kostenbereich „{kostenbereichBezeichnung ?? "beliebig"}&ldquo; wird ebenfalls als Bedingung gespeichert.</p>
          </div>
        )}
      </div>

      {/* Aktionen */}
      <div className="flex gap-2">
        <Button variant="primary" size="sm" loading={loading} disabled={!summeOk} onClick={handleSave}>
          Speichern
        </Button>
        <Button variant="secondary" size="sm" onClick={() => { setEditing(false); setSaveAsRule(false); }}>
          Abbrechen
        </Button>
      </div>
    </div>
  );
}
