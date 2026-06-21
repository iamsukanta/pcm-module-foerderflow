import { type ReactNode } from "react";
import { clsx } from "clsx";

type BadgeVariant = "default" | "success" | "warning" | "danger" | "muted";

const variantClasses: Record<BadgeVariant, string> = {
  default: "bg-soft-accentSoft text-soft-accent border-soft-accent/20",
  success: "bg-soft-okSoft text-soft-ok border-soft-ok/20",
  warning: "bg-soft-warnSoft text-soft-warn border-soft-warn/20",
  danger: "bg-soft-critSoft text-soft-crit border-soft-crit/20",
  muted: "bg-soft-line2 text-soft-ink3 border-soft-line",
};

type BadgeProps = {
  variant?: BadgeVariant;
  children: ReactNode;
  className?: string;
};

export function Badge({ variant = "default", children, className }: BadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 px-2.5 py-0.5 rounded-soft-xs text-xs font-medium border",
        variantClasses[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
