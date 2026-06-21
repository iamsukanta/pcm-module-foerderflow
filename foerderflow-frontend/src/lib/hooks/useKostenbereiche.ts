"use client";

import { useEffect, useState } from "react";

export type KostenbereichItem = {
  id: string;
  code: string;
  bezeichnung: string;
  ist_personal: boolean;
  ist_gemeinkosten: boolean;
  parent_id: string | null;
  sort_order: number;
};

export type KostenbereichWithKinder = KostenbereichItem & {
  kinder: KostenbereichItem[];
};

type CacheEntry = {
  data: KostenbereichWithKinder[] | null;
  promise: Promise<KostenbereichWithKinder[]> | null;
};

// Process-globaler Cache: einmal pro Session laden, dann aus Memory bedienen.
const cache: CacheEntry = { data: null, promise: null };

async function fetchKostenbereiche(): Promise<KostenbereichWithKinder[]> {
  if (cache.data) return cache.data;
  if (cache.promise) return cache.promise;

  cache.promise = fetch("/api/protected/kostenbereiche")
    .then(async (res) => {
      if (!res.ok)
        throw new Error(`Kostenbereiche konnten nicht geladen werden (HTTP ${res.status})`);
      const json = (await res.json()) as { data: KostenbereichWithKinder[] };
      cache.data = json.data;
      return json.data;
    })
    .finally(() => {
      cache.promise = null;
    });

  return cache.promise;
}

/**
 * Lädt die systemweite Kostenbereich-Taxonomie. Cached process-weit.
 * Liefert { obergruppen, alle, loading, error }.
 */
export function useKostenbereiche() {
  const [data, setData] = useState<KostenbereichWithKinder[] | null>(cache.data);
  const [loading, setLoading] = useState(!cache.data);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (cache.data) {
      setData(cache.data);
      setLoading(false);
      return;
    }
    let mounted = true;
    fetchKostenbereiche()
      .then((rows) => {
        if (mounted) {
          setData(rows);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (mounted) {
          setError(String(e));
          setLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  // Obergruppen = parent_id == null; Unterkategorien hängen via `kinder`.
  const obergruppen = (data ?? []).filter((k) => !k.parent_id);

  // Flatliste aller Kostenbereiche (Obergruppen + Kinder), für Lookups
  const alle: KostenbereichItem[] = [];
  for (const og of data ?? []) {
    alle.push(og);
    for (const k of og.kinder) alle.push(k);
  }

  return { obergruppen, alle, loading, error };
}
