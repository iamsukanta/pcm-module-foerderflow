/**
 * Fristen (deadlines) — BFF wrapper around the backend GET /protected/fristen,
 * which already returns the consolidated, sorted FristItem[] shape verbatim.
 */
import { serverFetch } from "@/lib/serverApi";

export type FristTyp =
  | "MITTELABRUF"
  | "VERWENDUNGSNACHWEIS"
  | "MASSNAHME_LAUFZEIT"
  | "HAUSHALTSJAHR";

export type Dringlichkeit = "KRITISCH" | "WARNUNG" | "OK";

export type FristItem = {
  id: string;
  typ: FristTyp;
  bezeichnung: string;
  detail: string | null;
  frist: string; // ISO-Datum (YYYY-MM-DD)
  tage_verbleibend: number;
  dringlichkeit: Dringlichkeit;
  entity_link: string;
};

export async function loadFristen(daysAhead = 90): Promise<FristItem[]> {
  return serverFetch<FristItem[]>(`/protected/fristen?days_ahead=${daysAhead}`);
}
