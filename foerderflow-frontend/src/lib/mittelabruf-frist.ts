// Berechnet Frist-Status eines Abrufs
export type FristStatus = "OK" | "WARNING" | "KRITISCH" | "ABGELAUFEN";

export function getFristStatus(frist_bis: Date, status: string): FristStatus {
  // Abgeschlossene Status sind immer OK — Frist irrelevant
  if (status === "VERWENDET" || status === "ZURUECKGEZAHLT") return "OK";
  if (status === "ABGELAUFEN" || frist_bis < new Date()) return "ABGELAUFEN";
  const heute = new Date();
  const ms7 = 7 * 24 * 60 * 60 * 1000;
  const ms14 = 14 * 24 * 60 * 60 * 1000;
  if (frist_bis.getTime() <= heute.getTime() + ms7) return "KRITISCH";
  if (frist_bis.getTime() <= heute.getTime() + ms14) return "WARNING";
  return "OK";
}

export function getTageVerbleibend(frist_bis: Date): number {
  const heute = new Date();
  heute.setHours(0, 0, 0, 0);
  const frist = new Date(frist_bis);
  frist.setHours(0, 0, 0, 0);
  return Math.round((frist.getTime() - heute.getTime()) / (1000 * 60 * 60 * 24));
}
