"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { FileText, Trash2, RefreshCw, Upload, Sparkles, Lock } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useToast } from "@/components/ui/ToastProvider";

type BescheidQuelle = "OCR_IMPORT" | "MANUAL_UPLOAD";

export type BescheidDokumentMeta = {
  id: string;
  filename: string;
  size_bytes: number;
  uploaded_at: string; // ISO
  quelle: BescheidQuelle;
};

type Props = {
  measureId: string;
  canEdit: boolean;
  initialDokument: BescheidDokumentMeta | null;
};

const SUGGESTED_QUESTIONS = [
  "Wann ist der Verwendungsnachweis fällig?",
  "Sind Bewirtungskosten erstattungsfähig?",
  "Wie hoch ist der Eigenanteil und kann er aus anderen Mitteln gedeckt werden?",
];

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatUploadDate(iso: string): string {
  const date = new Date(iso);
  return new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}

export function BescheidTab({ measureId, canEdit, initialDokument }: Props) {
  const router = useRouter();
  const toast = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dokument, setDokument] = useState<BescheidDokumentMeta | null>(initialDokument);
  const [uploading, setUploading] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [previewKey, setPreviewKey] = useState(0); // erzwingt iframe-Reload nach Replace

  function openFilePicker() {
    fileInputRef.current?.click();
  }

  async function handleFileSelected(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = ""; // erlaubt erneuten Upload derselben Datei
    if (!file) return;

    if (file.type !== "application/pdf") {
      toast.error("Nur PDF-Dateien werden unterstützt.");
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("quelle", "MANUAL_UPLOAD");

      const res = await fetch(
        `/api/protected/foerdermassnahmen/${measureId}/bescheid`,
        { method: "POST", body: formData }
      );

      const json = await res.json();
      if (!res.ok) {
        toast.error(json.error ?? "Upload fehlgeschlagen.");
        return;
      }

      setDokument(json.data as BescheidDokumentMeta);
      setPreviewKey((k) => k + 1);
      toast.success("Bescheid wurde gespeichert.");
      router.refresh();
    } catch {
      toast.error("Netzwerkfehler beim Upload.");
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      const res = await fetch(
        `/api/protected/foerdermassnahmen/${measureId}/bescheid`,
        { method: "DELETE" }
      );
      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        toast.error(json.error ?? "Löschen fehlgeschlagen.");
        return;
      }
      setDokument(null);
      setConfirmDelete(false);
      toast.success("Bescheid wurde entfernt.");
      router.refresh();
    } catch {
      toast.error("Netzwerkfehler beim Löschen.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div>
      {/* Hidden Datei-Input für Upload + Replace */}
      <input
        ref={fileInputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={handleFileSelected}
      />

      {dokument ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Linke Spalte — PDF-Vorschau */}
          <div className="rounded-soft border border-soft-line bg-white overflow-hidden flex flex-col">
            <div className="flex items-start justify-between gap-4 p-5 border-b border-soft-line">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  {dokument.quelle === "OCR_IMPORT" ? (
                    <Badge variant="success">Verifiziert</Badge>
                  ) : (
                    <Badge variant="muted">Manuell hochgeladen</Badge>
                  )}
                </div>
                <h3
                  className="text-sm font-semibold text-soft-ink truncate"
                  title={dokument.filename}
                >
                  {dokument.filename}
                </h3>
                <p className="text-xs text-soft-ink3 mt-0.5">
                  <span className="numeric">{formatSize(dokument.size_bytes)}</span>
                  {" · hochgeladen "}
                  <span className="numeric">{formatUploadDate(dokument.uploaded_at)}</span>
                </p>
              </div>
              {canEdit && (
                <div className="flex items-center gap-1 shrink-0">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={openFilePicker}
                    loading={uploading}
                    disabled={uploading || deleting}
                  >
                    <RefreshCw className="h-4 w-4 mr-1.5" aria-hidden="true" />
                    Ersetzen
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setConfirmDelete(true)}
                    disabled={uploading || deleting}
                  >
                    <Trash2 className="h-4 w-4 mr-1.5" aria-hidden="true" />
                    Löschen
                  </Button>
                </div>
              )}
            </div>

            <div className="bg-soft-surfaceAlt p-3">
              <iframe
                key={previewKey}
                src={`/api/protected/foerdermassnahmen/${measureId}/bescheid#view=FitH`}
                className="w-full h-[700px] rounded-soft-sm border border-soft-line bg-white"
                title={`Vorschau: ${dokument.filename}`}
              />
            </div>
          </div>

          {/* Rechte Spalte — KI-Q&A Stub */}
          <KiPanel disabled />
        </div>
      ) : canEdit ? (
        <div className="rounded-soft border border-soft-line bg-white p-2">
          <EmptyState
            icon={FileText}
            title="Kein Zuwendungsbescheid hinterlegt"
            description="Lade das PDF des Zuwendungsbescheids hoch, um es hier dauerhaft einsehen zu können. Beim OCR-Import wird der Bescheid automatisch übernommen."
            action={{
              label: uploading ? "Wird hochgeladen…" : "PDF hochladen",
              onClick: openFilePicker,
            }}
          />
          <div className="text-center pb-4">
            <p className="text-xs text-soft-ink4 inline-flex items-center gap-1.5">
              <Upload className="h-3 w-3" aria-hidden="true" />
              PDF, max. 10 MB
            </p>
          </div>
        </div>
      ) : (
        <div className="rounded-soft border border-soft-line bg-white p-2">
          <EmptyState
            icon={Lock}
            title="Kein Zuwendungsbescheid hinterlegt"
            description="Diese Massnahme ist widerrufen — ein nachträglicher Upload ist nicht mehr möglich."
          />
        </div>
      )}

      <ConfirmDialog
        open={confirmDelete}
        title="Bescheid wirklich löschen?"
        description="Das hinterlegte PDF wird unwiderruflich entfernt. Du kannst danach jederzeit ein neues hochladen."
        confirmLabel="Löschen"
        variant="danger"
        loading={deleting}
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(false)}
      />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// KI-Q&A Panel — statischer Vorschau-Stub. Funktion folgt in einer
