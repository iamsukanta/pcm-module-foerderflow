import { requireOrgSession } from "@/lib/session";
import { PageShell } from "@/components/ui/PageShell";
import { ProfilForm, type ProfilFormProps } from "@/components/forms/ProfilForm";

export const dynamic = "force-dynamic";

// Best-Effort-Split eines name in Vorname/Nachname. Nur als initialer Vorschlag
// beim ersten Profil-Edit, falls vorname/nachname noch leer sind.
function splitName(name: string | null): { vorname: string | null; nachname: string | null } {
  if (!name) return { vorname: null, nachname: null };
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return { vorname: parts[0]!, nachname: null };
  return { vorname: parts[0]!, nachname: parts.slice(1).join(" ") };
}

export default async function ProfilPage() {
  const { user } = await requireOrgSession();

  const split = splitName(user.name);
  const initialVorname = user.vorname ?? split.vorname ?? "";
  const initialNachname = user.nachname ?? split.nachname ?? "";

  const props: ProfilFormProps = {
    email: user.email,
    initialVorname,
    initialNachname,
    isSuperAdmin: user.is_super_admin,
    memberships: user.memberships.map((m) => ({
      org_id: m.org_id,
      org_name: m.org_name,
      role: m.role,
    })),
  };

  return (
    <PageShell width="form">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-soft-ink">Mein Profil</h1>
        <p className="mt-1 text-sm text-soft-ink3">
          Vorname und Nachname kannst du selbst pflegen. Email, Rollen und Super-Admin-Status werden
          vom jeweiligen Admin verwaltet.
        </p>
      </div>

      <ProfilForm {...props} />
    </PageShell>
  );
}
