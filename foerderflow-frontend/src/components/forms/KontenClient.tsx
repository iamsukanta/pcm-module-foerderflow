"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useToast } from "@/components/ui/ToastProvider";
import { Plus, Pencil, Trash2, Banknote, Wallet, Globe, Check, X } from "lucide-react";

export type FiscalYearOption = {
  id: string;
  jahr: number;
  status: string;
};

export type OpeningBalanceForUi = {
  id: string;
  fiscal_year_id: string;
  fiscal_year_jahr: number;
  saldo_eroeffnung: number;
  datum: string;
};

export type KontoForUi = {
  id: string;
  code: string;
  bezeichnung: string;
  typ: "BANK" | "KASSE" | "ONLINE_WALLET";
  iban: string | null;
  bic: string | null;
  bankname: string | null;
  ist_aktiv: boolean;
  anzahl_transaktionen: number;
  saldo_aktuell: number;
  opening_balances: OpeningBalanceForUi[];
};

const TYP_ICON: Record<KontoForUi["typ"], typeof Banknote> = {
  BANK: Banknote,
  KASSE: Wallet,
  ONLINE_WALLET: Globe,
};
const TYP_LABEL: Record<KontoForUi["typ"], string> = {
  BANK: "Bankkonto",
  KASSE: "Kasse",
  ONLINE_WALLET: "Online-Wallet",
};

function formatEur(n: number): string {
  return new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 2,
  }).format(n);
}

type Mode =
  | { kind: "list" }
  | { kind: "create" }
  | { kind: "edit"; account: KontoForUi }
  | { kind: "opening"; account: KontoForUi }
  | { kind: "delete"; account: KontoForUi };

