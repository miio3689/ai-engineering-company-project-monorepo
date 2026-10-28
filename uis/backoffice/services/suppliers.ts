import type { Supplier, SupplierFilters, SupplierInput, SupplierStatus } from "@/types/supplier";

function getApiBaseUrl(): string {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!baseUrl) throw new Error("Falta NEXT_PUBLIC_API_BASE_URL en el entorno.");
  return baseUrl.replace(/\/$/, "");
}

export async function fetchSuppliers(
  filters: SupplierFilters = {},
  signal?: AbortSignal,
): Promise<Supplier[]> {
  const baseUrl = getApiBaseUrl();

  const params = new URLSearchParams();
  if (filters.country) params.set("country", filters.country);
  if (filters.category) params.set("category", filters.category);
  const query = params.toString();
  const response = await fetch(
    `${baseUrl.replace(/\/$/, "")}/suppliers${query ? `?${query}` : ""}`,
    { cache: "no-store", signal },
  );

  if (!response.ok) {
    throw new Error(`No se pudo cargar el directorio de proveedores (HTTP ${response.status}).`);
  }

  return (await response.json()) as Supplier[];
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

async function writeSupplier(path: string, method: "POST" | "PATCH", body: object): Promise<Supplier> {
  const response = await fetch(`${getApiBaseUrl()}/suppliers${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    let payload: unknown;
    try {
      payload = JSON.parse(text);
    } catch (error) {
      if (!(error instanceof SyntaxError)) throw error;
      throw new Error(`No se pudo guardar el proveedor (HTTP ${response.status}).`);
    }
    if (response.status === 422 && payload && typeof payload === "object" && "detail" in payload) {
      throw new Error(validationMessage(payload.detail));
    }
    if (response.status === 404) throw new Error("El proveedor ya no existe. Vuelve a cargar el listado.");
    throw new Error(`No se pudo guardar el proveedor (HTTP ${response.status}).`);
  }
  return (await response.json()) as Supplier;
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
