import { apiRequest } from "@/services/api-client";
import {
  API_UNAVAILABLE_MESSAGE,
  INVALID_API_RESPONSE_MESSAGE,
  readJsonResponse,
} from "@/services/api-errors";
import type {
  ExitReason,
  Ingredient,
  IngredientCategory,
  IngredientCountry,
  IngredientUnit,
  InboundOrderInput,
  InventoryOrder,
  OutboundOrderInput,
} from "@/types/inventory";

const INGREDIENT_UNITS: readonly IngredientUnit[] = ["kg", "litro", "unidad"];
const INGREDIENT_CATEGORIES: readonly IngredientCategory[] = [
  "meat",
  "produce",
  "sauce",
  "beverage",
  "packaging",
  "cleaning",
];
const INGREDIENT_COUNTRIES: readonly IngredientCountry[] = ["CO", "US"];
const EXIT_REASONS: readonly ExitReason[] = ["consumption", "waste"];

export class InventoryServiceError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = "InventoryServiceError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isIngredient(value: unknown): value is Ingredient {
  return isRecord(value)
    && typeof value.id === "number"
    && Number.isInteger(value.id)
    && typeof value.name === "string"
    && typeof value.sku === "string"
    && typeof value.unit === "string"
    && INGREDIENT_UNITS.includes(value.unit as IngredientUnit)
    && typeof value.category === "string"
    && INGREDIENT_CATEGORIES.includes(value.category as IngredientCategory)
    && typeof value.country === "string"
    && INGREDIENT_COUNTRIES.includes(value.country as IngredientCountry)
    && typeof value.current_stock === "number"
    && Number.isFinite(value.current_stock);
}

function isIngredientList(value: unknown): value is Ingredient[] {
  return Array.isArray(value) && value.every(isIngredient);
}

function isInventoryOrder(value: unknown): value is InventoryOrder {
  if (!isRecord(value)
    || typeof value.id !== "number"
    || !Number.isInteger(value.id)
    || typeof value.ingredient_id !== "number"
    || !Number.isInteger(value.ingredient_id)
    || typeof value.name !== "string"
    || typeof value.sku !== "string"
    || typeof value.quantity !== "number"
    || !Number.isFinite(value.quantity)
    || typeof value.location_id !== "number"
    || !Number.isInteger(value.location_id)
    || typeof value.created_at !== "string"
    || Number.isNaN(Date.parse(value.created_at))
    || typeof value.user_uuid !== "string") {
    return false;
  }

  if (value.type === "inbound") return typeof value.supplier_name === "string";
  return value.type === "outbound"
    && typeof value.reason === "string"
    && EXIT_REASONS.includes(value.reason as ExitReason);
}

function isInventoryOrderList(value: unknown): value is InventoryOrder[] {
  return Array.isArray(value) && value.every(isInventoryOrder);
}

function formatHttpError(payload: unknown): string {
  if (!isRecord(payload) || !("detail" in payload)) return API_UNAVAILABLE_MESSAGE;

  if (typeof payload.detail === "string") return payload.detail;

  if (Array.isArray(payload.detail)) {
    const messages = payload.detail.flatMap((issue: unknown) =>
      isRecord(issue) && typeof issue.msg === "string" && issue.msg.trim()
        ? [issue.msg.trim()]
        : []
    );
    return messages.length ? messages.join(" ") : API_UNAVAILABLE_MESSAGE;
  }

  return API_UNAVAILABLE_MESSAGE;
}

async function throwHttpError(
  response: Response,
  signal?: AbortSignal,
): Promise<never> {
  let payload: unknown;
  try {
    payload = await readResponseJson<unknown>(response, signal);
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new InventoryServiceError(API_UNAVAILABLE_MESSAGE, response.status);
  }

  throw new InventoryServiceError(formatHttpError(payload), response.status);
}

async function readResponseJson<T>(
  response: Response,
  signal?: AbortSignal,
): Promise<T> {
  try {
    return await readJsonResponse<T>(response);
  } catch (error) {
    if (signal?.aborted) {
      throw new DOMException("La operación fue cancelada.", "AbortError");
    }
    throw error;
  }
}

async function requestJson<T>(
  path: string,
  isExpected: (value: unknown) => value is T,
  options: RequestInit = {},
): Promise<T> {
  const response = await apiRequest(path, options);
  if (!response.ok) await throwHttpError(response, options.signal ?? undefined);

  const payload = await readResponseJson<unknown>(response, options.signal ?? undefined);
  if (!isExpected(payload)) throw new Error(INVALID_API_RESPONSE_MESSAGE);
  return payload;
}

export function fetchIngredients(signal?: AbortSignal): Promise<Ingredient[]> {
  return requestJson("/inventory/products", isIngredientList, { signal });
}

export function fetchIngredient(
  id: number,
  signal?: AbortSignal,
): Promise<Ingredient> {
  return requestJson(`/inventory/products/${id}`, isIngredient, { signal });
}

export function createInboundOrder(input: InboundOrderInput): Promise<InventoryOrder> {
  return requestJson("/inventory/orders/inbound", isInventoryOrder, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function createOutboundOrder(input: OutboundOrderInput): Promise<InventoryOrder> {
  return requestJson("/inventory/orders/outbound", isInventoryOrder, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function fetchOrders(signal?: AbortSignal): Promise<InventoryOrder[]> {
  return requestJson("/inventory/orders", isInventoryOrderList, { signal });
}