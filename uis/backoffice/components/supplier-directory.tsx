"use client";

import { useEffect, useState } from "react";

import { fetchSuppliers } from "@/services/suppliers";
import {
  SUPPLIER_CATEGORIES,
  SUPPLIER_CATEGORY_LABELS,
  SUPPLIER_COUNTRIES,
  SupplierStatus,
  type Supplier,
  type SupplierCategory,
  type SupplierCountry,
} from "@/types/supplier";

interface DirectoryResult {
  key: string;
  suppliers: Supplier[];
  error: string | null;
}

export default function SupplierDirectory() {
  const [country, setCountry] = useState<SupplierCountry>();
  const [category, setCategory] = useState<SupplierCategory>();
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<DirectoryResult | null>(null);
  const key = JSON.stringify([country, category, attempt]);
  const loading = result?.key !== key;

  useEffect(() => {
    const controller = new AbortController();
    fetchSuppliers({ country, category }, controller.signal)
      .then((suppliers) => {
        if (!controller.signal.aborted) {
          setResult({ key, suppliers, error: null });
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          const message = error instanceof Error ? error.message : "Error inesperado al cargar proveedores.";
          setResult({
            key,
            suppliers: [],
            error: message.includes("Failed to fetch")
              ? "No se pudo conectar con la API. Comprueba la conexión e inténtalo de nuevo."
              : message,
          });
        }
      });
    return () => controller.abort();
  }, [country, category, key]);

  return (
    <>
      <header className="rounded-2xl border border-orange-200 bg-orange-50 p-5 sm:p-8">
        <p className="text-sm font-semibold text-orange-800">Brasaland · Compras</p>
        <h1 className="mt-2 text-2xl font-bold sm:text-3xl" itemProp="name">Directorio de proveedores</h1>
        <p className="mt-2 text-gray-600">
          Consulta las tarifas vigentes y los proveedores de Colombia y Florida.
        </p>
      </header>

      <section className="grid gap-4 rounded-2xl border border-gray-200 bg-white p-5 sm:grid-cols-2" aria-label="Filtros de proveedores">
        <div className="grid gap-2">
          <label className="font-semibold" htmlFor="supplier-country">País</label>
          <select
            id="supplier-country"
            className="min-h-11 w-full rounded-lg border border-gray-400 bg-white px-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-700"
            value={country ?? ""}
            onChange={(event) => setCountry(SUPPLIER_COUNTRIES.find((value) => value === event.target.value))}
          >
            <option value="">Todos los países</option>
            {SUPPLIER_COUNTRIES.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </div>
        <div className="grid gap-2">
          <label className="font-semibold" htmlFor="supplier-category">Categoría</label>
          <select
            id="supplier-category"
            className="min-h-11 w-full rounded-lg border border-gray-400 bg-white px-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-700"
            value={category ?? ""}
            onChange={(event) => setCategory(SUPPLIER_CATEGORIES.find((value) => value === event.target.value))}
          >
            <option value="">Todas las categorías</option>
            {SUPPLIER_CATEGORIES.map((value) => (
              <option key={value} value={value}>{SUPPLIER_CATEGORY_LABELS[value]}</option>
            ))}
          </select>
        </div>
      </section>

      <section className="min-w-0 rounded-2xl border border-gray-200 bg-white p-5" aria-label="Listado de proveedores" aria-busy={loading}>
        <p role="status" className="mb-4 text-sm text-gray-600">
          {loading ? "Cargando proveedores…" : result?.error ? "No se pudo cargar el listado." : `${result?.suppliers.length ?? 0} proveedores encontrados`}
        </p>
        {!loading && result?.error && (
          <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-4 text-red-900">
            <p>{result.error}</p>
            <button type="button" className="mt-3 min-h-11 rounded-lg border border-red-700 px-4 font-semibold underline focus-visible:outline-2 focus-visible:outline-offset-2" onClick={() => setAttempt((value) => value + 1)}>
              Reintentar
            </button>
          </div>
        )}
        {!loading && !result?.error && result?.suppliers.length === 0 && (
          <p>No hay proveedores que coincidan con los filtros seleccionados.</p>
        )}
        {!loading && !result?.error && Boolean(result?.suppliers.length) && (
          <div className="overflow-x-auto rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2" tabIndex={0} role="region" aria-label="Tabla de proveedores; desplaza horizontalmente en pantallas pequeñas">
            <table className="w-full min-w-[640px] text-left text-sm">
              <caption className="sr-only">Proveedores con los filtros seleccionados</caption>
              <thead className="border-b border-gray-300 bg-gray-50">
                <tr>
                  {["Nombre", "País", "Categorías", "Tarifa por unidad", "Estado"].map((heading) => (
                    <th key={heading} scope="col" className="px-3 py-3 font-semibold">{heading}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {result?.suppliers.map((supplier) => (
                  <tr key={supplier.id} className="hover:bg-orange-50">
                    <th scope="row" className="px-3 py-4 font-semibold">{supplier.name}</th>
                    <td className="px-3 py-4">{supplier.country}</td>
                    <td className="px-3 py-4">{supplier.categories.map((value) => SUPPLIER_CATEGORY_LABELS[value]).join(", ")}</td>
                    <td className="whitespace-nowrap px-3 py-4 tabular-nums">
                      {new Intl.NumberFormat("es-CO", { style: "currency", currency: supplier.currency, currencyDisplay: "code" }).format(supplier.rate_per_unit)}
                    </td>
                    <td className="px-3 py-4">
                      <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${supplier.status === SupplierStatus.Active ? "bg-green-100 text-green-900" : "bg-gray-200 text-gray-800"}`}>
                        {supplier.status === SupplierStatus.Active ? "Activo" : "Suspendido"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
