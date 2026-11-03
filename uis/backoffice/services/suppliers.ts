import {
  SUPPLIER_CATEGORIES,
  SUPPLIER_COUNTRIES,
  SupplierStatus,
  type Supplier,
  type SupplierFilters,
  type SupplierInput,
} from "@/types/supplier";
import { apiRequest } from "@/services/api-client";
import {
  API_UNAVAILABLE_MESSAGE,
  INVALID_API_RESPONSE_MESSAGE,
  buildApiErrorMessage,
  readJsonResponse,
} from "@/services/api-errors";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export async function fetchSuppliers(
  filters: SupplierFilters = {},
  signal?: AbortSignal,
): Promise<Supplier[]> {
  const params = new URLSearchParams();
  if (filters.country) params.set("country", filters.country);
  if (filters.category) params.set("category", filters.category);
  const query = params.toString();
  const response = await apiRequest(
    `/suppliers${query ? `?${query}` : ""}`,
    { cache: "no-store", signal },
  );

  if (!response.ok) {
    throw new Error(await buildApiErrorMessage(response));
  }

  const suppliers = await readJsonResponse<unknown>(response);
  if (!Array.isArray(suppliers) || !suppliers.every(isSupplier)) {
    throw new Error(INVALID_API_RESPONSE_MESSAGE);
  }
  return suppliers;
}

function isSupplier(value: unknown): value is Supplier {
  if (!isRecord(value)) return false;
  return typeof value.id === "number"
    && typeof value.name === "string"
    && SUPPLIER_COUNTRIES.some((country) => country === value.country)
    && Array.isArray(value.categories)
    && value.categories.every((category) =>
      SUPPLIER_CATEGORIES.some((allowed) => allowed === category)
    )
    && typeof value.rate_per_unit === "number"
    && (value.currency === "COP" || value.currency === "USD")
    && (value.status === SupplierStatus.Active || value.status === SupplierStatus.Suspended)
    && typeof value.updated_at === "string"
    && (typeof value.contact_email === "string" || value.contact_email === null)
    && (typeof value.notes === "string" || value.notes === null);
}

function validationMessage(detail: unknown): string {
  if (typeof detail === "string") {
    if (detail.includes("currency must be COP")) return "Para Colombia, la moneda debe ser COP.";
    if (detail.includes("currency must be USD")) return "Para USA, la moneda debe ser USD.";
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail.map((issue: unknown) => {
      if (!issue || typeof issue !== "object") return "Revisa los datos del proveedor.";
      if ("msg" in issue && typeof issue.msg === "string" && issue.msg.includes("currency must be")) {
        return validationMessage(issue.msg);
      }
      const field = "loc" in issue && Array.isArray(issue.loc) ? issue.loc[1] : undefined;
      const messages: Record<string, string> = {
        name: "Introduce el nombre del proveedor.",
        country: "Selecciona Colombia o USA.",
        categories: "Selecciona al menos una categoría válida.",
        rate_per_unit: "La tarifa debe ser un número mayor que cero.",
        currency: "Selecciona COP o USD y comprueba que corresponda al país.",
        status: "El estado debe ser activo o suspendido.",
        contact_email: "Revisa el correo de contacto.",
        notes: "Revisa las notas del proveedor.",
      };
      return typeof field === "string" && messages[field]
        ? messages[field]
        : "Revisa los campos enviados: hay datos no válidos.";
    }).join(" ");
  }
  return "Revisa los datos del proveedor.";
}

function supplierErrorMessage(payload: unknown): string {
  if (!payload || typeof payload !== "object") {
    return "Revisa los datos del proveedor.";
  }
  if ("errors" in payload && Array.isArray(payload.errors)) {
    const messages = payload.errors.flatMap((issue: unknown) => {
      if (!issue || typeof issue !== "object" || !("message" in issue)) return [];
      return typeof issue.message === "string" ? [validationMessage(issue.message)] : [];
    });
    if (messages.length) return messages.join(" ");
  }
  if ("detail" in payload) return validationMessage(payload.detail);
  return "Revisa los datos del proveedor.";
}

async function writeSupplier(path: string, method: "POST" | "PATCH", body: object): Promise<Supplier> {
  const response = await apiRequest(`/suppliers${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    if (response.status === 400 || response.status === 422) {
      let payload: unknown;
      try {
        payload = await readJsonResponse<unknown>(response);
      } catch {
        throw new Error("Los datos no son válidos. Revísalos e inténtalo de nuevo.");
      }
      throw new Error(supplierErrorMessage(payload));
    }
    if (response.status === 404) throw new Error("El proveedor ya no existe. Vuelve a cargar el listado.");
    throw new Error(`No se pudo guardar el proveedor. ${API_UNAVAILABLE_MESSAGE}`);
  }
  const supplier = await readJsonResponse<unknown>(response);
  if (!isSupplier(supplier)) throw new Error(INVALID_API_RESPONSE_MESSAGE);
  return supplier;
}

export function createSupplier(input: SupplierInput): Promise<Supplier> {
  return writeSupplier("", "POST", input);
}

export function updateSupplierRate(id: number, rate_per_unit: number): Promise<Supplier> {
  return writeSupplier(`/${id}/rate`, "PATCH", { rate_per_unit });
}

export function updateSupplierStatus(id: number, status: SupplierStatus): Promise<Supplier> {
  return writeSupplier(`/${id}/status`, "PATCH", { status });
}
