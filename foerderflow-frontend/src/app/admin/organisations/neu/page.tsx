import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { requireSuperAdmin } from "@/lib/session";
import { PageShell } from "@/components/ui/PageShell";
import { OnboardingWizard } from "@/components/admin/OnboardingWizard";

export const dynamic = "force-dynamic";

export default async function AdminOrganisationNeuPage() {
  await requireSuperAdmin();

  return (
    <PageShell width="form">
      <div className="mb-6">
        <Link
          href="/admin/organisations"
          className="inline-flex items-center gap-1.5 text-sm text-soft-ink3 hover:text-soft-accent mb-4"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden /> Alle Organisationen
        </Link>
        <h1 className="text-2xl font-bold text-soft-ink">Neue Organisation anlegen</h1>
        <p className="mt-1 text-sm text-soft-ink3">
          3-Schritt-Wizard: Stammdaten → Haushaltsjahr (optional) → Erste Mitglieder einladen.
        </p>
      </div>

      <OnboardingWizard />
    </PageShell>
  );
}
