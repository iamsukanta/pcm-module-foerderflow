"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { useToast } from "@/components/ui/ToastProvider";
import type { ImportBatchResult } from "@/types/transaktionen";
import { Check, XCircle, ArrowLeft, AlertTriangle } from "lucide-react";

type FiscalYear = { id: string; jahr: number; beginn: string; ende: string; status: string };
type CsvProfile = {
  id: string;
  name: string;
  beschreibung: string | null;
  ist_systemweit: boolean;
};
type BankAccount = { id: string; code: string; bezeichnung: string; iban: string | null };

type DetectionResult = {
  detection: {
    delimiter: string;
    encoding: string;
    decimalSeparator: string;
    dateFormat: string;
    headerRow: number;
    header: string[];
    confidence: number;
  };
  builtin_profile: { name: string; beschreibung: string } | null;
  suggested_mapping: Record<string, string>;
  preview_rows: string[];
};

function formatEur(n: number): string {
  return new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 2,
  }).format(n);
}

export function TransaktionImportForm() {
  const [file, setFile] = useState<File | null>(null);
  const [fiscalYears, setFiscalYears] = useState<FiscalYear[]>([]);
  const [fiscalYearId, setFiscalYearId] = useState<string>("");
  const [profiles, setProfiles] = useState<CsvProfile[]>([]);
  const [bankAccounts, setBankAccounts] = useState<BankAccount[]>([]);
  const [detection, setDetection] = useState<DetectionResult | null>(null);
  const [selectedProfileId, setSelectedProfileId] = useState<string>("");
  const [fallbackBankAccountId, setFallbackBankAccountId] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [result, setResult] = useState<ImportBatchResult | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const toast = useToast();

  useEffect(() => {
    void (async () => {
      try {
        const [fyRes, profilesRes, accountsRes] = await Promise.all([
          fetch("/api/protected/haushaltsjahre"),
          fetch("/api/protected/csv-profiles"),
          fetch("/api/protected/bank-accounts"),
        ]);
        const fyJson = (await fyRes.json()) as { data: FiscalYear[] };
        const profilesJson = (await profilesRes.json()) as { data: CsvProfile[] };
        const accountsJson = (await accountsRes.json()) as { data: BankAccount[] };
        const open = (fyJson.data ?? []).filter((y) => y.status !== "GESCHLOSSEN");
        setFiscalYears(open);
        if (open.length > 0 && open[0]) setFiscalYearId(open[0].id);
        setProfiles(profilesJson.data ?? []);
        setBankAccounts(accountsJson.data ?? []);
      } catch {
        // ignore — UI bleibt benutzbar, einzelne Selects sind ggf. leer
      }
    })();
  }, []);

  async function runAutoDetect(f: File) {
    setDetecting(true);
    setDetection(null);
    setSelectedProfileId("");
    try {
      const fd = new FormData();
      fd.append("file", f);
      const res = await fetch("/api/protected/transaktionen/import", {
        method: "PUT",
        body: fd,
      });
      const json = (await res.json()) as { data?: DetectionResult; error?: string };
      if (!res.ok || !json.data) {
        toast.error(json.error ?? "Auto-Detect fehlgeschlagen.");
        return;
      }
      setDetection(json.data);
      // Wenn Built-in-Profil erkannt → auto-select
      if (json.data.builtin_profile) {
        const match = profiles.find((p) => p.name === json.data!.builtin_profile!.name);
        if (match) setSelectedProfileId(match.id);
      }
    } finally {
      setDetecting(false);
    }
  }

  async function handleFileSelect(f: File) {
    setFile(f);
    setResult(null);
    await runAutoDetect(f);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !fiscalYearId) return;
    if (!selectedProfileId && !detection?.builtin_profile) {
      toast.error("Bitte ein CSV-Profil auswählen oder ein erkanntes Profil bestätigen.");
      return;
    }

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("fiscal_year_id", fiscalYearId);
      if (selectedProfileId) formData.append("csv_import_profile_id", selectedProfileId);
      if (fallbackBankAccountId)
        formData.append("fallback_bank_account_id", fallbackBankAccountId);

      const res = await fetch("/api/protected/transaktionen/import", {
        method: "POST",
        body: formData,
      });
      const json = (await res.json()) as { data?: ImportBatchResult; error?: string };
      if (!res.ok || !json.data) {
        toast.error(json.error ?? "Import fehlgeschlagen.");
        return;
      }
      setResult(json.data);
      toast.success(
        `${json.data.anzahl_importiert} Transaktion(en) importiert${
          json.data.anzahl_auto_matched ? `, ${json.data.anzahl_auto_matched} via BookingRule auto-zugeordnet` : ""
        }.`,
      );
    } catch {
      toast.error("Netzwerkfehler beim Import.");
    } finally {
      setLoading(false);
    }
  }

  const profileSelected = profiles.find((p) => p.id === selectedProfileId);
  const fileNeedsFallback =
    detection !== null &&
    selectedProfileId !== "" &&
    profileSelected !== undefined &&
    !detection.suggested_mapping.bank_account_iban;

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Drag & Drop Zone */}
      <div
        className={`border-2 border-dashed rounded-soft-sm p-10 text-center cursor-pointer transition-colors ${
          isDragging
            ? "border-soft-accent bg-soft-accentSoft"
            : "border-soft-line hover:border-soft-ink4 bg-soft-surfaceAlt"
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          const dropped = e.dataTransfer.files[0];
          if (dropped) void handleFileSelect(dropped);
        }}
        onClick={() => fileInputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.txt"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void handleFileSelect(f);
          }}
        />
        {file ? (
          <div className="space-y-1">
            <p className="font-semibold text-soft-ink">{file.name}</p>
            <p className="text-sm text-soft-ink3">{(file.size / 1024).toFixed(1)} KB</p>
            {detecting && <p className="text-sm text-soft-ink3">Analysiere CSV…</p>}
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-soft-ink2 font-medium">CSV-Datei hierher ziehen</p>
            <p className="text-sm text-soft-ink4">oder klicken zum Auswählen</p>
            <p className="text-xs text-soft-ink4 mt-2">
              Jedes CSV-Format wird unterstützt — beim ersten Upload Spalten zuordnen, danach automatisch.
            </p>
          </div>
        )}
      </div>

      {/* Detection Feedback */}
      {detection && (
        <div className="rounded-soft-sm border border-soft-line bg-white p-4 space-y-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-medium text-soft-ink">CSV-Analyse</p>
              <div className="mt-1 text-xs text-soft-ink3 flex flex-wrap gap-x-3 gap-y-1">
                <span>Encoding: <span className="font-mono">{detection.detection.encoding}</span></span>
                <span>Trenner: <span className="font-mono">{detection.detection.delimiter === "\t" ? "Tab" : detection.detection.delimiter}</span></span>
                <span>Dezimal: <span className="font-mono">{detection.detection.decimalSeparator}</span></span>
                <span>Datum: <span className="font-mono">{detection.detection.dateFormat}</span></span>
                <span>Sicherheit: <span className="font-mono">{Math.round(detection.detection.confidence * 100)}%</span></span>
              </div>
            </div>
            {detection.builtin_profile && (
              <Badge variant="success">
                <Check className="h-3 w-3" aria-hidden /> {detection.builtin_profile.name}
              </Badge>
            )}
          </div>
          <details className="text-xs text-soft-ink3">
            <summary className="cursor-pointer font-medium">Header & Vorschau</summary>
            <div className="mt-2 space-y-1.5">
              <div>
                <span className="font-medium text-soft-ink2">Spalten:</span>{" "}
                {detection.detection.header.map((h, i) => (
                  <span key={i} className="inline-block bg-soft-line2 rounded-soft-xs px-2 py-0.5 mr-1 mb-1 text-soft-ink2">
                    {h}
                  </span>
                ))}
              </div>
              {Object.keys(detection.suggested_mapping).length > 0 && (
                <div className="pt-2 border-t border-soft-line2">
                  <span className="font-medium text-soft-ink2">Auto-Mapping-Vorschlag:</span>
                  <ul className="mt-1 space-y-0.5">
                    {Object.entries(detection.suggested_mapping).map(([target, source]) => (
                      <li key={target}>
                        <span className="font-mono">{target}</span> ← {source}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </details>
        </div>
      )}

      {/* Profile Select */}
      {file && (
        <div>
          <label htmlFor="profile-select" className="block text-sm font-medium text-soft-ink2 mb-1.5">
            CSV-Profil
          </label>
          <select
            id="profile-select"
            value={selectedProfileId}
            onChange={(e) => setSelectedProfileId(e.target.value)}
            className="w-full border border-soft-line rounded-soft-xs px-3 py-2.5 text-sm bg-white"
          >
            <option value="">— ohne Profil (Auto-Detect oder Mapping-Builder) —</option>
            <optgroup label="System-Profile">
              {profiles.filter((p) => p.ist_systemweit).map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </optgroup>
            {profiles.some((p) => !p.ist_systemweit) && (
              <optgroup label="Eigene Profile">
                {profiles.filter((p) => !p.ist_systemweit).map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </optgroup>
            )}
          </select>
          {profileSelected?.beschreibung && (
            <p className="mt-1 text-xs text-soft-ink4">{profileSelected.beschreibung}</p>
          )}
        </div>
      )}

      {/* Fallback Bank Account (wenn CSV keine IBAN-Spalte hat) */}
      {fileNeedsFallback && (
        <div className="rounded-soft-xs border border-soft-warn/30 bg-soft-warnSoft p-3">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-soft-warn shrink-0 mt-0.5" aria-hidden />
            <div className="flex-1">
              <p className="text-sm font-medium text-soft-warn">Bank-Konto-Zuordnung nötig</p>
              <p className="text-xs text-soft-ink3 mb-2">
                Das Profil kennt keine IBAN-Spalte. Wähle, zu welchem Konto die Buchungen gehören:
              </p>
              <select
                value={fallbackBankAccountId}
                onChange={(e) => setFallbackBankAccountId(e.target.value)}
                className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm bg-white"
                required
              >
                <option value="">Konto wählen…</option>
                {bankAccounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.bezeichnung} ({a.code}{a.iban ? ` · ${a.iban.slice(0, 12)}…` : ""})
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Haushaltsjahr */}
      <div>
        <label htmlFor="fiscal-year-select" className="block text-sm font-medium text-soft-ink2 mb-1.5">
          Haushaltsjahr
        </label>
        <select
          id="fiscal-year-select"
          value={fiscalYearId}
          onChange={(e) => setFiscalYearId(e.target.value)}
          className="w-full border border-soft-line rounded-soft-xs px-3 py-2.5 text-sm bg-white"
          required
        >
          <option value="">Haushaltsjahr wählen…</option>
          {fiscalYears.map((y) => (
            <option key={y.id} value={y.id}>
              {y.jahr} ({new Date(y.beginn).toLocaleDateString("de-DE")} – {new Date(y.ende).toLocaleDateString("de-DE")})
            </option>
          ))}
        </select>
        {fiscalYears.length === 0 && (
          <p className="mt-1 text-xs text-soft-warn">
            Kein offenes Haushaltsjahr — bitte zuerst eines anlegen.
          </p>
        )}
      </div>

      <Button
        type="submit"
        disabled={
          !file ||
          !fiscalYearId ||
          loading ||
          (fileNeedsFallback && !fallbackBankAccountId)
        }
        className="w-full"
      >
        {loading ? "Wird importiert…" : "Importieren"}
      </Button>

      {/* Result */}
      {result && (
        <div className="rounded-soft-sm border border-soft-ok/30 bg-soft-okSoft p-5 space-y-3">
          <p className="font-semibold text-soft-ok">Import abgeschlossen</p>
          {result.profile_used && (
            <p className="text-xs text-soft-ink3">
              Profil verwendet: <span className="font-medium">{result.profile_used}</span>
            </p>
          )}
          <ul className="text-sm space-y-1.5">
            <li className="text-soft-ok flex items-center gap-1.5">
              <Check className="h-4 w-4 shrink-0" />
              {result.anzahl_importiert} Transaktion{result.anzahl_importiert !== 1 ? "en" : ""} importiert
            </li>
            {result.anzahl_duplikate > 0 && (
              <li className="text-soft-warn flex items-center gap-1.5">
                <ArrowLeft className="h-4 w-4 shrink-0" />
                {result.anzahl_duplikate} Duplikat{result.anzahl_duplikate !== 1 ? "e" : ""} übersprungen
              </li>
            )}
            {result.anzahl_auto_matched !== undefined && result.anzahl_auto_matched > 0 && (
              <li className="text-soft-ok flex items-center gap-1.5">
                <Check className="h-4 w-4 shrink-0" />
                {result.anzahl_auto_matched} via BookingRule auto-zugeordnet
              </li>
            )}
            {result.bank_accounts_neu && result.bank_accounts_neu.length > 0 && (
              <li className="text-soft-accent flex items-center gap-1.5">
                <Check className="h-4 w-4 shrink-0" />
                {result.bank_accounts_neu.length} neue/r Bank-Account{result.bank_accounts_neu.length !== 1 ? "s" : ""} angelegt:{" "}
                {result.bank_accounts_neu.join(", ")}
              </li>
            )}
            {result.anzahl_fehler > 0 && (
              <li className="text-soft-crit flex items-center gap-1.5">
                <XCircle className="h-4 w-4 shrink-0" />
                {result.anzahl_fehler} Zeile{result.anzahl_fehler !== 1 ? "n" : ""} mit Fehlern
              </li>
            )}
          </ul>

          {/* Saldo-Check */}
          {result.saldo_check && result.saldo_check.length > 0 && (
            <div className="pt-3 border-t border-soft-ok/30">
              <p className="text-sm font-medium text-soft-ink mb-2">Saldo-Konsistenz</p>
              <div className="space-y-1">
                {result.saldo_check.map((s) => (
                  <div
                    key={s.bank_account_id}
                    className={`flex items-center justify-between text-xs gap-2 rounded-soft-xs px-2 py-1.5 ${
                      s.passed ? "bg-white/50" : "bg-soft-warnSoft border border-soft-warn/30"
                    }`}
                  >
                    <span className="font-mono text-soft-ink3">{s.iban}</span>
                    <span className="numeric text-soft-ink2">
                      {s.opening !== null ? formatEur(s.opening) : "—"} + {formatEur(s.sum_betrag)} ={" "}
                      <span className="font-medium">
                        {s.expected_end !== null ? formatEur(s.expected_end) : "?"}
                      </span>
                    </span>
                    {s.csv_last_saldo !== null && (
                      <span className={`numeric ${s.passed ? "text-soft-ok" : "text-soft-warn"}`}>
                        CSV: {formatEur(s.csv_last_saldo)}
                        {s.diff !== null && Math.abs(s.diff) >= 0.01 && (
                          <span className="ml-1">(Δ {formatEur(s.diff)})</span>
                        )}
                      </span>
                    )}
                  </div>
                ))}
              </div>
              <p className="text-xs text-soft-ink4 mt-2">
                Hinweis: Saldo-Check setzt einen Eröffnungssaldo im selben Geschäftsjahr voraus. Ohne
                Eröffnung wird nur die Bewegungssumme angezeigt.
              </p>
            </div>
          )}

          {result.errors.length > 0 && (
            <details className="text-xs text-soft-crit border-t border-soft-ok/30 pt-3">
              <summary className="cursor-pointer font-medium">
                Fehlerdetails ({result.errors.length})
              </summary>
              <ul className="mt-2 space-y-1">
                {result.errors.slice(0, 30).map((e, i) => (
                  <li key={i}>
                    Zeile {e.line}: {e.message}
                  </li>
                ))}
                {result.errors.length > 30 && (
                  <li className="text-soft-ink4">… weitere {result.errors.length - 30} Fehler ausgeblendet</li>
                )}
              </ul>
            </details>
          )}
        </div>
      )}
    </form>
  );
}
