// Pure functions — no DB access. Safe for client components.

export type GehaltsBerechnung = {
  actual_salary: number;
  an_brutto: number;
  ag_brutto: number;
  komponenten_vor_multiplikator: number;
  komponenten_nach_multiplikator: number;
};

export function berechneGehalt(params: {
  base_salary: number;
  assigned_hours: number;
  standard_hours: number;
  ag_faktor: number;
  components: Array<{ betrag: number; nach_multiplikator: boolean }>;
}): GehaltsBerechnung {
  const { base_salary, assigned_hours, standard_hours, ag_faktor, components } = params;
  const actual_salary = base_salary * (assigned_hours / standard_hours);
  const komponenten_vor_multiplikator = components
    .filter((c) => !c.nach_multiplikator)
    .reduce((sum, c) => sum + c.betrag, 0);
  const komponenten_nach_multiplikator = components
    .filter((c) => c.nach_multiplikator)
    .reduce((sum, c) => sum + c.betrag, 0);
  const an_brutto = actual_salary + komponenten_vor_multiplikator;
  const ag_brutto = an_brutto * ag_faktor + komponenten_nach_multiplikator;
  return {
    actual_salary,
    an_brutto,
    ag_brutto,
    komponenten_vor_multiplikator,
    komponenten_nach_multiplikator,
  };
}
