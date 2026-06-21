"use client";

import { useState, useCallback, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/ToastProvider";
import { PositionenEditor } from "@/components/forms/PositionenEditor";
import {
  ALLOCATION_BASIS_DESCRIPTIONS,
  ALLOCATION_BASIS_LABELS,
  type AllocationKeyBasis,
  type AllocationKeyWithPositions,
  type PositionDraft,
} from "@/types/verteilungsschluessel";
import { clsx } from "clsx";

const BASIS_OPTIONS: AllocationKeyBasis[] = [
  "MITARBEITERZAHL",
  "QUADRATMETER",
  "BUDGET_ANTEIL",
  "MANUELL",
];

type CostCenterOption = {
  id: string;
  name: string;
  code: string;
  typ: string;
};

type FormMode = "create" | "edit" | "neue-version";

type VerteilungsschluesselFormProps = {
  mode: FormMode;
  /** ID des zu bearbeitenden/versionierenden Schlüssels */
  keyId?: string;
  /** Vorausgefüllte Werte (edit / neue-version) */
  initialValues?: Partial<{
    name: string;
    basis: AllocationKeyBasis;
    gueltig_von: string;
    gueltig_bis: string | null;
    positions: PositionDraft[];
  }>;
  availableCostCenters: CostCenterOption[];
};

type FieldErrors = {
  name?: string;
  basis?: string;
  gueltig_von?: string;
  gueltig_bis?: string;
  positions?: string;
  general?: string;
};

function generateKey(): string {
  return `pos-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

function calcSum(positions: PositionDraft[]): number {
  const sum = positions.reduce((acc, p) => {
    const v = parseFloat(p.prozent);
    return acc + (isNaN(v) ? 0 : v);
  }, 0);
  return Number(sum.toFixed(3));
}

function isExact100(sum: number): boolean {
  return Math.abs(sum - 100) < 0.001;
}

/** Wandelt AllocationKeyWithPositions.positions in PositionDraft[] um. */
export function positionsToEditorDrafts(
  positions: AllocationKeyWithPositions["positions"],
): PositionDraft[] {
  return positions.map((p) => ({
    _key: generateKey(),
    cost_center_id: p.cost_center_id,
    prozent: p.prozent,
  }));
}

export function VerteilungsschluesselForm({
  mode,
  keyId,
  initialValues,
  availableCostCenters,
}: VerteilungsschluesselFormProps) {
  const router = useRouter();
  const toast = useToast();

  const [name, setName] = useState(initialValues?.name ?? "");
  const [basis, setBasis] = useState<AllocationKeyBasis>(initialValues?.basis ?? "MANUELL");
  const [gueltigVon, setGueltigVon] = useState(initialValues?.gueltig_von ?? "");
  const [gueltigBis, setGueltigBis] = useState(initialValues?.gueltig_bis ?? "");
  const [positions, setPositions] = useState<PositionDraft[]>(initialValues?.positions ?? []);

  const [errors, setErrors] = useState<FieldErrors>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);

  const summe = calcSum(positions);
  const summeValid = isExact100(summe);

  const validateField = useCallback(
    (field: string): string | undefined => {
      switch (field) {
        case "name":
          if (!name.trim()) return "Name ist erforderlich.";
          if (name.trim().length < 2) return "Name muss mindestens 2 Zeichen lang sein.";
          if (name.trim().length > 100) return "Name darf maximal 100 Zeichen lang sein.";
          return undefined;
        case "gueltig_von":
          if (!gueltigVon) return "Gültig-von-Datum ist erforderlich.";
          return undefined;
        case "gueltig_bis":
          if (gueltigBis && gueltigVon && gueltigBis <= gueltigVon)
            return "Gültig-bis muss nach Gültig-von liegen.";
          return undefined;
        default:
          return undefined;
      }
    },
    [name, gueltigVon, gueltigBis],
  );

  const handleBlur = useCallback(
    (field: string) => {
      setTouched((prev) => ({ ...prev, [field]: true }));
      setErrors((prev) => ({ ...prev, [field]: validateField(field) }));
    },
    [validateField],
  );

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    const allTouched = { name: true, gueltig_von: true, gueltig_bis: true };
    setTouched(allTouched);

    const fieldErrors: FieldErrors = {
      name: validateField("name"),
      gueltig_von: validateField("gueltig_von"),
      gueltig_bis: validateField("gueltig_bis"),
    };

    if (positions.length === 0) {
      fieldErrors.positions = "Mindestens eine Kostenstelle ist erforderlich.";
    } else if (positions.some((p) => !p.cost_center_id)) {
      fieldErrors.positions = "Alle Zeilen müssen eine Kostenstelle ausgewählt haben.";
    } else if (!summeValid) {
      fieldErrors.positions = `Die Summe muss 100 % ergeben (aktuell: ${summe.toFixed(2)} %).`;
    }

    const hasErrors = Object.values(fieldErrors).some(Boolean);
    if (hasErrors) {
      setErrors(fieldErrors);
      return;
    }

    setErrors({});
    setWarnings([]);
    setLoading(true);

    try {
      let url: string;
      let method: string;

      if (mode === "create") {
        url = "/api/protected/verteilungsschluessel";
        method = "POST";
      } else if (mode === "neue-version") {
        url = `/api/protected/verteilungsschluessel/${keyId}/neue-version`;
        method = "POST";
      } else {
        // edit: nur Name und gueltig_bis
        url = `/api/protected/verteilungsschluessel/${keyId}`;
        method = "PATCH";
      }

      const payload =
        mode === "edit"
          ? {
              name: name.trim(),
              gueltig_bis: gueltigBis || null,
            }
          : {
              name: name.trim(),
              basis,
              gueltig_von: gueltigVon,
              gueltig_bis: gueltigBis || null,
              positions: positions.map((p) => ({
                cost_center_id: p.cost_center_id,
                prozent: p.prozent,
              })),
            };

      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const json = (await res.json()) as {
        data?: unknown;
        message?: string;
        error?: string;
        code?: string;
        warnings?: string[];
        summe_prozent?: number;
      };

      if (!res.ok) {
        const code = json.code ?? "";
        const errMsg = json.error ?? "Ein Fehler ist aufgetreten.";

        if (code === "VALIDATION_NAME") {
          setErrors({ name: errMsg });
        } else if (code === "VALIDATION_GUELTIG_VON") {
          setErrors({ gueltig_von: errMsg });
        } else if (code === "VALIDATION_GUELTIG_BIS" || code === "VALIDATION_DATE_ORDER") {
          setErrors({ gueltig_bis: errMsg });
        } else if (
          code === "INVARIANT_SUM_NOT_100" ||
          code === "VALIDATION_POSITIONS_EMPTY" ||
          code === "VALIDATION_POSITIONS_DUPLICATE" ||
          code === "COST_CENTER_INVALID"
        ) {
          setErrors({ positions: errMsg });
        } else {
          setErrors({ general: errMsg });
        }
        return;
      }

      if (json.warnings && json.warnings.length > 0) {
        setWarnings(json.warnings);
      }

      toast.success(json.message ?? "Gespeichert.");
      router.push("/dashboard/verteilungsschluessel");
      router.refresh();
    } catch {
      setErrors({ general: "Netzwerkfehler. Bitte versuche es erneut." });
    } finally {
      setLoading(false);
    }
  };

  const isEditMode = mode === "edit";

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-7">
      {/* General error */}
      {errors.general && (
        <div
          role="alert"
          className="rounded-soft-xs bg-soft-critSoft border border-soft-crit/30 p-4 text-sm text-soft-crit"
        >
          <strong className="font-medium">Fehler: </strong>
          {errors.general}
        </div>
      )}

      {/* Warnings */}
      {warnings.length > 0 && (
        <div
          role="status"
          className="rounded-soft-xs bg-soft-warnSoft border border-soft-warn/30 p-4 text-sm text-soft-warn space-y-1"
        >
          <strong className="font-medium block mb-1">Hinweise:</strong>
          {warnings.map((w, i) => (
            <p key={i}>⚠️ {w}</p>
          ))}
        </div>
      )}

      {/* Name */}
      <div>
        <label htmlFor="vsk-name" className="block text-sm font-medium text-soft-ink2 mb-1">
          Name{" "}
          <span className="text-soft-crit" aria-hidden="true">
            *
          </span>
        </label>
        <input
          id="vsk-name"
          type="text"
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            if (touched.name) setErrors((prev) => ({ ...prev, name: validateField("name") }));
          }}
          onBlur={() => handleBlur("name")}
          placeholder="z.B. Gemeinkostenverteilung 2026"
          maxLength={100}
          aria-required="true"
          aria-describedby={errors.name ? "vsk-name-error" : undefined}
          aria-invalid={!!errors.name}
          className={clsx(
            "w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors",
            "focus:ring-2 focus:ring-soft-accent focus:border-soft-accent",
            errors.name
              ? "border-soft-crit bg-soft-critSoft text-soft-crit"
              : "border-soft-line bg-white",
          )}
        />
        {errors.name && (
          <p id="vsk-name-error" role="alert" className="mt-1 text-xs text-soft-crit">
            {errors.name}
          </p>
        )}
      </div>

      {/* Basis — nur bei create / neue-version */}
      {!isEditMode && (
        <fieldset>
          <legend className="block text-sm font-medium text-soft-ink2 mb-2">
            Berechnungsbasis{" "}
            <span className="text-soft-crit" aria-hidden="true">
              *
            </span>
          </legend>
          <div className="space-y-2">
            {BASIS_OPTIONS.map((b) => (
              <label
                key={b}
                className={clsx(
                  "flex items-start gap-3 rounded-soft-sm border p-3.5 cursor-pointer transition-colors",
                  basis === b
                    ? "border-soft-accent bg-soft-accentSoft"
                    : "border-soft-line hover:border-soft-line hover:bg-soft-line2",
                )}
              >
                <input
                  type="radio"
                  name="vsk-basis"
                  value={b}
                  checked={basis === b}
                  onChange={() => setBasis(b)}
                  className="mt-0.5 h-4 w-4 accent-soft-accent focus:ring-2 focus:ring-soft-accent"
                />
                <div>
                  <div className="text-sm font-medium text-soft-ink">
                    {ALLOCATION_BASIS_LABELS[b]}
                  </div>
                  <div className="text-xs text-soft-ink3 mt-0.5">
                    {ALLOCATION_BASIS_DESCRIPTIONS[b]}
                  </div>
                </div>
              </label>
            ))}
          </div>
        </fieldset>
      )}

      {/* Gültigkeitszeitraum */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Gültig von — bei edit nicht änderbar */}
        <div>
          <label htmlFor="vsk-gueltig-von" className="block text-sm font-medium text-soft-ink2 mb-1">
            Gültig von{" "}
            <span className="text-soft-crit" aria-hidden="true">
              *
            </span>
          </label>
          <input
            id="vsk-gueltig-von"
            type="date"
            value={gueltigVon}
            onChange={(e) => {
              setGueltigVon(e.target.value);
              if (touched.gueltig_von)
                setErrors((prev) => ({
                  ...prev,
                  gueltig_von: validateField("gueltig_von"),
                }));
            }}
            onBlur={() => handleBlur("gueltig_von")}
            disabled={isEditMode}
            aria-required="true"
            aria-describedby={errors.gueltig_von ? "vsk-von-error" : undefined}
            aria-invalid={!!errors.gueltig_von}
            className={clsx(
              "w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors",
              "focus:ring-2 focus:ring-soft-accent focus:border-soft-accent",
              "disabled:bg-soft-line2 disabled:text-soft-ink3 disabled:cursor-not-allowed",
              errors.gueltig_von ? "border-soft-crit bg-soft-critSoft" : "border-soft-line bg-white",
            )}
          />
          {errors.gueltig_von && (
            <p id="vsk-von-error" role="alert" className="mt-1 text-xs text-soft-crit">
              {errors.gueltig_von}
            </p>
          )}
        </div>

        {/* Gültig bis */}
        <div>
          <label htmlFor="vsk-gueltig-bis" className="block text-sm font-medium text-soft-ink2 mb-1">
            Gültig bis <span className="text-xs font-normal text-soft-ink3">(optional)</span>
          </label>
          <input
            id="vsk-gueltig-bis"
            type="date"
            value={gueltigBis}
            onChange={(e) => {
              setGueltigBis(e.target.value);
              if (touched.gueltig_bis)
                setErrors((prev) => ({
                  ...prev,
                  gueltig_bis: validateField("gueltig_bis"),
                }));
            }}
            onBlur={() => handleBlur("gueltig_bis")}
            aria-describedby={errors.gueltig_bis ? "vsk-bis-error" : "vsk-bis-hint"}
            aria-invalid={!!errors.gueltig_bis}
            className={clsx(
              "w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors",
              "focus:ring-2 focus:ring-soft-accent focus:border-soft-accent",
              errors.gueltig_bis ? "border-soft-crit bg-soft-critSoft" : "border-soft-line bg-white",
            )}
          />
          {errors.gueltig_bis ? (
            <p id="vsk-bis-error" role="alert" className="mt-1 text-xs text-soft-crit">
              {errors.gueltig_bis}
            </p>
          ) : (
            <p id="vsk-bis-hint" className="mt-1 text-xs text-soft-ink3">
              Leer lassen für unbegrenzte Gültigkeit.
            </p>
          )}
        </div>
      </div>

      {/* Positionen — bei edit read-only */}
      {!isEditMode && (
        <div>
          <div className="mb-2">
            <span className="text-sm font-medium text-soft-ink2">
              Kostenstellenanteile{" "}
              <span className="text-soft-crit" aria-hidden="true">
                *
              </span>
            </span>
            <p className="text-xs text-soft-ink3 mt-0.5">
              Geben Sie an, zu welchem Anteil jede Kostenstelle an den Gemeinkosten beteiligt ist.
              Die Summe muss exakt 100 % ergeben.
            </p>
          </div>

          <PositionenEditor
            positions={positions}
            onChange={setPositions}
            availableCostCenters={availableCostCenters}
            disabled={loading}
          />

          {errors.positions && (
            <p role="alert" className="mt-2 text-xs text-soft-crit">
              {errors.positions}
            </p>
          )}
        </div>
      )}

      {/* Submit */}
      <div className="pt-2 flex items-center justify-end gap-3">
        <Button type="button" variant="secondary" onClick={() => router.back()} disabled={loading}>
          Abbrechen
        </Button>
        <Button
          type="submit"
          variant="primary"
          loading={loading}
          disabled={!isEditMode && !summeValid}
          title={
            !isEditMode && !summeValid
              ? `Speichern nicht möglich: Summe ist ${summe.toFixed(2)} % (muss 100 % sein)`
              : undefined
          }
        >
          {mode === "create" && "Schlüssel anlegen"}
          {mode === "edit" && "Änderungen speichern"}
          {mode === "neue-version" && "Neue Version anlegen"}
        </Button>
      </div>
    </form>
  );
}
