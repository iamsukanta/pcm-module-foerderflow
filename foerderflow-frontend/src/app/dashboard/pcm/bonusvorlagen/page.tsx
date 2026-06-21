import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";
import type { BonusTemplate } from "@/types/pcm";
import { BonusTemplatesClient } from "./BonusTemplatesClient";

export const metadata = {
  title: "Bonusvorlagen — FoerderFlow",
};

export default async function BonusvorlagenPage() {
  await requireOrgSession();
  const templates = await serverFetch<BonusTemplate[]>("/protected/pcm/bonus-templates");

  return (
    <PageShell width="wide">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-soft-ink">Bonusvorlagen</h1>
        <p className="text-sm text-soft-ink3 mt-1">
          Organisationsweite Zulagen- und Bonusregeln (z.&nbsp;B. Münchenzulage,
          LOB), die bei jeder Abrechnung automatisch auf passende Mitarbeitende
          angewendet werden. Ein individueller Eintrag derselben Art hat Vorrang
          vor der Vorlage.
        </p>
      </div>
      <BonusTemplatesClient templates={templates} />
    </PageShell>
  );
}
