"use client";

import { useState, useEffect, useCallback, use } from "react";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { useToast } from "@/components/ui/ToastProvider";
import { getFristStatus, getTageVerbleibend, type FristStatus } from "@/lib/mittelabruf-frist";
import { PageShell } from "@/components/ui/PageShell";

type MittelabrufDetail = {
  id: string;
  abruf_datum: string;
  betrag: string;
  frist_bis: string;
  betrag_verwendet: string;
  betrag_zurueck: string | null;
  verwendungsfrist_tage: number;
  status: string;
  notiz: string | null;
  funding_measure: { name: string; funder: { name: string } };
  fiscal_year: { jahr: number };
};

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

export default function MittelabrufDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { success, error } = useToast();

  const [abruf, setAbruf] = useState<MittelabrufDetail | null>(null);
  const [loading, setLoading] = useState(true);

  // Status-action state
  const [showVerwendetInput, setShowVerwendetInput] = useState(false);
  const [betragsInput, setBetragsInput] = useState("");
  const [showRueckzahlungInput, setShowRueckzahlungInput] = useState(false);
  const [rueckzahlungInput, setRueckzahlungInput] = useState("");

  // Frist-Anpassen state
  const [showFristInput, setShowFristInput] = useState(false);
  const [neueFristTage, setNeueFristTage] = useState("");

  // Notiz state
  const [notiz, setNotiz] = useState("");
  const [notizDirty, setNotizDirty] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    fetch(`/api/protected/mittelabrufe/${id}`)
      .then((r) => r.json())
      .then((j) => {
        setAbruf(j.data);
        setNotiz(j.data?.notiz ?? "");
      })
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return <div className="p-6 text-sm text-soft-ink3">Lade…</div>;
  }
  if (!abruf) {
    return (
      <div className="p-6">
        <p className="text-sm text-soft-ink3">Mittelabruf nicht gefunden.</p>
        <Link
          href="/dashboard/mittelabrufe"
          className="text-sm text-soft-accent hover:underline mt-2 inline-block"
        >
          Zurück zur Übersicht
        </Link>
      </div>
    );
  }

  const frist_bis = new Date(abruf.frist_bis);
  const tage = getTageVerbleibend(frist_bis);
  const fristStatus = getFristStatus(frist_bis, abruf.status);
  const betragOffen = Number(abruf.betrag) - Number(abruf.betrag_verwendet);

  async function patchStatus(status: string, extra?: Record<string, unknown>) {
    const res = await fetch(`/api/protected/mittelabrufe/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, ...extra }),
    });
    const json = await res.json();
    if (!res.ok) {
      error(json.error ?? "Fehler beim Aktualisieren.");
      return false;
    }
    success("Status aktualisiert.");
    load();
    return true;
  }

  async function handleMarkVerwendet() {
    const val = parseFloat(betragsInput);
    if (isNaN(val)) {
      error("Bitte einen gültigen Betrag eingeben.");
      return;
    }
    const ok = await patchStatus("VERWENDET", { betrag_verwendet: val });
    if (ok) setShowVerwendetInput(false);
  }

  async function handleRueckzahlung() {
    const val = parseFloat(rueckzahlungInput);
    if (isNaN(val) || val <= 0) {
      error("Bitte einen gültigen Rückzahlungsbetrag eingeben.");
      return;
    }
    const ok = await patchStatus("ZURUECKGEZAHLT", { betrag_zurueck: val });
    if (ok) setShowRueckzahlungInput(false);
  }

  async function handleFristAnpassen() {
    const tageVal = parseInt(neueFristTage, 10);
    if (isNaN(tageVal) || tageVal < 1 || tageVal > 180) {
      error("Bitte eine Zahl zwischen 1 und 180 eingeben.");
      return;
    }
    const res = await fetch(`/api/protected/mittelabrufe/${id}/frist`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ verwendungsfrist_tage: tageVal }),
    });
    const json = await res.json();
    if (!res.ok) {
      error(json.error ?? "Frist konnte nicht angepasst werden.");
      return;
    }
    success("Verwendungsfrist angepasst.");
    setShowFristInput(false);
    load();
  }

  async function handleNotizSpeichern() {
    const res = await fetch(`/api/protected/mittelabrufe/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notiz }),
    });
    const json = await res.json();
    if (!res.ok) {
      error(json.error ?? "Notiz konnte nicht gespeichert werden.");
      return;
    }
    success("Notiz gespeichert.");
    setNotizDirty(false);
  }

  const isReadonly = abruf.status === "VERWENDET" || abruf.status === "ZURUECKGEZAHLT";

  return (
    <PageShell width="content">
      {/* Back */}
      <Link
        href="/dashboard/mittelabrufe"
        className="flex items-center gap-1 text-sm text-soft-ink3 hover:text-soft-ink mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Zurück zur Übersicht
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-soft-ink">{abruf.funding_measure.name}</h1>
          <p className="text-sm text-soft-ink3">
            {abruf.funding_measure.funder.name} · HJ {abruf.fiscal_year.jahr}
          </p>
        </div>
        <Badge variant={fristBadgeVariant(fristStatus)}>
          {fristStatus === "OK"
            ? "Frist OK"
            : fristStatus === "WARNING"
              ? "Warnung"
              : fristStatus === "KRITISCH"
                ? "Kritisch"
                : "Abgelaufen"}
        </Badge>
      </div>

      {/* Betrag-Übersicht */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-soft-sm border border-soft-line p-4">
          <p className="text-xs text-soft-ink4 uppercase tracking-wide mb-1">Abgerufen</p>
          <p className="text-xl font-bold text-soft-ink">{formatEur(abruf.betrag)}</p>
        </div>
        <div className="bg-white rounded-soft-sm border border-soft-line p-4">
          <p className="text-xs text-soft-ink4 uppercase tracking-wide mb-1">Verwendet</p>
          <p className="text-xl font-bold text-soft-ok">{formatEur(abruf.betrag_verwendet)}</p>
        </div>
        <div className="bg-white rounded-soft-sm border border-soft-line p-4">
          <p className="text-xs text-soft-ink4 uppercase tracking-wide mb-1">Offen</p>
          <p className={`text-xl font-bold ${betragOffen > 0 ? "text-soft-warn" : "text-soft-ink4"}`}>
            {formatEur(betragOffen)}
          </p>
        </div>
      </div>

      {/* Verwendungsfrist-Block */}
      <div className="bg-white rounded-soft-sm border border-soft-line p-5 mb-4">
        <h2 className="text-base font-semibold text-soft-ink mb-3">Verwendungsfrist</h2>
        <div className="grid grid-cols-2 gap-4 text-sm mb-4">
          <div>
            <p className="text-soft-ink4 mb-0.5">Abruf-Datum</p>
            <p className="text-soft-ink font-medium">
              {new Date(abruf.abruf_datum).toLocaleDateString("de-DE")}
            </p>
          </div>
          <div>
            <p className="text-soft-ink4 mb-0.5">Frist bis</p>
            <p className="text-soft-ink font-medium">
              {new Date(abruf.frist_bis).toLocaleDateString("de-DE")}
            </p>
          </div>
          <div>
            <p className="text-soft-ink4 mb-0.5">Konfigurierte Frist</p>
            <p className="text-soft-ink font-medium">{abruf.verwendungsfrist_tage} Tage</p>
          </div>
          <div>
            <p className="text-soft-ink4 mb-0.5">Verbleibend</p>
            <p
              className={`font-bold ${
                fristStatus === "OK"
                  ? "text-soft-ok"
                  : fristStatus === "WARNING"
                    ? "text-soft-warn"
                    : fristStatus === "KRITISCH"
                      ? "text-soft-crit"
                      : "text-soft-ink4"
              }`}
            >
              {tage >= 0 ? `${tage} Tage` : `${Math.abs(tage)} Tage überfällig`}
            </p>
          </div>
        </div>

        {abruf.status === "ABGERUFEN" && (
          <div>
            {!showFristInput ? (
              <button
                onClick={() => {
                  setNeueFristTage(String(abruf.verwendungsfrist_tage));
                  setShowFristInput(true);
                }}
                className="text-sm text-soft-accent hover:underline"
              >
                Frist anpassen
              </button>
            ) : (
              <div className="flex items-center gap-2 mt-2">
                <input
                  type="number"
                  min="1"
                  max="180"
                  value={neueFristTage}
                  onChange={(e) => setNeueFristTage(e.target.value)}
                  className="border border-soft-line rounded px-2 py-1 text-sm w-24"
                  placeholder="Tage"
                />
                <span className="text-sm text-soft-ink3">Tage</span>
                <button
                  onClick={handleFristAnpassen}
                  className="bg-soft-accent text-white px-3 py-1 rounded text-sm hover:bg-soft-accentDark"
                >
                  Speichern
                </button>
                <button
                  onClick={() => setShowFristInput(false)}
                  className="text-sm text-soft-ink3 hover:text-soft-ink"
                >
                  Abbrechen
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Status-Aktionen */}
      <div className="bg-white rounded-soft-sm border border-soft-line p-5 mb-4">
        <h2 className="text-base font-semibold text-soft-ink mb-3">Status</h2>
        {isReadonly ? (
          <div className="text-sm text-soft-ink3">
            Status:{" "}
            <span className="font-medium text-soft-ink">
              {abruf.status === "VERWENDET" ? "Verwendet" : "Zurückgezahlt"}
            </span>
            {abruf.betrag_zurueck && (
              <span className="ml-2">· Rückzahlung: {formatEur(abruf.betrag_zurueck)}</span>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {/* Mark as verwendet */}
            {!showVerwendetInput ? (
              <button
                onClick={() => {
                  setBetragsInput(abruf.betrag);
                  setShowVerwendetInput(true);
                  setShowRueckzahlungInput(false);
                }}
                className="block w-full text-left px-4 py-2 border border-soft-ok/40 text-soft-ok rounded-soft-xs text-sm hover:bg-soft-okSoft transition-colors"
              >
                Als verwendet markieren
              </button>
            ) : (
              <div className="p-3 border border-soft-ok/30 rounded-soft-xs bg-soft-okSoft space-y-2">
                <p className="text-sm font-medium text-soft-ok">Verwendeten Betrag bestätigen</p>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={betragsInput}
                    onChange={(e) => setBetragsInput(e.target.value)}
                    className="border border-soft-line rounded px-2 py-1 text-sm w-36"
                    placeholder="0,00"
                  />
                  <span className="text-sm text-soft-ink3">€</span>
                  <button
                    onClick={handleMarkVerwendet}
                    className="bg-soft-ok text-white px-3 py-1 rounded text-sm hover:bg-soft-ok/85"
                  >
                    Bestätigen
                  </button>
                  <button
                    onClick={() => setShowVerwendetInput(false)}
                    className="text-sm text-soft-ink3 hover:text-soft-ink"
                  >
                    Abbrechen
                  </button>
                </div>
              </div>
            )}

            {/* Rückzahlung erfassen */}
            {!showRueckzahlungInput ? (
              <button
                onClick={() => {
                  setShowRueckzahlungInput(true);
                  setShowVerwendetInput(false);
                }}
                className="block w-full text-left px-4 py-2 border border-soft-warn/40 text-soft-warn rounded-soft-xs text-sm hover:bg-soft-warnSoft transition-colors"
              >
                Rückzahlung erfassen
              </button>
            ) : (
              <div className="p-3 border border-soft-warn/30 rounded-soft-xs bg-soft-warnSoft space-y-2">
                <p className="text-sm font-medium text-soft-warn">Rückzahlungsbetrag erfassen</p>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={rueckzahlungInput}
                    onChange={(e) => setRueckzahlungInput(e.target.value)}
                    className="border border-soft-line rounded px-2 py-1 text-sm w-36"
                    placeholder="0,00"
                  />
                  <span className="text-sm text-soft-ink3">€</span>
                  <button
                    onClick={handleRueckzahlung}
                    className="bg-soft-warn text-white px-3 py-1 rounded text-sm hover:bg-soft-warn/85"
                  >
                    Bestätigen
                  </button>
                  <button
                    onClick={() => setShowRueckzahlungInput(false)}
                    className="text-sm text-soft-ink3 hover:text-soft-ink"
                  >
                    Abbrechen
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Notiz */}
      <div className="bg-white rounded-soft-sm border border-soft-line p-5">
        <h2 className="text-base font-semibold text-soft-ink mb-3">Notiz</h2>
        <textarea
          value={notiz}
          onChange={(e) => {
            setNotiz(e.target.value);
            setNotizDirty(true);
          }}
          rows={4}
          className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soft-accent"
          placeholder="Optionale Notizen zu diesem Abruf…"
        />
        {notizDirty && (
          <button
            onClick={handleNotizSpeichern}
            className="mt-2 bg-soft-accent text-white px-4 py-1.5 rounded text-sm hover:bg-soft-accentDark"
          >
            Notiz speichern
          </button>
        )}
      </div>
    </PageShell>
  );
}
