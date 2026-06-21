import type { PrognoseStatus } from "@/lib/jahresendprognose";

type PrognoseData = {
  monatsrate: number;
  betrag_ist_gesamt: number;
  prognose_gesamt: number;
  prognose_prozent: number;
  days_remaining: number;
  status: PrognoseStatus;
  betrag_bewilligt: string;
};

type Props = {
  data: PrognoseData;
};

const STATUS_CONFIG: Record<PrognoseStatus, { label: string; badge: string; icon: string }> = {
  UNTERAUSSCHOEPFUNG: {
    label: "Unterausschöpfung erwartet (< 80%)",
    badge: "bg-soft-warnSoft border-soft-warn text-soft-warn",
    icon: "M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z",
  },
  OK: {
    label: "Auf Kurs",
    badge: "bg-soft-okSoft border-soft-ok text-soft-ok",
    icon: "M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
  },
  UEBERSCHREITUNG: {
    label: "Budgetüberschreitung erwartet",
    badge: "bg-soft-critSoft border-soft-crit text-soft-crit",
    icon: "M12 9v3.75m9.303-3.376c.866 1.5-.217 3.374-1.948 3.374H4.645c-1.73 0-2.813-1.874-1.948-3.374l5.306-9.5C8.82 2.63 11.18 2.63 12.082 3.75l5.221 5.374z",
  },
};

function formatEur(val: number): string {
  return new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(val);
}

/**
 * Jahresendprognose-Karte auf der Fördermassnahmen-Detailseite.
 * Server-gerendert, erhält vorberechnete Prognosedaten.
 */
export function PrognoseCard({ data }: Props) {
  const cfg = STATUS_CONFIG[data.status];

  return (
    <div className="rounded-soft-sm border border-soft-line bg-soft-surface p-5 shadow-soft">
      <h2 className="text-sm font-semibold text-soft-ink2 uppercase tracking-wide mb-4">
        Jahresendprognose
      </h2>

      {/* Status-Badge */}
      <div className={`flex items-center gap-2 rounded-soft-xs border px-3 py-2.5 mb-4 text-sm font-medium ${cfg.badge}`}>
        <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d={cfg.icon} />
        </svg>
        {cfg.label}
      </div>

      {/* Metriken */}
      <dl className="space-y-3 text-sm">
        <div className="flex justify-between">
          <dt className="text-soft-ink2">Ø Ausgaben letzte 90 Tage</dt>
          <dd className="font-semibold text-soft-ink numeric">
            {formatEur(data.monatsrate)}/Monat
          </dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-soft-ink2">Bisher ausgegeben</dt>
          <dd className="font-medium text-soft-ink numeric">
            {formatEur(data.betrag_ist_gesamt)}
          </dd>
        </div>
        <div className="flex justify-between border-t border-soft-line2 pt-3">
          <dt className="text-soft-ink font-medium">Prognose Jahresende</dt>
          <dd className={`font-bold numeric ${
            data.status === "UEBERSCHREITUNG" ? "text-soft-crit" :
            data.status === "UNTERAUSSCHOEPFUNG" ? "text-soft-warn" :
            "text-soft-ok"
          }`}>
            {formatEur(data.prognose_gesamt)}
            <span className="text-xs font-normal text-soft-ink3 ml-1 font-sans">
              ({data.prognose_prozent.toFixed(1)}%)
            </span>
          </dd>
        </div>
        <div className="flex justify-between text-xs text-soft-ink3">
          <dt>Genehmigtes Budget</dt>
          <dd className="numeric">{new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(parseFloat(data.betrag_bewilligt))}</dd>
        </div>
        {data.days_remaining > 0 && (
          <div className="flex justify-between text-xs text-soft-ink3">
            <dt>Verbleibende Tage</dt>
            <dd className="numeric">{data.days_remaining}</dd>
          </div>
        )}
        {data.days_remaining === 0 && (
          <div className="text-xs text-soft-ink3 italic">Laufzeit abgelaufen</div>
        )}
      </dl>
    </div>
  );
}
