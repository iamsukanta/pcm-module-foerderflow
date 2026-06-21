"use client";

import { useState, useEffect, useCallback, useMemo, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/ToastProvider";
import { EmployeeForm } from "@/components/forms/EmployeeForm";
import { SearchInput } from "@/components/ui/SearchInput";
import { useDebounce } from "@/lib/hooks/useDebounce";
import { Users, Plus } from "lucide-react";
import { PageShell } from "@/components/ui/PageShell";

type EmployeeContract = {
  id: string;
  vertragsart: string;
  assigned_hours: string;
  base_salary: string;
  gueltig_ab: string;
  gueltig_bis: string | null;
};

type Employee = {
  id: string;
  employee_code: string;
  vorname: string;
  nachname: string;
  ist_aktiv: boolean;
  contracts: EmployeeContract[];
  active_contract_id: string | null;
};

type FilterTab = "aktiv" | "alle";

const VERTRAGSART_LABELS: Record<string, string> = {
  FESTANSTELLUNG: "Festanstellung",
  MINIJOB: "Minijob",
  WERKVERTRAG: "Werkvertrag",
  EHRENAMT: "Ehrenamt",
};

function findActiveContract(contracts: EmployeeContract[]): EmployeeContract | null {
  const now = new Date();
  return (
    contracts.find((c) => {
      const ab = new Date(c.gueltig_ab);
      const bis = c.gueltig_bis ? new Date(c.gueltig_bis) : null;
      return ab <= now && (bis === null || bis >= now);
    }) ?? null
  );
}

// ─────────────────────────────────────────────
// Top-level page tabs
// ─────────────────────────────────────────────

type PageTab = "mitarbeitende" | "gehaltserfassung" | "einstellungen";

function PageTabNav({ activeTab }: { activeTab: PageTab }) {
  const tabs: Array<{ key: PageTab; label: string; href: string }> = [
    { key: "mitarbeitende", label: "Mitarbeitende", href: "/dashboard/personal" },
    { key: "gehaltserfassung", label: "Gehaltserfassung", href: "/dashboard/personal/gehaltserfassung" },
    { key: "einstellungen", label: "Einstellungen", href: "/dashboard/personal?tab=einstellungen" },
  ];

  return (
    <div className="flex gap-1 mb-6 border-b border-soft-line">
      {tabs.map((tab) => (
        <Link
          key={tab.key}
          href={tab.href}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
            activeTab === tab.key
              ? "border-soft-accent text-soft-accent"
              : "border-transparent text-soft-ink2 hover:text-soft-ink"
          }`}
        >
          {tab.label}
        </Link>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────
// Mitarbeitende tab content
// ─────────────────────────────────────────────

function MitarbeitendeTab() {
  const router = useRouter();
  const toast = useToast();

  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterTab>("aktiv");
  const [showForm, setShowForm] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const loadEmployees = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/protected/employees");
      if (!res.ok) throw new Error("Fehler beim Laden der Mitarbeiter.");
      const json = (await res.json()) as { data: Employee[] };
      setEmployees(json.data);
    } catch {
      toast.error("Mitarbeiter konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void loadEmployees();
  }, [loadEmployees]);

  const debouncedSearch = useDebounce(searchQuery, 300);

  const filteredEmployees = useMemo(() => {
    let result = filter === "aktiv" ? employees.filter((e) => e.ist_aktiv) : employees;

    if (debouncedSearch.trim()) {
      const query = debouncedSearch.toLowerCase();
      result = result.filter(
        (e) =>
          e.vorname.toLowerCase().includes(query) ||
          e.nachname.toLowerCase().includes(query) ||
          e.employee_code.toLowerCase().includes(query)
      );
    }

    return result;
  }, [employees, filter, debouncedSearch]);

  const handleRowClick = (id: string) => {
    router.push(`/dashboard/personal/${id}`);
  };

  const handleFormSuccess = (id: string) => {
    setShowForm(false);
    void loadEmployees();
    router.push(`/dashboard/personal/${id}`);
  };

  return (
    <PageShell width="content">
      {/* Header */}
      <div className="flex items-center justify-between mb-8 gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-soft-accentWash rounded-soft-xs">
            <Users className="h-5 w-5 text-soft-accent" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-soft-ink">Personal</h1>
            <p className="text-sm text-soft-ink3">Mitarbeiterstammdaten und Verträge</p>
          </div>
        </div>
        <Button
          variant="primary"
          size="sm"
          onClick={() => setShowForm(true)}
        >
          <Plus className="h-4 w-4 mr-1.5" />
          Mitarbeiter anlegen
        </Button>
      </div>

      {/* Modal overlay for EmployeeForm */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/30 backdrop-blur-sm pt-16 px-4">
          <div className="bg-soft-surface rounded-soft-sm shadow-soft-lg w-full max-w-2xl max-h-[80vh] overflow-y-auto">
            <div className="px-6 py-5 border-b border-soft-line">
              <h2 className="text-base font-semibold text-soft-ink">Neuer Mitarbeiter</h2>
              <p className="text-sm text-soft-ink3 mt-0.5">Stammdaten und ersten Vertrag anlegen</p>
            </div>
            <div className="px-6 py-5">
              <EmployeeForm
                onSuccess={handleFormSuccess}
                onCancel={() => setShowForm(false)}
              />
            </div>
          </div>
        </div>
      )}

      {/* Search input */}
      <SearchInput
        value={searchQuery}
        onChange={setSearchQuery}
        placeholder="Suche nach Name oder Code..."
        className="mb-4"
      />

      {/* Filter tabs */}
      <div className="flex gap-1 mb-4 border-b border-soft-line">
        {(["aktiv", "alle"] as FilterTab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setFilter(tab)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              filter === tab
                ? "border-soft-accent text-soft-accent"
                : "border-transparent text-soft-ink2 hover:text-soft-ink"
            }`}
          >
            {tab === "aktiv" ? "Aktiv" : "Alle"}
          </button>
        ))}
      </div>

      {/* Table */}
      {loading ? (
        <div className="py-16 text-center text-soft-ink3 text-sm">Laden…</div>
      ) : filteredEmployees.length === 0 ? (
        <div className="py-16 text-center">
          <Users className="h-10 w-10 text-soft-ink4 mx-auto mb-3" />
          <p className="text-soft-ink2 text-sm">
            {filter === "aktiv" ? "Keine aktiven Mitarbeiter gefunden." : "Noch keine Mitarbeiter angelegt."}
          </p>
          <Button
            variant="secondary"
            size="sm"
            className="mt-4"
            onClick={() => setShowForm(true)}
          >
            Mitarbeiter anlegen
          </Button>
        </div>
      ) : (
        <div className="bg-soft-surface rounded-soft-sm border border-soft-line overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-soft-line bg-soft-line2">
                <th className="text-left px-4 py-3 font-medium text-soft-ink2 text-xs uppercase tracking-wide">
                  Code
                </th>
                <th className="text-left px-4 py-3 font-medium text-soft-ink2 text-xs uppercase tracking-wide">
                  Name
                </th>
                <th className="text-left px-4 py-3 font-medium text-soft-ink2 text-xs uppercase tracking-wide">
                  Vertragsart
                </th>
                <th className="text-left px-4 py-3 font-medium text-soft-ink2 text-xs uppercase tracking-wide">
                  Std./Woche
                </th>
                <th className="text-left px-4 py-3 font-medium text-soft-ink2 text-xs uppercase tracking-wide">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-soft-line">
              {filteredEmployees.map((emp) => {
                const activeContract = findActiveContract(emp.contracts);
                return (
                  <tr
                    key={emp.id}
                    onClick={() => handleRowClick(emp.id)}
                    className="hover:bg-soft-line2 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 font-mono text-xs text-soft-ink3">
                      {emp.employee_code}
                    </td>
                    <td className="px-4 py-3 font-medium text-soft-ink">
                      {emp.nachname}, {emp.vorname}
                    </td>
                    <td className="px-4 py-3 text-soft-ink2">
                      {activeContract
                        ? (VERTRAGSART_LABELS[activeContract.vertragsart] ?? activeContract.vertragsart)
                        : <span className="text-soft-ink3 italic">–</span>
                      }
                    </td>
                    <td className="px-4 py-3 text-soft-ink2">
                      {activeContract
                        ? `${Number(activeContract.assigned_hours).toLocaleString("de-DE")} h`
                        : <span className="text-soft-ink3">–</span>
                      }
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={emp.ist_aktiv ? "success" : "muted"}>
                        {emp.ist_aktiv ? "Aktiv" : "Inaktiv"}
                      </Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </PageShell>
  );
}

// ─────────────────────────────────────────────
// Einstellungen tab content (placeholder)
// ─────────────────────────────────────────────

function EinstellungenTab() {
  return (
    <div className="py-16 text-center">
      <p className="text-soft-ink2 text-sm">Einstellungen werden in Kürze verfügbar sein.</p>
    </div>
  );
}

// ─────────────────────────────────────────────
// Inner component (uses useSearchParams)
// ─────────────────────────────────────────────

function PersonalPageInner() {
  const searchParams = useSearchParams();
  const tabParam = searchParams.get("tab");

  const activeTab: PageTab = tabParam === "einstellungen" ? "einstellungen" : "mitarbeitende";

  return (
    <PageShell width="content">
      <PageTabNav activeTab={activeTab} />
      {activeTab === "einstellungen" ? <EinstellungenTab /> : <MitarbeitendeTab />}
    </PageShell>
  );
}

// ─────────────────────────────────────────────
// Page export (Suspense for useSearchParams)
// ─────────────────────────────────────────────

export default function PersonalPage() {
  return (
    <Suspense fallback={<div className="p-6 text-soft-ink3 text-sm">Laden…</div>}>
      <PersonalPageInner />
    </Suspense>
  );
}
