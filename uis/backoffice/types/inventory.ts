export type IngredientUnit = "kg" | "litro" | "unidad";
export type IngredientCategory =
  | "meat"
  | "produce"
  | "sauce"
  | "beverage"
  | "packaging"
  | "cleaning";
export type IngredientCountry = "CO" | "US";
export type ExitReason = "consumption" | "waste";

export interface Ingredient {
  id: number;
  name: string;
  sku: string;
  unit: IngredientUnit;
  category: IngredientCategory;
  country: IngredientCountry;
  current_stock: number;
}

interface InventoryOrderBase {
  id: number;
  ingredient_id: number;
  name: string;
  sku: string;
  quantity: number;
  location_id: number;
  created_at: string;
  user_uuid: string;
}

export interface InboundOrder extends InventoryOrderBase {
  type: "inbound";
  supplier_name: string;
}

export interface OutboundOrder extends InventoryOrderBase {
  type: "outbound";
  reason: ExitReason;
}

export type InventoryOrder = InboundOrder | OutboundOrder;

export interface InboundOrderInput {
  ingredient_id: number;
  quantity: number;
  supplier_name: string;
  location_id: number;
}

export interface OutboundOrderInput {
  ingredient_id: number;
  quantity: number;
  reason: ExitReason;
  location_id: number;
}

export const INGREDIENT_UNIT_LABELS: Record<IngredientUnit, string> = {
  kg: "Kilogramos",
  litro: "Litros",
  unidad: "Unidades",
};

export const INGREDIENT_CATEGORY_LABELS: Record<IngredientCategory, string> = {
  meat: "Carnes",
  produce: "Frutas y verduras",
  sauce: "Salsas",
  beverage: "Bebidas",
  packaging: "Empaques",
  cleaning: "Productos de limpieza",
};

export const INGREDIENT_COUNTRY_LABELS: Record<IngredientCountry, string> = {
  CO: "Colombia",
  US: "Estados Unidos",
};

export const EXIT_REASON_LABELS: Record<ExitReason, string> = {
  consumption: "Consumo",
  waste: "Merma",
};

export const LOCATION_IDS = [
  1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14,
] as const;