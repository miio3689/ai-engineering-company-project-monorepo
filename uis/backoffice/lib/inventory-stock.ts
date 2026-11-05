import type { IngredientUnit } from "@/types/inventory";

export type StockLevel = "low" | "medium" | "healthy";

export const STOCK_LEVEL_PRESENTATION: Record<
  StockLevel,
  { label: string; symbol: string; className: string }
> = {
  low: {
    label: "Stock bajo",
    symbol: "!",
    className: "bg-red-100 text-red-900",
  },
  medium: {
    label: "Stock medio",
    symbol: "~",
    className: "bg-amber-100 text-amber-950",
  },
  healthy: {
    label: "Stock saludable",
    symbol: "+",
    className: "bg-green-100 text-green-950",
  },
};

// kg/litro: bajo < 20, medio < 50 y saludable >= 50; unidad: bajo < 50, medio < 150 y saludable >= 150.
export function getStockLevel(
  unit: IngredientUnit,
  currentStock: number,
): StockLevel {
  const lowThreshold = unit === "unidad" ? 50 : 20;
  const healthyThreshold = unit === "unidad" ? 150 : 50;

  if (currentStock < lowThreshold) return "low";
  if (currentStock < healthyThreshold) return "medium";
  return "healthy";
}