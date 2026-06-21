"use client";

import { useState, useCallback, type FormEvent, type ChangeEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/ToastProvider";
import type { FiscalYearWithMeta } from "@/types/haushaltsjahre";

type FormMode = "create" | "edit";

type HaushaltjahrFormProps = {
  mode: FormMode;
  fiscalYearId?: string;
  initialValues?: {
    jahr: number;
    beginn: string;
    ende: string;
  };
};

type FieldErrors = {
  jahr?: string;
  beginn?: string;
  ende?: string;
  general?: string;
};

function getDefaultBeginn(jahr: number): string {
  return `${jahr}-01-01`;
}

function getDefaultEnde(jahr: number): string {
  return `${jahr}-12-31`;
}

function validateJahr(value: string): string | undefined {
  const num = parseInt(value, 10);
  if (!value || isNaN(num)) return "Jahr ist erforderlich.";
  if (!Number.isInteger(num) || num < 2000 || num > 2099)
    return "Jahr muss zwischen 2000 und 2099 liegen.";
  return undefined;
}

function validateBeginn(value: string): string | undefined {
  if (!value) return "Beginn ist erforderlich.";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || isNaN(Date.parse(value)))
    return "Beginn muss ein gültiges Datum sein.";
  return undefined;
}

function validateEnde(value: string, beginn: string): string | undefined {
  if (!value) return "Ende ist erforderlich.";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || isNaN(Date.parse(value)))
    return "Ende muss ein gültiges Datum sein.";
  if (beginn && new Date(beginn) >= new Date(value))
    return "Ende muss nach dem Beginndatum liegen.";
  return undefined;
}

