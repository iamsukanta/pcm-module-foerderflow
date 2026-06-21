"use client";

import { useState, useEffect, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useToast } from "@/components/ui/ToastProvider";
import { SearchInput } from "@/components/ui/SearchInput";
import { useDebounce } from "@/lib/hooks/useDebounce";
import { useKostenbereiche } from "@/lib/hooks/useKostenbereiche";
import { Pencil, Trash2, AlertTriangle, Plus, Check, X, Repeat } from "lucide-react";

type CostCenter = { id: string; name: string; code: string };

type RuleSplit = {
  cost_center: CostCenter;
  prozent: string | number | { toString(): string };
};

type BookingRule = {
  id: string;
  name: string;
  aktiv: boolean;
  prioritaet: number;
  match_auftraggeber: string | null;
  match_verwendungszweck: string | null;
  match_kostenbereich_id: string | null;
  match_kostenbereich?: { id: string; code: string; bezeichnung: string } | null;
  set_kostenbereich_id: string | null;
  set_kostenbereich?: { id: string; code: string; bezeichnung: string } | null;
  funding_measure_id: string | null;
  funding_measure?: { id: string; name: string } | null;
  splits: RuleSplit[];
};

type NewRuleSplit = {
  cost_center_id: string;
  prozent: number;
  /// E2 (2026-05-20): optionaler Maßnahmen-Bezug pro Split
  funding_measure_id?: string | null;
  allocation_prozent?: number | null;
};

type MassnahmeOption = { id: string; name: string };

type Props = {
  initialRules: BookingRule[];
  costCenters: CostCenter[];
  fundingMeasures?: MassnahmeOption[];
};

