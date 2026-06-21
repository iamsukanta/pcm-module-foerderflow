"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useToast } from "@/components/ui/ToastProvider";
import {
  UserPlus,
  Mail,
  Trash2,
  X,
  Check,
  AlertTriangle,
  Building2,
} from "lucide-react";

type Role = "ADMIN" | "FINANCE" | "READONLY";
const ROLE_LABEL: Record<Role, string> = {
  ADMIN: "Org-Admin",
  FINANCE: "Finance",
  READONLY: "Nur-Lese",
};
const ROLE_BADGE: Record<Role, "default" | "success" | "muted"> = {
  ADMIN: "default",
  FINANCE: "success",
  READONLY: "muted",
};

type OrgInfo = {
  id: string;
  name: string;
  rechtsform: string;
  regelarbeitszeit_stunden: number;
};
type Member = {
  id: string;
  user_id: string;
  email: string;
  vorname: string | null;
  nachname: string | null;
  role: Role;
  created_at: string;
};
type Invite = {
  id: string;
  email: string;
  role: Role;
  expires_at: string;
  created_at: string;
  created_by_label: string;
};

type Tab = "stammdaten" | "members" | "invites" | "danger";

export function OrganisationDetailClient({
  org,
  members,
  invites,
  counts,
}: {
  org: OrgInfo;
  members: Member[];
  invites: Invite[];
  counts: { transactions: number; funding_measures: number; cost_centers: number };
}) {
  const [tab, setTab] = useState<Tab>("members");

  return (
    <div>
      {/* Tab-Bar */}
      <div className="border-b border-soft-line mb-6">
        <nav className="flex gap-1 -mb-px">
          <TabButton active={tab === "stammdaten"} onClick={() => setTab("stammdaten")}>
            Stammdaten
          </TabButton>
          <TabButton active={tab === "members"} onClick={() => setTab("members")}>
            Mitglieder ({members.length})
          </TabButton>
          <TabButton active={tab === "invites"} onClick={() => setTab("invites")}>
            Einladungen ({invites.length})
          </TabButton>
          <TabButton active={tab === "danger"} onClick={() => setTab("danger")}>
            Gefährliche Zone
          </TabButton>
        </nav>
      </div>

      {tab === "stammdaten" && <StammdatenTab org={org} />}
      {tab === "members" && <MembersTab orgId={org.id} members={members} />}
      {tab === "invites" && <InvitesTab orgId={org.id} invites={invites} />}
      {tab === "danger" && <DangerTab orgId={org.id} orgName={org.name} counts={counts} hasMembers={members.length > 0} />}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-4 py-2.5 text-sm border-b-2 transition-colors ${
        active
          ? "border-soft-accent text-soft-ink font-medium"
          : "border-transparent text-soft-ink3 hover:text-soft-ink2"
      }`}
    >
      {children}
    </button>
  );
}

// ─── Stammdaten ───
function StammdatenTab({ org }: { org: OrgInfo }) {
  const router = useRouter();
  const toast = useToast();
  const [name, setName] = useState(org.name);
  const [rechtsform, setRechtsform] = useState(org.rechtsform);
  const [stunden, setStunden] = useState(String(org.regelarbeitszeit_stunden));
  const [submitting, setSubmitting] = useState(false);
  const dirty = name !== org.name || rechtsform !== org.rechtsform || Number(stunden) !== org.regelarbeitszeit_stunden;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const res = await fetch(`/api/admin/organisations/${org.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, rechtsform, regelarbeitszeit_stunden: Number(stunden) }),
      });
      const json = (await res.json()) as { error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Speichern fehlgeschlagen.");
        return;
      }
      toast.success("Stammdaten aktualisiert.");
      router.refresh();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={save} className="bg-white rounded-soft-sm border border-soft-line p-6 space-y-4 max-w-2xl">
      <FormRow label="Name">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={200}
          className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm"
        />
      </FormRow>
      <FormRow label="Rechtsform">
        <select
          value={rechtsform}
          onChange={(e) => setRechtsform(e.target.value)}
          className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm bg-white"
        >
          <option value="EV">e.V.</option>
          <option value="GGMBH">gGmbH</option>
          <option value="STIFTUNG">Stiftung</option>
          <option value="ANDERE">Andere</option>
        </select>
      </FormRow>
      <FormRow label="Regelarbeitszeit (h/Woche)">
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
      <div className="flex justify-end pt-2">
        <Button type="submit" disabled={!dirty || submitting}>
          {submitting ? "Speichere…" : "Speichern"}
        </Button>
      </div>
    </form>
  );
}

