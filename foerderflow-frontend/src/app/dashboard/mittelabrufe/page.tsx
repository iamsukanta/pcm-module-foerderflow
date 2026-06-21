"use client";

import { useState, useEffect, useCallback } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { Plus, AlertTriangle, List, Calendar } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { SkeletonCard } from "@/components/ui/SkeletonCard";
import { getFristStatus, getTageVerbleibend, type FristStatus } from "@/lib/mittelabruf-frist";
import { PageShell } from "@/components/ui/PageShell";

// Schwere Client-Komponenten erst laden, wenn der Nutzer sie tatsächlich öffnet.
const MittelabrufForm = dynamic(
  () => import("@/components/forms/MittelabrufForm").then((m) => m.MittelabrufForm),
  { ssr: false, loading: () => <SkeletonCard /> },
);
const MittelabrufKalender = dynamic(
  () => import("@/components/ui/MittelabrufKalender").then((m) => m.MittelabrufKalender),
  { ssr: false, loading: () => <SkeletonCard /> },
);

type Mittelabruf = {
  id: string;
  abruf_datum: string;
  betrag: string;
  frist_bis: string;
  betrag_verwendet: string;
  status: string;
  funding_measure: { name: string; funder: { name: string } };
};

type HaushaltsjahrOption = { id: string; jahr: number };

type FilterTab = "alle" | "offen" | "warnung" | "kritisch" | "abgelaufen" | "verwendet";
type ViewMode = "liste" | "kalender";

function fristBadgeVariant(status: FristStatus): "success" | "warning" | "danger" | "muted" {
  switch (status) {
    case "OK":
      return "success";
    case "WARNING":
      return "warning";
    case "KRITISCH":
      return "danger";
    case "ABGELAUFEN":
      return "muted";
  }
}

function formatEur(val: string | number): string {
  return Number(val).toLocaleString("de-DE", { style: "currency", currency: "EUR" });
}

