export type KostenstelleWithChildren = {
  id: string;
  org_id: string;
  name: string;
  code: string;
  typ: "PROJECT" | "OVERHEAD";
  ist_aktiv: boolean;
  parent_id: string | null;
  parent?: { id: string; name: string; code: string } | null;
  children?: KostenstelleWithChildren[];
  _count?: { funding_measure_cost_centers: number };
};

export type KostenstelleCreateInput = {
  name: string;
  code: string;
  typ: "PROJECT" | "OVERHEAD";
  parent_id?: string | null;
};

export type KostenstelleUpdateInput = Partial<KostenstelleCreateInput>;

export type ApiError = {
  error: string;
  code: string;
};

export type ApiSuccess<T> = {
  data: T;
  message?: string;
};