// ─── Mitglieder ───
function MembersTab({ orgId, members }: { orgId: string; members: Member[] }) {
  const router = useRouter();
  const toast = useToast();
  const [addModal, setAddModal] = useState(false);
  const [removeMember, setRemoveMember] = useState<Member | null>(null);
  const [forceOverride, setForceOverride] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Berechnet wie viele Admins die Org aktuell hat — bestimmt UI für Last-Admin-Fall.
  const adminCount = members.filter((m) => m.role === "ADMIN").length;
  const isLastAdminAction = (member: Member, newRole: Role | null) =>
    member.role === "ADMIN" &&
    newRole !== "ADMIN" && // bei null = entfernen, oder Rolle-Change weg von ADMIN
    adminCount <= 1;

  async function changeRole(member: Member, role: Role) {
    if (member.role === role) return;

    // Last-Admin-Schutz: bei Degradierung des letzten Admins erst bestätigen.
    if (isLastAdminAction(member, role)) {
      const ok = window.confirm(
        `${member.email} ist der einzige Org-Admin. Wenn du die Rolle änderst, hat "${member.email}" keinen Admin-Zugang mehr und die Org ist ohne Org-Admin. Trotzdem fortfahren?`,
      );
      if (!ok) return;
    }

    const force = isLastAdminAction(member, role) ? "?force=true" : "";
    const res = await fetch(`/api/admin/organisations/${orgId}/members/${member.user_id}${force}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    });
    const json = (await res.json()) as { error?: string };
    if (!res.ok) {
      toast.error(json.error ?? "Rolle ändern fehlgeschlagen.");
      return;
    }
    toast.success(`Rolle aktualisiert: ${ROLE_LABEL[role]}.`);
    router.refresh();
  }

  async function add(form: HTMLFormElement) {
    const fd = new FormData(form);
    setSubmitting(true);
    try {
      const res = await fetch(`/api/admin/organisations/${orgId}/members`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: String(fd.get("email") ?? "").trim(),
          role: String(fd.get("role") ?? "FINANCE"),
        }),
      });
      const json = (await res.json()) as { error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Hinzufügen fehlgeschlagen.");
        return;
      }
      toast.success("Mitglied hinzugefügt.");
      setAddModal(false);
      router.refresh();
    } finally {
      setSubmitting(false);
    }
  }

  async function remove(force: boolean) {
    if (!removeMember) return;
    setSubmitting(true);
    try {
      const url = `/api/admin/organisations/${orgId}/members/${removeMember.user_id}${force ? "?force=true" : ""}`;
      const res = await fetch(url, { method: "DELETE" });
      const json = (await res.json()) as { error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Entfernen fehlgeschlagen.");
        return;
      }
      toast.success("Mitglied entfernt.");
      closeRemoveModal();
      router.refresh();
    } finally {
      setSubmitting(false);
    }
  }

  function closeRemoveModal() {
    setRemoveMember(null);
    setForceOverride(false);
  }

  return (
    <>
      <div className="flex justify-end mb-3">
        <Button onClick={() => setAddModal(true)}>
          <UserPlus className="h-4 w-4 mr-1.5" aria-hidden /> Mitglied direkt hinzufügen
        </Button>
      </div>

      {members.length === 0 ? (
        <div className="bg-white rounded-soft-sm border border-soft-line p-12 text-center text-sm text-soft-ink3">
          Diese Organisation hat noch keine Mitglieder.
        </div>
      ) : (
        <div className="bg-white rounded-soft-sm border border-soft-line overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-soft-surfaceAlt border-b border-soft-line text-left text-xs uppercase tracking-wide text-soft-ink3">
              <tr>
                <th className="px-4 py-3">Email / Name</th>
                <th className="px-4 py-3">Rolle</th>
                <th className="px-4 py-3">Beigetreten</th>
                <th className="px-4 py-3 w-12"></th>
              </tr>
            </thead>
            <tbody>
              {members.map((m) => {
                const display = [m.vorname, m.nachname].filter(Boolean).join(" ");
                return (
                  <tr key={m.id} className="border-b border-soft-line2 last:border-0">
                    <td className="px-4 py-3">
                      <div className="font-medium text-soft-ink">{m.email}</div>
                      {display && <div className="text-xs text-soft-ink3">{display}</div>}
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={m.role}
                        onChange={(e) => void changeRole(m, e.target.value as Role)}
                        className="border border-soft-line rounded-soft-xs px-2 py-1 text-xs bg-white"
                      >
                        <option value="ADMIN">Org-Admin</option>
                        <option value="FINANCE">Finance</option>
                        <option value="READONLY">Nur-Lese</option>
                      </select>
                    </td>
                    <td className="px-4 py-3 text-xs text-soft-ink3">
                      {new Date(m.created_at).toLocaleDateString("de-DE")}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => setRemoveMember(m)}
                        aria-label={`${m.email} entfernen`}
                        className="p-2 rounded-soft-xs hover:bg-soft-critSoft"
                      >
                        <Trash2 className="h-4 w-4 text-soft-ink3 hover:text-soft-crit" aria-hidden />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {addModal && (
        <ModalShell title="Mitglied direkt hinzufügen" onClose={() => setAddModal(false)}>
          <p className="text-xs text-soft-ink3 mb-4">
            Der User muss bereits einen FörderFlow-Account haben (mindestens einmal eingeloggt).
            Andernfalls den Tab „Einladungen&ldquo; nutzen.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void add(e.currentTarget);
            }}
            className="space-y-4"
          >
            <FormRow label="Email">
              <input
                name="email"
                type="email"
                required
                className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm"
              />
            </FormRow>
            <FormRow label="Rolle">
              <select
                name="role"
                defaultValue="FINANCE"
                className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm bg-white"
              >
                <option value="ADMIN">Org-Admin</option>
                <option value="FINANCE">Finance</option>
                <option value="READONLY">Nur-Lese</option>
              </select>
            </FormRow>
            <ModalFooter onCancel={() => setAddModal(false)} submitting={submitting} />
          </form>
        </ModalShell>
      )}

      {removeMember && !isLastAdminAction(removeMember, null) && (
        <ConfirmDialog
          open
          title={`${removeMember.email} entfernen?`}
          description="Die Mitgliedschaft wird sofort gelöscht. Die Person verliert den Zugriff auf diese Org. Transaktionen und andere Daten bleiben erhalten."
          confirmLabel="Entfernen"
          variant="danger"
          loading={submitting}
          onConfirm={() => void remove(false)}
          onCancel={closeRemoveModal}
        />
      )}

      {removeMember && isLastAdminAction(removeMember, null) && (
        <ModalShell title={`${removeMember.email} entfernen?`} onClose={closeRemoveModal}>
          <div className="space-y-4">
            <div className="rounded-soft-xs border border-soft-crit/30 bg-soft-critSoft p-3 text-sm">
              <div className="flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 text-soft-crit shrink-0 mt-0.5" aria-hidden />
                <div className="text-soft-crit">
                  <p className="font-medium">Letzter Org-Admin</p>
                  <p className="mt-1 text-soft-ink2">
                    Das ist der einzige Org-Admin von dieser Organisation. Wenn du ihn entfernst,
                    hat die Org keinen Admin-Zugang mehr. Du kannst als VoluLink Super-Admin
                    jederzeit einen neuen Member als Org-Admin hinzufügen — Transaktionen,
                    Fördermaßnahmen und andere Daten bleiben erhalten.
                  </p>
                </div>
              </div>
            </div>
            <label className="flex items-start gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={forceOverride}
                onChange={(e) => setForceOverride(e.target.checked)}
                className="mt-0.5 rounded-soft-xs"
              />
              <span className="text-soft-ink2">
                Mir ist klar, dass die Organisation danach ohne Org-Admin ist.
              </span>
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="ghost" onClick={closeRemoveModal} disabled={submitting}>
                Abbrechen
              </Button>
              <Button
                type="button"
                variant="danger"
                onClick={() => void remove(true)}
                disabled={!forceOverride || submitting}
              >
                {submitting ? "Entferne…" : "Trotzdem entfernen"}
              </Button>
            </div>
          </div>
        </ModalShell>
      )}
    </>
  );
}

// ─── Einladungen ───
function InvitesTab({ orgId, invites }: { orgId: string; invites: Invite[] }) {
  const router = useRouter();
  const toast = useToast();
  const [inviteModal, setInviteModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function sendInvite(form: HTMLFormElement) {
    const fd = new FormData(form);
    setSubmitting(true);
    try {
      const res = await fetch(`/api/admin/organisations/${orgId}/invite`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: String(fd.get("email") ?? "").trim(),
          role: String(fd.get("role") ?? "FINANCE"),
        }),
      });
      const json = (await res.json()) as { error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Einladung fehlgeschlagen.");
        return;
      }
      toast.success("Einladung verschickt.");
      setInviteModal(false);
      router.refresh();
    } finally {
      setSubmitting(false);
    }
  }

  async function revoke(invite: Invite) {
    const res = await fetch(`/api/admin/organisations/${orgId}/invites/${invite.id}`, {
      method: "DELETE",
    });
    const json = (await res.json()) as { error?: string };
    if (!res.ok) {
      toast.error(json.error ?? "Widerrufen fehlgeschlagen.");
      return;
    }
    toast.success("Einladung widerrufen.");
    router.refresh();
  }

  return (
    <>
      <div className="flex justify-end mb-3">
        <Button onClick={() => setInviteModal(true)}>
          <Mail className="h-4 w-4 mr-1.5" aria-hidden /> Per Email einladen
        </Button>
      </div>

      {invites.length === 0 ? (
        <div className="bg-white rounded-soft-sm border border-soft-line p-12 text-center text-sm text-soft-ink3">
          Keine offenen Einladungen.
        </div>
      ) : (
        <div className="bg-white rounded-soft-sm border border-soft-line overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-soft-surfaceAlt border-b border-soft-line text-left text-xs uppercase tracking-wide text-soft-ink3">
              <tr>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Rolle</th>
                <th className="px-4 py-3">Eingeladen von</th>
                <th className="px-4 py-3">Läuft ab</th>
                <th className="px-4 py-3 w-12"></th>
              </tr>
            </thead>
            <tbody>
              {invites.map((i) => (
                <tr key={i.id} className="border-b border-soft-line2 last:border-0">
                  <td className="px-4 py-3 font-medium text-soft-ink">{i.email}</td>
                  <td className="px-4 py-3">
                    <Badge variant={ROLE_BADGE[i.role]}>{ROLE_LABEL[i.role]}</Badge>
                  </td>
                  <td className="px-4 py-3 text-xs text-soft-ink3">{i.created_by_label}</td>
                  <td className="px-4 py-3 text-xs text-soft-ink3">
                    {new Date(i.expires_at).toLocaleDateString("de-DE")}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => void revoke(i)}
                      aria-label={`Einladung an ${i.email} widerrufen`}
                      className="p-2 rounded-soft-xs hover:bg-soft-critSoft"
                    >
                      <X className="h-4 w-4 text-soft-ink3 hover:text-soft-crit" aria-hidden />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {inviteModal && (
        <ModalShell title="Einladung per Email" onClose={() => setInviteModal(false)}>
          <p className="text-xs text-soft-ink3 mb-4">
            Magic-Link wird verschickt (7 Tage gültig). Beim ersten Login wird die Mitgliedschaft
            automatisch hergestellt.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void sendInvite(e.currentTarget);
            }}
            className="space-y-4"
          >
            <FormRow label="Email">
              <input
                name="email"
                type="email"
                required
                className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm"
              />
            </FormRow>
            <FormRow label="Rolle">
              <select
                name="role"
                defaultValue="FINANCE"
                className="w-full border border-soft-line rounded-soft-xs px-3 py-2 text-sm bg-white"
              >
                <option value="ADMIN">Org-Admin</option>
                <option value="FINANCE">Finance</option>
                <option value="READONLY">Nur-Lese</option>
              </select>
            </FormRow>
            <ModalFooter onCancel={() => setInviteModal(false)} submitting={submitting} />
          </form>
        </ModalShell>
      )}
    </>
  );
}

// ─── Danger Zone ───
function DangerTab({
  orgId,
  orgName,
  counts,
  hasMembers,
}: {
  orgId: string;
  orgName: string;
  counts: { transactions: number; funding_measures: number; cost_centers: number };
  hasMembers: boolean;
}) {
  const router = useRouter();
  const toast = useToast();
  const [confirm, setConfirm] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const blockers: string[] = [];
  if (counts.transactions > 0) blockers.push(`${counts.transactions} Transaktion(en)`);
  if (counts.funding_measures > 0) blockers.push(`${counts.funding_measures} Fördermaßnahme(n)`);
  if (counts.cost_centers > 0) blockers.push(`${counts.cost_centers} Kostenstelle(n)`);
  if (hasMembers) blockers.push(`Mitgliedschaften`);

  async function del() {
    setSubmitting(true);
    try {
      const res = await fetch(`/api/admin/organisations/${orgId}`, { method: "DELETE" });
      const json = (await res.json()) as { error?: string };
      if (!res.ok) {
        toast.error(json.error ?? "Löschen fehlgeschlagen.");
        return;
      }
      toast.success("Organisation gelöscht.");
      router.push("/admin/organisations");
    } finally {
      setSubmitting(false);
      setConfirm(false);
    }
  }

  return (
    <div className="bg-white rounded-soft-sm border border-soft-crit/30 p-6 max-w-2xl">
      <h3 className="text-base font-semibold text-soft-crit mb-1">Organisation löschen</h3>
      <p className="text-sm text-soft-ink3 mb-4">
        Endgültiges Löschen ist nur möglich, wenn keine produktiven Daten anhängen.
      </p>
      {blockers.length > 0 ? (
        <div className="rounded-soft-xs border border-soft-warn/30 bg-soft-warnSoft p-3 text-sm text-soft-warn">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" aria-hidden />
            <div>
              <p className="font-medium">Löschen aktuell nicht möglich:</p>
              <ul className="list-disc list-inside mt-1 text-xs">
                {blockers.map((b, i) => (
                  <li key={i}>{b}</li>
                ))}
              </ul>
              <p className="mt-2 text-xs">
                Erst alle Daten und Mitgliedschaften entfernen, dann erneut versuchen.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <Button variant="danger" onClick={() => setConfirm(true)}>
          <Trash2 className="h-4 w-4 mr-1.5" aria-hidden /> Organisation endgültig löschen
        </Button>
      )}

      {confirm && (
        <ConfirmDialog
          open
          title={`„${orgName}" wirklich löschen?`}
          description="Diese Aktion kann nicht rückgängig gemacht werden."
          confirmLabel="Endgültig löschen"
          variant="danger"
          loading={submitting}
          onConfirm={() => void del()}
          onCancel={() => setConfirm(false)}
        />
      )}
    </div>
  );
}

// ─── Modal helpers ───
function FormRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-soft-ink2 mb-1">{label}</span>
      {children}
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
        {submitting ? "Speichere…" : <><Check className="h-4 w-4 mr-1.5" aria-hidden /> Speichern</>}
      </Button>
    </div>
  );
}
