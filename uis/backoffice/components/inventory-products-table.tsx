"use client";

import Link from "next/link";
import { useState } from "react";

import {
  getLocationStock,
  getStockLevel,
  STOCK_LEVEL_PRESENTATION,
} from "@/lib/inventory-stock";
import {
  INGREDIENT_CATEGORY_LABELS,
  INGREDIENT_COUNTRY_LABELS,
  INGREDIENT_UNIT_LABELS,
  LOCATION_IDS,
  type Ingredient,
} from "@/types/inventory";

interface InventoryProductsTableProps {
  ingredients: Ingredient[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

const stockFormatter = new Intl.NumberFormat("es-ES", {
  maximumFractionDigits: 3,
});

export default function InventoryProductsTable({
  ingredients,
  loading,
  error,
  onRetry,
}: InventoryProductsTableProps) {
  const [locationId, setLocationId] = useState<number | null>(null);

  if (loading) {
    return (
      <p role="status" className="rounded-lg border border-gray-200 bg-white p-5 text-gray-700">
        Cargando ingredientes...
      </p>
    );
  }

  if (error) {
    return (
      <div role="alert" className="grid gap-3 rounded-lg border border-red-300 bg-red-50 p-5 text-red-950">
        <p>{error}</p>
        <button
          type="button"
          onClick={onRetry}
          className="min-h-11 w-fit rounded border border-red-800 px-4 font-semibold underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2"
        >
          Reintentar
        </button>
      </div>
    );
  }

  if (ingredients.length === 0) {
    return (
      <p role="status" className="rounded-lg border border-gray-200 bg-white p-5 text-gray-700">
        No hay ingredientes registrados
      </p>
    );
  }

  return (
    <div className="grid min-w-0 gap-4">
      <div className="grid w-full max-w-xs gap-2">
        <label htmlFor="inventory-location-filter" className="font-semibold text-gray-800">
          Local
        </label>
        <select
          id="inventory-location-filter"
          value={locationId ?? ""}
          onChange={(event) => setLocationId(
            event.target.value ? Number(event.target.value) : null,
          )}
          className="min-h-11 w-full rounded-lg border border-gray-400 bg-white px-3 py-2 text-base focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-700"
        >
          <option value="">Todos los locales</option>
          {LOCATION_IDS.map((id) => (
            <option key={id} value={id}>Local {id}</option>
          ))}
        </select>
      </div>

      <div className="min-w-0 overflow-x-auto rounded-lg border border-gray-200 bg-white">
        <table className="w-full min-w-[1120px] border-collapse text-left text-sm text-gray-800">
          <caption className="sr-only">Ingredientes y niveles de stock actuales</caption>
          <thead className="bg-gray-100 text-xs uppercase text-gray-700">
            <tr>
              <th scope="col" className="px-4 py-3">Ingrediente</th>
              <th scope="col" className="px-4 py-3">SKU</th>
              <th scope="col" className="px-4 py-3">Categoría</th>
              <th scope="col" className="px-4 py-3">País</th>
              <th scope="col" className="px-4 py-3">Unidad</th>
              <th scope="col" className="px-4 py-3">
                {locationId === null ? "Stock total" : `Stock en Local ${locationId}`}
              </th>
              <th scope="col" className="px-4 py-3">Stock por local</th>
              <th scope="col" className="px-4 py-3">Nivel</th>
              <th scope="col" className="px-4 py-3">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {ingredients.map((ingredient) => {
              const locationStock = getLocationStock(ingredient, locationId);
              const level = getStockLevel(ingredient.unit, locationStock);
              const presentation = STOCK_LEVEL_PRESENTATION[level];
              const stock = stockFormatter.format(locationStock);

              return (
                <tr key={ingredient.id} className="align-middle">
                  <th scope="row" className="px-4 py-4 font-semibold">{ingredient.name}</th>
                  <td className="px-4 py-4">{ingredient.sku}</td>
                  <td className="px-4 py-4">{INGREDIENT_CATEGORY_LABELS[ingredient.category]}</td>
                  <td className="px-4 py-4">{INGREDIENT_COUNTRY_LABELS[ingredient.country]}</td>
                  <td className="px-4 py-4">{INGREDIENT_UNIT_LABELS[ingredient.unit]}</td>
                  <td className="whitespace-nowrap px-4 py-4">
                    {stock} {INGREDIENT_UNIT_LABELS[ingredient.unit]}
                  </td>
                  <td className="px-4 py-4">
                    <details>
                      <summary className="w-fit cursor-pointer font-semibold text-orange-800 underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2">
                        Ver stock por local
                      </summary>
                      {ingredient.stock_by_location.length > 0 ? (
                        <ul className="mt-2 grid gap-1 pl-5 text-gray-700">
                          {ingredient.stock_by_location.map((stockAtLocation) => (
                            <li key={stockAtLocation.location_id}>
                              Local {stockAtLocation.location_id}: {stockFormatter.format(stockAtLocation.quantity)} {ingredient.unit}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="mt-2 text-gray-700">Sin movimientos</p>
                      )}
                    </details>
                  </td>
                  <td className="px-4 py-4">
                    <span className={`inline-flex items-center gap-2 rounded px-2.5 py-1 font-semibold ${presentation.className}`}>
                      <span aria-hidden="true">{presentation.symbol}</span>
                      {presentation.label}
                    </span>
                  </td>
                  <td className="px-4 py-4">
                    <div className="flex flex-wrap gap-x-4 gap-y-2">
                      <Link
                        href={`/inventory/orders/inbound?ingredient_id=${ingredient.id}`}
                        aria-label={`Registrar entrada de ${ingredient.name}`}
                        className="font-semibold text-orange-800 underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2"
                      >
                        Registrar entrada
                      </Link>
                      <Link
                        href={`/inventory/orders/outbound?ingredient_id=${ingredient.id}`}
                        aria-label={`Registrar salida de ${ingredient.name}`}
                        className="font-semibold text-orange-800 underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2"
                      >
                        Registrar salida
                      </Link>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}