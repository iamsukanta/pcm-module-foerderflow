"use client";

import { useState, type ElementType, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import type { FunderTyp } from "@/types/foerdermassnahmen";

type FunderTypOption = {
  value: FunderTyp;
  label: string;
  icon: string;
  description: string;
};

const FUNDER_TYP_OPTIONS: FunderTypOption[] = [
  { value: "STIFTUNG", label: "Stiftung", icon: "🏛️", description: "Private oder öffentliche Stiftungen" },
  { value: "KOMMUNE", label: "Kommune", icon: "🏙️", description: "Städte, Gemeinden, Landkreise" },
  { value: "MINISTERIUM", label: "Ministerium", icon: "🏛️", description: "Bundes- oder Landesministerien" },
  { value: "EU", label: "EU", icon: "🇪🇺", description: "Europäische Förderprogramme (ESF, EFRE, ...)" },
  { value: "ANDERE", label: "Andere", icon: "📋", description: "Sonstige Fördergeber" },
];

type FunderFormProps = {
  onSuccess: (funder: { id: string; name: string; typ: FunderTyp }) => void;
  onCancel?: () => void;
  /** When true, renders inline (no card wrapper) */
  inline?: boolean;
  /** Pre-fill the name field (e.g. from OCR extraction) */
  defaultName?: string;
};

type FieldErrors = {
  name?: string;
  typ?: string;
  general?: string;
};

export function FunderForm({ onSuccess, onCancel, inline = false, defaultName }: FunderFormProps) {
  const [name, setName] = useState(defaultName ?? "");
  const [typ, setTyp] = useState<FunderTyp>("STIFTUNG");
  const [notizen, setNotizen] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [loading, setLoading] = useState(false);

  const validate = (): boolean => {
    const newErrors: FieldErrors = {};
    if (!name.trim() || name.trim().length < 2) {
      newErrors.name = "Name muss mindestens 2 Zeichen lang sein.";
    }
    if (name.trim().length > 200) {
      newErrors.name = "Name darf maximal 200 Zeichen lang sein.";
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!validate()) return;

    setLoading(true);
    try {
      const res = await fetch("/api/protected/funder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          typ,
          notizen: notizen.trim() || null,
        }),
      });

      const json = await res.json() as { data?: { id: string; name: string; typ: FunderTyp }; error?: string; code?: string };

      if (!res.ok) {
        const errCode = json.code ?? "";
        if (errCode === "VALIDATION_NAME") {
          setErrors({ name: json.error });
        } else {
          setErrors({ general: json.error ?? "Ein Fehler ist aufgetreten." });
        }
        return;
      }

      if (json.data) {
        onSuccess(json.data);
      }
    } catch {
      setErrors({ general: "Netzwerkfehler. Bitte versuche es erneut." });
    } finally {
      setLoading(false);
    }
  };

  // Wenn inline=true: kein <form>-Wrapper (verhindert nested forms im Wizard)
  const Wrapper: ElementType = inline ? "div" : "form";
  const wrapperProps: Record<string, unknown> = inline
    ? { className: "space-y-4" }
    : { onSubmit: handleSubmit, noValidate: true, className: "space-y-5 rounded-soft-sm border border-soft-line bg-soft-line2 p-5" };

  return (
    <Wrapper {...wrapperProps}>
      {!inline && (
        <h3 className="text-sm font-semibold text-soft-ink">Neuen Fördergeber anlegen</h3>
      )}

      {errors.general && (
        <div role="alert" className="rounded-soft-xs bg-soft-critSoft border border-soft-crit/30 p-3 text-sm text-soft-crit">
          {errors.general}
        </div>
      )}

      {/* Name */}
      <div>
        <label htmlFor="funder-name" className="block text-sm font-medium text-soft-ink2 mb-1">
          Name <span className="text-soft-crit" aria-hidden="true">*</span>
        </label>
        <input
          id="funder-name"
          type="text"
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            if (errors.name) setErrors((p) => ({ ...p, name: undefined }));
          }}
          placeholder="z.B. Stiftung Hamburg"
          maxLength={200}
          aria-required="true"
          aria-invalid={!!errors.name}
          className={`w-full rounded-soft-xs border px-3 py-2 text-sm outline-none transition-colors
            focus:ring-2 focus:ring-soft-accent focus:border-soft-accent
            ${errors.name ? "border-soft-crit bg-soft-critSoft" : "border-soft-line bg-white"}`}
        />
        {errors.name && (
          <p role="alert" className="mt-1 text-xs text-soft-crit">{errors.name}</p>
        )}
      </div>

      {/* Typ */}
      <fieldset>
        <legend className="block text-sm font-medium text-soft-ink2 mb-2">Typ *</legend>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {FUNDER_TYP_OPTIONS.map((opt) => (
            <label
              key={opt.value}
              className={`flex items-center gap-2 rounded-soft-xs border p-2.5 cursor-pointer transition-colors text-sm
                ${typ === opt.value
                  ? "border-soft-accent bg-soft-accentSoft text-soft-accent"
                  : "border-soft-line hover:border-soft-line hover:bg-soft-line2 text-soft-ink2"
                }`}
            >
              <input
                type="radio"
                name="funder-typ"
                value={opt.value}
                checked={typ === opt.value}
                onChange={() => setTyp(opt.value)}
                className="h-3.5 w-3.5 accent-soft-accent"
              />
              <span>{opt.icon}</span>
              <span className="font-medium">{opt.label}</span>
            </label>
          ))}
        </div>
      </fieldset>

      {/* Notizen */}
      <div>
        <label htmlFor="funder-notizen" className="block text-sm font-medium text-soft-ink2 mb-1">
          Notizen <span className="text-xs font-normal text-soft-ink3">(optional)</span>
        </label>
        <textarea
          id="funder-notizen"
          value={notizen}
          onChange={(e) => setNotizen(e.target.value)}
          rows={3}
          placeholder="z.B. Ansprechperson, Website, Hinweise zur Antragstellung"
          className="w-full rounded-soft-xs border border-soft-line bg-white px-3 py-2 text-sm outline-none
            transition-colors focus:ring-2 focus:ring-soft-accent focus:border-soft-accent resize-none"
        />
      </div>

      {/* Actions */}
      <div className="flex items-center justify-end gap-2">
        {onCancel && (
          <Button type="button" variant="secondary" size="sm" onClick={onCancel} disabled={loading}>
            Abbrechen
          </Button>
        )}
        <Button
          type={inline ? "button" : "submit"}
          onClick={inline ? () => void handleSubmit() : undefined}
          variant="primary"
          size="sm"
          loading={loading}
        >
          Fördergeber anlegen
        </Button>
      </div>
    </Wrapper>
  );
}
