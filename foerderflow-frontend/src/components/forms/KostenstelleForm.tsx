"use client";

import { useState, useCallback, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/ToastProvider";
import type { KostenstelleWithChildren } from "@/types/kostenstellen";

type FormMode = "create" | "edit";

type KostenstelleFormProps = {
  mode: FormMode;
  kstId?: string;
  initialValues?: {
    name: string;
    code: string;
    typ: "PROJECT" | "OVERHEAD";
    parent_id: string | null;
  };
  /** Liste der möglichen Eltern-KSTs (aktive PROJECT-KSTs ohne eigenes parent) */
  parentOptions: Pick<KostenstelleWithChildren, "id" | "name" | "code">[];
};

type FieldErrors = {
  name?: string;
  code?: string;
  typ?: string;
  parent_id?: string;
  general?: string;
};

function validateCode(value: string): string | undefined {
  if (!value) return "Kürzel ist erforderlich.";
  if (value.length < 2) return "Kürzel muss mindestens 2 Zeichen lang sein.";
  if (value.length > 10) return "Kürzel darf maximal 10 Zeichen lang sein.";
  if (!/^[A-Z0-9-]+$/.test(value))
    return "Nur Großbuchstaben, Ziffern und Bindestriche erlaubt.";
  return undefined;
}

function validateName(value: string): string | undefined {
  if (!value.trim()) return "Name ist erforderlich.";
  if (value.trim().length < 2) return "Name muss mindestens 2 Zeichen lang sein.";
  if (value.trim().length > 100) return "Name darf maximal 100 Zeichen lang sein.";
  return undefined;
}

export function KostenstelleForm({
  mode,
  kstId,
  initialValues,
  parentOptions,
}: KostenstelleFormProps) {
  const router = useRouter();
  const toast = useToast();

  const [name, setName] = useState(initialValues?.name ?? "");
  const [code, setCode] = useState(initialValues?.code ?? "");
  const [typ, setTyp] = useState<"PROJECT" | "OVERHEAD">(initialValues?.typ ?? "PROJECT");
  const [parentId, setParentId] = useState<string>(initialValues?.parent_id ?? "");

  const [errors, setErrors] = useState<FieldErrors>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);

  const handleCodeChange = useCallback(
    (val: string) => {
      const upper = val.toUpperCase().replace(/[^A-Z0-9-]/g, "");
      setCode(upper);
      if (touched.code) {
        setErrors((prev) => ({ ...prev, code: validateCode(upper) }));
      }
    },
    [touched.code],
  );

  const handleNameChange = useCallback(
    (val: string) => {
      setName(val);
      if (touched.name) {
        setErrors((prev) => ({ ...prev, name: validateName(val) }));
      }
    },
    [touched.name],
  );

  const handleBlur = useCallback(
    (field: string) => {
      setTouched((prev) => ({ ...prev, [field]: true }));
      if (field === "name") setErrors((prev) => ({ ...prev, name: validateName(name) }));
      if (field === "code") setErrors((prev) => ({ ...prev, code: validateCode(code) }));
    },
    [name, code],
  );

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    setTouched({ name: true, code: true, typ: true });

    const nameErr = validateName(name);
    const codeErr = validateCode(code);

    if (nameErr || codeErr) {
      setErrors({ name: nameErr, code: codeErr });
      return;
    }

    setErrors({});
    setLoading(true);

    try {
      const url =
        mode === "create"
          ? "/api/protected/kostenstellen"
          : `/api/protected/kostenstellen/${kstId}`;
      const method = mode === "create" ? "POST" : "PATCH";

      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          code: code.trim(),
          typ,
          parent_id: parentId || null,
        }),
      });

      const json = (await res.json()) as {
        data?: unknown;
        message?: string;
        error?: string;
        code?: string;
      };

      if (!res.ok) {
        const errMsg = json.error ?? "Ein Fehler ist aufgetreten.";
        const errCode = json.code ?? "";

        if (errCode === "CODE_DUPLICATE" || errCode === "VALIDATION_CODE") {
          setErrors({ code: errMsg });
        } else if (errCode === "VALIDATION_NAME") {
          setErrors({ name: errMsg });
        } else if (errCode === "HIERARCHY_TOO_DEEP" || errCode === "PARENT_NOT_FOUND") {
          setErrors({ parent_id: errMsg });
        } else {
          setErrors({ general: errMsg });
        }
        return;
      }

      toast.success(json.message ?? "Kostenstelle gespeichert.");
      router.push("/dashboard/kostenstellen");
      router.refresh();
    } catch {
      setErrors({ general: "Netzwerkfehler. Bitte versuche es erneut." });
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-6">
      {/* General error banner */}
      {errors.general && (
        <div
          role="alert"
          className="rounded-soft-xs bg-soft-critSoft border border-soft-crit/30 p-4 text-sm text-soft-crit"
        >
          <strong className="font-medium">Fehler: </strong>
          {errors.general}
        </div>
      )}

      {/* Name */}
      <div>
        <label htmlFor="kst-name" className="block text-sm font-medium text-soft-ink2 mb-1">
          Name{" "}
          <span className="text-soft-crit" aria-hidden="true">
            *
          </span>
        </label>
        <input
          id="kst-name"
          type="text"
          value={name}
          onChange={(e) => handleNameChange(e.target.value)}
          onBlur={() => handleBlur("name")}
          placeholder="z.B. Soziale Beratung"
          maxLength={100}
          aria-required="true"
          aria-describedby={errors.name ? "kst-name-error" : undefined}
          aria-invalid={!!errors.name}
          className={`w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors
            focus:ring-2 focus:ring-soft-accent focus:border-soft-accent
            ${
              errors.name
                ? "border-soft-crit bg-soft-critSoft text-soft-crit placeholder-soft-crit"
                : "border-soft-line bg-white placeholder-soft-ink4"
            }`}
        />
        {errors.name && (
          <p id="kst-name-error" role="alert" className="mt-1 text-xs text-soft-crit">
            {errors.name}
          </p>
        )}
      </div>

      {/* Code */}
      <div>
        <label htmlFor="kst-code" className="block text-sm font-medium text-soft-ink2 mb-1">
          Kürzel{" "}
          <span className="text-soft-crit" aria-hidden="true">
            *
          </span>
          <span className="ml-1 text-xs font-normal text-soft-ink3">
            (max. 10 Zeichen, z.B. SB01)
          </span>
        </label>
        <input
          id="kst-code"
          type="text"
          value={code}
          onChange={(e) => handleCodeChange(e.target.value)}
          onBlur={() => handleBlur("code")}
          placeholder="SB01"
          maxLength={10}
          aria-required="true"
          aria-describedby={errors.code ? "kst-code-error" : "kst-code-hint"}
          aria-invalid={!!errors.code}
          className={`w-full rounded-soft-xs border px-3 py-2.5 text-sm font-mono uppercase outline-none transition-colors
            focus:ring-2 focus:ring-soft-accent focus:border-soft-accent
            ${
              errors.code
                ? "border-soft-crit bg-soft-critSoft text-soft-crit placeholder-soft-crit"
                : "border-soft-line bg-white placeholder-soft-ink4"
            }`}
        />
        {errors.code ? (
          <p id="kst-code-error" role="alert" className="mt-1 text-xs text-soft-crit">
            {errors.code}
          </p>
        ) : (
          <p id="kst-code-hint" className="mt-1 text-xs text-soft-ink3">
            Nur Großbuchstaben, Ziffern und Bindestriche. Wird automatisch uppercase gesetzt.
          </p>
        )}
      </div>

      {/* Typ */}
      <fieldset>
        <legend className="block text-sm font-medium text-soft-ink2 mb-2">
          Typ{" "}
          <span className="text-soft-crit" aria-hidden="true">
            *
          </span>
        </legend>
        <div className="space-y-3">
          {/* PROJECT */}
          <label
            className={`flex items-start gap-3 rounded-soft-sm border p-4 cursor-pointer transition-colors
              ${
                typ === "PROJECT"
                  ? "border-soft-accent bg-soft-accentSoft"
                  : "border-soft-line hover:border-soft-line hover:bg-soft-line2"
              }`}
          >
            <input
              type="radio"
              name="kst-typ"
              value="PROJECT"
              checked={typ === "PROJECT"}
              onChange={() => setTyp("PROJECT")}
              className="mt-0.5 h-4 w-4 accent-soft-accent focus:ring-2 focus:ring-soft-accent"
            />
            <div>
              <div className="text-sm font-medium text-soft-ink">Projektkostenstelle</div>
              <div className="text-xs text-soft-ink3 mt-0.5">
                Direkte Projektarbeit — Kosten werden einem konkreten Projekt zugeordnet
              </div>
            </div>
          </label>

          {/* OVERHEAD */}
          <label
            className={`flex items-start gap-3 rounded-soft-sm border p-4 cursor-pointer transition-colors
              ${
                typ === "OVERHEAD"
                  ? "border-soft-accent bg-soft-accentSoft"
                  : "border-soft-line hover:border-soft-line hover:bg-soft-line2"
              }`}
          >
            <input
              type="radio"
              name="kst-typ"
              value="OVERHEAD"
              checked={typ === "OVERHEAD"}
              onChange={() => setTyp("OVERHEAD")}
              className="mt-0.5 h-4 w-4 accent-soft-accent focus:ring-2 focus:ring-soft-accent"
            />
            <div>
              <div className="text-sm font-medium text-soft-ink">Overhead / Verwaltung</div>
              <div className="text-xs text-soft-ink3 mt-0.5">
                z.B. Geschäftsführung, IT, HR — nicht direkt einem Projekt zuzuordnen
              </div>
            </div>
          </label>
        </div>
      </fieldset>

      {/* Übergeordnete KST */}
      <div>
        <label htmlFor="kst-parent" className="block text-sm font-medium text-soft-ink2 mb-1">
          Übergeordnete Kostenstelle{" "}
          <span className="text-xs font-normal text-soft-ink3">(optional)</span>
        </label>
        <select
          id="kst-parent"
          value={parentId}
          onChange={(e) => setParentId(e.target.value)}
          aria-describedby={errors.parent_id ? "kst-parent-error" : "kst-parent-hint"}
          aria-invalid={!!errors.parent_id}
          className={`w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors
            focus:ring-2 focus:ring-soft-accent focus:border-soft-accent bg-white
            ${errors.parent_id ? "border-soft-crit" : "border-soft-line"}`}
        >
          <option value="">— Keine übergeordnete KST —</option>
          {parentOptions.map((p) => (
            <option key={p.id} value={p.id}>
              {p.code} — {p.name}
            </option>
          ))}
        </select>
        {errors.parent_id ? (
          <p id="kst-parent-error" role="alert" className="mt-1 text-xs text-soft-crit">
            {errors.parent_id}
          </p>
        ) : (
          <p id="kst-parent-hint" className="mt-1 text-xs text-soft-ink3">
            Nur eine Hierarchieebene möglich. Zeigt nur aktive Projektkostenstellen ohne eigenes
            Elternteil.
          </p>
        )}
      </div>

      {/* Submit */}
      <div className="pt-2 flex items-center justify-end gap-3">
        <Button type="button" variant="secondary" onClick={() => router.back()} disabled={loading}>
          Abbrechen
        </Button>
        <Button type="submit" variant="primary" loading={loading}>
          {mode === "create" ? "Kostenstelle anlegen" : "Änderungen speichern"}
        </Button>
      </div>
    </form>
  );
}
