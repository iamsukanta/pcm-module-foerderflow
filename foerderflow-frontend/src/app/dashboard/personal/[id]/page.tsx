"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/ToastProvider";
import { SalaryComponentForm } from "@/components/forms/SalaryComponentForm";
import { ContractChangeForm } from "@/components/forms/ContractChangeForm";
import { berechneGehalt } from "@/lib/personal/berechnung-client";
import { PageShell } from "@/components/ui/PageShell";
import { ArrowLeft, Plus, ChevronDown } from "lucide-react";

type SalaryComponentItem = {
  id: string;
  typ: string;
  bezeichnung: string;
  betrag: string;
  nach_multiplikator: boolean;
  einmalig: boolean;
  gilt_fuer_monat: string | null;
  ist_aktiv: boolean;
};

type ContractWithComponents = {
  id: string;
  vertragsart: string;
  assigned_hours: string;
  base_salary: string;
  tarifwerk: string | null;
  entgeltgruppe: string | null;
  stufe: number | null;
  gueltig_ab: string;
  gueltig_bis: string | null;
  notiz: string | null;
  components: SalaryComponentItem[];
};

type EmployeeDetail = {
  id: string;
  employee_code: string;
  vorname: string;
  nachname: string;
  email: string | null;
  eintrittsdatum: string;
  austrittsdatum: string | null;
  ist_aktiv: boolean;
  contracts: ContractWithComponents[];
};

const VERTRAGSART_LABELS: Record<string, string> = {
  FESTANSTELLUNG: "Festanstellung",
  MINIJOB: "Minijob",
  WERKVERTRAG: "Werkvertrag",
  EHRENAMT: "Ehrenamt",
};

const TARIFWERK_LABELS: Record<string, string> = {
  TVOEDD: "TVöD",
  TVOEL: "TV-L",
  AVR_CARITAS: "AVR Caritas",
  AVR_DD: "AVR DD",
  INDIVIDUELL: "Individuell",
};

const TYP_LABELS: Record<string, string> = {
  FESTBEZUG: "Festbezug",
  VWL_AG_ZUSCHUSS: "VWL AG-Zuschuss",
  JOBTICKET_SACHBEZUG: "Jobticket/Sachbezug",
  SALARY_ADJUSTMENT: "Gehaltsanpassung",
  SONSTIGES: "Sonstiges",
};

const STANDARD_HOURS = 40;
const DEFAULT_AG_FAKTOR = 1.2121;