export function HaushaltjahrForm({ mode, fiscalYearId, initialValues }: HaushaltjahrFormProps) {
  const router = useRouter();
  const toast = useToast();

  const currentYear = new Date().getFullYear();

  const [jahrStr, setJahrStr] = useState<string>(
    initialValues?.jahr?.toString() ?? String(currentYear + 1),
  );
  const [beginn, setBeginn] = useState<string>(
    initialValues?.beginn ?? getDefaultBeginn(initialValues?.jahr ?? currentYear + 1),
  );
  const [ende, setEnde] = useState<string>(
    initialValues?.ende ?? getDefaultEnde(initialValues?.jahr ?? currentYear + 1),
  );

  const [errors, setErrors] = useState<FieldErrors>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);
  const [serverWarning, setServerWarning] = useState<string | null>(null);

  // When year changes → auto-set beginn/ende (user can override)
  const handleJahrChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const val = e.target.value;
      setJahrStr(val);

      const num = parseInt(val, 10);
      if (!isNaN(num) && num >= 2000 && num <= 2099) {
        setBeginn(getDefaultBeginn(num));
        setEnde(getDefaultEnde(num));
      }

      if (touched.jahr) {
        setErrors((prev) => ({ ...prev, jahr: validateJahr(val) }));
      }
    },
    [touched.jahr],
  );

  const handleBeginnChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const val = e.target.value;
      setBeginn(val);
      if (touched.beginn) {
        setErrors((prev) => ({ ...prev, beginn: validateBeginn(val) }));
      }
    },
    [touched.beginn],
  );

  const handleEndeChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const val = e.target.value;
      setEnde(val);
      if (touched.ende) {
        setErrors((prev) => ({ ...prev, ende: validateEnde(val, beginn) }));
      }
    },
    [touched.ende, beginn],
  );

  const handleBlur = useCallback(
    (field: "jahr" | "beginn" | "ende") => {
      setTouched((prev) => ({ ...prev, [field]: true }));
      if (field === "jahr") setErrors((prev) => ({ ...prev, jahr: validateJahr(jahrStr) }));
      if (field === "beginn") setErrors((prev) => ({ ...prev, beginn: validateBeginn(beginn) }));
      if (field === "ende") setErrors((prev) => ({ ...prev, ende: validateEnde(ende, beginn) }));
    },
    [jahrStr, beginn, ende],
  );

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setTouched({ jahr: true, beginn: true, ende: true });

    const jahrErr = validateJahr(jahrStr);
    const beginnErr = validateBeginn(beginn);
    const endeErr = validateEnde(ende, beginn);

    if (jahrErr || beginnErr || endeErr) {
      setErrors({ jahr: jahrErr, beginn: beginnErr, ende: endeErr });
      return;
    }

    setErrors({});
    setLoading(true);
    setServerWarning(null);

    try {
      const url =
        mode === "create"
          ? "/api/protected/haushaltsjahre"
          : `/api/protected/haushaltsjahre/${fiscalYearId}`;
      const method = mode === "create" ? "POST" : "PATCH";

      const bodyPayload =
        mode === "create" ? { jahr: parseInt(jahrStr, 10), beginn, ende } : { beginn, ende };

      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(bodyPayload),
      });

      const json = (await res.json()) as {
        data?: FiscalYearWithMeta;
        message?: string;
        warning?: string;
        error?: string;
        code?: string;
      };

      if (!res.ok) {
        const errMsg = json.error ?? "Ein Fehler ist aufgetreten.";
        const errCode = json.code ?? "";

        if (errCode === "VALIDATION_JAHR") {
          setErrors({ jahr: errMsg });
        } else if (errCode === "VALIDATION_BEGINN") {
          setErrors({ beginn: errMsg });
        } else if (errCode === "VALIDATION_ENDE" || errCode === "VALIDATION_DATES_ORDER") {
          setErrors({ ende: errMsg });
        } else {
          setErrors({ general: errMsg });
        }
        return;
      }

      if (json.warning) {
        setServerWarning(json.warning);
      }

      toast.success(json.message ?? "Haushaltsjahr gespeichert.");
      router.push("/dashboard/haushaltsjahre");
      router.refresh();
    } catch {
      setErrors({ general: "Netzwerkfehler. Bitte versuche es erneut." });
    } finally {
      setLoading(false);
    }
  };

  const inputClass = (hasError: boolean) =>
    `w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors
      focus:ring-2 focus:ring-soft-accent focus:border-soft-accent
      ${
        hasError
          ? "border-soft-crit bg-soft-critSoft text-soft-crit placeholder-soft-crit"
          : "border-soft-line bg-white placeholder-soft-ink4"
      }`;

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-6">
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

      {/* Server warning (e.g. already one open year) */}
      {serverWarning && (
        <div
          role="status"
          className="rounded-soft-xs bg-soft-warnSoft border border-soft-warn/40 p-4 text-sm text-soft-warn"
        >
          <strong className="font-medium">Hinweis: </strong>
          {serverWarning}
        </div>
      )}

      {/* Jahr */}
      <div>
        <label htmlFor="fy-jahr" className="block text-sm font-medium text-soft-ink2 mb-1">
          Haushaltsjahr{" "}
          <span className="text-soft-crit" aria-hidden="true">
            *
          </span>
          <span className="ml-1 text-xs font-normal text-soft-ink3">(2000–2099)</span>
        </label>
        <input
          id="fy-jahr"
          type="number"
          min={2000}
          max={2099}
          step={1}
          value={jahrStr}
          onChange={handleJahrChange}
          onBlur={() => handleBlur("jahr")}
          placeholder="2026"
          aria-required="true"
          aria-describedby={errors.jahr ? "fy-jahr-error" : undefined}
          aria-invalid={!!errors.jahr}
          disabled={mode === "edit"}
          className={
            inputClass(!!errors.jahr) + (mode === "edit" ? " opacity-50 cursor-not-allowed" : "")
          }
        />
        {errors.jahr && (
          <p id="fy-jahr-error" role="alert" className="mt-1 text-xs text-soft-crit">
            {errors.jahr}
          </p>
        )}
        {mode === "edit" && (
          <p className="mt-1 text-xs text-soft-ink3">
            Das Jahr kann nach dem Anlegen nicht mehr geändert werden.
          </p>
        )}
      </div>

      {/* Beginn */}
      <div>
        <label htmlFor="fy-beginn" className="block text-sm font-medium text-soft-ink2 mb-1">
          Beginn{" "}
          <span className="text-soft-crit" aria-hidden="true">
            *
          </span>
        </label>
        <input
          id="fy-beginn"
          type="date"
          value={beginn}
          onChange={handleBeginnChange}
          onBlur={() => handleBlur("beginn")}
          aria-required="true"
          aria-describedby={errors.beginn ? "fy-beginn-error" : undefined}
          aria-invalid={!!errors.beginn}
          className={inputClass(!!errors.beginn)}
        />
        {errors.beginn && (
          <p id="fy-beginn-error" role="alert" className="mt-1 text-xs text-soft-crit">
            {errors.beginn}
          </p>
        )}
      </div>

      {/* Ende */}
      <div>
        <label htmlFor="fy-ende" className="block text-sm font-medium text-soft-ink2 mb-1">
          Ende{" "}
          <span className="text-soft-crit" aria-hidden="true">
            *
          </span>
        </label>
        <input
          id="fy-ende"
          type="date"
          value={ende}
          onChange={handleEndeChange}
          onBlur={() => handleBlur("ende")}
          aria-required="true"
          aria-describedby={errors.ende ? "fy-ende-error" : undefined}
          aria-invalid={!!errors.ende}
          className={inputClass(!!errors.ende)}
        />
        {errors.ende && (
          <p id="fy-ende-error" role="alert" className="mt-1 text-xs text-soft-crit">
            {errors.ende}
          </p>
        )}
      </div>

      {/* Submit */}
      <div className="pt-2 flex items-center justify-end gap-3">
        <Button type="button" variant="secondary" onClick={() => router.back()} disabled={loading}>
          Abbrechen
        </Button>
        <Button type="submit" variant="primary" loading={loading}>
          {mode === "create" ? "Haushaltsjahr anlegen" : "Änderungen speichern"}
        </Button>
      </div>
    </form>
  );
}