// späteren Phase (Anbindung an LLM mit Quellen-Verweis auf Bescheid).
// ─────────────────────────────────────────────────────────────────
function KiPanel({ disabled }: { disabled: boolean }) {
  return (
    <div className="rounded-soft border border-soft-line bg-white flex flex-col">
      <div className="flex items-start justify-between gap-3 p-5 border-b border-soft-line">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <Sparkles className="h-4 w-4 text-soft-accent" aria-hidden="true" />
            <h3 className="text-sm font-semibold text-soft-ink">Fragen zum Bescheid</h3>
            <Badge variant="default">Vorschau</Badge>
          </div>
          <p className="text-xs text-soft-ink3">
            Antworten mit Verweis auf Ziffer und Seite — kommt in einer der nächsten Versionen.
          </p>
        </div>
      </div>

      <div className="p-5 space-y-4 flex-1">
        <div>
          <h4 className="text-xs font-semibold text-soft-ink4 uppercase tracking-wide mb-2">
            Häufige Fragen
          </h4>
          <div className="flex flex-wrap gap-2">
            {SUGGESTED_QUESTIONS.map((q) => (
              <button
                key={q}
                type="button"
                disabled={disabled}
                title="Bald verfügbar"
                className="text-left text-xs px-3 py-1.5 rounded-soft-sm border border-soft-line bg-soft-surface text-soft-ink2 hover:bg-soft-line2 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        <div className="rounded-soft-sm bg-soft-accentWash border border-soft-accent/15 p-4 text-sm text-soft-ink2">
          <p className="font-medium text-soft-ink mb-1">Wie es funktionieren wird</p>
          <p className="text-xs text-soft-ink3">
            Frage stellen → die KI liest den hochgeladenen Bescheid und antwortet mit konkretem
            Verweis auf Ziffer und Seitenzahl, damit jede Antwort nachprüfbar bleibt.
          </p>
        </div>
      </div>

      <div className="p-4 border-t border-soft-line bg-soft-surfaceAlt">
        <div className="flex items-center gap-2">
          <input
            type="text"
            disabled={disabled}
            placeholder="KI-Q&A wird in einer der nächsten Versionen aktiviert."
            className="flex-1 px-3 py-2 text-sm rounded-soft-sm border border-soft-line bg-white text-soft-ink placeholder:text-soft-ink4 disabled:bg-soft-line2 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-soft-accent"
          />
          <Button variant="primary" size="sm" disabled={disabled}>
            Senden
          </Button>
        </div>
      </div>
    </div>
  );
}
