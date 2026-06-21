"use client";

import { useState, useEffect, useCallback } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/ToastProvider";
import { Download, ChevronDown, ChevronRight, Users } from "lucide-react";
import { PageShell } from "@/components/ui/PageShell";

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────

type VzaeEintrag = {
  employee: { vorname: string; nachname: string; employee_code: string };
  vzae_gesamt: number;
  vzae_projekt: number;
  stunden_projekt: number;
  betrag_ag_brutto: number;
  prozent_kst: number;
};

type VzaeMonat = {
  monat: string;
  eintraege: VzaeEintrag[];
  summe_vzae_projekt: number;
  summe_betrag: number;
};

type VzaeUebersichtResponse = {
  massnahme: { name: string; laufzeit_von: string; laufzeit_bis: string };
  monate: VzaeMonat[];
  gesamt_betrag: number;
  gesamt_vzae_monate: number;
};

type PersonalkostenSollIst = {
  kostenart: string;
  betrag_soll: number;
  betrag_ist: number;
  differenz: number;
  ausschoepfung_prozent: number;
  status: "OK" | "WARNING" | "KRITISCH" | "UEBERSCHRITTEN";
};

type SollIstResponse = {
  data: PersonalkostenSollIst[];
  gesamt_ist: number;
  gesamt_soll: number;
};

type Massnahme = { id: string; name: string; status: string };
type FiscalYear = { id: string; jahr: number };

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────

function formatEur(value: number): string {
  return value.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatVzae(value: number): string {
  return value.toFixed(2);
}

function statusToVariant(status: PersonalkostenSollIst["status"]): "success" | "warning" | "danger" | "muted" {
  switch (status) {
    case "OK": return "success";
    case "WARNING": return "warning";
    case "KRITISCH": return "danger";
    case "UEBERSCHRITTEN": return "danger";
    default: return "muted";
  }
}

function statusToBarColor(status: PersonalkostenSollIst["status"]): string {
  switch (status) {
    case "OK": return "bg-soft-ok";
    case "WARNING": return "bg-soft-warn";
    case "KRITISCH": return "bg-soft-warn";
    case "UEBERSCHRITTEN": return "bg-soft-crit";
    default: return "bg-soft-line";
  }
}

function formatMonatLabel(monat: string): string {
  // monat is "YYYY-MM"
  const [yyyy, mm] = monat.split("-");
  const months = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
  ];
  const monthIdx = parseInt(mm ?? "1", 10) - 1;
  return `${months[monthIdx] ?? mm} ${yyyy}`;
}

// ─────────────────────────────────────────────
// Soll-Ist card
// ─────────────────────────────────────────────