export function KontenClient({
  initialAccounts,
  fiscalYears,
}: {
  initialAccounts: KontoForUi[];
  fiscalYears: FiscalYearOption[];
}) {
  const router = useRouter();
  const toast = useToast();
  const [mode, setMode] = useState<Mode>({ kind: "list" });
  const [submitting, setSubmitting] = useState(false);

  async function createAccount(form: HTMLFormElement) {
    const fd = new FormData(form);
    setSubmitting(true);
    try {
      const res = await fetch("/api/protected/bank-accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: String(fd.get("code") ?? ""),
          bezeichnung: String(fd.get("bezeichnung") ?? ""),
          typ: String(fd.get("typ") ?? "BANK"),
          iban: fd.get("iban") || null,
          bic: fd.get("bic") || null,
          bankname: fd.get("bankname") || null,
        }),
      });
      const json = (await res.json()) as { data?: unknown; error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Anlegen fehlgeschlagen.");
        return;
      }
      toast.success("Konto angelegt.");
      setMode({ kind: "list" });
      router.refresh();
    } finally {
      setSubmitting(false);
    }
  }

  async function updateAccount(form: HTMLFormElement, accountId: string) {
    const fd = new FormData(form);
    setSubmitting(true);
    try {
      const res = await fetch(`/api/protected/bank-accounts/${accountId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          bezeichnung: String(fd.get("bezeichnung") ?? ""),
          bic: fd.get("bic") || null,
          bankname: fd.get("bankname") || null,
          ist_aktiv: fd.get("ist_aktiv") === "on",
        }),
      });
      const json = (await res.json()) as { error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Update fehlgeschlagen.");
        return;
      }
      toast.success("Konto aktualisiert.");
      setMode({ kind: "list" });
      router.refresh();
    } finally {
      setSubmitting(false);
    }
  }

  async function saveOpeningBalance(form: HTMLFormElement, accountId: string) {
    const fd = new FormData(form);
    setSubmitting(true);
    try {
      const res = await fetch("/api/protected/opening-balances", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          bank_account_id: accountId,
          fiscal_year_id: String(fd.get("fiscal_year_id") ?? ""),
          saldo_eroeffnung: Number(String(fd.get("saldo_eroeffnung") ?? "0").replace(",", ".")),
          datum: fd.get("datum") || null,
          notiz: fd.get("notiz") || null,
        }),
      });
      const json = (await res.json()) as { error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Speichern fehlgeschlagen.");
        return;
      }
      toast.success("Eröffnungssaldo gespeichert.");
      setMode({ kind: "list" });
      router.refresh();
    } finally {
      setSubmitting(false);
    }
  }

  async function deleteAccount(account: KontoForUi) {
    setSubmitting(true);
    try {
      const res = await fetch(`/api/protected/bank-accounts/${account.id}`, { method: "DELETE" });
      const json = (await res.json()) as { error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Löschen fehlgeschlagen.");
        return;
      }
      toast.success("Konto gelöscht.");
      setMode({ kind: "list" });
      router.refresh();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <div className="mb-4 flex justify-end">
        <Button onClick={() => setMode({ kind: "create" })}>
          <Plus className="h-4 w-4 mr-1.5" aria-hidden /> Neues Konto
        </Button>
      </div>

      {initialAccounts.length === 0 ? (
        <EmptyState
          icon={Banknote}
          title="Noch keine Konten"
          description="Lege dein erstes Bank- oder Kassenkonto an. Spätere Imports ordnen sich automatisch via IBAN zu."
          action={{ label: "Konto anlegen", onClick: () => setMode({ kind: "create" }) }}
        />
      ) : (
        <div className="bg-white rounded-soft-sm border border-soft-line overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-soft-surfaceAlt border-b border-soft-line text-left text-xs uppercase tracking-wide text-soft-ink3">
              <tr>
                <th className="px-4 py-3">Konto</th>
                <th className="px-4 py-3">IBAN</th>
                <th className="px-4 py-3 text-right">Saldo aktuell</th>
                <th className="px-4 py-3 text-right">Transaktionen</th>
                <th className="px-4 py-3 text-right">Eröffnung</th>
                <th className="px-4 py-3 w-32"></th>
              </tr>
            </thead>
            <tbody>
              {initialAccounts.map((acc) => {
                const Icon = TYP_ICON[acc.typ];
                return (
                  <tr
                    key={acc.id}
                    className={`border-b border-soft-line2 last:border-0 hover:bg-soft-surfaceAlt ${
                      acc.ist_aktiv ? "" : "opacity-50"
                    }`}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Icon className="h-4 w-4 text-soft-ink3" aria-hidden />
                        <div>
                          <div className="font-medium text-soft-ink">{acc.bezeichnung}</div>
                          <div className="text-xs text-soft-ink3 flex items-center gap-1.5">
                            <span>{acc.code}</span>
                            <span>·</span>
                            <span>{TYP_LABEL[acc.typ]}</span>
                            {!acc.ist_aktiv && <Badge variant="muted">inaktiv</Badge>}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-soft-ink3 font-mono">{acc.iban ?? "—"}</td>
                    <td className="px-4 py-3 text-right numeric">{formatEur(acc.saldo_aktuell)}</td>
                    <td className="px-4 py-3 text-right text-soft-ink2 numeric">
                      {acc.anzahl_transaktionen}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {acc.opening_balances.length === 0 ? (
                        <button
                          type="button"
                          onClick={() => setMode({ kind: "opening", account: acc })}
                          className="text-xs text-soft-accent hover:underline"
                        >
                          + Eröffnungssaldo
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setMode({ kind: "opening", account: acc })}
                          className="text-xs text-soft-ink2 hover:text-soft-accent"
                        >
                          {acc.opening_balances.length} ×{" "}
                          {acc.opening_balances
                            .map((o) => `${o.fiscal_year_jahr}: ${formatEur(o.saldo_eroeffnung)}`)
                            .join(", ")}
                        </button>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => setMode({ kind: "edit", account: acc })}
                          className="p-2 rounded-soft-xs hover:bg-soft-line2 focus:outline-none focus:ring-2 focus:ring-soft-accent"
                          aria-label={`Konto ${acc.bezeichnung} bearbeiten`}
                        >
                          <Pencil className="h-4 w-4 text-soft-ink3" aria-hidden />
                        </button>
                        <button
                          type="button"
                          onClick={() => setMode({ kind: "delete", account: acc })}
                          className="p-2 rounded-soft-xs hover:bg-soft-critSoft focus:outline-none focus:ring-2 focus:ring-soft-crit"
                          aria-label={`Konto ${acc.bezeichnung} löschen`}
                        >
                          <Trash2 className="h-4 w-4 text-soft-ink3 hover:text-soft-crit" aria-hidden />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Create modal */}
      {mode.kind === "create" && (
        <ModalShell title="Neues Konto" onClose={() => setMode({ kind: "list" })}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void createAccount(e.currentTarget);
            }}
            className="space-y-4"
          >
            <FormRow label="Code" hint="Interner Kurzname, eindeutig je Org">
              <input
                name="code"
                required
                maxLength={50}
                className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm"
              />
            </FormRow>
            <FormRow label="Bezeichnung">
              <input
                name="bezeichnung"
                required
                maxLength={120}
                className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm"
              />
            </FormRow>
            <FormRow label="Typ">
              <select
                name="typ"
                defaultValue="BANK"
                className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm"
              >
                <option value="BANK">Bankkonto</option>
                <option value="KASSE">Kasse</option>
                <option value="ONLINE_WALLET">Online-Wallet (PayPal, …)</option>
              </select>
            </FormRow>
            <FormRow label="IBAN" hint="Optional, aber empfohlen für Auto-Match beim Import">
              <input
                name="iban"
                maxLength={34}
                className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm font-mono"
              />
            </FormRow>
            <div className="grid grid-cols-2 gap-3">
              <FormRow label="BIC">
                <input
                  name="bic"
                  maxLength={11}
                  className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm font-mono"
                />
              </FormRow>
              <FormRow label="Bankname">
                <input
                  name="bankname"
                  maxLength={120}
                  className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm"
                />
              </FormRow>
            </div>
            <ModalFooter onCancel={() => setMode({ kind: "list" })} submitting={submitting} />
          </form>
        </ModalShell>
      )}

      {/* Edit modal */}
      {mode.kind === "edit" && (
        <ModalShell
          title={`Konto bearbeiten: ${mode.account.bezeichnung}`}
          onClose={() => setMode({ kind: "list" })}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void updateAccount(e.currentTarget, mode.account.id);
            }}
            className="space-y-4"
          >
            <p className="text-xs text-soft-ink3">
              Code und IBAN sind nach Anlage nicht änderbar (würde Transaktionen entkoppeln). Bei
              Bedarf neues Konto anlegen.
            </p>
            <FormRow label="Bezeichnung">
              <input
                name="bezeichnung"
                required
                defaultValue={mode.account.bezeichnung}
                maxLength={120}
                className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm"
              />
            </FormRow>
            <div className="grid grid-cols-2 gap-3">
              <FormRow label="BIC">
                <input
                  name="bic"
                  defaultValue={mode.account.bic ?? ""}
                  maxLength={11}
                  className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm font-mono"
                />
              </FormRow>
              <FormRow label="Bankname">
                <input
                  name="bankname"
                  defaultValue={mode.account.bankname ?? ""}
                  maxLength={120}
                  className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm"
                />
              </FormRow>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                name="ist_aktiv"
                defaultChecked={mode.account.ist_aktiv}
                className="rounded-soft-xs"
              />
              <span>Aktiv (für Imports auswählbar)</span>
            </label>
            <ModalFooter onCancel={() => setMode({ kind: "list" })} submitting={submitting} />
          </form>
        </ModalShell>
      )}

      {/* Opening balance modal */}
      {mode.kind === "opening" && (
        <ModalShell
          title={`Eröffnungssaldo: ${mode.account.bezeichnung}`}
          onClose={() => setMode({ kind: "list" })}
        >
          <div className="mb-4 text-xs text-soft-ink3">
            Anfangsbestand zum Beginn eines Geschäftsjahrs. Nur 1 Eröffnung pro Jahr (Upsert).
          </div>
          {mode.account.opening_balances.length > 0 && (
            <div className="mb-4 bg-soft-surfaceAlt rounded-soft-xs p-3 space-y-1">
              {mode.account.opening_balances.map((o) => (
                <div key={o.id} className="flex justify-between text-sm">
                  <span className="text-soft-ink2">
                    Jahr {o.fiscal_year_jahr} (ab {new Date(o.datum).toLocaleDateString("de-DE")})
                  </span>
                  <span className="numeric font-medium">{formatEur(o.saldo_eroeffnung)}</span>
                </div>
              ))}
            </div>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void saveOpeningBalance(e.currentTarget, mode.account.id);
            }}
            className="space-y-4"
          >
            <FormRow label="Geschäftsjahr">
              <select
                name="fiscal_year_id"
                required
                className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm"
              >
                <option value="">Jahr wählen…</option>
                {fiscalYears.map((fy) => (
                  <option key={fy.id} value={fy.id}>
                    {fy.jahr} {fy.status === "GESCHLOSSEN" ? "(geschlossen)" : ""}
                  </option>
                ))}
              </select>
            </FormRow>
            <FormRow label="Saldo zum Stichtag" hint="Format: 1234,56 (negativ = Soll)">
              <input
                name="saldo_eroeffnung"
                required
                inputMode="decimal"
                className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm numeric"
              />
            </FormRow>
            <FormRow label="Stichtag" hint="Default = Beginn des Geschäftsjahrs">
              <input
                name="datum"
                type="date"
                className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm"
              />
            </FormRow>
            <FormRow label="Notiz (optional)">
              <textarea
                name="notiz"
                rows={2}
                className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm"
              />
            </FormRow>
            <ModalFooter onCancel={() => setMode({ kind: "list" })} submitting={submitting} />
          </form>
        </ModalShell>
      )}

      {/* Delete confirm */}
      {mode.kind === "delete" && (
        <ConfirmDialog
          open
          title={`Konto "${mode.account.bezeichnung}" löschen?`}
          description={
            mode.account.anzahl_transaktionen > 0
              ? `Dieses Konto hat ${mode.account.anzahl_transaktionen} Transaktion(en). Es kann nicht gelöscht werden — stattdessen bitte deaktivieren.`
              : "Das Löschen kann nicht rückgängig gemacht werden."
          }
          confirmLabel={mode.account.anzahl_transaktionen > 0 ? "Verstanden" : "Löschen"}
          variant={mode.account.anzahl_transaktionen > 0 ? "default" : "danger"}
          loading={submitting}
          onConfirm={() => {
            if (mode.account.anzahl_transaktionen > 0) {
              setMode({ kind: "list" });
            } else {
              void deleteAccount(mode.account);
            }
          }}
          onCancel={() => setMode({ kind: "list" })}
        />
      )}
    </>
  );
}

// ── kleine Form-Helfer ──
function FormRow({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-soft-ink2 mb-1">{label}</span>
      {children}
      {hint && <span className="block text-xs text-soft-ink4 mt-1">{hint}</span>}
    </label>
  );
}

function ModalShell({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-soft-ink/40 p-4">
      <div className="bg-white rounded-soft border border-soft-line shadow-soft-lg w-full max-w-md max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-soft-line2 px-5 py-4">
          <h2 className="text-base font-semibold text-soft-ink">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-soft-xs hover:bg-soft-line2"
            aria-label="Schließen"
          >
            <X className="h-4 w-4 text-soft-ink3" aria-hidden />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

function ModalFooter({ onCancel, submitting }: { onCancel: () => void; submitting: boolean }) {
  return (
    <div className="flex justify-end gap-2 pt-2">
      <Button type="button" variant="ghost" onClick={onCancel} disabled={submitting}>
        Abbrechen
      </Button>
      <Button type="submit" disabled={submitting}>
        {submitting ? (
          "Speichern…"
        ) : (
          <>
            <Check className="h-4 w-4 mr-1.5" aria-hidden /> Speichern
          </>
        )}
      </Button>
    </div>
  );
}
