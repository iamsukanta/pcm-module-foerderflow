import type { AmpelStatus } from "@/lib/ampel";

type Props = {
  status: AmpelStatus;
  gruende?: string[];
  size?: "sm" | "md";
};

const CONFIG: Record<
  AmpelStatus,
  { dot: string; text: string; label: string; bg: string; border: string }
> = {
  GRUEN: {
    dot: "bg-soft-ok",
    text: "text-soft-ok",
    label: "Im Zielkorridor",
    bg: "bg-soft-okSoft",
    border: "border-soft-ok/20",
  },
  GELB: {
    dot: "bg-soft-warn",
    text: "text-soft-warn",
    label: "Prüfen",
    bg: "bg-soft-warnSoft",
    border: "border-soft-warn/20",
  },
  ROT: {
    dot: "bg-soft-crit",
    text: "text-soft-crit",
    label: "Compliance-Risiko",
    bg: "bg-soft-critSoft",
    border: "border-soft-crit/20",
  },
};

/**
 * Ampel-Badge für Fördermassnahmen.
 * Zeigt farbigen Dot + Label, optional mit Tooltip bei hover (via title-Attribut).
 */
export function AmpelBadge({ status, gruende, size = "sm" }: Props) {
  const cfg = CONFIG[status];
  const title = gruende && gruende.length > 0 ? gruende.join(" · ") : undefined;

  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5
        ${cfg.bg} ${cfg.border} ${cfg.text}
        ${size === "md" ? "text-sm px-3 py-1" : "text-xs"}`}
    >
      <span className={`inline-block h-2 w-2 rounded-full shrink-0 ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}