function formatEur(val: string | number): string {
  return Number(val).toLocaleString("de-DE", { style: "currency", currency: "EUR" });
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function findActiveContract(contracts: ContractWithComponents[]): ContractWithComponents | null {
  const now = new Date();
  return (
    contracts.find((c) => {
      const ab = new Date(c.gueltig_ab);
      const bis = c.gueltig_bis ? new Date(c.gueltig_bis) : null;
      return ab <= now && (bis === null || bis >= now);
    }) ?? null
  );
}

export default function EmployeeDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const toast = useToast();

  const [employee, setEmployee] = useState<EmployeeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [showContractForm, setShowContractForm] = useState(false);
  const [showComponentForm, setShowComponentForm] = useState(false);
  const [deactivatingId, setDeactivatingId] = useState<string | null>(null);

  const loadEmployee = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/protected/employees/${params.id}`);
      if (!res.ok) throw new Error("Fehler beim Laden.");
      const json = (await res.json()) as { data: EmployeeDetail };
      setEmployee(json.data);
    } catch {
      toast.error("Mitarbeiter konnte nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, [params.id, toast]);

  useEffect(() => {
    void loadEmployee();
  }, [loadEmployee]);

  const handleDeactivateComponent = async (contractId: string, componentId: string) => {
    setDeactivatingId(componentId);
    try {
      const res = await fetch(
        `/api/protected/employees/${params.id}/contracts/${contractId}/components?action=deactivate&componentId=${componentId}`,
        { method: "PATCH" }
      );
      if (!res.ok) throw new Error("Fehler beim Deaktivieren.");
      toast.success("Komponente deaktiviert.");
      void loadEmployee();
    } catch {
      toast.error("Fehler beim Deaktivieren der Komponente.");
    } finally {
      setDeactivatingId(null);
    }
  };

  if (loading) {
    return (
      <div className="p-6 text-center text-soft-ink4 text-sm">Laden…</div>
    );
  }

  if (!employee) {
    return (
      <div className="p-6 text-center text-soft-ink3 text-sm">
        Mitarbeiter nicht gefunden.
      </div>
    );
  }

  const activeContract = findActiveContract(employee.contracts);
  const pastContracts = employee.contracts.filter((c) => c.id !== activeContract?.id);
  const activeComponents = activeContract?.components.filter((c) => c.ist_aktiv) ?? [];

  // Salary preview
  const preview = activeContract
    ? berechneGehalt({
        base_salary: Number(activeContract.base_salary),
        assigned_hours: Number(activeContract.assigned_hours),
        standard_hours: STANDARD_HOURS,
        ag_faktor: DEFAULT_AG_FAKTOR,
        components: activeComponents.map((c) => ({
          betrag: Number(c.betrag),
          nach_multiplikator: c.nach_multiplikator,
        })),
      })
    : null;

  return (
    <PageShell width="content">
      {/* Back button */}
      <button
        onClick={() => router.push("/dashboard/personal")}
        className="flex items-center gap-1.5 text-sm text-soft-ink3 hover:text-soft-ink2 mb-5 transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Zurück zur Liste
      </button>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-2xl font-semibold text-soft-ink">
              {employee.vorname} {employee.nachname}
            </h1>
            <Badge variant={employee.ist_aktiv ? "success" : "danger"}>
              {employee.ist_aktiv ? "Aktiv" : "Inaktiv"}
            </Badge>
          </div>
          <div className="flex items-center gap-4 text-sm text-soft-ink3">
            <span className="font-mono">{employee.employee_code}</span>
            <span>Eingetreten: {formatDate(employee.eintrittsdatum)}</span>
            {employee.austrittsdatum && (
              <span className="text-soft-crit">
                Ausgetreten: {formatDate(employee.austrittsdatum)}
              </span>
            )}
            {employee.email && <span>{employee.email}</span>}
          </div>
        </div>
      </div>

      <div className="space-y-6">
        {/* Active contract card */}
        <section className="bg-white rounded-soft-sm border border-soft-line p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-soft-ink">Aktueller Vertrag</h2>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowContractForm(!showContractForm)}
            >
              Vertrag ändern
            </Button>
          </div>

          {activeContract ? (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              <div>
                <p className="text-xs text-soft-ink3 mb-0.5">Vertragsart</p>
                <p className="text-sm font-medium text-soft-ink">
                  {VERTRAGSART_LABELS[activeContract.vertragsart] ?? activeContract.vertragsart}
                </p>
              </div>
              <div>
                <p className="text-xs text-soft-ink3 mb-0.5">Stunden/Woche</p>
                <p className="text-sm font-medium text-soft-ink">
                  {Number(activeContract.assigned_hours).toLocaleString("de-DE")} h
                </p>
              </div>
              <div>
                <p className="text-xs text-soft-ink3 mb-0.5">Grundgehalt</p>
                <p className="text-sm font-medium text-soft-ink">
                  {formatEur(activeContract.base_salary)}
                </p>
              </div>
              {activeContract.tarifwerk && (
                <div>
                  <p className="text-xs text-soft-ink3 mb-0.5">Tarifwerk</p>
                  <p className="text-sm font-medium text-soft-ink">
                    {TARIFWERK_LABELS[activeContract.tarifwerk] ?? activeContract.tarifwerk}
                  </p>
                </div>
              )}
              {activeContract.entgeltgruppe && (
                <div>
                  <p className="text-xs text-soft-ink3 mb-0.5">Entgeltgruppe</p>
                  <p className="text-sm font-medium text-soft-ink">
                    {activeContract.entgeltgruppe}
                    {activeContract.stufe ? ` / Stufe ${activeContract.stufe}` : ""}
                  </p>
                </div>
              )}
              <div>
                <p className="text-xs text-soft-ink3 mb-0.5">Gültig ab</p>
                <p className="text-sm font-medium text-soft-ink">
                  {formatDate(activeContract.gueltig_ab)}
                </p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-soft-ink4 italic">Kein aktiver Vertrag vorhanden.</p>
          )}

          {/* Contract change form */}
          {showContractForm && activeContract && (
            <div className="mt-5 pt-5 border-t border-soft-line2">
              <h3 className="text-sm font-semibold text-soft-ink mb-4">Neuer Vertrag (Vertragsänderung)</h3>
              <ContractChangeForm
                employeeId={employee.id}
                onSuccess={() => {
                  setShowContractForm(false);
                  void loadEmployee();
                  toast.success("Vertragsänderung gespeichert.");
                }}
                onCancel={() => setShowContractForm(false)}
              />
            </div>
          )}
        </section>

        {/* Salary components */}
        {activeContract && (
          <section className="bg-white rounded-soft-sm border border-soft-line p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-soft-ink">Gehaltskomponenten</h2>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setShowComponentForm(!showComponentForm)}
              >
                <Plus className="h-4 w-4 mr-1" />
                Komponente
              </Button>
            </div>

            {showComponentForm && (
              <div className="mb-5 pb-5 border-b border-soft-line2">
                <SalaryComponentForm
                  apiPath={`/api/protected/employees/${employee.id}/contracts/${activeContract.id}/components`}
                  onSuccess={() => {
                    setShowComponentForm(false);
                    void loadEmployee();
                  }}
                  onCancel={() => setShowComponentForm(false)}
                />
              </div>
            )}

            {activeComponents.length === 0 ? (
              <p className="text-sm text-soft-ink4 italic">Keine aktiven Gehaltskomponenten.</p>
            ) : (
              <div className="space-y-2">
                {activeComponents.map((comp) => (
                  <div
                    key={comp.id}
                    className="flex items-center justify-between rounded-soft-xs border border-soft-line2 px-4 py-3"
                  >
                    <div className="flex items-center gap-3">
                      <div>
                        <p className="text-sm font-medium text-soft-ink">{comp.bezeichnung}</p>
                        <p className="text-xs text-soft-ink3">{TYP_LABELS[comp.typ] ?? comp.typ}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge variant={comp.nach_multiplikator ? "warning" : "default"}>
                        {comp.nach_multiplikator ? "Nach Multiplikator" : "Vor Multiplikator"}
                      </Badge>
                      {comp.einmalig && (
                        <Badge variant="muted">Einmalig</Badge>
                      )}
                      <span className="text-sm font-medium text-soft-ink tabular-nums min-w-[80px] text-right">
                        {formatEur(comp.betrag)}
                      </span>
                      <button
                        onClick={() => handleDeactivateComponent(activeContract.id, comp.id)}
                        disabled={deactivatingId === comp.id}
                        className="text-xs text-soft-ink4 hover:text-soft-crit transition-colors disabled:opacity-50"
                        title="Komponente deaktivieren"
                      >
                        Entfernen
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* Salary preview */}
        {preview && activeContract && (
          <section className="bg-soft-accentSoft rounded-soft-sm border border-soft-accent/20 p-5">
            <h2 className="text-base font-semibold text-soft-ink mb-4">
              Gehaltsvorschau
              <span className="text-xs font-normal text-soft-ink3 ml-2">
                (Vollzeit = {STANDARD_HOURS}h, AG-Faktor = {DEFAULT_AG_FAKTOR})
              </span>
            </h2>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              <div>
                <p className="text-xs text-soft-ink3 mb-0.5">Tatsächliches Grundgehalt</p>
                <p className="text-sm font-medium text-soft-ink">{formatEur(preview.actual_salary)}</p>
                <p className="text-xs text-soft-ink4">
                  = {formatEur(activeContract.base_salary)} × ({Number(activeContract.assigned_hours)}h / {STANDARD_HOURS}h)
                </p>
              </div>
              <div>
                <p className="text-xs text-soft-ink3 mb-0.5">AN-Brutto</p>
                <p className="text-base font-semibold text-soft-ink">{formatEur(preview.an_brutto)}</p>
                {preview.komponenten_vor_multiplikator !== 0 && (
                  <p className="text-xs text-soft-ink4">
                    inkl. {formatEur(preview.komponenten_vor_multiplikator)} Zulagen
                  </p>
                )}
              </div>
              <div>
                <p className="text-xs text-soft-ink3 mb-0.5">AG-Brutto</p>
                <p className="text-base font-semibold text-soft-accent">{formatEur(preview.ag_brutto)}</p>
                {preview.komponenten_nach_multiplikator !== 0 && (
                  <p className="text-xs text-soft-ink4">
                    inkl. {formatEur(preview.komponenten_nach_multiplikator)} nach Multip.
                  </p>
                )}
              </div>
            </div>
          </section>
        )}

        {/* Contract history */}
        {pastContracts.length > 0 && (
          <section className="bg-white rounded-soft-sm border border-soft-line">
            <details>
              <summary className="flex items-center justify-between px-5 py-4 cursor-pointer list-none">
                <h2 className="text-base font-semibold text-soft-ink">
                  Vertragshistorie
                  <span className="ml-2 text-xs font-normal text-soft-ink3">
                    ({pastContracts.length} {pastContracts.length === 1 ? "Eintrag" : "Einträge"})
                  </span>
                </h2>
                <ChevronDown className="h-4 w-4 text-soft-ink4" />
              </summary>
              <div className="px-5 pb-5 space-y-3">
                {pastContracts.map((c) => (
                  <div
                    key={c.id}
                    className="rounded-soft-xs border border-soft-line2 px-4 py-3 text-sm"
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <Badge variant="muted">
                        {VERTRAGSART_LABELS[c.vertragsart] ?? c.vertragsart}
                      </Badge>
                      <span className="text-xs text-soft-ink3">
                        {formatDate(c.gueltig_ab)} – {c.gueltig_bis ? formatDate(c.gueltig_bis) : "–"}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-3 text-xs text-soft-ink2">
                      <span>{Number(c.assigned_hours).toLocaleString("de-DE")} h/Woche</span>
                      <span>Grundgehalt: {formatEur(c.base_salary)}</span>
                      {c.tarifwerk && (
                        <span>
                          {TARIFWERK_LABELS[c.tarifwerk] ?? c.tarifwerk}
                          {c.entgeltgruppe ? ` ${c.entgeltgruppe}` : ""}
                          {c.stufe ? `/S${c.stufe}` : ""}
                        </span>
                      )}
                    </div>
                    {c.notiz && (
                      <p className="mt-2 text-xs text-soft-ink3 italic">{c.notiz}</p>
                    )}
                  </div>
                ))}
              </div>
            </details>
          </section>
        )}
      </div>
    </PageShell>
  );
}
