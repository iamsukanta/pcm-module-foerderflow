"use client";

import { useCallback, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/ToastProvider";
import { FileText, FileImage, Paperclip } from "lucide-react";

type Tab = "upload" | "referenz";

const RETENTION_OPTIONS = [
  { value: "3", label: "3 Jahre" },
  { value: "5", label: "5 Jahre" },
  { value: "7", label: "7 Jahre" },
  { value: "10", label: "10 Jahre" },
];

const ACCEPTED_TYPES = ["application/pdf", "image/jpeg", "image/png", "image/webp"];
const ACCEPTED_EXTENSIONS = ".pdf,.jpg,.jpeg,.png,.webp";

function FileTypeIcon({ type }: { type: string }) {
  if (type === "application/pdf") return <FileText className="h-8 w-8 text-soft-crit" />;
  if (type.startsWith("image/")) return <FileImage className="h-8 w-8 text-soft-accent" />;
  return <Paperclip className="h-8 w-8 text-soft-ink4" />;
}

type Props = {
  transactionId: string;
  onSuccess?: () => void;
};

export function BelegUploadForm({ transactionId, onSuccess }: Props) {
  const toast = useToast();
  const [activeTab, setActiveTab] = useState<Tab>("upload");

  // Upload-Tab state
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [retentionYearsUpload, setRetentionYearsUpload] = useState("10");

  // Referenz-Tab state
  const [externeReferenz, setExterneReferenz] = useState("");
  const [retentionYearsRef, setRetentionYearsRef] = useState("10");

  const [loading, setLoading] = useState(false);

  const handleFileSelect = useCallback((f: File) => {
    if (!ACCEPTED_TYPES.includes(f.type)) {
      toast.error("Nicht erlaubter Dateityp. Erlaubt: PDF, JPEG, PNG, WEBP");
      return;
    }
    if (f.size > 10 * 1024 * 1024) {
      toast.error("Datei zu groß. Maximum: 10 MB");
      return;
    }
    setFile(f);
  }, [toast]);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const dropped = e.dataTransfer.files[0];
      if (dropped) handleFileSelect(dropped);
    },
    [handleFileSelect]
  );

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => setIsDragging(false);

  const handleSubmitUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      toast.error("Bitte eine Datei auswählen.");
      return;
    }
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("retention_years", retentionYearsUpload);

      const res = await fetch(`/api/protected/transaktionen/${transactionId}/belege`, {
        method: "POST",
        body: fd,
      });
      const json = (await res.json()) as { data?: unknown; error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Upload fehlgeschlagen.");
        return;
      }
      toast.success("Beleg erfolgreich hochgeladen.");
      setFile(null);
      onSuccess?.();
    } catch {
      toast.error("Netzwerkfehler — bitte erneut versuchen.");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitReferenz = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!externeReferenz.trim()) {
      toast.error("Bitte eine externe Referenz eingeben.");
      return;
    }
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append("externe_referenz", externeReferenz.trim());
      fd.append("retention_years", retentionYearsRef);

      const res = await fetch(`/api/protected/transaktionen/${transactionId}/belege`, {
        method: "POST",
        body: fd,
      });
      const json = (await res.json()) as { data?: unknown; error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Speichern fehlgeschlagen.");
        return;
      }
      toast.success("Externe Referenz gespeichert.");
      setExterneReferenz("");
      onSuccess?.();
    } catch {
      toast.error("Netzwerkfehler — bitte erneut versuchen.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Tab-Leiste */}
      <div className="flex border-b border-soft-line">
        <button
          type="button"
          onClick={() => setActiveTab("upload")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "upload"
              ? "border-soft-accent text-soft-accent"
              : "border-transparent text-soft-ink3 hover:text-soft-ink2"
          }`}
        >
          Datei hochladen
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("referenz")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "referenz"
              ? "border-soft-accent text-soft-accent"
              : "border-transparent text-soft-ink3 hover:text-soft-ink2"
          }`}
        >
          Externe Referenz
        </button>
      </div>

      {/* ── Tab 1: Datei-Upload ─────────────── */}
      {activeTab === "upload" && (
        <form onSubmit={handleSubmitUpload} className="space-y-4">
          {/* Drag & Drop Zone */}
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => fileInputRef.current?.click()}
            className={`relative border-2 border-dashed rounded-soft-sm p-6 text-center cursor-pointer transition-colors ${
              isDragging
                ? "border-soft-accent bg-soft-accentSoft"
                : file
                ? "border-soft-ok bg-soft-okSoft"
                : "border-soft-line hover:border-soft-ink4 bg-soft-surfaceAlt"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_EXTENSIONS}
              className="sr-only"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFileSelect(f);
              }}
            />

            {file ? (
              <div className="flex flex-col items-center gap-2">
                <FileTypeIcon type={file.type} />
                <p className="text-sm font-medium text-soft-ink truncate max-w-full">
                  {file.name}
                </p>
                <p className="text-xs text-soft-ink3">
                  {(file.size / 1024).toFixed(0)} KB
                </p>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setFile(null);
                    if (fileInputRef.current) fileInputRef.current.value = "";
                  }}
                  className="text-xs text-soft-crit hover:text-soft-crit"
                >
                  Entfernen
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2 text-soft-ink3">
                <Paperclip className="h-8 w-8 text-soft-ink4" />
                <p className="text-sm font-medium">
                  Datei hierher ziehen oder klicken
                </p>
                <p className="text-xs">PDF, JPEG, PNG, WEBP — max. 10 MB</p>
              </div>
            )}
          </div>

          {/* Aufbewahrungsfrist */}
          <div className="flex items-center gap-3">
            <label className="text-sm text-soft-ink2 whitespace-nowrap" htmlFor="retention-upload">
              Aufbewahrungsfrist:
            </label>
            <select
              id="retention-upload"
              value={retentionYearsUpload}
              onChange={(e) => setRetentionYearsUpload(e.target.value)}
              className="text-sm border border-soft-line rounded-soft-xs px-3 py-1.5 focus:ring-2 focus:ring-soft-accent focus:outline-none"
            >
              {RETENTION_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>

          <Button type="submit" loading={loading} disabled={!file}>
            Hochladen
          </Button>
        </form>
      )}

      {/* ── Tab 2: Externe Referenz ─────────── */}
      {activeTab === "referenz" && (
        <form onSubmit={handleSubmitReferenz} className="space-y-4">
          <div>
            <label
              htmlFor="externe-ref"
              className="block text-sm font-medium text-soft-ink2 mb-1"
            >
              DATEV-Buchungsnummer oder Beschreibung
            </label>
            <input
              id="externe-ref"
              type="text"
              value={externeReferenz}
              onChange={(e) => setExterneReferenz(e.target.value)}
              placeholder="z. B. DATEV-2024-001234"
              className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm focus:ring-2 focus:ring-soft-accent focus:outline-none"
            />
          </div>

          <div className="flex items-center gap-3">
            <label className="text-sm text-soft-ink2 whitespace-nowrap" htmlFor="retention-ref">
              Aufbewahrungsfrist:
            </label>
            <select
              id="retention-ref"
              value={retentionYearsRef}
              onChange={(e) => setRetentionYearsRef(e.target.value)}
              className="text-sm border border-soft-line rounded-soft-xs px-3 py-1.5 focus:ring-2 focus:ring-soft-accent focus:outline-none"
            >
              {RETENTION_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>

          <Button type="submit" loading={loading} disabled={!externeReferenz.trim()}>
            Referenz speichern
          </Button>
        </form>
      )}
    </div>
  );
}
