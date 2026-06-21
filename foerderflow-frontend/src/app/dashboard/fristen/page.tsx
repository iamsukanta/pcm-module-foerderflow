import Link from "next/link";
import { Banknote, FileCheck, Calendar, BookOpen, CheckCircle2 } from "lucide-react";

import { requireOrgSession } from "@/lib/session";
import { loadFristen, type FristItem, type FristTyp } from "@/lib/fristen";
import { PageShell } from "@/components/ui/PageShell";
import { Badge } from "@/components/ui/Badge";

const TYP_ICON: Record<FristTyp, typeof Banknote> = {
  MITTELABRUF: Banknote,
  VERWENDUNGSNACHWEIS: FileCheck,
  MASSNAHME_LAUFZEIT: Calendar,
  HAUSHALTSJAHR: BookOpen,
};

const TYP_LABEL: Record<FristTyp, string> = {
  MITTELABRUF: "Mittelabruf",
  VERWENDUNGSNACHWEIS: "Nachweis",
  MASSNAHME_LAUFZEIT: "Massnahme",
  HAUSHALTSJAHR: "Haushaltsjahr",
};

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${iso}T00:00:00Z`));
}

function tageLabel(tage: number): string {
  if (tage < 0) return `${Math.abs(tage)} Tage überfällig`;
  if (tage === 0) return "heute fällig";
  if (tage === 1) return "noch 1 Tag";
  return `noch ${tage} Tage`;
}

function FristCard({ frist }: { frist: FristItem }) {
  const Icon = TYP_ICON[frist.typ];
  const dringend = frist.dringlichkeit;
  const colorClass =
    dringend === "KRITISCH"
      ? "text-soft-crit bg-soft-critSoft"
      : dringend === "WARNUNG"
        ? "text-soft-warn bg-soft-warnSoft"
        : "text-soft-ok bg-soft-okSoft";

  return (
    <Link
      href={frist.entity_link}
      className="flex items-start gap-3 rounded-soft border border-soft-line bg-white px-4 py-3 hover:border-soft-accent/40 hover:shadow-soft transition-all group"
    >
      <div className={`p-2 rounded-soft-xs shrink-0 ${colorClass}`}>
        <Icon className="h-4 w-4" aria-hidden="true" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap mb-0.5">
          <span className="text-[10px] font-medium text-soft-ink4 uppercase tracking-wide">
            {TYP_LABEL[frist.typ]}
          </span>
        </div>
        <p className="text-sm font-medium text-soft-ink group-hover:text-soft-accent transition-colors truncate">
          {frist.bezeichnung}
        </p>
        {frist.detail && <p className="text-xs text-soft-ink3 truncate mt-0.5">{frist.detail}</p>}
      </div>
      <div className="text-right shrink-0">
        <div className="numeric text-sm font-semibold text-soft-ink">{formatDate(frist.frist)}</div>
        <div
          className={`text-xs mt-0.5 ${
            dringend === "KRITISCH"
              ? "text-soft-crit"
              : dringend === "WARNUNG"
                ? "text-soft-warn"
                : "text-soft-ink3"
          }`}
        >
          {tageLabel(frist.tage_verbleibend)}
        </div>
      </div>
    </Link>
  );
}

function GroupSection({ title, fristen }: { title: string; fristen: FristItem[] }) {
  return (
    <section>
      <div className="flex items-baseline gap-2 mb-3">
        <h2 className="text-xs font-semibold text-soft-ink3 uppercase tracking-widest">{title}</h2>
        <span className="numeric text-xs text-soft-ink4">({fristen.length})</span>
      </div>
      {fristen.length === 0 ? (
        <p className="text-sm text-soft-ink4 italic px-1">Keine Einträge.</p>
      ) : (
        <div className="space-y-2">
          {fristen.map((f) => (
            <FristCard key={`${f.typ}-${f.id}`} frist={f} />
          ))}
        </div>
      )}
    </section>
  );
}

export default async function FristenDashboardPage() {
  await requireOrgSession();
  const fristen = await loadFristen(90);

  const dieseWoche = fristen.filter((f) => f.tage_verbleibend <= 7);
  const naechste30 = fristen.filter((f) => f.tage_verbleibend > 7 && f.tage_verbleibend <= 30);
  const naechste90 = fristen.filter((f) => f.tage_verbleibend > 30 && f.tage_verbleibend <= 90);

  const kritisch = fristen.filter((f) => f.dringlichkeit === "KRITISCH").length;
  const warnung = fristen.filter((f) => f.dringlichkeit === "WARNUNG").length;

  return (
    <PageShell width="content">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-soft-ink">Fristen &amp; Termine</h1>
        <p className="text-sm text-soft-ink2 mt-1">
          Konsolidierte Sicht auf alle relevanten Stichtage der nächsten 90 Tage — aus
          Mittelabrufen, Verwendungsnachweisen, Massnahmen-Laufzeiten und Haushaltsjahren.
        </p>
      </div>

      {/* Übersichts-Badges */}
      <div className="flex items-center gap-2 mb-6 flex-wrap">
        {kritisch > 0 ? (
          <Badge variant="danger">
            <span className="numeric mr-1">{kritisch}</span> kritisch (≤7 Tage)
          </Badge>
        ) : (
          <Badge variant="success">Keine kritischen Fristen</Badge>
        )}
        {warnung > 0 && (
          <Badge variant="warning">
            <span className="numeric mr-1">{warnung}</span> Warnung (8–14 Tage)
          </Badge>
        )}
        <Badge variant="muted">
          <span className="numeric mr-1">{fristen.length}</span> insgesamt
        </Badge>
      </div>

      {fristen.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center rounded-soft border border-soft-line bg-white">
          <div className="rounded-full bg-soft-okSoft p-4 mb-4">
            <CheckCircle2 className="h-8 w-8 text-soft-ok" aria-hidden="true" />
          </div>
          <h2 className="text-lg font-semibold text-soft-ink mb-1">Alles im grünen Bereich</h2>
          <p className="text-sm text-soft-ink2 max-w-sm">
            In den nächsten 90 Tagen stehen keine offenen Fristen an. Sobald ein Mittelabruf,
            Nachweis oder Laufzeitende näherrückt, erscheint es hier.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <GroupSection title="Diese Woche" fristen={dieseWoche} />
          <GroupSection title="Nächste 30 Tage" fristen={naechste30} />
          <GroupSection title="Nächste 90 Tage" fristen={naechste90} />
        </div>
      )}
    </PageShell>
  );
}
