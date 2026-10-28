import type { Supplier, SupplierFilters } from "@/types/supplier";

export async function fetchSuppliers(
  filters: SupplierFilters = {},
  signal?: AbortSignal,
): Promise<Supplier[]> {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!baseUrl) {
    throw new Error("Falta NEXT_PUBLIC_API_BASE_URL en el entorno.");
  }

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