function SollIstKarte({ data }: { data: SollIstResponse }) {
  if (data.data.length === 0) {
    return (
      <div className="bg-white rounded-soft-sm border border-soft-line p-6">
        <p className="text-sm text-soft-ink3 italic">Keine Budgetpositionen vorhanden.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-soft-sm border border-soft-line overflow-hidden">
      <div className="px-5 py-4 border-b border-soft-line2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-soft-ink">Soll-Ist-Vergleich Personalkosten</h2>
        <span className="text-xs text-soft-ink3">
          Gesamt: {formatEur(data.gesamt_ist)} € / {formatEur(data.gesamt_soll)} €
        </span>
      </div>
      <div className="divide-y divide-slate-100">
        {data.data.map((item) => {
          const cappedPct = Math.min(item.ausschoepfung_prozent, 100);
          return (
            <div key={item.kostenart} className="px-5 py-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-soft-ink">{item.kostenart}</span>
                <Badge variant={statusToVariant(item.status)}>{item.status}</Badge>
              </div>
              <div className="flex items-center gap-4 text-xs text-soft-ink2 mb-2">
                <span>Budget: <strong>{formatEur(item.betrag_soll)} €</strong></span>
                <span>Ausgegeben: <strong>{formatEur(item.betrag_ist)} €</strong></span>
                <span>
                  Verbleibend:{" "}
                  <strong className={item.differenz < 0 ? "text-soft-crit" : "text-soft-ok"}>
                    {formatEur(item.differenz)} €
                  </strong>
                </span>
                <span>Ausschöpfung: <strong>{item.ausschoepfung_prozent.toFixed(1)} %</strong></span>
              </div>
              <div className="w-full h-2 bg-soft-surfaceAlt rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${statusToBarColor(item.status)}`}
                  style={{ width: `${cappedPct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// VZÄ table row (expandable)
// ─────────────────────────────────────────────

function VzaeMonatRow({
  monat,
  isExpanded,
  onToggle,
}: {
  monat: VzaeMonat;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr
        className="hover:bg-soft-line2 cursor-pointer transition-colors border-b border-soft-line2"
        onClick={onToggle}
      >
        <td className="px-4 py-3 text-sm font-medium text-soft-ink flex items-center gap-2">
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-soft-ink4" />
          ) : (
            <ChevronRight className="h-4 w-4 text-soft-ink4" />
          )}
          {formatMonatLabel(monat.monat)}
        </td>
        <td className="px-4 py-3 text-sm text-soft-ink2 text-center">
          {monat.eintraege.length}
        </td>
        <td className="px-4 py-3 text-sm text-soft-ink text-right font-medium">
          {formatVzae(monat.summe_vzae_projekt)}
        </td>
        <td className="px-4 py-3 text-sm text-soft-ink2 text-right">—</td>
        <td className="px-4 py-3 text-sm text-soft-ink text-right font-medium">
          {formatEur(monat.summe_betrag)} €
        </td>
      </tr>
      {isExpanded &&
        monat.eintraege.map((eintrag, i) => (
          <tr key={i} className="bg-soft-line2 border-b border-soft-line2">
            <td className="px-4 py-2 text-xs text-soft-ink2 pl-10">
              <span className="font-mono text-soft-ink4 mr-2">{eintrag.employee.employee_code}</span>
              {eintrag.employee.nachname}, {eintrag.employee.vorname}
            </td>
            <td className="px-4 py-2 text-xs text-soft-ink3 text-center">
              {eintrag.prozent_kst.toFixed(1)} %
            </td>
            <td className="px-4 py-2 text-xs text-soft-ink2 text-right">
              {formatVzae(eintrag.vzae_projekt)}
            </td>
            <td className="px-4 py-2 text-xs text-soft-ink2 text-right">
              {eintrag.stunden_projekt.toFixed(2)} h
            </td>
            <td className="px-4 py-2 text-xs text-soft-ink2 text-right">
              {formatEur(eintrag.betrag_ag_brutto)} €
            </td>
          </tr>
        ))}
    </>
  );
}

// ─────────────────────────────────────────────
// Page
// ─────────────────────────────────────────────

export default function VzaePage() {
  const toast = useToast();

  const [massnahmen, setMassnahmen] = useState<Massnahme[]>([]);
  const [fiscalYears, setFiscalYears] = useState<FiscalYear[]>([]);
  const [selectedMassnahmeId, setSelectedMassnahmeId] = useState<string | null>(null);
  const [selectedFiscalYearId, setSelectedFiscalYearId] = useState<string | null>(null);

  const [vzaeData, setVzaeData] = useState<VzaeUebersichtResponse | null>(null);
  const [sollIstData, setSollIstData] = useState<SollIstResponse | null>(null);

  const [loading, setLoading] = useState(false);
  const [expandedMonths, setExpandedMonths] = useState<Set<string>>(new Set());

  // Load massnahmen and fiscal years on mount
  useEffect(() => {
    void (async () => {
      try {
        const [mRes, fyRes] = await Promise.all([
          fetch("/api/protected/foerdermassnahmen"),
          fetch("/api/protected/haushaltsjahre"),
        ]);
        if (!mRes.ok || !fyRes.ok) throw new Error("Laden fehlgeschlagen.");
        const mJson = (await mRes.json()) as { data: Massnahme[] };
        const fyJson = (await fyRes.json()) as { data: FiscalYear[] };
        setMassnahmen(mJson.data ?? []);
        setFiscalYears(fyJson.data ?? []);
      } catch {
        toast.error("Daten konnten nicht geladen werden.");
      }
    })();
  }, [toast]);

  // Load vzae + soll-ist when both are selected
  const loadData = useCallback(async (massnahmeId: string, fiscalYearId: string) => {
    setLoading(true);
    setVzaeData(null);
    setSollIstData(null);
    setExpandedMonths(new Set());
    try {
      const [vzaeRes, sollRes] = await Promise.all([
        fetch(`/api/protected/personal/vzae-uebersicht?funding_measure_id=${massnahmeId}&fiscal_year_id=${fiscalYearId}`),
        fetch(`/api/protected/personal/soll-ist?funding_measure_id=${massnahmeId}&fiscal_year_id=${fiscalYearId}`),
      ]);
      if (!vzaeRes.ok || !sollRes.ok) throw new Error("Laden fehlgeschlagen.");
      const vzaeJson = (await vzaeRes.json()) as VzaeUebersichtResponse;
      const sollJson = (await sollRes.json()) as SollIstResponse;
      setVzaeData(vzaeJson);
      setSollIstData(sollJson);
    } catch {
      toast.error("VZÄ-Daten konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    if (selectedMassnahmeId && selectedFiscalYearId) {
      void loadData(selectedMassnahmeId, selectedFiscalYearId);
    }
  }, [selectedMassnahmeId, selectedFiscalYearId, loadData]);

  const toggleMonth = (monat: string) => {
    setExpandedMonths((prev) => {
      const next = new Set(prev);
      if (next.has(monat)) {
        next.delete(monat);
      } else {
        next.add(monat);
      }
      return next;
    });
  };

  const handleExport = () => {
    if (!selectedMassnahmeId || !selectedFiscalYearId) return;
    window.open(
      `/api/protected/foerdermassnahmen/${selectedMassnahmeId}/stundennachweis?fiscal_year_id=${selectedFiscalYearId}`,
      "_blank"
    );
  };

  const bothSelected = selectedMassnahmeId !== null && selectedFiscalYearId !== null;

  return (
    <PageShell width="content">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-soft-accentSoft rounded-soft-xs">
            <Users className="h-5 w-5 text-soft-accent" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-soft-ink">VZÄ &amp; Personalkosten</h1>
            <p className="text-sm text-soft-ink3">Vollzeitäquivalente und Kostenstellen-Auswertung</p>
          </div>
        </div>
        {bothSelected && (
          <Button variant="secondary" size="sm" onClick={handleExport}>
            <Download className="h-4 w-4 mr-1.5" />
            Stundennachweis exportieren
          </Button>
        )}
      </div>

      {/* Selects */}
      <div className="flex gap-4 mb-6">
        <div className="flex-1">
          <label className="block text-xs font-medium text-soft-ink2 mb-1">Fördermassnahme</label>
          <select
            className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-soft-accent"
            value={selectedMassnahmeId ?? ""}
            onChange={(e) => setSelectedMassnahmeId(e.target.value || null)}
          >
            <option value="">— bitte wählen —</option>
            {massnahmen.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </div>
        <div className="flex-1">
          <label className="block text-xs font-medium text-soft-ink2 mb-1">Haushaltsjahr</label>
          <select
            className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-soft-accent"
            value={selectedFiscalYearId ?? ""}
            onChange={(e) => setSelectedFiscalYearId(e.target.value || null)}
          >
            <option value="">— bitte wählen —</option>
            {fiscalYears.map((fy) => (
              <option key={fy.id} value={fy.id}>
                {fy.jahr}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Content */}
      {!bothSelected ? (
        <div className="py-20 text-center">
          <Users className="h-10 w-10 text-soft-ink4 mx-auto mb-3" />
          <p className="text-soft-ink3 text-sm">
            Bitte Massnahme und Haushaltsjahr wählen, um die Auswertung anzuzeigen.
          </p>
        </div>
      ) : loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-white rounded-soft-sm border border-soft-line p-6 animate-pulse">
              <div className="h-4 bg-soft-surfaceAlt rounded w-1/3 mb-3" />
              <div className="h-2 bg-soft-surfaceAlt rounded w-full" />
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-6">
          {/* Soll-Ist */}
          {sollIstData && <SollIstKarte data={sollIstData} />}

          {/* VZÄ table */}
          {vzaeData && (
            <div className="bg-white rounded-soft-sm border border-soft-line overflow-hidden">
              <div className="px-5 py-4 border-b border-soft-line2 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-soft-ink">VZÄ-Übersicht nach Monat</h2>
                <div className="flex gap-4 text-xs text-soft-ink3">
                  <span>
                    Gesamt VZÄ-Monate:{" "}
                    <strong className="text-soft-ink">{formatVzae(vzaeData.gesamt_vzae_monate)}</strong>
                  </span>
                  <span>
                    Gesamt Betrag:{" "}
                    <strong className="text-soft-ink">{formatEur(vzaeData.gesamt_betrag)} €</strong>
                  </span>
                </div>
              </div>

              {vzaeData.monate.length === 0 ? (
                <div className="py-12 text-center">
                  <p className="text-sm text-soft-ink3 italic">
                    Keine Abrechnungsdaten für diesen Zeitraum vorhanden.
                  </p>
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-soft-line2 bg-soft-line2">
                      <th className="text-left px-4 py-3 font-medium text-soft-ink2 text-xs uppercase tracking-wide">
                        Monat
                      </th>
                      <th className="text-center px-4 py-3 font-medium text-soft-ink2 text-xs uppercase tracking-wide">
                        Mitarbeitende
                      </th>
                      <th className="text-right px-4 py-3 font-medium text-soft-ink2 text-xs uppercase tracking-wide">
                        VZÄ Projekt
                      </th>
                      <th className="text-right px-4 py-3 font-medium text-soft-ink2 text-xs uppercase tracking-wide">
                        Stunden/Woche
                      </th>
                      <th className="text-right px-4 py-3 font-medium text-soft-ink2 text-xs uppercase tracking-wide">
                        AG-Brutto
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {vzaeData.monate.map((monat) => (
                      <VzaeMonatRow
                        key={monat.monat}
                        monat={monat}
                        isExpanded={expandedMonths.has(monat.monat)}
                        onToggle={() => toggleMonth(monat.monat)}
                      />
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="bg-soft-warnSoft border-t-2 border-soft-line">
                      <td className="px-4 py-3 text-sm font-bold text-soft-ink">Gesamt</td>
                      <td className="px-4 py-3 text-sm text-center text-soft-ink2">—</td>
                      <td className="px-4 py-3 text-sm text-right font-bold text-soft-ink">
                        {formatVzae(vzaeData.gesamt_vzae_monate)}
                      </td>
                      <td className="px-4 py-3 text-sm text-right text-soft-ink2">—</td>
                      <td className="px-4 py-3 text-sm text-right font-bold text-soft-ink">
                        {formatEur(vzaeData.gesamt_betrag)} €
                      </td>
                    </tr>
                  </tfoot>
                </table>
              )}
            </div>
          )}
        </div>
      )}
    </PageShell>
  );
}