export default function MittelabrufePage() {
  const [abrufe, setAbrufe] = useState<Mittelabruf[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterTab>("alle");
  const [showForm, setShowForm] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>("liste");
  const [haushaltsjahre, setHaushaltsjahre] = useState<HaushaltsjahrOption[]>([]);
  const [selectedHjId, setSelectedHjId] = useState<string>("");

  const load = useCallback(() => {
    setLoading(true);
    fetch("/api/protected/mittelabrufe")
      .then((r) => r.json())
      .then((j) => setAbrufe(j.data ?? []))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    fetch("/api/protected/haushaltsjahre")
      .then((r) => r.json())
      .then((j) => {
        const list: HaushaltsjahrOption[] = (j.data ?? []).map(
          (h: { id: string; jahr: number }) => ({
            id: h.id,
            jahr: h.jahr,
          }),
        );
        setHaushaltsjahre(list);
        if (list.length > 0) setSelectedHjId(list[0].id);
      });
  }, []);

  const enriched = abrufe.map((a) => {
    const frist_bis = new Date(a.frist_bis);
    const tage = getTageVerbleibend(frist_bis);
    const fristStatus = getFristStatus(frist_bis, a.status);
    return { ...a, tage, fristStatus };
  });

  const kritischCount = enriched.filter(
    (a) => a.fristStatus === "KRITISCH" && a.status === "ABGERUFEN",
  ).length;
  const abgelaufenCount = enriched.filter(
    (a) => a.fristStatus === "ABGELAUFEN" && a.status !== "VERWENDET" && a.status !== "ZURUECKGEZAHLT",
  ).length;

  const filtered = enriched.filter((a) => {
    if (filter === "alle") return true;
    if (filter === "offen") return a.status === "ABGERUFEN" && a.fristStatus === "OK";
    if (filter === "warnung") return a.fristStatus === "WARNING" && a.status === "ABGERUFEN";
    if (filter === "kritisch") return a.fristStatus === "KRITISCH" && a.status === "ABGERUFEN";
    if (filter === "abgelaufen") return a.fristStatus === "ABGELAUFEN";
    if (filter === "verwendet") return a.status === "VERWENDET" || a.status === "ZURUECKGEZAHLT";
    return true;
  });

  const TABS: { key: FilterTab; label: string }[] = [
    { key: "alle", label: "Alle" },
    { key: "offen", label: "Offen" },
    { key: "warnung", label: "Warnung" },
    { key: "kritisch", label: "Kritisch" },
    { key: "abgelaufen", label: "Abgelaufen" },
    { key: "verwendet", label: "Verwendet" },
  ];

  return (
    <PageShell width="wide">
      {/* Header */}
      <div className="flex items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-soft-ink">Mittelabruf-Tracking</h1>
          <p className="text-sm text-soft-ink3 mt-1">
            Überwachung abgerufener Fördermittel und Verwendungsfristen
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* View toggle */}
          <div className="flex rounded-soft-xs border border-soft-line bg-soft-line2 p-0.5 gap-0.5">
            <button
              onClick={() => setViewMode("liste")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-soft-xs text-sm font-medium transition-colors ${
                viewMode === "liste"
                  ? "bg-soft-surface text-soft-ink shadow-soft"
                  : "text-soft-ink2 hover:text-soft-ink"
              }`}
            >
              <List className="h-3.5 w-3.5" />
              Liste
            </button>
            <button
              onClick={() => setViewMode("kalender")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-soft-xs text-sm font-medium transition-colors ${
                viewMode === "kalender"
                  ? "bg-soft-surface text-soft-ink shadow-soft"
                  : "text-soft-ink2 hover:text-soft-ink"
              }`}
            >
              <Calendar className="h-3.5 w-3.5" />
              Cashflow
            </button>
          </div>
          <button
            onClick={() => setShowForm((v) => !v)}
            className="flex items-center gap-2 bg-soft-accent text-white px-4 py-2 rounded-soft-sm text-sm font-medium hover:bg-soft-accentDark transition-colors shadow-soft min-h-[44px]"
          >
            <Plus className="h-4 w-4" />
            Neuer Abruf
          </button>
        </div>
      </div>

      {/* Alert banners */}
      {abgelaufenCount > 0 && (
        <div className="mb-4 p-3 rounded-soft-xs bg-soft-crit text-white text-sm font-medium flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {abgelaufenCount} {abgelaufenCount === 1 ? "Abruf ist" : "Abrufe sind"} abgelaufen
        </div>
      )}
      {kritischCount > 0 && (
        <div className="mb-4 p-3 rounded-soft-xs bg-soft-critSoft border border-soft-crit/20 text-soft-crit text-sm font-medium flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {kritischCount} {kritischCount === 1 ? "Abruf läuft" : "Abrufe laufen"} in weniger als 7
          Tagen ab
        </div>
      )}

      {/* Inline form */}
      {showForm && (
        <div className="mb-6 p-6 bg-soft-surface rounded-soft-sm border border-soft-line shadow-soft">
          <h2 className="text-base font-semibold text-soft-ink mb-4">Neuen Mittelabruf erfassen</h2>
          <MittelabrufForm
            onSuccess={() => {
              setShowForm(false);
              load();
            }}
          />
        </div>
      )}

      {/* Kalenderansicht */}
      {viewMode === "kalender" && (
        <div>
          {/* Haushaltsjahr-Selektor */}
          {haushaltsjahre.length > 0 && (
            <div className="flex items-center gap-3 mb-6">
              <label className="text-sm text-soft-ink3 shrink-0">Haushaltsjahr:</label>
              <select
                value={selectedHjId}
                onChange={(e) => setSelectedHjId(e.target.value)}
                className="rounded-soft-xs border border-soft-line bg-soft-surface px-3 py-1.5 text-sm text-soft-ink focus:outline-none focus:ring-2 focus:ring-soft-accent"
              >
                {haushaltsjahre.map((h) => (
                  <option key={h.id} value={h.id}>
                    {h.jahr}
                  </option>
                ))}
              </select>
            </div>
          )}
          {selectedHjId ? (
            <MittelabrufKalender haushaltsjahrId={selectedHjId} />
          ) : (
            <div className="text-sm text-soft-ink2 py-8 text-center">
              Kein Haushaltsjahr verfügbar.
            </div>
          )}
        </div>
      )}

      {/* Listenansicht */}
      {viewMode === "liste" && (
        <>
          {/* Filter tabs */}
          <div className="flex gap-1 mb-4 border-b border-soft-line">
            {TABS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={`px-4 py-2 text-sm font-medium rounded-t-soft-xs transition-colors ${
                  filter === key
                    ? "bg-soft-surface border border-b-soft-surface border-soft-line text-soft-accent -mb-px"
                    : "text-soft-ink2 hover:text-soft-ink"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Table */}
          {loading ? (
            <div className="text-sm text-soft-ink2">Lade…</div>
          ) : filtered.length === 0 ? (
            <div className="text-sm text-soft-ink2 py-8 text-center">Keine Einträge gefunden.</div>
          ) : (
            <div className="bg-soft-surface rounded-soft-sm border border-soft-line overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-soft-line2 text-soft-ink2 text-xs uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-3 text-left">Massnahme</th>
                    <th className="px-4 py-3 text-left">Abruf-Datum</th>
                    <th className="px-4 py-3 text-right">Betrag</th>
                    <th className="px-4 py-3 text-left">Frist bis</th>
                    <th className="px-4 py-3 text-right">Tage verbleibend</th>
                    <th className="px-4 py-3 text-right">Verwendet</th>
                    <th className="px-4 py-3 text-left">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-soft-line">
                  {filtered.map((a) => {
                    const betrag = Number(a.betrag);
                    const verwendet = Number(a.betrag_verwendet);
                    const progress = betrag > 0 ? Math.min(100, (verwendet / betrag) * 100) : 0;
                    const progressColor =
                      a.fristStatus === "KRITISCH" || a.fristStatus === "ABGELAUFEN"
                        ? progress < 50
                          ? "bg-soft-crit"
                          : "bg-soft-ok"
                        : "bg-soft-ok";

                    return (
                      <tr
                        key={a.id}
                        className="hover:bg-soft-line2 cursor-pointer transition-colors"
                      >
                        <td className="px-4 py-3">
                          <Link href={`/dashboard/mittelabrufe/${a.id}`} className="block">
                            <span className="font-medium text-soft-ink">
                              {a.funding_measure.name}
                            </span>
                            <span className="block text-xs text-soft-ink3">
                              {a.funding_measure.funder.name}
                            </span>
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-soft-ink2">
                          <Link href={`/dashboard/mittelabrufe/${a.id}`} className="block">
                            {new Date(a.abruf_datum).toLocaleDateString("de-DE")}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-right numeric text-soft-ink">
                          <Link href={`/dashboard/mittelabrufe/${a.id}`} className="block">
                            {formatEur(a.betrag)}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-soft-ink2">
                          <Link href={`/dashboard/mittelabrufe/${a.id}`} className="block">
                            {new Date(a.frist_bis).toLocaleDateString("de-DE")}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Link href={`/dashboard/mittelabrufe/${a.id}`} className="block">
                            <span
                              className={`font-medium ${
                                a.fristStatus === "OK"
                                  ? "text-soft-ok"
                                  : a.fristStatus === "WARNING"
                                    ? "text-soft-warn"
                                    : a.fristStatus === "KRITISCH"
                                      ? "text-soft-crit"
                                      : "text-soft-ink3"
                              }`}
                            >
                              {a.tage >= 0 ? `${a.tage} Tage` : `${Math.abs(a.tage)} Tage überfällig`}
                            </span>
                          </Link>
                        </td>
                        <td className="px-4 py-3">
                          <Link href={`/dashboard/mittelabrufe/${a.id}`} className="block">
                            <div className="flex items-center gap-2">
                              <div className="flex-1 bg-soft-line2 rounded-full h-1.5 min-w-[60px]">
                                <div
                                  className={`h-1.5 rounded-full ${progressColor}`}
                                  style={{ width: `${progress}%` }}
                                />
                              </div>
                              <span className="text-xs text-soft-ink3 numeric whitespace-nowrap">
                                {formatEur(a.betrag_verwendet)}
                              </span>
                            </div>
                          </Link>
                        </td>
                        <td className="px-4 py-3">
                          <Link href={`/dashboard/mittelabrufe/${a.id}`} className="block">
                            <Badge variant={fristBadgeVariant(a.fristStatus)}>
                              {a.status === "VERWENDET"
                                ? "Verwendet"
                                : a.status === "ZURUECKGEZAHLT"
                                  ? "Zurückgezahlt"
                                  : a.status === "ABGELAUFEN"
                                    ? "Abgelaufen"
                                    : "Abgerufen"}
                            </Badge>
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </PageShell>
  );
}
