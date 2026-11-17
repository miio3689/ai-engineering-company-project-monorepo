import { getLowStockThreshold } from "@/lib/inventory-stock";
import { InventoryServiceError } from "@/services/inventory";
import { track } from "@/services/telemetry";
import type {
  InboundOrderInput,
  Ingredient,
  IngredientCountry,
  InventoryOrder,
  OutboundOrderInput,
} from "@/types/inventory";

export type WasteReason = "expired" | "kitchen_error" | "theft_suspected";
export type InventoryForm = "inbound_order" | "outbound_order" | "product_create";

const CURRENCY_BY_COUNTRY: Record<IngredientCountry, "COP" | "USD"> = { CO: "COP", US: "USD" };
const VALIDATION_THROTTLE_MS = 10_000;
const lastValidationEvent = new Map<string, number>();

// Brecha B3 del plan: no existe un mapa local→país. Hasta que exista, el país
// del evento es el del producto; la moneda se deriva de ese país.
function eventBase(ingredient: Ingredient, locationId: number, quantity: number) {
  return {
    location_id: locationId,
    country: ingredient.country,
    product_id: ingredient.id,
    product_category: ingredient.category,
    quantity,
    unit: ingredient.unit,
    currency: CURRENCY_BY_COUNTRY[ingredient.country],
  };
}

export function trackInboundCreated(
  ingredient: Ingredient,
  input: InboundOrderInput,
  order: InventoryOrder,
): void {
  track("inbound_order_created", {
    ...eventBase(ingredient, input.location_id, input.quantity),
    inbound_order_id: order.id,
    supplier_name: input.supplier_name,
    unit_cost: input.unit_cost,
  });

  const variance = order.type === "inbound" ? order.price_variance : null;
  if (variance) {
    track("ingredient_price_variance_detected", {
      ...eventBase(ingredient, input.location_id, input.quantity),
      inbound_order_id: order.id,
      supplier_name: input.supplier_name,
      unit_cost: input.unit_cost,
      baseline_unit_cost: variance.baseline_unit_cost,
      variance_pct: variance.variance_pct,
      threshold_pct: variance.threshold_pct,
    });
  }
}

/**
 * Una salida de consumo emite outbound_order_created y una de merma emite
 * stock_waste_registered (excluyentes, ver plan sección 10). Si el stock del
 * local cruza hacia abajo el mínimo, emite además stock_threshold_triggered.
 */
export function trackOutboundCreated(
  ingredient: Ingredient,
  input: OutboundOrderInput,
  order: InventoryOrder,
  wasteReason: WasteReason | null,
  stockBefore: number | null,
): void {
  const base = eventBase(ingredient, input.location_id, input.quantity);
  if (input.reason === "waste") {
    if (wasteReason) {
      track("stock_waste_registered", { ...base, outbound_order_id: order.id, reason: wasteReason });
    }
  } else {
    track("outbound_order_created", { ...base, outbound_order_id: order.id });
  }

  if (stockBefore === null) return;
  const threshold = getLowStockThreshold(ingredient.unit);
  const stockAfter = Math.round((stockBefore - input.quantity) * 1000) / 1000;
  if (stockBefore >= threshold && stockAfter < threshold) {
    track("stock_threshold_triggered", {
      ...base,
      quantity: Math.max(stockAfter, 0),
      threshold_quantity: threshold,
      triggering_outbound_order_id: order.id,
    });
  }
}

export function trackOutboundRejected(
  ingredient: Ingredient,
  input: OutboundOrderInput,
  error: InventoryServiceError,
  availableQuantity: number | null,
): void {
  const reason =
    error.status === 400 ? "insufficient_stock"
    : error.status === 404 ? "ingredient_not_found"
    : error.status === 422 ? "validation_error"
    : error.status >= 500 ? "database_error"
    : null;
  if (!reason) return;
  const base = eventBase(ingredient, input.location_id, input.quantity);
  track("outbound_order_rejected", {
    ...base,
    rejection_reason: reason,
    available_quantity: availableQuantity ?? undefined,
  });
}

/** Intento de fijar el stock a mano: la API lo rechaza siempre (403). */
export function trackDirectStockEditRejected(
  ingredient: Ingredient,
  locationId: number,
  quantity: number,
): void {
  track("direct_stock_edit_rejected", {
    ...eventBase(ingredient, locationId, quantity),
    attempted_operation: "set_stock",
    rejection_reason: "direct_edit_not_allowed",
  });
}

const FIELD_NAMES: Record<string, string> = {
  ingredientId: "ingredient_id",
  quantity: "quantity",
  supplierName: "supplier_name",
  unitCost: "unit_cost",
  locationId: "location_id",
  reason: "reason",
  wasteReason: "waste_reason",
};

/** Un evento por formulario y campo cada 10 s como máximo; nunca incluye el valor escrito. */
export function trackInventoryValidationFailed(
  form: InventoryForm,
  errors: Record<string, string | undefined>,
  locationId?: number,
): void {
  const now = Date.now();
  for (const [field, message] of Object.entries(errors)) {
    if (!message) continue;
    const key = `${form}:${field}`;
    const last = lastValidationEvent.get(key);
    if (last !== undefined && now - last < VALIDATION_THROTTLE_MS) continue;
    lastValidationEvent.set(key, now);
    track("inventory_form_validation_failed", {
      form,
      field_name: FIELD_NAMES[field] ?? field.toLowerCase(),
      error_code: /mayor que cero/.test(message) ? "out_of_range" : "required",
      location_id: locationId,
    });
  }
}
