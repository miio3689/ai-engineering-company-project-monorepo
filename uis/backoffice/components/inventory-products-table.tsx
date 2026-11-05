import Link from "next/link";

import {
  getStockLevel,
  STOCK_LEVEL_PRESENTATION,
} from "@/lib/inventory-stock";
import {
  INGREDIENT_CATEGORY_LABELS,
  INGREDIENT_COUNTRY_LABELS,
  INGREDIENT_UNIT_LABELS,
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
    <div className="min-w-0 overflow-x-auto rounded-lg border border-gray-200 bg-white">
      <table className="w-full min-w-[980px] border-collapse text-left text-sm text-gray-800">
        <caption className="sr-only">Ingredientes y niveles de stock actuales</caption>
        <thead className="bg-gray-100 text-xs uppercase text-gray-700">
          <tr>
            <th scope="col" className="px-4 py-3">Ingrediente</th>
            <th scope="col" className="px-4 py-3">SKU</th>
            <th scope="col" className="px-4 py-3">Categoría</th>
            <th scope="col" className="px-4 py-3">País</th>
            <th scope="col" className="px-4 py-3">Unidad</th>
            <th scope="col" className="px-4 py-3">Stock actual</th>
            <th scope="col" className="px-4 py-3">Nivel</th>
            <th scope="col" className="px-4 py-3">Acciones</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {ingredients.map((ingredient) => {
            const level = getStockLevel(ingredient.unit, ingredient.current_stock);
            const presentation = STOCK_LEVEL_PRESENTATION[level];
            const stock = stockFormatter.format(ingredient.current_stock);

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
  );
}