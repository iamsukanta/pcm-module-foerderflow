import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Tailwind-aware className combiner (ported from the monolith lib/utils.ts). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** Formatiert Decimal-Werte als EUR-Betrag: 1234.56 → "1.234,56 €" */
export function formatEur(value: number | string): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  return new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
  }).format(num);
}
