"use client";

import { useState, useEffect, useCallback, useRef, useMemo, Suspense } from "react";
import Link from "next/link";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { formatEur } from "@/lib/utils";
import { Badge } from "@/components/ui/Badge";
import { KostenbereichSelect } from "@/components/forms/KostenbereichSelect";
import { useToast } from "@/components/ui/ToastProvider";
import { FileText, X, SlidersHorizontal } from "lucide-react";
import { PageShell } from "@/components/ui/PageShell";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";

type BadgeVariant = "muted" | "default" | "success" | "warning";

const STATUS_LABELS: Record<string, string> = {
  IMPORTIERT: "Offen",
  KATEGORISIERT: "Kategorisiert",
  ZUGEORDNET: "Zugeordnet",
  ABGESCHLOSSEN: "Abgeschlossen",
};

const STATUS_COLORS: Record<string, BadgeVariant> = {
  IMPORTIERT: "muted",
  KATEGORISIERT: "default",
  ZUGEORDNET: "warning",
  ABGESCHLOSSEN: "success",
};

type Split = {
  id: string;
  cost_center: { id: string; name: string; code: string };
  prozent: string;
  fund_allocations: { funding_measure: { id: string; name: string } | null }[];
};

type Transaction = {
  id: string;
  datum: string;
  betrag: string;
  auftraggeber: string | null;
  verwendungszweck: string | null;
  kostenbereich: { id: string; code: string; bezeichnung: string } | null;
  status: string;
  confidence?: string | null;
  _count?: { splits: number; belege: number };
  splits?: Split[];
  massnahme?: { id: string; name: string } | null;
};

type Kpis = {
  einnahmen: number;
  ausgaben: number;
  cashflow: number;
  total: number;
  zugeordnet: number;
  fortschritt: number;
};

type Pagination = { page: number; limit: number; total: number; pages: number };

const FILTER_TABS = [
  { label: "Alle", value: "" },
  { label: "Offen", value: "IMPORTIERT" },
  { label: "Kategorisiert", value: "KATEGORISIERT" },
  { label: "Zugeordnet", value: "ZUGEORDNET" },
  { label: "Abgeschlossen", value: "ABGESCHLOSSEN" },
];

type BookingRuleOption = { id: string; name: string; aktiv: boolean };
type MassnahmeOption = { id: string; name: string; cost_center_ids: string[] };

/**
 * Kategorisiert die zur Auswahl stehenden Maßnahmen relativ zu den KSTs der Transaktion(en).
 *
 * - `primary`: Maßnahme hat KST-Zuordnung UND mindestens eine davon deckt eine TX-KST ab.
 * - `wildcard`: Maßnahme hat KEINE KST-Zuordnung (offen für alle KSTs).
 * - `others`: Maßnahme hat KST-Zuordnung, deckt aber keine der TX-KSTs ab.
 *
 * Wenn `txKstSets` mehrere Mengen enthält (Batch-Modus), muss eine Maßnahme jede einzelne
 * TX-KST-Menge bedienen, um als `primary` zu zählen — d.h. wir bilden den Schnitt
 * der einzeln-passenden Maßnahmen.
 */
function categorizeMassnahmen(
  massnahmen: MassnahmeOption[],
  txKstSets: Set<string>[]
): { primary: MassnahmeOption[]; wildcard: MassnahmeOption[]; others: MassnahmeOption[] } {
  const primary: MassnahmeOption[] = [];
  const wildcard: MassnahmeOption[] = [];
  const others: MassnahmeOption[] = [];

  for (const m of massnahmen) {
    if (m.cost_center_ids.length === 0) {
      wildcard.push(m);
      continue;
    }
    const coversAll =
      txKstSets.length === 0
        ? false
        : txKstSets.every((txKstSet) =>
            [...txKstSet].some((id) => m.cost_center_ids.includes(id))
          );
    if (coversAll) primary.push(m);
    else others.push(m);
  }

  return { primary, wildcard, others };
}

function KstBadge({ splits }: { splits?: Split[] }) {
  if (!splits || splits.length === 0) return <span className="text-soft-ink4 text-xs italic">—</span>;
  return (
    <span className="text-xs text-soft-ink2">
      {splits
        .map((s) => `${Number(s.prozent).toFixed(0)}% ${s.cost_center.name}`)
        .join(" / ")}
    </span>
  );
}

