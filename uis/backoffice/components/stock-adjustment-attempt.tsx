"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { trackDirectStockEditRejected } from "@/lib/inventory-telemetry";
import { attemptDirectStockEdit, InventoryServiceError } from "@/services/inventory";
import { LOCATION_IDS, type Ingredient } from "@/types/inventory";

interface StockAdjustmentAttemptProps {
  ingredient: Ingredient;
  defaultLocationId: number | null;
}

const fieldClass = "min-h-11 w-full rounded-lg border border-gray-400 bg-white px-3 py-2 text-base focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-700";
const linkClass = "font-semibold text-orange-800 underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2";

/**
 * El stock nunca se edita directamente. Esta acción deja intentarlo, la API lo
 * rechaza siempre (403) y se mide como direct_stock_edit_rejected.
 */
export default function StockAdjustmentAttempt({
  ingredient,
  defaultLocationId,
}: StockAdjustmentAttemptProps) {
  const [open, setOpen] = useState(false);
  const [locationId, setLocationId] = useState(
    defaultLocationId === null ? "" : String(defaultLocationId),
  );
  const [quantity, setQuantity] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rejection, setRejection] = useState<string | null>(null);
  const panelId = `stock-adjustment-${ingredient.id}`;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const location = Number(locationId);
    const amount = Number(quantity);
    setError(null);
    setRejection(null);
    if (!LOCATION_IDS.some((id) => id === location)) {
      setError("Selecciona un local.");
      return;
    }
    if (!quantity.trim() || !Number.isFinite(amount) || amount < 0) {
      setError("Introduce un stock válido (cero o mayor).");
      return;
    }

    setBusy(true);
    try {
      await attemptDirectStockEdit(ingredient.id, { location_id: location, quantity: amount });
    } catch (caught) {
      if (caught instanceof InventoryServiceError && caught.status === 403) {
        setRejection(caught.message);
        trackDirectStockEditRejected(ingredient, location, amount);
      } else {
        setError(
          caught instanceof Error
            ? caught.message
            : "No se pudo completar la solicitud. Inténtalo de nuevo.",
        );
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-2 grid gap-2">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((current) => !current)}
        className="min-h-11 w-fit rounded border border-gray-400 px-3 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-offset-2"
      >
        {open ? "Cerrar ajuste" : "Ajustar stock"}
      </button>

      {open && (
        <form id={panelId} noValidate onSubmit={submit} className="grid gap-3 rounded-lg border border-gray-300 bg-gray-50 p-3">
          <label className="grid gap-1 text-sm font-semibold" htmlFor={`${panelId}-location`}>
            Local
            <select
              id={`${panelId}-location`}
              value={locationId}
              onChange={(event) => setLocationId(event.target.value)}
              className={fieldClass}
              disabled={busy}
            >
              <option value="">Selecciona un local</option>
              {LOCATION_IDS.map((id) => (
                <option key={id} value={id}>Local {id}</option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-sm font-semibold" htmlFor={`${panelId}-quantity`}>
            Nuevo stock ({ingredient.unit})
            <input
              id={`${panelId}-quantity`}
              type="number"
              step="any"
              inputMode="decimal"
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
              className={fieldClass}
              disabled={busy}
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="min-h-11 w-fit rounded-lg bg-orange-700 px-4 text-sm font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-60"
          >
            {busy ? "Enviando…" : "Intentar ajuste"}
          </button>

          {error && <p role="alert" className="text-sm text-red-900">{error}</p>}
          {rejection && (
            <div role="alert" className="grid gap-1 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-950">
              <p>{rejection}</p>
              <p className="flex flex-wrap gap-x-4 gap-y-1">
                <Link href={`/inventory/orders/inbound?ingredient_id=${ingredient.id}`} className={linkClass}>
                  Registrar entrada
                </Link>
                <Link href={`/inventory/orders/outbound?ingredient_id=${ingredient.id}`} className={linkClass}>
                  Registrar salida
                </Link>
              </p>
            </div>
          )}
        </form>
      )}
    </div>
  );
}
