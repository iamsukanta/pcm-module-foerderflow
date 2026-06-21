import { clsx } from "clsx";
import type { ReactNode } from "react";

/**
 * Einheitliches Width-System für alle Dashboard-Seiten.
 *
 * - `form`    → Wizards, Form-Detail-Edit (max-w-3xl)
 * - `content` → Detail-Seiten mit mehr Inhalt (max-w-5xl)
 * - `wide`    → Listen, Cockpits, Multi-Spalten-Übersichten (max-w-6xl)
 * - `full`    → Wide-Tables (Gehaltserfassung) (max-w-full)
 */
export type PageShellWidth = "form" | "content" | "wide" | "full";

const WIDTH_CLASSES: Record<PageShellWidth, string> = {
  form: "max-w-3xl mx-auto px-6 py-8",
  content: "max-w-5xl mx-auto px-6 py-8",
  wide: "max-w-6xl mx-auto px-6 py-8",
  full: "max-w-full px-6 py-8",
};

type Props = {
  width?: PageShellWidth;
  children: ReactNode;
  className?: string;
};

export function PageShell({ width = "wide", children, className }: Props) {
  return <div className={clsx(WIDTH_CLASSES[width], className)}>{children}</div>;
}
