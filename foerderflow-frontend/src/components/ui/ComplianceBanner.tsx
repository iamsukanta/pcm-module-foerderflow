"use client";

import { useState } from "react";
import { AlertTriangle, AlertOctagon, X } from "lucide-react";

export type ComplianceBannerVariant = "HINWEIS" | "WARNUNG";

type Props = {
  variant: ComplianceBannerVariant;
  title: string;
  message: string;
  /** Stable hash (z.B. Status + Beträge) — wird als entitaet_id für Dismiss-Audit gespeichert. */
  alertHash: string;
  /** Optional: Action-Button (z.B. „Mittelabruf öffnen"). */
  actionLabel?: string;
  actionHref?: string;
  /**
   * Wenn gesetzt, ist der Banner schon einmal vom User dismissed worden
   * (für genau diesen alertHash). Render dann nichts.
   */
  initiallyDismissed?: boolean;
  /**
   * Endpoint zum Persistieren des Dismiss. Wird als POST mit
   * { alertHash } gerufen — typische Implementation schreibt AuditLog
   * mit aktion='COMPLIANCE_ALERT_DISMISSED'.
   */
  dismissEndpoint?: string;
};

const VARIANTS: Record<
  ComplianceBannerVariant,
  { bg: string; border: string; text: string; icon: typeof AlertTriangle }
> = {
  HINWEIS: {
    bg: "bg-soft-warnSoft",
    border: "border-soft-warn/30",
    text: "text-soft-warn",
    icon: AlertTriangle,
  },
  WARNUNG: {
    // Orange/intensiver — wir nutzen crit-Tokens als „dringend"
    bg: "bg-soft-critSoft",
    border: "border-soft-crit/30",
    text: "text-soft-crit",
    icon: AlertOctagon,
  },
};

/**
 * Persistenter Compliance-Banner für Fehlbedarfs-Maßnahmen.
 * Variants: HINWEIS (gelb) und WARNUNG (orange/rot).
 *
 * Dismiss-Pattern: alertHash + dismissEndpoint. Beim Dismiss wird der
 * Banner hidden (Client-State) UND ein POST an dismissEndpoint geschickt,
 * der server-side den Dismissed-Marker schreibt (AuditLog). Beim nächsten
 * Page-Load wird `initiallyDismissed=true` gerendert wenn der Marker existiert.
 *
 * Wenn sich der Status weiterentwickelt (anderer alertHash), kommt der
 * Banner automatisch wieder.
 */
export function ComplianceBanner({
  variant,
  title,
  message,
  alertHash,
  actionLabel,
  actionHref,
  initiallyDismissed = false,
  dismissEndpoint,
}: Props) {
  const [dismissed, setDismissed] = useState(initiallyDismissed);
  const cfg = VARIANTS[variant];
  const Icon = cfg.icon;

  if (dismissed) return null;

  async function handleDismiss() {
    setDismissed(true);
    if (dismissEndpoint) {
      try {
        await fetch(dismissEndpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ alertHash }),
        });
      } catch (err) {
        console.error("[ComplianceBanner] Dismiss-Persistierung fehlgeschlagen:", err);
      }
    }
  }

  return (
    <div
      role="alert"
      className={`rounded-soft-sm border px-4 py-3 ${cfg.bg} ${cfg.border} mb-4`}
    >
      <div className="flex items-start gap-3">
        <Icon className={`h-5 w-5 shrink-0 mt-0.5 ${cfg.text}`} aria-hidden />
        <div className="flex-1 min-w-0">
          <h3 className={`text-sm font-semibold ${cfg.text}`}>{title}</h3>
          <p className="text-sm text-soft-ink2 mt-1 whitespace-pre-line">{message}</p>
          {actionLabel && actionHref && (
            <div className="mt-2">
              <a
                href={actionHref}
                className={`text-sm font-medium underline ${cfg.text} hover:no-underline`}
              >
                {actionLabel}
              </a>
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={handleDismiss}
          aria-label="Hinweis schließen"
          className="text-soft-ink4 hover:text-soft-ink2 transition-colors p-1 -m-1"
        >
          <X className="h-4 w-4" aria-hidden />
        </button>
      </div>
    </div>
  );
}
