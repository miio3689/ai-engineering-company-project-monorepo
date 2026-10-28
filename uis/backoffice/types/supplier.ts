export enum SupplierStatus {
  Active = "active",
  Suspended = "suspended",
}

export const SUPPLIER_CATEGORIES = [
  "carne",
  "verduras_y_hortalizas",
  "salsas_y_condimentos",
  "bebidas",
  "packaging",
  "productos_limpieza",
  "lacteos",
  "carbon_y_combustible",
] as const;

export const SUPPLIER_COUNTRIES = ["Colombia", "USA"] as const;

export type SupplierCategory = (typeof SUPPLIER_CATEGORIES)[number];
export type SupplierCountry = (typeof SUPPLIER_COUNTRIES)[number];

export const SUPPLIER_CATEGORY_LABELS: Record<SupplierCategory, string> = {
  carne: "Carne",
  verduras_y_hortalizas: "Verduras y hortalizas",
  salsas_y_condimentos: "Salsas y condimentos",
  bebidas: "Bebidas",
  packaging: "Packaging",
  productos_limpieza: "Productos de limpieza",
  lacteos: "Lácteos",
  carbon_y_combustible: "Carbón y combustible",
};

export interface Supplier {
  id: number;
  name: string;
  country: SupplierCountry;
  categories: SupplierCategory[];
  rate_per_unit: number;
  currency: "COP" | "USD";
  updated_at: string;
  status: SupplierStatus;
  contact_email: string | null;
  notes: string | null;
}

export interface SupplierFilters {
  country?: SupplierCountry;
  category?: SupplierCategory;
}
