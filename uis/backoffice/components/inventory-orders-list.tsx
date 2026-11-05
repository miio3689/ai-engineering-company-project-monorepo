"use client";

import Link from "next/link";

import { useInventoryOrders } from "@/hooks/use-inventory-orders";
import { formatOrderDate, formatQuantity } from "@/lib/inventory-format";
import { EXIT_REASON_LABELS, type InventoryOrder } from "@/types/inventory";

function orderType(order: InventoryOrder) {
  return order.type === "inbound"
    ? { label: "Entrada", symbol: "↓", className: "bg-green-100 text-green-950" }
    : { label: "Salida", symbol: "↑", className: "bg-amber-100 text-amber-950" };
}

function orderDetail(order: InventoryOrder) {
  return order.type === "inbound"
    ? order.supplier_name
    : EXIT_REASON_LABELS[order.reason];
}

function orderSummary(orders: InventoryOrder[]) {
  const inbound = orders.filter((order) => order.type === "inbound").length;
  const outbound = orders.length - inbound;
  const orderLabel = orders.length === 1 ? "orden" : "órdenes";
  const inboundLabel = inbound === 1 ? "entrada" : "entradas";
  const outboundLabel = outbound === 1 ? "salida" : "salidas";

  return `${orders.length} ${orderLabel}: ${inbound} ${inboundLabel} y ${outbound} ${outboundLabel}`;
}

function InventoryOrderType({ order }: { order: InventoryOrder }) {
  const type = orderType(order);
  return (
    <span className={`inline-flex items-center gap-2 rounded px-2.5 py-1 font-semibold ${type.className}`}>
      <span aria-hidden="true">{type.symbol}</span>
      {type.label}
    </span>
  );
}

export default function InventoryOrdersList() {
  const { orders, unitsByIngredientId, loading, error, retry } = useInventoryOrders();

  if (loading) {
    return (
      <p role="status" className="rounded-lg border border-gray-200 bg-white p-5 text-gray-700">
        Cargando historial de órdenes...
      </p>
    );
  }

  if (error) {
    return (
      <div role="alert" className="grid gap-3 rounded-lg border border-red-300 bg-red-50 p-5 text-red-950">
        <p>{error}</p>
        <button
          type="button"
          onClick={retry}
          className="min-h-11 w-fit rounded border border-red-800 px-4 font-semibold underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2"
        >
          Reintentar
        </button>
      </div>
    );
  }

  if (orders.length === 0) {
    return (
      <section className="grid gap-4 rounded-lg border border-gray-200 bg-white p-5">
        <p role="status" className="text-gray-700">Aún no hay órdenes registradas</p>
        <div className="flex flex-wrap gap-4">
          <Link
            href="/inventory/orders/inbound"
            className="font-semibold text-orange-800 underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2"
          >
            Registrar entrada
          </Link>
          <Link
            href="/inventory/orders/outbound"
            className="font-semibold text-orange-800 underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2"
          >
            Registrar salida
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="grid min-w-0 gap-4" aria-label="Órdenes de inventario">
      <p className="font-semibold text-gray-800">{orderSummary(orders)}</p>

      <div className="hidden min-w-0 overflow-x-auto rounded-lg border border-gray-200 bg-white md:block">
        <table className="w-full min-w-[980px] border-collapse text-left text-sm text-gray-800">
          <caption className="sr-only">Historial de órdenes de inventario, solo lectura</caption>
          <thead className="bg-gray-100 text-xs uppercase text-gray-700">
            <tr>
              <th scope="col" className="px-4 py-3">Fecha</th>
              <th scope="col" className="px-4 py-3">Tipo</th>
              <th scope="col" className="px-4 py-3">Ingrediente</th>
              <th scope="col" className="px-4 py-3">Cantidad</th>
              <th scope="col" className="px-4 py-3">Detalle</th>
              <th scope="col" className="px-4 py-3">Local</th>
              <th scope="col" className="px-4 py-3">Usuario</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {orders.map((order) => (
              <tr key={`${order.type}-${order.id}`} className="align-middle">
                <td className="whitespace-nowrap px-4 py-4">{formatOrderDate(order.created_at)}</td>
                <td className="px-4 py-4"><InventoryOrderType order={order} /></td>
                <td className="px-4 py-4">
                  <span className="block font-semibold">{order.name}</span>
                  <span className="text-gray-600">{order.sku}</span>
                </td>
                <td className="whitespace-nowrap px-4 py-4">
                  {formatQuantity(order.quantity)}{unitsByIngredientId[order.ingredient_id]
                    ? ` ${unitsByIngredientId[order.ingredient_id]}`
                    : ""}
                </td>
                <td className="px-4 py-4">
                  <span className="text-gray-600">
                    {order.type === "inbound" ? "Proveedor: " : "Motivo: "}
                  </span>
                  {orderDetail(order)}
                </td>
                <td className="whitespace-nowrap px-4 py-4">Local {order.location_id}</td>
                <td className="px-4 py-4">{order.user_uuid}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className="grid gap-3 md:hidden" aria-label="Órdenes">
        {orders.map((order) => (
          <li key={`${order.type}-${order.id}`} className="grid gap-3 rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-800">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <InventoryOrderType order={order} />
              <time className="text-gray-600">{formatOrderDate(order.created_at)}</time>
            </div>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-2">
              <dt className="font-semibold">Ingrediente</dt>
              <dd>{order.name} <span className="text-gray-600">({order.sku})</span></dd>
              <dt className="font-semibold">Cantidad</dt>
              <dd>
                {formatQuantity(order.quantity)}{unitsByIngredientId[order.ingredient_id]
                  ? ` ${unitsByIngredientId[order.ingredient_id]}`
                  : ""}
              </dd>
              <dt className="font-semibold">
                {order.type === "inbound" ? "Proveedor" : "Motivo"}
              </dt>
              <dd>{orderDetail(order)}</dd>
              <dt className="font-semibold">Local</dt>
              <dd>Local {order.location_id}</dd>
              <dt className="font-semibold">Usuario</dt>
              <dd className="break-all">{order.user_uuid}</dd>
            </dl>
          </li>
        ))}
      </ul>
    </section>
  );
}