/**
 * Helpers for the /protected/kostenstellen list (top-level rows with nested
 * children). Several forms need a *flat* list of active cost centers.
 */
import { serverFetch } from "@/lib/serverApi";
import type { KostenstelleWithChildren } from "@/types/kostenstellen";

export type CostCenterOption = { id: string; code: string; name: string; typ: string };

/** Flat, active-only cost centers (parents + children), sorted by code. */
export async function loadActiveCostCenters(): Promise<CostCenterOption[]> {
  const tree = await serverFetch<KostenstelleWithChildren[]>("/protected/kostenstellen");
  const flat: CostCenterOption[] = [];
  for (const k of tree) {
    if (k.ist_aktiv) flat.push({ id: k.id, code: k.code, name: k.name, typ: k.typ });
    for (const c of k.children ?? []) {
      if (c.ist_aktiv) flat.push({ id: c.id, code: c.code, name: c.name, typ: c.typ });
    }
  }
  flat.sort((a, b) => a.code.localeCompare(b.code));
  return flat;
}

export type CostCenterFormOption = { id: string; name: string; code: string; ist_aktiv: boolean };

/** Active cost centers shaped for the measure/wizard forms (sorted by name). */
export async function loadActiveCostCentersForForms(): Promise<CostCenterFormOption[]> {
  const flat = await loadActiveCostCenters();
  return flat
    .map((c) => ({ id: c.id, name: c.name, code: c.code, ist_aktiv: true }))
    .sort((a, b) => a.name.localeCompare(b.name));
}
