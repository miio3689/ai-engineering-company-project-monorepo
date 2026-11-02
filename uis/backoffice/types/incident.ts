export const INCIDENT_CATEGORIES = [
  { value: "equipment_failure", label: "Fallo de equipamiento" },
  { value: "supply_issue", label: "Problema de insumos" },
  { value: "customer_complaint", label: "Queja de cliente" },
  { value: "staff_issue", label: "Incidencia de personal" },
  { value: "facility_issue", label: "Problema de instalaciones" },
  { value: "pos_system", label: "Sistema de caja (TPV)" },
  { value: "delivery_issue", label: "Problema de domicilios" },
  { value: "other", label: "Otra" },
] as const;

export const INCIDENT_STATUSES = [
  { value: "open", label: "Abierta" },
  { value: "in_progress", label: "En progreso" },
  { value: "resolved", label: "Resuelta" },
  { value: "discarded", label: "Descartada" },
] as const;

export const INCIDENT_ORIGINS = [
  { value: "customer", label: "Cliente" },
  { value: "branch", label: "Sede" },
  { value: "internal", label: "Interno" },
] as const;

export const INCIDENT_BRANCHES = [
  { value: "central", label: "Central (Medellín / Miami)" },
  { value: "medellin_centro", label: "Medellín Centro" },
  { value: "medellin_laureles", label: "Medellín Laureles" },
  { value: "medellin_envigado", label: "Medellín Envigado" },
  { value: "medellin_bello", label: "Medellín Bello" },
  { value: "medellin_itagui", label: "Medellín Itagüí" },
  { value: "bogota_chapinero", label: "Bogotá Chapinero" },
  { value: "bogota_usaquen", label: "Bogotá Usaquén" },
  { value: "cali_granada", label: "Cali Granada" },
  { value: "barranquilla_norte", label: "Barranquilla Norte" },
  { value: "miami_doral", label: "Miami Doral" },
  { value: "miami_hialeah", label: "Miami Hialeah" },
  { value: "miami_kendall", label: "Miami Kendall" },
  { value: "orlando_international", label: "Orlando International Drive" },
  { value: "fort_lauderdale", label: "Fort Lauderdale" },
] as const;

export type IncidentCategory = (typeof INCIDENT_CATEGORIES)[number]["value"];
export type IncidentStatus = (typeof INCIDENT_STATUSES)[number]["value"];
export type IncidentOrigin = (typeof INCIDENT_ORIGINS)[number]["value"];
export type IncidentBranch = (typeof INCIDENT_BRANCHES)[number]["value"];

export const INCIDENT_STATUS_TRANSITIONS: Record<
  IncidentStatus,
  readonly IncidentStatus[]
> = {
  open: ["in_progress", "discarded"],
  in_progress: ["resolved", "discarded"],
  resolved: [],
  discarded: [],
};

export function getIncidentOptionLabel<
  T extends readonly { value: string; label: string }[],
>(options: T, value: T[number]["value"]): string {
  return options.find((option) => option.value === value)?.label ?? "Valor no disponible";
}

export interface Incident {
  id: number;
  title: string;
  description: string;
  category: IncidentCategory;
  status: IncidentStatus;
  origin: IncidentOrigin;
  branch: IncidentBranch;
  created_at: string;
  updated_at: string;
}

export type IncidentCreateInput = Pick<
  Incident,
  "title" | "description" | "category" | "status" | "origin" | "branch"
>;

export type IncidentFormField = keyof IncidentCreateInput;
export type IncidentFieldErrors = Partial<Record<IncidentFormField, string>>;

export interface IncidentFilters {
  status?: IncidentStatus;
  origin?: IncidentOrigin;
  branch?: IncidentBranch;
}

export interface IncidentSummary {
  total: number;
  by_status: Record<IncidentStatus, number>;
  by_category: Record<IncidentCategory, number>;
  by_origin: Record<IncidentOrigin, number>;
  by_branch: Record<IncidentBranch, number>;
}