function MassnahmeDropdown({
  transaction,
  massnahmen,
  onAssigned,
}: {
  transaction: Transaction;
  massnahmen: MassnahmeOption[];
  onAssigned: (txId: string, massnahme: { id: string; name: string } | null) => void;
}) {
  const toast = useToast();
  const [saving, setSaving] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [pendingChange, setPendingChange] = useState<MassnahmeOption | null>(null);
  const hasSplits = (transaction._count?.splits ?? transaction.splits?.length ?? 0) > 0;
  const currentId = transaction.massnahme?.id ?? "";
  const currentName = transaction.massnahme?.name ?? "";

  if (!hasSplits) {
    return (
      <Link
        href={`/dashboard/transaktionen/${transaction.id}`}
        className="text-xs text-soft-accent hover:underline italic"
        onClick={(e) => e.stopPropagation()}
      >
        Erst KST zuordnen
      </Link>
    );
  }

  const txKstSet = new Set((transaction.splits ?? []).map((s) => s.cost_center.id));
  const { primary, wildcard, others } = categorizeMassnahmen(massnahmen, [txKstSet]);
  const autoSuggest: MassnahmeOption | null =
    primary.length === 1 ? primary[0] :
    primary.length === 0 && wildcard.length === 1 ? wildcard[0] :
    null;

  async function performAssign(massnahmeId: string) {
    setSaving(true);
    try {
      const res = await fetch(`/api/protected/transaktionen/${transaction.id}/massnahme`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ funding_measure_id: massnahmeId }),
      });
      const json = await res.json() as { error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Fehler beim Zuordnen.");
        return;
      }
      const found = massnahmen.find((m) => m.id === massnahmeId) ?? null;
      onAssigned(transaction.id, found);
    } catch {
      toast.error("Netzwerkfehler.");
    } finally {
      setSaving(false);
      setPendingChange(null);
    }
  }

  function handleChange(e: React.ChangeEvent<HTMLSelectElement>) {
    e.stopPropagation();
    const massnahmeId = e.target.value;
    if (!massnahmeId || massnahmeId === currentId) return;
    const target = massnahmen.find((m) => m.id === massnahmeId) ?? null;
    if (!target) return;
    if (currentId) {
      setPendingChange(target);
      return;
    }
    void performAssign(massnahmeId);
  }

  return (
    <div className="relative flex flex-col gap-1" onClick={(e) => e.stopPropagation()}>
      {saving && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/70 rounded z-10">
          <span className="w-3 h-3 border-2 border-soft-accent border-t-transparent rounded-full animate-spin" />
        </div>
      )}
      {autoSuggest && !currentId && (
        <button
          type="button"
          onClick={() => void performAssign(autoSuggest.id)}
          disabled={saving}
          className="text-xs rounded border border-soft-accent/40 bg-soft-accentSoft text-soft-accent px-2 py-1 hover:bg-soft-accent hover:text-white transition-colors text-left truncate max-w-[160px]"
          title={`Vorschlag basierend auf KST: ${autoSuggest.name}`}
        >
          ✓ {autoSuggest.name}
        </button>
      )}
      <select
        className="text-xs rounded border border-soft-line bg-white px-2 py-1 pr-5 focus:outline-none focus:ring-1 focus:ring-soft-accent max-w-[160px] truncate disabled:opacity-60"
        value={currentId}
        disabled={saving}
        onChange={handleChange}
      >
        <option value="" disabled={!!currentId}>
          {currentId ? "— ändern —" : autoSuggest ? "andere wählen…" : "Massnahme wählen…"}
        </option>
        {primary.length > 0 && (
          <optgroup label="Vorschläge (passende KST)">
            {primary.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </optgroup>
        )}
        {wildcard.length > 0 && (
          <optgroup label="Ohne KST-Beschränkung">
            {wildcard.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </optgroup>
        )}
        {showAll && others.length > 0 && (
          <optgroup label="Weitere (KST passt nicht)">
            {others.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </optgroup>
        )}
      </select>
      {others.length > 0 && (
        <button
          type="button"
          onClick={() => setShowAll((s) => !s)}
          className="text-[10px] text-soft-ink4 hover:text-soft-accent self-start"
        >
          {showAll ? "Nur passende zeigen" : `+${others.length} weitere zeigen`}
        </button>
      )}
      <ConfirmDialog
        open={pendingChange !== null}
        title="Förderzuordnung ersetzen?"
        description={
          pendingChange
            ? `Diese Transaktion ist bereits Massnahme „${currentName}" zugeordnet. Beim Wechsel auf „${pendingChange.name}" werden die bestehenden Förderzuordnungen auf allen Splits ersetzt.`
            : ""
        }
        confirmLabel="Auf neue Massnahme umhängen"
        variant="danger"
        loading={saving}
        onConfirm={() => pendingChange && void performAssign(pendingChange.id)}
        onCancel={() => setPendingChange(null)}
      />
    </div>
  );
}

type BankAccountOption = { id: string; bezeichnung: string };

const FILTER_PARAM_KEYS = [
  "status",
  "kostenbereich_id",
  "cost_center_id",
  "funding_measure_id",
  "has_massnahme",
  "confidence",
  "datum_von",
  "datum_bis",
  "betrag_min",
  "betrag_max",
  "iban_partner",
  "bank_account_id",
  "search",
] as const;

type FilterKey = (typeof FILTER_PARAM_KEYS)[number];

function TransaktionenInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const statusParam = searchParams.get("status") ?? "";
  const pageParam = parseInt(searchParams.get("page") ?? "1");
  const toast = useToast();

  const activeFilters = useMemo(() => {
    const result: Partial<Record<FilterKey, string>> = {};
    for (const k of FILTER_PARAM_KEYS) {
      const v = searchParams.get(k);
      if (v) result[k] = v;
    }
    return result;
  }, [searchParams]);

  const [filterDraft, setFilterDraft] = useState<Partial<Record<FilterKey, string>>>(activeFilters);
  const [filterPanelOpen, setFilterPanelOpen] = useState(false);

  useEffect(() => {
    setFilterDraft(activeFilters);
  }, [activeFilters]);

  const updateUrlWithFilters = useCallback(
    (next: Partial<Record<FilterKey, string>>) => {
      const params = new URLSearchParams();
      for (const k of FILTER_PARAM_KEYS) {
        const v = next[k];
        if (v) params.set(k, v);
      }
      params.delete("page");
      const qs = params.toString();
      router.push(qs ? `${pathname}?${qs}` : pathname);
    },
    [router, pathname]
  );

  const clearFilter = (k: FilterKey) => {
    const next = { ...activeFilters };
    delete next[k];
    updateUrlWithFilters(next);
  };

  const clearAllFilters = () => updateUrlWithFilters({});

  const applyDraft = () => updateUrlWithFilters(filterDraft);

  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [loading, setLoading] = useState(true);
  const [bankAccounts, setBankAccounts] = useState<BankAccountOption[]>([]);
  const [kostenbereiche, setKostenbereiche] = useState<{ id: string; bezeichnung: string }[]>([]);
  const [kostenstellen, setKostenstellen] = useState<
    { id: string; code: string; name: string; parent_id: string | null }[]
  >([]);

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [selectionMode, setSelectionMode] = useState<"ids" | "filter">("ids");
  const [excludedIds, setExcludedIds] = useState<Set<string>>(new Set());
  const [bookingRules, setBookingRules] = useState<BookingRuleOption[]>([]);
  const [massnahmen, setMassnahmen] = useState<MassnahmeOption[]>([]);
  const [selectedRuleId, setSelectedRuleId] = useState("");
  const [selectedBatchMassnahmeId, setSelectedBatchMassnahmeId] = useState("");
  const [batchShowAllMassnahmen, setBatchShowAllMassnahmen] = useState(false);
  const [batchLoading, setBatchLoading] = useState(false);
  const [batchOverwriteConfirm, setBatchOverwriteConfirm] = useState<{
    targetMassnahme: string;
    overwriteCount: number;
  } | null>(null);

  // track ongoing inline-massnahme saves per tx
  const savingRef = useRef<Set<string>>(new Set());

  const fetchTransactions = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      for (const k of FILTER_PARAM_KEYS) {
        const v = searchParams.get(k);
        if (v) params.set(k, v);
      }
      params.set("page", String(pageParam));
      params.set("limit", "50");
      params.set("cockpit", "true");

      const res = await fetch(`/api/protected/transaktionen?${params.toString()}`);
      const json = (await res.json()) as {
        data: Transaction[];
        pagination: Pagination;
        kpis?: Kpis;
      };
      setTransactions(json.data ?? []);
      setPagination(json.pagination ?? null);
      setKpis(json.kpis ?? null);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [searchParams, pageParam]);

  useEffect(() => {
    void fetchTransactions();
    setSelectedIds(new Set());
    setSelectionMode("ids");
    setExcludedIds(new Set());
  }, [fetchTransactions]);

  // Selection-Helper: in filter-mode arbeitet die Logik invers (excludedIds),
  // damit "alle gefilterten" auch dann gilt wenn Filter-Treffer > Seitengröße sind.
  const isRowSelected = (tx_id: string) =>
    selectionMode === "filter" ? !excludedIds.has(tx_id) : selectedIds.has(tx_id);

  const toggleRow = (tx_id: string, checked: boolean) => {
    if (selectionMode === "filter") {
      setExcludedIds((prev) => {
        const next = new Set(prev);
        if (checked) next.delete(tx_id);
        else next.add(tx_id);
        return next;
      });
    } else {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        if (checked) next.add(tx_id);
        else next.delete(tx_id);
        return next;
      });
    }
  };

  const selectedCount =
    selectionMode === "filter"
      ? Math.max(0, (pagination?.total ?? 0) - excludedIds.size)
      : selectedIds.size;

  const allPageSelected =
    transactions.length > 0 &&
    (selectionMode === "filter"
      ? transactions.every((t) => !excludedIds.has(t.id))
      : transactions.every((t) => selectedIds.has(t.id)));

  const headerCheckboxToggle = (checked: boolean) => {
    if (selectionMode === "filter") {
      setExcludedIds((prev) => {
        const next = new Set(prev);
        for (const t of transactions) {
          if (checked) next.delete(t.id);
          else next.add(t.id);
        }
        return next;
      });
    } else {
      setSelectedIds(checked ? new Set(transactions.map((t) => t.id)) : new Set());
    }
  };

  const activateFilterMode = () => {
    setSelectionMode("filter");
    setSelectedIds(new Set());
    setExcludedIds(new Set());
  };

  const deactivateAll = () => {
    setSelectionMode("ids");
    setSelectedIds(new Set());
    setExcludedIds(new Set());
  };

  const showAcrossPagesBanner =
    selectionMode === "ids" &&
    transactions.length > 0 &&
    selectedIds.size === transactions.length &&
    (pagination?.total ?? 0) > transactions.length;

  // Currently active server-side filter (für Filter-Mode-Requests)
  const serverFilter = useMemo(() => {
    const f: Record<string, string> = {};
    for (const k of FILTER_PARAM_KEYS) {
      const v = searchParams.get(k);
      if (v) f[k] = v;
    }
    return f;
  }, [searchParams]);

  useEffect(() => {
    fetch("/api/protected/buchungsregeln")
      .then((r) => r.json())
      .then((json: { data?: BookingRuleOption[] }) => setBookingRules(json.data ?? []))
      .catch(() => {});

    fetch("/api/protected/foerdermassnahmen?status=AKTIV")
      .then((r) => r.json())
      .then((json: { data?: MassnahmeOption[] }) => setMassnahmen(json.data ?? []))
      .catch(() => {});

    fetch("/api/protected/bank-accounts")
      .then((r) => r.json())
      .then((json: { data?: BankAccountOption[] }) => setBankAccounts(json.data ?? []))
      .catch(() => {});

    fetch("/api/protected/kostenbereiche")
      .then((r) => r.json())
      .then((json: { data?: { id: string; bezeichnung: string }[] }) =>
        setKostenbereiche(json.data ?? [])
      )
      .catch(() => {});

    fetch("/api/protected/kostenstellen")
      .then((r) => r.json())
      .then(
        (json: {
          data?: { id: string; code: string; name: string; parent_id: string | null }[];
        }) => {
          const list = json.data ?? [];
          // Flach sortieren: erst Eltern, dann ihre Kinder, alphabetisch nach Code
          const parents = list.filter((k) => !k.parent_id).sort((a, b) => a.code.localeCompare(b.code));
          const children = list.filter((k) => k.parent_id);
          const sorted: typeof list = [];
          for (const p of parents) {
            sorted.push(p);
            const kids = children
              .filter((c) => c.parent_id === p.id)
              .sort((a, b) => a.code.localeCompare(b.code));
            sorted.push(...kids);
          }
          // Orphan-Kinder (parent nicht in Liste) hinten anhängen
          const orphans = children.filter((c) => !parents.some((p) => p.id === c.parent_id));
          sorted.push(...orphans.sort((a, b) => a.code.localeCompare(b.code)));
          setKostenstellen(sorted);
        }
      )
      .catch(() => {});
  }, []);

  function handleMassnahmeAssigned(txId: string, massnahme: { id: string; name: string } | null) {
    setTransactions((prev) =>
      prev.map((t) =>
        t.id === txId
          ? { ...t, massnahme, status: massnahme ? "ZUGEORDNET" : t.status }
          : t
      )
    );
  }

  function batchPayload(extra: Record<string, unknown>) {
    if (selectionMode === "filter") {
      return JSON.stringify({
        filter: serverFilter,
        excluded_ids: [...excludedIds],
        ...extra,
      });
    }
    return JSON.stringify({
      transaction_ids: [...selectedIds],
      ...extra,
    });
  }

  async function suggestRuleFromSelection() {
    if (selectedCount === 0) return;
    setBatchLoading(true);
    try {
      const res = await fetch("/api/protected/buchungsregeln/suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: batchPayload({}),
      });
      const json = (await res.json()) as {
        data?: {
          suggestion: {
            match_auftraggeber: string | null;
            match_auftraggeber_exact: boolean;
            match_kostenbereich_id: string | null;
          };
          basis_count: number;
          total_in_selection: number;
        };
        error?: string;
      };
      if (!res.ok || !json.data) {
        toast.error(json.error ?? "Keine Muster erkennbar.");
        return;
      }
      const prefill = btoa(
        encodeURIComponent(
          JSON.stringify({
            ...json.data.suggestion,
            _basis_count: json.data.basis_count,
            _total_in_selection: json.data.total_in_selection,
          })
        )
      );
      router.push(`/dashboard/buchungsregeln?prefill=${prefill}`);
    } catch {
      toast.error("Netzwerkfehler.");
    } finally {
      setBatchLoading(false);
    }
  }

  async function applyBatchRule() {
    if (!selectedRuleId || selectedCount === 0) return;
    setBatchLoading(true);
    try {
      const res = await fetch("/api/protected/transaktionen/batch-regeln", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: batchPayload({ rule_id: selectedRuleId }),
      });
      const json = (await res.json()) as { data?: { matched: number }; error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Fehler.");
        return;
      }
      toast.success(`${json.data?.matched ?? 0} Transaktion(en) zugeordnet.`);
      deactivateAll();
      setSelectedRuleId("");
      void fetchTransactions();
    } catch {
      toast.error("Netzwerkfehler.");
    } finally {
      setBatchLoading(false);
    }
  }

  async function performBatchMassnahme() {
    setBatchLoading(true);
    try {
      const res = await fetch("/api/protected/transaktionen/batch-massnahme", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: batchPayload({ funding_measure_id: selectedBatchMassnahmeId }),
      });
      const json = (await res.json()) as {
        data?: { matched: number; skipped: { id: string; reason: string }[] };
        error?: string;
      };
      if (!res.ok) {
        toast.error(json.error ?? "Fehler beim Zuordnen.");
        return;
      }
      const matched = json.data?.matched ?? 0;
      const skipped = json.data?.skipped?.length ?? 0;
      if (matched > 0) toast.success(`${matched} Fördermassnahme(n) zugeordnet.`);
      if (skipped > 0) toast.error(`${skipped} übersprungen (z.B. Transaktionen ohne KST-Splits).`);
      deactivateAll();
      setSelectedBatchMassnahmeId("");
      void fetchTransactions();
    } catch {
      toast.error("Netzwerkfehler.");
    } finally {
      setBatchLoading(false);
      setBatchOverwriteConfirm(null);
    }
  }

  function applyBatchMassnahme() {
    if (!selectedBatchMassnahmeId || selectedCount === 0) return;
    // Doppelförderungs-Schutz: nur in 'ids'-Mode sichtbar berechenbar
    // (in Filter-Mode würden wir die Information ohne extra Fetch nicht haben — dann skip).
    if (selectionMode === "ids") {
      const overwriteCount = transactions.filter(
        (t) =>
          selectedIds.has(t.id) &&
          t.massnahme &&
          t.massnahme.id !== selectedBatchMassnahmeId
      ).length;
      if (overwriteCount > 0) {
        const target = massnahmen.find((m) => m.id === selectedBatchMassnahmeId);
        setBatchOverwriteConfirm({
          targetMassnahme: target?.name ?? "—",
          overwriteCount,
        });
        return;
      }
    }
    void performBatchMassnahme();
  }

  const total = pagination?.total ?? 0;
  const pages = pagination?.pages ?? 1;

  return (
    <PageShell width="wide" className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-soft-ink">Transaktionen</h1>
          <p className="text-sm text-soft-ink3 mt-1">
            {loading ? "Lädt…" : `${total} Einträge`}
          </p>
        </div>
        <Link
          href="/dashboard/transaktionen/import"
          className="inline-flex items-center gap-2 px-4 py-2 bg-soft-accent text-white text-sm font-medium rounded-soft-xs hover:bg-soft-accentDark transition-colors"
        >
          + Importieren
        </Link>
      </div>

      {/* KPI-Karten */}
      {kpis && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="rounded-soft-sm border border-soft-line bg-white px-4 py-3">
            <p className="text-xs text-soft-ink3 mb-1">Einnahmen</p>
            <p className="text-lg font-bold text-soft-ok">{formatEur(kpis.einnahmen)}</p>
          </div>
          <div className="rounded-soft-sm border border-soft-line bg-white px-4 py-3">
            <p className="text-xs text-soft-ink3 mb-1">Ausgaben</p>
            <p className="text-lg font-bold text-soft-crit">{formatEur(kpis.ausgaben)}</p>
          </div>
          <div className="rounded-soft-sm border border-soft-line bg-white px-4 py-3">
            <p className="text-xs text-soft-ink3 mb-1">Cashflow</p>
            <p className={`text-lg font-bold ${kpis.cashflow >= 0 ? "text-soft-accent" : "text-soft-crit"}`}>
              {formatEur(kpis.cashflow)}
            </p>
          </div>
          <div className="rounded-soft-sm border border-soft-line bg-white px-4 py-3">
            <p className="text-xs text-soft-ink3 mb-1">Zugeordnet</p>
            <p className="text-lg font-bold text-soft-ink">
              {kpis.zugeordnet} / {kpis.total}
              <span className="text-sm font-normal text-soft-ink4 ml-1">({kpis.fortschritt}%)</span>
            </p>
            <div className="mt-1.5 h-1.5 rounded-full bg-soft-surfaceAlt">
              <div
                className="h-full rounded-full bg-soft-accent transition-all"
                style={{ width: `${kpis.fortschritt}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Filter-Tabs (Status) */}
      <div className="flex gap-2 flex-wrap">
        {FILTER_TABS.map((tab) => {
          const isActive = statusParam === tab.value;
          const params = new URLSearchParams(searchParams.toString());
          if (tab.value) params.set("status", tab.value);
          else params.delete("status");
          params.delete("page");
          const qs = params.toString();
          const href = qs ? `${pathname}?${qs}` : pathname;
          return (
            <Link
              key={tab.value || "alle"}
              href={href}
              className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                isActive
                  ? "bg-soft-accentSoft text-soft-accent"
                  : "bg-soft-surfaceAlt text-soft-ink2 hover:bg-soft-line2"
              }`}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>

      {/* Filter-Strip */}
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="search"
            value={filterDraft.search ?? ""}
            onChange={(e) =>
              setFilterDraft((d) => ({ ...d, search: e.target.value || undefined }))
            }
            onKeyDown={(e) => e.key === "Enter" && applyDraft()}
            placeholder="Auftraggeber oder Verwendungszweck…"
            className="flex-1 min-w-[200px] rounded-soft-xs border border-soft-line bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
          />
          <input
            type="date"
            value={filterDraft.datum_von ?? ""}
            onChange={(e) =>
              setFilterDraft((d) => ({ ...d, datum_von: e.target.value || undefined }))
            }
            className="rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
            aria-label="Datum von"
          />
          <span className="text-soft-ink4 text-sm">–</span>
          <input
            type="date"
            value={filterDraft.datum_bis ?? ""}
            onChange={(e) =>
              setFilterDraft((d) => ({ ...d, datum_bis: e.target.value || undefined }))
            }
            className="rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
            aria-label="Datum bis"
          />
          <button
            type="button"
            onClick={applyDraft}
            className="rounded-soft-xs bg-soft-accent text-white text-sm px-3 py-1.5 hover:bg-soft-accentDark transition-colors"
          >
            Anwenden
          </button>
          <button
            type="button"
            onClick={() => setFilterPanelOpen((s) => !s)}
            className="inline-flex items-center gap-1.5 rounded-soft-xs border border-soft-line bg-white text-soft-ink2 text-sm px-3 py-1.5 hover:bg-soft-surfaceAlt transition-colors"
            aria-label="Erweiterte Filter"
          >
            <SlidersHorizontal className="h-4 w-4" />
            Mehr Filter
          </button>
        </div>

        {filterPanelOpen && (
          <div className="rounded-soft-sm border border-soft-line bg-soft-surfaceAlt p-3 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-soft-ink3">Kostenbereich</label>
              <select
                value={filterDraft.kostenbereich_id ?? ""}
                onChange={(e) =>
                  setFilterDraft((d) => ({
                    ...d,
                    kostenbereich_id: e.target.value || undefined,
                  }))
                }
                className="rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
              >
                <option value="">— alle —</option>
                {kostenbereiche.map((k) => (
                  <option key={k.id} value={k.id}>
                    {k.bezeichnung}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-soft-ink3">Kostenstelle</label>
              <select
                value={filterDraft.cost_center_id ?? ""}
                onChange={(e) =>
                  setFilterDraft((d) => ({
                    ...d,
                    cost_center_id: e.target.value || undefined,
                  }))
                }
                className="rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
              >
                <option value="">— alle —</option>
                {kostenstellen.map((k) => (
                  <option key={k.id} value={k.id}>
                    {k.parent_id ? `  └ ${k.code} — ${k.name}` : `${k.code} — ${k.name}`}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-soft-ink3">Fördermassnahme</label>
              <select
                value={filterDraft.funding_measure_id ?? ""}
                onChange={(e) =>
                  setFilterDraft((d) => ({
                    ...d,
                    funding_measure_id: e.target.value || undefined,
                  }))
                }
                className="rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
              >
                <option value="">— alle —</option>
                {massnahmen.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-soft-ink3">Zuordnungs-Status</label>
              <select
                value={filterDraft.has_massnahme ?? ""}
                onChange={(e) =>
                  setFilterDraft((d) => ({
                    ...d,
                    has_massnahme: e.target.value || undefined,
                  }))
                }
                className="rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
              >
                <option value="">— alle —</option>
                <option value="true">Mit Massnahme</option>
                <option value="false">Ohne Massnahme</option>
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-soft-ink3">Konfidenz</label>
              <select
                value={filterDraft.confidence ?? ""}
                onChange={(e) =>
                  setFilterDraft((d) => ({ ...d, confidence: e.target.value || undefined }))
                }
                className="rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
              >
                <option value="">— alle —</option>
                <option value="ORANGE">ORANGE (Review)</option>
                <option value="GELB">GELB</option>
                <option value="GRUEN">GRÜN</option>
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-soft-ink3">Bankkonto</label>
              <select
                value={filterDraft.bank_account_id ?? ""}
                onChange={(e) =>
                  setFilterDraft((d) => ({
                    ...d,
                    bank_account_id: e.target.value || undefined,
                  }))
                }
                className="rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
              >
                <option value="">— alle —</option>
                {bankAccounts.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.bezeichnung}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-soft-ink3">IBAN-Partner (exakt)</label>
              <input
                type="text"
                value={filterDraft.iban_partner ?? ""}
                onChange={(e) =>
                  setFilterDraft((d) => ({ ...d, iban_partner: e.target.value || undefined }))
                }
                placeholder="DE…"
                className="rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-soft-accent"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-soft-ink3">Betrag von €</label>
              <input
                type="number"
                step="0.01"
                value={filterDraft.betrag_min ?? ""}
                onChange={(e) =>
                  setFilterDraft((d) => ({ ...d, betrag_min: e.target.value || undefined }))
                }
                className="rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-soft-ink3">Betrag bis €</label>
              <input
                type="number"
                step="0.01"
                value={filterDraft.betrag_max ?? ""}
                onChange={(e) =>
                  setFilterDraft((d) => ({ ...d, betrag_max: e.target.value || undefined }))
                }
                className="rounded-soft-xs border border-soft-line bg-white px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
              />
            </div>
            <div className="flex items-end gap-2">
              <button
                type="button"
                onClick={applyDraft}
                className="flex-1 rounded-soft-xs bg-soft-accent text-white text-sm px-3 py-1.5 hover:bg-soft-accentDark transition-colors"
              >
                Anwenden
              </button>
              <button
                type="button"
                onClick={clearAllFilters}
                className="rounded-soft-xs border border-soft-line bg-white text-soft-ink2 text-sm px-3 py-1.5 hover:bg-soft-line transition-colors"
              >
                Alle löschen
              </button>
            </div>
          </div>
        )}

        {/* Aktive-Filter-Chips */}
        {Object.keys(activeFilters).filter((k) => k !== "status").length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-soft-ink3 mr-1">Aktive Filter:</span>
            {FILTER_PARAM_KEYS.filter((k) => k !== "status" && activeFilters[k]).map((k) => {
              const v = activeFilters[k]!;
              let label = `${k}: ${v}`;
              if (k === "funding_measure_id") {
                const m = massnahmen.find((x) => x.id === v);
                if (m) label = `Massnahme: ${m.name}`;
              } else if (k === "kostenbereich_id") {
                const kb = kostenbereiche.find((x) => x.id === v);
                if (kb) label = `Kostenbereich: ${kb.bezeichnung}`;
              } else if (k === "cost_center_id") {
                const kst = kostenstellen.find((x) => x.id === v);
                if (kst) label = `KST: ${kst.code} — ${kst.name}`;
              } else if (k === "bank_account_id") {
                const ba = bankAccounts.find((x) => x.id === v);
                if (ba) label = `Konto: ${ba.bezeichnung}`;
              } else if (k === "has_massnahme") {
                label = v === "true" ? "Mit Massnahme" : "Ohne Massnahme";
              } else if (k === "search") {
                label = `Suche: „${v}"`;
              } else if (k === "datum_von") {
                label = `ab ${v}`;
              } else if (k === "datum_bis") {
                label = `bis ${v}`;
              } else if (k === "betrag_min") {
                label = `≥ ${v}€`;
              } else if (k === "betrag_max") {
                label = `≤ ${v}€`;
              } else if (k === "iban_partner") {
                label = `IBAN: ${v}`;
              } else if (k === "confidence") {
                label = `Konfidenz: ${v}`;
              }
              return (
                <button
                  key={k}
                  type="button"
                  onClick={() => clearFilter(k)}
                  className="inline-flex items-center gap-1 rounded-full bg-soft-accentSoft text-soft-accent text-xs px-2 py-0.5 hover:bg-soft-accent hover:text-white transition-colors"
                >
                  {label}
                  <X className="h-3 w-3" />
                </button>
              );
            })}
            <button
              type="button"
              onClick={clearAllFilters}
              className="text-xs text-soft-ink3 hover:text-soft-accent ml-1 underline"
            >
              alle entfernen
            </button>
          </div>
        )}
      </div>

      {/* Inhalt */}
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-10 bg-soft-surfaceAlt rounded-soft-xs animate-pulse" />
          ))}
        </div>
      ) : transactions.length === 0 ? (
        <div className="text-center py-20">
          <FileText className="h-10 w-10 text-soft-ink4 mx-auto mb-4" />
          <p className="text-soft-ink2 font-medium">
            {statusParam
              ? "Keine Transaktionen mit diesem Filter"
              : "Noch keine Transaktionen importiert"}
          </p>
          {!statusParam && (
            <Link
              href="/dashboard/transaktionen/import"
              className="mt-3 inline-block text-soft-accent text-sm hover:underline"
            >
              Ersten Kontoauszug importieren →
            </Link>
          )}
        </div>
      ) : (
        <>
          {/* Fortschrittsbalken */}
          {kpis && kpis.total > 0 && (
            <div className="flex items-center gap-3 text-sm text-soft-ink2">
              <span className="shrink-0 text-xs font-medium text-soft-ink3">Zuordnungsfortschritt</span>
              <div className="flex-1 h-2 rounded-full bg-soft-surfaceAlt">
                <div
                  className="h-full rounded-full bg-soft-accent transition-all"
                  style={{ width: `${kpis.fortschritt}%` }}
                />
              </div>
              <span className="shrink-0 text-xs text-soft-ink3">
                {kpis.zugeordnet} von {kpis.total} zugeordnet ({kpis.fortschritt}%)
              </span>
            </div>
          )}

          {/* Hinweis wenn keine Buchungsregeln */}
          {bookingRules.length === 0 && (
            <div className="text-xs text-soft-ink3 bg-soft-line2 border border-soft-line rounded-soft-xs px-4 py-2">
              Noch keine Buchungsregeln.{" "}
              <Link href="/dashboard/buchungsregeln" className="text-soft-accent hover:underline font-medium">
                Jetzt anlegen
              </Link>
              {" "}— Buchungsregeln werden per Checkbox-Auswahl auf Transaktionen angewandt.
            </div>
          )}

          {/* Select-All-Across-Pages Banner */}
          {showAcrossPagesBanner && (
            <div className="rounded-soft-sm bg-soft-warnSoft border border-soft-warn/40 px-4 py-2.5 text-sm text-soft-warn flex items-center justify-between gap-3 flex-wrap">
              <span>
                Alle {transactions.length} auf dieser Seite sind ausgewählt.
              </span>
              <button
                type="button"
                onClick={activateFilterMode}
                className="underline font-medium hover:no-underline"
              >
                Alle {pagination?.total ?? 0} gefilterten Transaktionen auswählen →
              </button>
            </div>
          )}

          {/* Batch ActionBar */}
          {selectedCount > 0 && (
            <div className="flex flex-wrap items-center gap-3 rounded-soft-sm bg-soft-accentSoft border border-soft-accent/30 px-4 py-3">
              <span className="text-sm text-soft-accent font-medium">
                {selectedCount} ausgewählt{selectionMode === "filter" ? " (über alle Seiten)" : ""}
              </span>

              {/* Buchungsregel */}
              <select
                className="rounded-soft-xs border border-soft-accent/30 bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                value={selectedRuleId}
                onChange={(e) => setSelectedRuleId(e.target.value)}
              >
                <option value="">— Buchungsregel —</option>
                {bookingRules.filter((r) => r.aktiv).map((r) => (
                  <option key={r.id} value={r.id}>{r.name}</option>
                ))}
                {bookingRules.filter((r) => r.aktiv).length === 0 && (
                  <option disabled value="">Noch keine aktiven Regeln</option>
                )}
              </select>
              <button
                type="button"
                disabled={!selectedRuleId || batchLoading}
                onClick={applyBatchRule}
                className="rounded-soft-xs bg-soft-accent text-white text-sm px-3 py-1.5 hover:bg-soft-accentDark disabled:opacity-50 transition-colors"
              >
                {batchLoading ? "Wird angewandt…" : "Anwenden"}
              </button>

              <span className="text-soft-ink4 text-sm hidden sm:block">|</span>

              {/* Fördermassnahme (gefiltert nach KSTs der ausgewählten TXs) */}
              {(() => {
                const selectedTxs = transactions.filter((t) => isRowSelected(t.id));
                const selectedKstSets = selectedTxs
                  .map((t) => new Set((t.splits ?? []).map((s) => s.cost_center.id)))
                  .filter((s) => s.size > 0);
                const cat = categorizeMassnahmen(massnahmen, selectedKstSets);
                return (
                  <div className="flex items-center gap-2">
                    <select
                      className="rounded-soft-xs border border-soft-accent/30 bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
                      value={selectedBatchMassnahmeId}
                      onChange={(e) => setSelectedBatchMassnahmeId(e.target.value)}
                    >
                      <option value="">— Fördermassnahme —</option>
                      {cat.primary.length > 0 && (
                        <optgroup label="Vorschläge (passen für alle Auswahlen)">
                          {cat.primary.map((m) => (
                            <option key={m.id} value={m.id}>{m.name}</option>
                          ))}
                        </optgroup>
                      )}
                      {cat.wildcard.length > 0 && (
                        <optgroup label="Ohne KST-Beschränkung">
                          {cat.wildcard.map((m) => (
                            <option key={m.id} value={m.id}>{m.name}</option>
                          ))}
                        </optgroup>
                      )}
                      {batchShowAllMassnahmen && cat.others.length > 0 && (
                        <optgroup label="Weitere (KST-Konflikt möglich)">
                          {cat.others.map((m) => (
                            <option key={m.id} value={m.id}>{m.name}</option>
                          ))}
                        </optgroup>
                      )}
                    </select>
                    {cat.others.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setBatchShowAllMassnahmen((s) => !s)}
                        className="text-xs text-soft-accent hover:underline"
                      >
                        {batchShowAllMassnahmen ? "nur passende" : `+${cat.others.length}`}
                      </button>
                    )}
                  </div>
                );
              })()}
              <button
                type="button"
                disabled={!selectedBatchMassnahmeId || batchLoading}
                onClick={applyBatchMassnahme}
                className="rounded-soft-xs bg-soft-ok text-white text-sm px-3 py-1.5 hover:bg-soft-ok/85 disabled:opacity-50 transition-colors"
              >
                {batchLoading ? "Wird angewandt…" : "Zuordnen"}
              </button>

              <span className="text-soft-ink4 text-sm hidden sm:block">|</span>

              <button
                type="button"
                onClick={() => void suggestRuleFromSelection()}
                disabled={batchLoading}
                className="rounded-soft-xs border border-soft-accent/30 bg-white text-soft-accent text-sm px-3 py-1.5 hover:bg-soft-accent hover:text-white disabled:opacity-50 transition-colors"
                title="Aus dieser Auswahl ein Muster ableiten und als neue Buchungsregel anlegen"
              >
                Regel daraus erstellen
              </button>

              <button
                type="button"
                onClick={deactivateAll}
                className="text-xs text-soft-accent hover:underline ml-auto"
              >
                Auswahl aufheben
              </button>
            </div>
          )}

          <div className="overflow-x-auto rounded-soft-sm border border-soft-line">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-soft-surfaceAlt">
                <tr>
                  <th className="px-3 py-3 w-8">
                    <input
                      type="checkbox"
                      className="rounded border-soft-line"
                      checked={allPageSelected}
                      onChange={(e) => headerCheckboxToggle(e.target.checked)}
                    />
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-soft-ink3 uppercase tracking-wider">
                    Typ
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-soft-ink3 uppercase tracking-wider">
                    Datum
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-soft-ink3 uppercase tracking-wider">
                    Auftraggeber / Verwendungszweck
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-soft-ink3 uppercase tracking-wider">
                    Betrag
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-soft-ink3 uppercase tracking-wider">
                    Kostenart
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-soft-ink3 uppercase tracking-wider">
                    KST
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-soft-ink3 uppercase tracking-wider">
                    Fördermassnahme
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-soft-ink3 uppercase tracking-wider">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-100">
                {transactions.map((t) => {
                  const betrag = parseFloat(t.betrag);
                  const isAusgabe = betrag < 0;
                  const datum = new Date(t.datum);

                  return (
                    <tr
                      key={t.id}
                      className="hover:bg-soft-surfaceAlt transition-colors cursor-pointer"
                      onClick={() => {
                        window.location.href = `/dashboard/transaktionen/${t.id}`;
                      }}
                    >
                      <td className="px-3 py-2.5" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          className="rounded border-soft-line"
                          checked={isRowSelected(t.id)}
                          onChange={(e) => toggleRow(t.id, e.target.checked)}
                        />
                      </td>
                      <td className="px-3 py-2.5">
                        <Badge variant={isAusgabe ? "muted" : "success"}>
                          {isAusgabe ? "Ausgabe" : "Einnahme"}
                        </Badge>
                      </td>
                      <td className="px-4 py-2.5 text-soft-ink3 whitespace-nowrap text-xs">
                        {datum.toLocaleDateString("de-DE")}
                      </td>
                      <td className="px-4 py-2.5 text-soft-ink max-w-[200px]">
                        <div className="truncate font-medium text-xs">
                          {t.auftraggeber ?? (
                            <span className="text-soft-ink4 italic">unbekannt</span>
                          )}
                        </div>
                        <div className="truncate text-xs text-soft-ink4 mt-0.5">
                          {t.verwendungszweck ?? ""}
                        </div>
                      </td>
                      <td
                        className={`px-4 py-2.5 text-right font-mono font-semibold whitespace-nowrap text-sm ${
                          isAusgabe ? "text-soft-crit" : "text-soft-ok"
                        }`}
                      >
                        {formatEur(betrag)}
                      </td>
                      <td className="px-4 py-2.5" onClick={(e) => e.stopPropagation()}>
                        <KostenbereichSelect
                          transactionId={t.id}
                          currentKostenbereichId={t.kostenbereich?.id ?? null}
                          onSuccess={() => void fetchTransactions()}
                        />
                      </td>
                      <td className="px-4 py-2.5 max-w-[140px]">
                        {(t._count?.splits ?? 0) > 0 ? (
                          <KstBadge splits={t.splits} />
                        ) : (
                          <Link
                            href={`/dashboard/transaktionen/${t.id}`}
                            className="text-xs text-soft-accent hover:underline"
                            onClick={(e) => e.stopPropagation()}
                          >
                            — Zuordnen →
                          </Link>
                        )}
                      </td>
                      <td className="px-4 py-2.5" onClick={(e) => e.stopPropagation()}>
                        {t.massnahme ? (
                          <span className="text-xs font-medium text-soft-ok bg-soft-okSoft border border-soft-ok/30 rounded px-1.5 py-0.5 truncate max-w-[140px] inline-block">
                            {t.massnahme.name}
                          </span>
                        ) : (
                          <MassnahmeDropdown
                            transaction={t}
                            massnahmen={massnahmen}
                            onAssigned={handleMassnahmeAssigned}
                          />
                        )}
                      </td>
                      <td className="px-4 py-2.5">
                        <Badge variant={STATUS_COLORS[t.status] ?? ("muted" as const)}>
                          {STATUS_LABELS[t.status] ?? t.status}
                        </Badge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Paginierung */}
      {pages > 1 && (
        <div className="flex gap-2 justify-center pt-2">
          {Array.from({ length: pages }, (_, i) => i + 1).map((p) => {
            const params = new URLSearchParams(searchParams.toString());
            params.set("page", String(p));
            return (
              <Link
                key={p}
                href={`${pathname}?${params.toString()}`}
                className={`w-8 h-8 flex items-center justify-center rounded text-sm font-medium transition-colors ${
                  p === pageParam
                    ? "bg-soft-accent text-white"
                    : "bg-soft-surfaceAlt text-soft-ink2 hover:bg-soft-line2"
                }`}
              >
                {p}
              </Link>
            );
          })}
        </div>
      )}

      {/* Doppelförderungs-Schutz: Bestätigung beim Überschreiben bestehender Zuordnungen */}
      <ConfirmDialog
        open={batchOverwriteConfirm !== null}
        title="Bestehende Zuordnungen ersetzen?"
        description={
          batchOverwriteConfirm
            ? `${batchOverwriteConfirm.overwriteCount} der ausgewählten Transaktionen sind bereits einer anderen Fördermassnahme zugeordnet. Beim Fortfahren werden diese Zuordnungen auf „${batchOverwriteConfirm.targetMassnahme}" umgehängt.`
            : ""
        }
        confirmLabel="Auf neue Massnahme umhängen"
        variant="danger"
        loading={batchLoading}
        onConfirm={() => void performBatchMassnahme()}
        onCancel={() => setBatchOverwriteConfirm(null)}
      />
    </PageShell>
  );
}

export function TransaktionenClient() {
  return (
    <Suspense
      fallback={
        <PageShell width="wide" className="space-y-6">
          <div className="h-8 bg-soft-surfaceAlt rounded-soft-xs animate-pulse w-48" />
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-10 bg-soft-surfaceAlt rounded-soft-xs animate-pulse" />
          ))}
        </PageShell>
      }
    >
      <TransaktionenInner />
    </Suspense>
  );
}