export function BuchungsregelnClient({
  initialRules,
  costCenters,
  fundingMeasures: initialMassnahmen,
}: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  const [rules, setRules] = useState<BookingRule[]>(initialRules);
  const [showForm, setShowForm] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [massnahmen, setMassnahmen] = useState<MassnahmeOption[]>(initialMassnahmen ?? []);
  const [searchQuery, setSearchQuery] = useState("");

  // Edit-Modus State
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editMatchAuftraggeber, setEditMatchAuftraggeber] = useState("");
  const [editMatchVerwendung, setEditMatchVerwendung] = useState("");
  const [editMatchKostenbereichId, setEditMatchKostenbereichId] = useState("");
  const [editSetKostenbereichId, setEditSetKostenbereichId] = useState("");
  const [editFundingMeasureId, setEditFundingMeasureId] = useState("");
  const [editSplits, setEditSplits] = useState<NewRuleSplit[]>([]);
  const [editSaving, setEditSaving] = useState(false);

  // Kostenbereich-Taxonomie für Match-Selects
  const { obergruppen: kostenbereichGruppen } = useKostenbereiche();

  // Neues Regel-Formular State
  const [name, setName] = useState("");
  const [matchAuftraggeber, setMatchAuftraggeber] = useState("");
  const [matchAuftraggeberExact, setMatchAuftraggeberExact] = useState(false);
  const [matchVerwendung, setMatchVerwendung] = useState("");
  const [matchKostenbereichId, setMatchKostenbereichId] = useState("");
  const [matchIbanPartner, setMatchIbanPartner] = useState("");
  const [matchBetragMin, setMatchBetragMin] = useState("");
  const [matchBetragMax, setMatchBetragMax] = useState("");
  const [matchDatumVon, setMatchDatumVon] = useState("");
  const [matchDatumBis, setMatchDatumBis] = useState("");
  const [showAdvancedMatch, setShowAdvancedMatch] = useState(false);
  const [setKostenbereichId, setSetKostenbereichId] = useState("");
  const [fundingMeasureId, setFundingMeasureId] = useState("");
  const [formSplits, setFormSplits] = useState<NewRuleSplit[]>([
    { cost_center_id: costCenters[0]?.id ?? "", prozent: 100 },
  ]);

  const summe = formSplits.reduce((a, s) => a + (s.prozent || 0), 0);
  const summeOk = Math.abs(summe - 100) <= 0.01;

  type PreviewResult = {
    matched_count: number;
    sample: {
      id: string;
      datum: string;
      betrag: string;
      auftraggeber: string | null;
      verwendungszweck: string | null;
      kostenbereich: { bezeichnung: string } | null;
    }[];
    total_betrag: string;
  };
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const [backfillRule, setBackfillRule] = useState<{
    id: string;
    name: string;
    count: number;
  } | null>(null);
  const [backfillLoading, setBackfillLoading] = useState(false);

  async function startBackfill(rule: BookingRule) {
    setBackfillLoading(true);
    try {
      const res = await fetch(`/api/protected/buchungsregeln/${rule.id}/backfill`);
      const json = (await res.json()) as { data?: { count: number }; error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Fehler beim Vorbereiten des Backfills.");
        return;
      }
      setBackfillRule({ id: rule.id, name: rule.name, count: json.data?.count ?? 0 });
    } catch {
      toast.error("Netzwerkfehler.");
    } finally {
      setBackfillLoading(false);
    }
  }

  async function performBackfill() {
    if (!backfillRule) return;
    setBackfillLoading(true);
    try {
      const res = await fetch(`/api/protected/buchungsregeln/${backfillRule.id}/backfill`, {
        method: "POST",
      });
      const json = (await res.json()) as {
        data?: { matched: number; skipped: number };
        error?: string;
      };
      if (!res.ok) {
        toast.error(json.error ?? "Backfill fehlgeschlagen.");
        return;
      }
      const matched = json.data?.matched ?? 0;
      const skipped = json.data?.skipped ?? 0;
      toast.success(
        `Backfill: ${matched} zugeordnet${skipped > 0 ? `, ${skipped} übersprungen` : ""}.`,
      );
      setBackfillRule(null);
      router.refresh();
    } catch {
      toast.error("Netzwerkfehler.");
    } finally {
      setBackfillLoading(false);
    }
  }

  async function handlePreview() {
    setPreviewLoading(true);
    try {
      const res = await fetch("/api/protected/buchungsregeln/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          match_auftraggeber: matchAuftraggeber || null,
          match_auftraggeber_exact: matchAuftraggeberExact,
          match_verwendungszweck: matchVerwendung || null,
          match_kostenbereich_id: matchKostenbereichId || null,
          match_iban_partner: matchIbanPartner || null,
          match_betrag_min: matchBetragMin || null,
          match_betrag_max: matchBetragMax || null,
          match_datum_von: matchDatumVon || null,
          match_datum_bis: matchDatumBis || null,
        }),
      });
      const json = (await res.json()) as { data?: PreviewResult; error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Fehler bei der Vorschau.");
        return;
      }
      setPreview(json.data ?? null);
    } catch {
      toast.error("Netzwerkfehler.");
    } finally {
      setPreviewLoading(false);
    }
  }

  const editSumme = editSplits.reduce((a, s) => a + (s.prozent || 0), 0);
  const editSummeOk = Math.abs(editSumme - 100) <= 0.01;

  useEffect(() => {
    // Nur fetchen wenn nicht schon Server-seitig übergeben
    if (initialMassnahmen && initialMassnahmen.length > 0) return;
    fetch("/api/protected/foerdermassnahmen?status=AKTIV")
      .then((r) => r.json())
      .then((json: { data?: MassnahmeOption[] }) => setMassnahmen(json.data ?? []))
      .catch(() => {});
  }, [initialMassnahmen]);

  // Prefill aus URL: Cockpit kann via ?prefill=base64-json eine Inferenz übergeben
  useEffect(() => {
    const raw = searchParams.get("prefill");
    if (!raw) return;
    try {
      const data = JSON.parse(decodeURIComponent(atob(raw))) as {
        match_auftraggeber?: string | null;
        match_auftraggeber_exact?: boolean;
        match_kostenbereich_id?: string | null;
        _basis_count?: number;
        _total_in_selection?: number;
      };
      setShowForm(true);
      if (data.match_auftraggeber) setMatchAuftraggeber(data.match_auftraggeber);
      if (data.match_auftraggeber_exact) setMatchAuftraggeberExact(true);
      if (data.match_kostenbereich_id) setMatchKostenbereichId(data.match_kostenbereich_id);
      if (data.match_auftraggeber) {
        setName(`Auto: ${data.match_auftraggeber}`);
      }
      toast.success(
        `Regel-Vorschlag aus ${data._basis_count ?? "?"} TXs übernommen — bitte prüfen + Splits ergänzen.`,
      );
      // URL aufräumen, damit ein Reload nicht erneut prefilled.
      router.replace("/dashboard/buchungsregeln");
    } catch {
      // ignore broken prefill
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const debouncedSearch = useDebounce(searchQuery, 300);

  const filteredRules = useMemo(() => {
    if (!debouncedSearch.trim()) return rules;

    const query = debouncedSearch.toLowerCase();
    return rules.filter(
      (rule) =>
        rule.name.toLowerCase().includes(query) ||
        rule.match_auftraggeber?.toLowerCase().includes(query) ||
        rule.match_verwendungszweck?.toLowerCase().includes(query) ||
        rule.match_kostenbereich?.bezeichnung.toLowerCase().includes(query) ||
        rule.set_kostenbereich?.bezeichnung.toLowerCase().includes(query) ||
        rule.funding_measure?.name.toLowerCase().includes(query),
    );
  }, [rules, debouncedSearch]);

  function startEdit(rule: BookingRule) {
    setEditingId(rule.id);
    setEditName(rule.name);
    setEditMatchAuftraggeber(rule.match_auftraggeber ?? "");
    setEditMatchVerwendung(rule.match_verwendungszweck ?? "");
    setEditMatchKostenbereichId(rule.match_kostenbereich_id ?? "");
    setEditSetKostenbereichId(rule.set_kostenbereich_id ?? "");
    setEditFundingMeasureId(rule.funding_measure_id ?? "");
    setEditSplits(
      rule.splits.map((s) => ({
        cost_center_id: s.cost_center.id,
        prozent: Number(s.prozent),
      })),
    );
  }

  function cancelEdit() {
    setEditingId(null);
  }

  function addEditSplitRow() {
    const rem = Math.max(0, 100 - editSumme);
    setEditSplits((p) => [
      ...p,
      { cost_center_id: costCenters[0]?.id ?? "", prozent: parseFloat(rem.toFixed(3)) },
    ]);
  }

  function removeEditSplitRow(i: number) {
    setEditSplits((p) => p.filter((_, idx) => idx !== i));
  }

  async function handleEditSave(ruleId: string) {
    if (!editName.trim()) {
      toast.error("Name ist erforderlich.");
      return;
    }
    if (!editSummeOk) {
      toast.error(`Prozent-Summe muss 100% ergeben (aktuell ${editSumme.toFixed(1)}%).`);
      return;
    }
    setEditSaving(true);
    try {
      const res = await fetch(`/api/protected/buchungsregeln/${ruleId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: editName.trim(),
          match_auftraggeber: editMatchAuftraggeber.trim() || undefined,
          match_verwendungszweck: editMatchVerwendung.trim() || undefined,
          match_kostenbereich_id: editMatchKostenbereichId || null,
          set_kostenbereich_id: editSetKostenbereichId || null,
          funding_measure_id: editFundingMeasureId || undefined,
          splits: editSplits,
        }),
      });
      const json = (await res.json()) as { error?: string; data?: BookingRule };
      if (!res.ok) {
        toast.error(json.error ?? "Fehler.");
        return;
      }
      if (json.data) {
        setRules((prev) => prev.map((r) => (r.id === ruleId ? json.data! : r)));
      }
      toast.success("Buchungsregel aktualisiert.");
      setEditingId(null);
    } catch {
      toast.error("Netzwerkfehler.");
    } finally {
      setEditSaving(false);
    }
  }

  function addSplitRow() {
    const rem = Math.max(0, 100 - summe);
    setFormSplits((p) => [
      ...p,
      { cost_center_id: costCenters[0]?.id ?? "", prozent: parseFloat(rem.toFixed(3)) },
    ]);
  }

  function removeSplitRow(i: number) {
    setFormSplits((p) => p.filter((_, idx) => idx !== i));
  }

  async function handleSave() {
    if (!name.trim()) {
      toast.error("Name ist erforderlich.");
      return;
    }
    if (!summeOk) {
      toast.error(`Prozent-Summe muss 100% ergeben (aktuell ${summe.toFixed(1)}%).`);
      return;
    }
    setSaving(true);
    try {
      const res = await fetch("/api/protected/buchungsregeln", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          match_auftraggeber: matchAuftraggeber.trim() || undefined,
          match_verwendungszweck: matchVerwendung.trim() || undefined,
          match_kostenbereich_id: matchKostenbereichId || null,
          match_auftraggeber_exact: matchAuftraggeberExact,
          match_iban_partner: matchIbanPartner || null,
          match_betrag_min: matchBetragMin || null,
          match_betrag_max: matchBetragMax || null,
          match_datum_von: matchDatumVon || null,
          match_datum_bis: matchDatumBis || null,
          set_kostenbereich_id: setKostenbereichId || null,
          funding_measure_id: fundingMeasureId || undefined,
          splits: formSplits,
        }),
      });
      const json = (await res.json()) as { error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Fehler.");
        return;
      }
      toast.success("Buchungsregel gespeichert.");
      setShowForm(false);
      setName("");
      setMatchAuftraggeber("");
      setMatchVerwendung("");
      setMatchKostenbereichId("");
      setSetKostenbereichId("");
      setFundingMeasureId("");
      setMatchAuftraggeberExact(false);
      setMatchIbanPartner("");
      setMatchBetragMin("");
      setMatchBetragMax("");
      setMatchDatumVon("");
      setMatchDatumBis("");
      setShowAdvancedMatch(false);
      setFormSplits([{ cost_center_id: costCenters[0]?.id ?? "", prozent: 100 }]);
      router.refresh();
    } catch {
      toast.error("Netzwerkfehler.");
    } finally {
      setSaving(false);
    }
  }

  async function toggleAktiv(rule: BookingRule) {
    const res = await fetch(`/api/protected/buchungsregeln/${rule.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ aktiv: !rule.aktiv }),
    });
    if (res.ok) {
      setRules((prev) => prev.map((r) => (r.id === rule.id ? { ...r, aktiv: !r.aktiv } : r)));
    }
  }

  async function handleDelete(id: string) {
    const res = await fetch(`/api/protected/buchungsregeln/${id}`, { method: "DELETE" });
    if (res.ok) {
      setRules((prev) => prev.filter((r) => r.id !== id));
      toast.success("Regel gelöscht.");
    }
    setDeletingId(null);
  }

  return (
    <div className="space-y-4">
      {/* Search input */}
      <SearchInput
        value={searchQuery}
        onChange={setSearchQuery}
        placeholder="Suche nach Regelname oder Bedingungen..."
        className="mb-4"
      />

      {/* Neue Regel */}
      {!showForm ? (
        <Button variant="primary" size="sm" onClick={() => setShowForm(true)}>
          <Plus className="h-4 w-4 mr-1" />
          Neue Buchungsregel
        </Button>
      ) : (
        <div className="rounded-soft-sm border border-soft-accent bg-soft-accentWash p-5 space-y-4">
          <h2 className="text-sm font-semibold text-soft-ink">Neue Buchungsregel</h2>

          <div>
            <label className="block text-xs text-soft-ink3 mb-1">Name *</label>
            <input
              type="text"
              className="w-full rounded-soft-xs border border-soft-line bg-soft-surface px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="z. B. Miete Büro"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs text-soft-ink3 mb-1">Auftraggeber enthält</label>
              <input
                type="text"
                className="w-full rounded-soft-xs border border-soft-line bg-soft-surface px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                value={matchAuftraggeber}
                onChange={(e) => setMatchAuftraggeber(e.target.value)}
                placeholder="z. B. Stadtwerke"
              />
            </div>
            <div>
              <label className="block text-xs text-soft-ink3 mb-1">Verwendungszweck enthält</label>
              <input
                type="text"
                className="w-full rounded-soft-xs border border-soft-line bg-soft-surface px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                value={matchVerwendung}
                onChange={(e) => setMatchVerwendung(e.target.value)}
                placeholder="z. B. Miete"
              />
            </div>
            <div>
              <label className="block text-xs text-soft-ink3 mb-1">Match: Kostenbereich</label>
              <select
                className="w-full rounded-soft-xs border border-soft-line bg-soft-surface px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                value={matchKostenbereichId}
                onChange={(e) => setMatchKostenbereichId(e.target.value)}
              >
                <option value="">— alle Kostenbereiche —</option>
                {kostenbereichGruppen.map((g) => (
                  <optgroup key={g.id} label={g.bezeichnung}>
                    {g.kinder.map((k) => (
                      <option key={k.id} value={k.id}>
                        {k.bezeichnung}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>
          </div>

          <div>
            <button
              type="button"
              onClick={() => setShowAdvancedMatch((s) => !s)}
              className="text-xs text-soft-accent hover:underline"
            >
              {showAdvancedMatch
                ? "− Erweiterte Bedingungen ausblenden"
                : "+ Erweiterte Bedingungen (IBAN, Betrag, Datum)"}
            </button>
            {showAdvancedMatch && (
              <div className="mt-2 rounded-soft-sm border border-soft-line bg-soft-surface p-3 grid grid-cols-1 sm:grid-cols-3 gap-3">
                <label className="inline-flex items-center gap-2 text-xs text-soft-ink2 sm:col-span-3">
                  <input
                    type="checkbox"
                    className="rounded border-soft-line"
                    checked={matchAuftraggeberExact}
                    onChange={(e) => setMatchAuftraggeberExact(e.target.checked)}
                  />
                  Auftraggeber exakt vergleichen (statt Substring)
                </label>
                <div>
                  <label className="block text-xs text-soft-ink3 mb-1">IBAN-Partner (exakt)</label>
                  <input
                    type="text"
                    value={matchIbanPartner}
                    onChange={(e) => setMatchIbanPartner(e.target.value)}
                    placeholder="DE…"
                    className="w-full rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-soft-accent"
                  />
                </div>
                <div>
                  <label className="block text-xs text-soft-ink3 mb-1">Betrag ab €</label>
                  <input
                    type="number"
                    step="0.01"
                    value={matchBetragMin}
                    onChange={(e) => setMatchBetragMin(e.target.value)}
                    className="w-full rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                  />
                </div>
                <div>
                  <label className="block text-xs text-soft-ink3 mb-1">Betrag bis €</label>
                  <input
                    type="number"
                    step="0.01"
                    value={matchBetragMax}
                    onChange={(e) => setMatchBetragMax(e.target.value)}
                    className="w-full rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                  />
                </div>
                <div>
                  <label className="block text-xs text-soft-ink3 mb-1">Datum von</label>
                  <input
                    type="date"
                    value={matchDatumVon}
                    onChange={(e) => setMatchDatumVon(e.target.value)}
                    className="w-full rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                  />
                </div>
                <div>
                  <label className="block text-xs text-soft-ink3 mb-1">Datum bis</label>
                  <input
                    type="date"
                    value={matchDatumBis}
                    onChange={(e) => setMatchDatumBis(e.target.value)}
                    className="w-full rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                  />
                </div>
                <p className="text-xs text-soft-ink4 sm:col-span-3 italic">
                  Betrag-Range vergleicht den Brutto-Wert ohne Vorzeichen — eine Regel mit 80–120€
                  matcht sowohl Einnahmen +100€ als auch Ausgaben −100€.
                </p>
              </div>
            )}
          </div>

          <div>
            <label className="block text-xs text-soft-ink3 mb-1">
              Kostenbereich setzen (überschreibt Heuristik)
            </label>
            <select
              className="w-full sm:w-72 rounded-soft-xs border border-soft-line bg-soft-surface px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
              value={setKostenbereichId}
              onChange={(e) => setSetKostenbereichId(e.target.value)}
            >
              <option value="">— Heuristik-Wert behalten —</option>
              {kostenbereichGruppen.map((g) => (
                <optgroup key={g.id} label={g.bezeichnung}>
                  {g.kinder.map((k) => (
                    <option key={k.id} value={k.id}>
                      {k.bezeichnung}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs text-soft-ink3 mb-1">
              Fördermassnahme automatisch zuordnen
            </label>
            <select
              className="w-full sm:w-72 rounded-soft-xs border border-soft-line bg-soft-surface px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
              value={fundingMeasureId}
              onChange={(e) => setFundingMeasureId(e.target.value)}
            >
              <option value="">— keine automatische Zuordnung —</option>
              {massnahmen.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs text-soft-ink3 mb-2">Kostenstellen-Aufteilung *</label>
            <p className="text-[11px] text-soft-ink4 mb-2 italic">
              Förder-Zuordnung kann pro KST gesetzt werden (M:N seit 2026-05-20). Leer = Fallback auf
              die Maßnahme aus dem oberen Dropdown. Bei FamEV-Pattern (Z-GF/Z-HR ohne Förderung) leer
              lassen.
            </p>
            <div className="space-y-2">
              {formSplits.map((s, i) => (
                <div key={i} className="space-y-1">
                  <div className="flex items-center gap-2">
                    <select
                      className="flex-1 rounded-soft-xs border border-soft-line bg-soft-surface px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                      value={s.cost_center_id}
                      onChange={(e) =>
                        setFormSplits((p) =>
                          p.map((x, idx) =>
                            idx === i ? { ...x, cost_center_id: e.target.value } : x,
                          ),
                        )
                      }
                    >
                      {costCenters.map((cc) => (
                        <option key={cc.id} value={cc.id}>
                          {cc.name} ({cc.code})
                        </option>
                      ))}
                    </select>
                    <div className="relative w-24">
                      <input
                        type="number"
                        min={0}
                        max={100}
                        step={0.1}
                        className="w-full rounded-soft-xs border border-soft-line bg-white px-3 py-2 text-sm pr-7 focus:outline-none focus:ring-2 focus:ring-soft-accent"
                        value={s.prozent}
                        onChange={(e) =>
                          setFormSplits((p) =>
                            p.map((x, idx) =>
                              idx === i ? { ...x, prozent: Number(e.target.value) } : x,
                            ),
                          )
                        }
                      />
                      <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-soft-ink4">
                        %
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeSplitRow(i)}
                      disabled={formSplits.length <= 1}
                      className="text-soft-ink4 hover:text-soft-crit transition-colors"
                    >
                      ×
                    </button>
                  </div>
                  {/* Förder-Zuordnung pro KST (E2-Migration 2026-05-20) */}
                  <div className="flex items-center gap-2 pl-3">
                    <span className="text-[10px] text-soft-ink4">↳ Förder-Zuordnung:</span>
                    <select
                      className="flex-1 max-w-[280px] rounded-soft-xs border border-soft-line bg-white px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-soft-accent"
                      value={s.funding_measure_id ?? ""}
                      onChange={(e) =>
                        setFormSplits((p) =>
                          p.map((x, idx) =>
                            idx === i ? { ...x, funding_measure_id: e.target.value || null } : x,
                          ),
                        )
                      }
                    >
                      <option value="">— Fallback auf Regel-Maßnahme / keine Förderung —</option>
                      {massnahmen.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.name}
                        </option>
                      ))}
                    </select>
                    {s.funding_measure_id && (
                      <div className="relative w-20">
                        <input
                          type="number"
                          min={0}
                          max={100}
                          step={0.1}
                          placeholder="100"
                          className="w-full rounded-soft-xs border border-soft-line bg-white px-2 py-1 text-xs pr-6 focus:outline-none focus:ring-1 focus:ring-soft-accent"
                          value={s.allocation_prozent ?? ""}
                          onChange={(e) =>
                            setFormSplits((p) =>
                              p.map((x, idx) =>
                                idx === i
                                  ? {
                                      ...x,
                                      allocation_prozent:
                                        e.target.value === "" ? null : Number(e.target.value),
                                    }
                                  : x,
                              ),
                            )
                          }
                          title="Förder-Prozent (Default 100 = vollständig)"
                        />
                        <span className="absolute right-1.5 top-1/2 -translate-y-1/2 text-[10px] text-soft-ink4">
                          %
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-2">
              <div className={`text-xs mb-1 ${summeOk ? "text-soft-ok" : "text-soft-crit"}`}>
                {summe.toFixed(1)} % von 100 %
              </div>
              <div className="h-1.5 rounded-full bg-soft-line2">
                <div
                  className={`h-full rounded-full ${summeOk ? "bg-soft-ok" : "bg-soft-warn"}`}
                  style={{ width: `${Math.min(summe, 100)}%` }}
                />
              </div>
            </div>
            <button
              type="button"
              onClick={addSplitRow}
              className="mt-2 text-xs text-soft-accent hover:underline"
            >
              + Weitere Kostenstelle
            </button>
          </div>

          <div className="flex gap-2 flex-wrap">
            <Button
              variant="primary"
              size="sm"
              loading={saving}
              disabled={!summeOk}
              onClick={handleSave}
            >
              Speichern
            </Button>
            <Button
              variant="secondary"
              size="sm"
              loading={previewLoading}
              onClick={() => void handlePreview()}
              disabled={
                !matchAuftraggeber &&
                !matchVerwendung &&
                !matchKostenbereichId &&
                !matchIbanPartner &&
                !matchBetragMin &&
                !matchBetragMax &&
                !matchDatumVon &&
                !matchDatumBis
              }
            >
              Vorschau
            </Button>
            <Button variant="secondary" size="sm" onClick={() => setShowForm(false)}>
              Abbrechen
            </Button>
          </div>

          {preview && (
            <div className="mt-3 rounded-soft-sm border border-soft-line bg-soft-surfaceAlt p-3 text-sm space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-medium text-soft-ink">
                  Diese Regel würde <b>{preview.matched_count}</b> Transaktion(en) matchen
                  {preview.matched_count > 0 && (
                    <>
                      {" "}
                      · Summe{" "}
                      {Number(preview.total_betrag).toLocaleString("de-DE", {
                        style: "currency",
                        currency: "EUR",
                      })}
                    </>
                  )}
                </span>
                <button
                  type="button"
                  onClick={() => setPreview(null)}
                  className="text-soft-ink4 hover:text-soft-accent"
                  aria-label="Vorschau schließen"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              {preview.sample.length > 0 && (
                <ul className="space-y-1 text-xs text-soft-ink2">
                  {preview.sample.map((s) => (
                    <li key={s.id} className="flex gap-2 truncate">
                      <span className="text-soft-ink4 shrink-0">{s.datum}</span>
                      <span className="truncate">{s.auftraggeber ?? "—"}</span>
                      <span className="ml-auto font-mono shrink-0">
                        {Number(s.betrag).toLocaleString("de-DE", {
                          style: "currency",
                          currency: "EUR",
                        })}
                      </span>
                    </li>
                  ))}
                  {preview.matched_count > preview.sample.length && (
                    <li className="text-soft-ink4 italic">
                      … und {preview.matched_count - preview.sample.length} weitere
                    </li>
                  )}
                </ul>
              )}
            </div>
          )}
        </div>
      )}

      {/* Regeln-Liste */}
      {rules.length === 0 ? (
        <div className="text-center py-12 text-soft-ink4 text-sm">
          Noch keine Buchungsregeln. Lege eine Regel an und sie wird beim nächsten Import automatisch
          angewandt.
        </div>
      ) : filteredRules.length === 0 ? (
        <div className="text-center py-12 text-soft-ink4 text-sm">
          Keine Buchungsregeln gefunden für „{searchQuery}&ldquo;.
        </div>
      ) : (
        <div className="space-y-3">
          {filteredRules.map((rule) => (
            <div
              key={rule.id}
              className={`rounded-soft-sm border bg-white p-4 ${!rule.aktiv ? "opacity-50" : ""}`}
            >
              {editingId === rule.id ? (
                /* ── Edit-Modus ── */
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs text-soft-ink3 mb-1">Name *</label>
                    <input
                      type="text"
                      className="w-full rounded-soft-xs border border-soft-line bg-soft-surface px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                    />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs text-soft-ink3 mb-1">
                        Auftraggeber enthält
                      </label>
                      <input
                        type="text"
                        className="w-full rounded-soft-xs border border-soft-line bg-soft-surface px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                        value={editMatchAuftraggeber}
                        onChange={(e) => setEditMatchAuftraggeber(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-soft-ink3 mb-1">
                        Verwendungszweck enthält
                      </label>
                      <input
                        type="text"
                        className="w-full rounded-soft-xs border border-soft-line bg-soft-surface px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                        value={editMatchVerwendung}
                        onChange={(e) => setEditMatchVerwendung(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-soft-ink3 mb-1">Match: Kostenbereich</label>
                      <select
                        className="w-full rounded-soft-xs border border-soft-line bg-soft-surface px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                        value={editMatchKostenbereichId}
                        onChange={(e) => setEditMatchKostenbereichId(e.target.value)}
                      >
                        <option value="">— alle Kostenbereiche —</option>
                        {kostenbereichGruppen.map((g) => (
                          <optgroup key={g.id} label={g.bezeichnung}>
                            {g.kinder.map((k) => (
                              <option key={k.id} value={k.id}>
                                {k.bezeichnung}
                              </option>
                            ))}
                          </optgroup>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs text-soft-ink3 mb-1">
                      Kostenbereich setzen (überschreibt Heuristik)
                    </label>
                    <select
                      className="w-full sm:w-72 rounded-soft-xs border border-soft-line bg-soft-surface px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                      value={editSetKostenbereichId}
                      onChange={(e) => setEditSetKostenbereichId(e.target.value)}
                    >
                      <option value="">— Heuristik-Wert behalten —</option>
                      {kostenbereichGruppen.map((g) => (
                        <optgroup key={g.id} label={g.bezeichnung}>
                          {g.kinder.map((k) => (
                            <option key={k.id} value={k.id}>
                              {k.bezeichnung}
                            </option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-soft-ink3 mb-1">Fördermassnahme</label>
                    <select
                      className="w-full sm:w-72 rounded-soft-xs border border-soft-line bg-soft-surface px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                      value={editFundingMeasureId}
                      onChange={(e) => setEditFundingMeasureId(e.target.value)}
                    >
                      <option value="">— keine automatische Zuordnung —</option>
                      {massnahmen.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-soft-ink3 mb-2">
                      Kostenstellen-Aufteilung *
                    </label>
                    <div className="space-y-2">
                      {editSplits.map((s, i) => (
                        <div key={i} className="flex items-center gap-2">
                          <select
                            className="flex-1 rounded-soft-xs border border-soft-line bg-soft-surface px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                            value={s.cost_center_id}
                            onChange={(e) =>
                              setEditSplits((p) =>
                                p.map((x, idx) =>
                                  idx === i ? { ...x, cost_center_id: e.target.value } : x,
                                ),
                              )
                            }
                          >
                            {costCenters.map((cc) => (
                              <option key={cc.id} value={cc.id}>
                                {cc.name} ({cc.code})
                              </option>
                            ))}
                          </select>
                          <div className="relative w-24">
                            <input
                              type="number"
                              min={0}
                              max={100}
                              step={0.1}
                              className="w-full rounded-soft-xs border border-soft-line bg-white px-3 py-2 text-sm pr-7 focus:outline-none focus:ring-2 focus:ring-soft-accent"
                              value={s.prozent}
                              onChange={(e) =>
                                setEditSplits((p) =>
                                  p.map((x, idx) =>
                                    idx === i ? { ...x, prozent: Number(e.target.value) } : x,
                                  ),
                                )
                              }
                            />
                            <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-soft-ink4">
                              %
                            </span>
                          </div>
                          <button
                            type="button"
                            onClick={() => removeEditSplitRow(i)}
                            disabled={editSplits.length <= 1}
                            className="text-soft-ink4 hover:text-soft-crit transition-colors"
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>
                    <div className="mt-2">
                      <div
                        className={`text-xs mb-1 ${editSummeOk ? "text-soft-ok" : "text-soft-crit"}`}
                      >
                        {editSumme.toFixed(1)} % von 100 %
                      </div>
                      <div className="h-1.5 rounded-full bg-soft-line2">
                        <div
                          className={`h-full rounded-full ${editSummeOk ? "bg-soft-ok" : "bg-soft-warn"}`}
                          style={{ width: `${Math.min(editSumme, 100)}%` }}
                        />
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={addEditSplitRow}
                      className="mt-2 text-xs text-soft-accent hover:underline"
                    >
                      + Weitere Kostenstelle
                    </button>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="primary"
                      size="sm"
                      loading={editSaving}
                      disabled={!editSummeOk}
                      onClick={() => void handleEditSave(rule.id)}
                    >
                      <Check className="h-3.5 w-3.5 mr-1" />
                      Speichern
                    </Button>
                    <Button variant="secondary" size="sm" onClick={cancelEdit}>
                      <X className="h-3.5 w-3.5 mr-1" />
                      Abbrechen
                    </Button>
                  </div>
                </div>
              ) : (
                /* ── Lese-Modus ── */
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className="font-medium text-soft-ink text-sm">{rule.name}</span>
                      {!rule.aktiv && (
                        <span className="text-xs bg-soft-line2 text-soft-ink3 px-2 py-0.5 rounded-full">
                          Inaktiv
                        </span>
                      )}
                      {rule.funding_measure && (
                        <span className="text-xs bg-soft-okSoft text-soft-ok border border-soft-ok/20 px-2 py-0.5 rounded-full">
                          Massnahme: {rule.funding_measure.name}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-soft-ink4 space-y-0.5">
                      {rule.match_auftraggeber && (
                        <p>
                          Auftraggeber enthält:{" "}
                          <span className="text-soft-ink2 font-mono">{rule.match_auftraggeber}</span>
                        </p>
                      )}
                      {rule.match_verwendungszweck && (
                        <p>
                          Verwendungszweck enthält:{" "}
                          <span className="text-soft-ink2 font-mono">
                            {rule.match_verwendungszweck}
                          </span>
                        </p>
                      )}
                      {rule.match_kostenbereich && (
                        <p>
                          Match-Kostenbereich:{" "}
                          <span className="text-soft-ink2">
                            {rule.match_kostenbereich.bezeichnung}
                          </span>
                        </p>
                      )}
                      {rule.set_kostenbereich && (
                        <p>
                          Setzt Kostenbereich →{" "}
                          <span className="text-soft-accent font-medium">
                            {rule.set_kostenbereich.bezeichnung}
                          </span>
                        </p>
                      )}
                      {!rule.match_auftraggeber &&
                        !rule.match_verwendungszweck &&
                        !rule.match_kostenbereich && (
                          <p className="text-soft-warn flex items-center gap-1">
                            <AlertTriangle className="h-3.5 w-3.5" />
                            Keine Bedingungen — gilt für alle Transaktionen
                          </p>
                        )}
                    </div>
                    <div className="flex gap-2 mt-2 flex-wrap">
                      {rule.splits.map((s, i) => (
                        <span
                          key={i}
                          className="text-xs bg-soft-line2 text-soft-ink2 px-2 py-0.5 rounded-full"
                        >
                          {s.cost_center.name} {Number(s.prozent).toFixed(1)}%
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={() => toggleAktiv(rule)}
                      className={`relative inline-flex h-5 w-9 rounded-full transition-colors ${rule.aktiv ? "bg-soft-ok" : "bg-soft-line"}`}
                      title={rule.aktiv ? "Deaktivieren" : "Aktivieren"}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform mt-0.5 ${rule.aktiv ? "translate-x-4" : "translate-x-0.5"}`}
                      />
                    </button>
                    <button
                      type="button"
                      onClick={() => void startBackfill(rule)}
                      disabled={!rule.aktiv || backfillLoading}
                      className="p-1.5 text-soft-ink4 hover:text-soft-accent rounded transition-colors disabled:opacity-50"
                      title="Auf bestehende Transaktionen anwenden"
                    >
                      <Repeat className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => startEdit(rule)}
                      className="p-1.5 text-soft-ink4 hover:text-soft-accent rounded transition-colors"
                      title="Bearbeiten"
                    >
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setDeletingId(rule.id)}
                      className="p-1.5 text-soft-ink4 hover:text-soft-crit rounded transition-colors"
                      title="Löschen"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <ConfirmDialog
        open={!!deletingId}
        title="Buchungsregel löschen"
        description="Diese Buchungsregel wird gelöscht. Bestehende Zuordnungen bleiben erhalten."
        confirmLabel="Ja, löschen"
        variant="danger"
        onConfirm={() => deletingId && handleDelete(deletingId)}
        onCancel={() => setDeletingId(null)}
      />

      <ConfirmDialog
        open={!!backfillRule}
        title="Regel auf bestehende Transaktionen anwenden"
        description={
          backfillRule
            ? backfillRule.count === 0
              ? `Regel „${backfillRule.name}" trifft auf keine bestehende, noch nicht zugeordnete Transaktion. Nichts zu tun.`
              : `Regel „${backfillRule.name}" wird auf ${backfillRule.count} noch nicht zugeordnete Transaktion(en) angewandt. Bestehende Splits dieser TXs werden ersetzt.`
            : ""
        }
        confirmLabel={backfillRule?.count === 0 ? "OK" : "Anwenden"}
        variant="default"
        loading={backfillLoading}
        onConfirm={() => {
          if (backfillRule && backfillRule.count > 0) void performBackfill();
          else setBackfillRule(null);
        }}
        onCancel={() => setBackfillRule(null)}
      />
    </div>
  );
}
