// Shared German-locale formatting for Module PCM screens.
// Per Tariff Registry DevGuide §10: amounts as €3.200,00, dates as DD.MM.YYYY,
// salary groups in natural (not lexicographic) order.

const EUR = new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" });
const EUR0 = new Intl.NumberFormat("de-DE", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

/** €3.200,00 */
export const eur = (v: string | number | null | undefined): string =>
  v === null || v === undefined || v === "" ? "—" : EUR.format(Number(v));

/** €3.200 (no cents) — for dense grids/cards. */
export const eur0 = (v: string | number | null | undefined): string =>
  v === null || v === undefined || v === "" ? "—" : EUR0.format(Number(v));

/** ISO (YYYY-MM-DD[...]) → DD.MM.YYYY. "offen" sentinel for null. */
export const deDate = (iso: string | null | undefined, open = "offen"): string => {
  if (!iso) return open;
  const [y, m, d] = iso.split("T")[0].split("-");
  return `${d}.${m}.${y}`;
};

/** Natural sort key for a salary group: E2 < E10, S6 < S6a. */
export function naturalGroupKey(group: string): [string, number, string] {
  const match = /^([^\d]*)(\d*)(.*)$/.exec(group) ?? ["", group, "", ""];
  return [match[1], match[2] ? parseInt(match[2], 10) : 0, match[3]];
}

export function compareGroups(a: string, b: string): number {
  const [pa, na, sa] = naturalGroupKey(a);
  const [pb, nb, sb] = naturalGroupKey(b);
  return pa.localeCompare(pb) || na - nb || sa.localeCompare(sb);
}
