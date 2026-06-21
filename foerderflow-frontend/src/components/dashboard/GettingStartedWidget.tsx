import Link from "next/link";
import { CheckCircle2, Circle } from "lucide-react";

type Step = {
  label: string;
  done: boolean;
  href: string;
};

export type OnboardingCounts = {
  fiscal_years: number;
  cost_centers: number;
  funding_measures: number;
  transactions: number;
};

export function GettingStartedWidget({ onboarding }: { onboarding: OnboardingCounts }) {
  const { fiscal_years, cost_centers, funding_measures, transactions } = onboarding;

  // Alle 4 erledigt → Widget nicht rendern
  if (fiscal_years > 0 && cost_centers > 0 && funding_measures > 0 && transactions > 0) {
    return null;
  }

  const steps: Step[] = [
    {
      label: "Haushaltsjahr anlegen",
      done: fiscal_years > 0,
      href: "/dashboard/haushaltsjahre/new",
    },
    {
      label: "Kostenstelle anlegen",
      done: cost_centers > 0,
      href: "/dashboard/kostenstellen/new",
    },
    {
      label: "Fördermassnahme anlegen",
      done: funding_measures > 0,
      href: "/dashboard/foerdermassnahmen/new",
    },
    {
      label: "Erste Transaktion importieren",
      done: transactions > 0,
      href: "/dashboard/transaktionen/import",
    },
  ];

  return (
    <div className="bg-soft-accentWash border border-soft-accent/20 rounded-soft-sm px-6 py-4 mb-6">
      <p className="font-semibold text-soft-accent">Erste Schritte</p>
      <p className="text-sm text-soft-ink2 mt-0.5 mb-3">Richte FoerderFlow in 4 Schritten ein:</p>
      <ul className="space-y-2">
        {steps.map((step) => (
          <li key={step.href} className="flex items-center gap-2">
            {step.done ? (
              <>
                <CheckCircle2 className="h-4 w-4 text-soft-ink3 shrink-0" />
                <span className="text-sm text-soft-ink3 line-through">{step.label}</span>
              </>
            ) : (
              <>
                <Circle className="h-4 w-4 text-soft-accent shrink-0" />
                <Link
                  href={step.href}
                  className="text-sm text-soft-accent font-medium hover:underline"
                >
                  {step.label}
                </Link>
              </>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
