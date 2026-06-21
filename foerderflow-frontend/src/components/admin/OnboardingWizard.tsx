"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/ToastProvider";
import { Plus, Trash2, ChevronLeft, ChevronRight, Check } from "lucide-react";

type Step = 1 | 2 | 3;
type Role = "ADMIN" | "FINANCE" | "READONLY";

const CURRENT_YEAR = new Date().getFullYear();

export function OnboardingWizard() {
  const router = useRouter();
  const toast = useToast();
  const [step, setStep] = useState<Step>(1);
  const [submitting, setSubmitting] = useState(false);

  // Step 1
  const [name, setName] = useState("");
  const [rechtsform, setRechtsform] = useState("EV");
  const [stunden, setStunden] = useState("39");

  // Step 2
  const [withFy, setWithFy] = useState(true);
  const [fyJahr, setFyJahr] = useState(String(CURRENT_YEAR));
  const [fyBeginn, setFyBeginn] = useState(`${CURRENT_YEAR}-01-01`);
  const [fyEnde, setFyEnde] = useState(`${CURRENT_YEAR}-12-31`);

  // Step 3
  const [invites, setInvites] = useState<{ email: string; role: Role }[]>([
    { email: "", role: "ADMIN" },
  ]);

  function addInvite() {
    setInvites((prev) => [...prev, { email: "", role: "FINANCE" }]);
  }
  function removeInvite(idx: number) {
    setInvites((prev) => prev.filter((_, i) => i !== idx));
  }
  function updateInvite(idx: number, patch: Partial<{ email: string; role: Role }>) {
    setInvites((prev) => prev.map((it, i) => (i === idx ? { ...it, ...patch } : it)));
  }

  function canNext(): boolean {
    if (step === 1) return name.trim().length >= 2 && Number(stunden) > 0;
    if (step === 2) {
      if (!withFy) return true;
      const j = Number(fyJahr);
      return j >= 2000 && j <= 2100 && fyBeginn !== "" && fyEnde !== "";
    }
    return true;
  }

  async function submit() {
    setSubmitting(true);
    try {
      const orgRes = await fetch("/api/admin/organisations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          rechtsform,
          regelarbeitszeit_stunden: Number(stunden),
          firstFiscalYear: withFy
            ? { jahr: Number(fyJahr), beginn: fyBeginn, ende: fyEnde }
            : undefined,
        }),
      });
      const orgJson = (await orgRes.json()) as { data?: { id: string }; error?: string };
      if (!orgRes.ok || !orgJson.data) {
        toast.error(orgJson.error ?? "Org-Anlage fehlgeschlagen.");
        return;
      }
      const orgId = orgJson.data.id;

      // Invites parallel
      const validInvites = invites.filter((i) => i.email.trim().length > 0);
      const inviteResults = await Promise.allSettled(
        validInvites.map((i) =>
          fetch(`/api/admin/organisations/${orgId}/invite`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: i.email.trim(), role: i.role }),
          }).then(async (r) => {
            if (!r.ok) {
              const j = (await r.json()) as { error?: string };
              throw new Error(j.error ?? `Einladung an ${i.email} fehlgeschlagen.`);
            }
          }),
        ),
      );

      const failedInvites = inviteResults.filter((r) => r.status === "rejected");
      if (failedInvites.length > 0) {
        toast.error(
          `Org angelegt, aber ${failedInvites.length} von ${validInvites.length} Einladungen schlugen fehl.`,
        );
      } else {
        toast.success(
          validInvites.length > 0
            ? `Org angelegt + ${validInvites.length} Einladung(en) verschickt.`
            : "Org angelegt.",
        );
      }
      router.push(`/admin/organisations/${orgId}`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="bg-white rounded-soft-sm border border-soft-line p-6">
      {/* Step indicator */}
      <div className="flex items-center gap-2 mb-6">
        {[1, 2, 3].map((s) => (
          <div key={s} className="flex items-center gap-2 flex-1">
            <div
              className={`h-7 w-7 rounded-full flex items-center justify-center text-xs font-semibold ${
                step === s
                  ? "bg-soft-accent text-white"
                  : step > s
                  ? "bg-soft-ok text-white"
                  : "bg-soft-line2 text-soft-ink3"
              }`}
            >
              {step > s ? <Check className="h-3.5 w-3.5" aria-hidden /> : s}
            </div>
            <span
              className={`text-xs ${step >= s ? "text-soft-ink2" : "text-soft-ink4"} ${
                step === s ? "font-medium" : ""
              } truncate`}
            >
              {s === 1 ? "Stammdaten" : s === 2 ? "Haushaltsjahr" : "Mitglieder"}
            </span>
            {s < 3 && <div className="flex-1 h-px bg-soft-line2" />}
          </div>
        ))}
      </div>

      {step === 1 && (
        <div className="space-y-4">
          <FormRow label="Name der Organisation">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={200}
              placeholder="z.B. Caritas München"
              className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm"
              autoFocus
            />
          </FormRow>
          <FormRow label="Rechtsform">
            <select
              value={rechtsform}
              onChange={(e) => setRechtsform(e.target.value)}
              className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm bg-white"
            >
              <option value="EV">e.V. (eingetragener Verein)</option>
              <option value="GGMBH">gGmbH (gemeinnützige GmbH)</option>
              <option value="STIFTUNG">Stiftung</option>
              <option value="ANDERE">Andere</option>
            </select>
          </FormRow>
          <FormRow label="Regelarbeitszeit (h/Woche, Vollzeit)">
            <input
              type="number"
              step="0.25"
              min={1}
              max={80}
              value={stunden}
              onChange={(e) => setStunden(e.target.value)}
              className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm numeric"
            />
          </FormRow>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-4">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={withFy}
              onChange={(e) => setWithFy(e.target.checked)}
              className="rounded-soft-xs"
            />
            <span>Erstes Haushaltsjahr direkt anlegen</span>
          </label>
          {withFy && (
            <>
              <FormRow label="Jahr">
                <input
                  type="number"
                  min={2000}
                  max={2100}
                  value={fyJahr}
                  onChange={(e) => setFyJahr(e.target.value)}
                  className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm numeric"
                />
              </FormRow>
              <div className="grid grid-cols-2 gap-3">
                <FormRow label="Beginn">
                  <input
                    type="date"
                    value={fyBeginn}
                    onChange={(e) => setFyBeginn(e.target.value)}
                    className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm"
                  />
                </FormRow>
                <FormRow label="Ende">
                  <input
                    type="date"
                    value={fyEnde}
                    onChange={(e) => setFyEnde(e.target.value)}
                    className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm"
                  />
                </FormRow>
              </div>
            </>
          )}
          {!withFy && (
            <p className="text-xs text-soft-ink3">
              Ohne Haushaltsjahr sieht der Kunde beim ersten Login ein leeres Dashboard. Lässt sich
              später jederzeit nachlegen.
            </p>
          )}
        </div>
      )}

      {step === 3 && (
        <div className="space-y-3">
          <p className="text-xs text-soft-ink3">
            Pro Mitglied: Email + Rolle. Magic-Link wird verschickt; beim ersten Login wird die
            Mitgliedschaft hergestellt. Felder mit leerer Email werden ignoriert.
          </p>
          {invites.map((inv, idx) => (
            <div key={idx} className="flex gap-2 items-end">
              <div className="flex-1">
                <FormRow label={idx === 0 ? "Email" : ""}>
                  <input
                    type="email"
                    value={inv.email}
                    onChange={(e) => updateInvite(idx, { email: e.target.value })}
                    placeholder="name@org.de"
                    className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm"
                  />
                </FormRow>
              </div>
              <div className="w-40">
                <FormRow label={idx === 0 ? "Rolle" : ""}>
                  <select
                    value={inv.role}
                    onChange={(e) => updateInvite(idx, { role: e.target.value as Role })}
                    className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm bg-white"
                  >
                    <option value="ADMIN">Org-Admin</option>
                    <option value="FINANCE">Finance</option>
                    <option value="READONLY">Nur-Lese</option>
                  </select>
                </FormRow>
              </div>
              <button
                type="button"
                onClick={() => removeInvite(idx)}
                disabled={invites.length === 1}
                aria-label="Eintrag entfernen"
                className="p-2 mb-0.5 rounded-soft-xs hover:bg-soft-critSoft disabled:opacity-30"
              >
                <Trash2 className="h-4 w-4 text-soft-ink3" aria-hidden />
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={addInvite}
            className="inline-flex items-center gap-1.5 text-sm text-soft-accent hover:underline"
          >
            <Plus className="h-4 w-4" aria-hidden /> Weiteres Mitglied
          </button>
        </div>
      )}

      <div className="flex justify-between gap-2 pt-6 mt-6 border-t border-soft-line2">
        <Button
          type="button"
          variant="ghost"
          onClick={() => setStep((s) => (s > 1 ? ((s - 1) as Step) : s))}
          disabled={step === 1 || submitting}
        >
          <ChevronLeft className="h-4 w-4 mr-1" aria-hidden /> Zurück
        </Button>
        {step < 3 ? (
          <Button
            type="button"
            onClick={() => setStep((s) => (s + 1) as Step)}
            disabled={!canNext()}
          >
            Weiter <ChevronRight className="h-4 w-4 ml-1" aria-hidden />
          </Button>
        ) : (
          <Button type="button" onClick={() => void submit()} disabled={submitting}>
            {submitting ? "Lege an…" : "Organisation anlegen"}
          </Button>
        )}
      </div>
    </div>
  );
}

function FormRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      {label && <span className="block text-sm font-medium text-soft-ink2 mb-1">{label}</span>}
      {children}
    </label>
  );
}
