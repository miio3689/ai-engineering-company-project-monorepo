"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { useInventoryIngredientStock } from "@/hooks/use-inventory-ingredient-stock";
import { useInventoryProducts } from "@/hooks/use-inventory-products";
import { useSubmissionLock } from "@/hooks/use-submission-lock";
import {
  getLocationStock,
  getStockLevel,
  isQuantityAboveLocationStock,
  STOCK_LEVEL_PRESENTATION,
} from "@/lib/inventory-stock";
import { createOutboundOrder, InventoryServiceError } from "@/services/inventory";
import {
  EXIT_REASON_LABELS,
  LOCATION_IDS,
  type ExitReason,
  type OutboundOrderInput,
} from "@/types/inventory";

interface FormValues {
  ingredientId: string;
  quantity: string;
  reason: ExitReason;
  locationId: string;
}

type InventoryFormField = keyof FormValues;
type InventoryFormErrors = Partial<Record<InventoryFormField, string>>;

interface SuccessSummary {
  ingredientName: string;
  quantity: number;
  unit: string;
  reason: ExitReason;
  locationId: number;
}

const REASONS: { value: ExitReason; label: string }[] = [
  { value: "consumption", label: "Consumo" },
  { value: "waste", label: "Merma" },
];

const INITIAL_VALUES: FormValues = {
  ingredientId: "",
  quantity: "",
  reason: "consumption",
  locationId: "",
};

const fieldClass = "min-h-11 w-full rounded-lg border border-gray-400 bg-white px-3 py-2 text-base focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-700";

const quantityFormatter = new Intl.NumberFormat("es-ES", {
  maximumFractionDigits: 3,
});

function formatQuantityUnit(quantity: number, unit: string): string {
  if (unit === "kg") return "kg";
  if (unit === "litro") return quantity === 1 ? "litro" : "litros";
  return quantity === 1 ? "unidad" : "unidades";
}

export default function InventoryOutboundForm() {
  const searchParams = useSearchParams();
  const { ingredients, loading, error: ingredientsError, retry } = useInventoryProducts();
  const [values, setValues] = useState<FormValues>(() => ({
    ...INITIAL_VALUES,
    ingredientId: searchParams.get("ingredient_id") ?? "",
  }));
  const [fieldErrors, setFieldErrors] = useState<InventoryFormErrors>({});
  const [quantityApiError, setQuantityApiError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<SuccessSummary | null>(null);
  const { isSubmitting, isLocked, run } = useSubmissionLock();
  const formRef = useRef<HTMLFormElement>(null);
  const selectedIngredient = ingredients.find(
    (ingredient) => String(ingredient.id) === values.ingredientId,
  );
  const stock = useInventoryIngredientStock(selectedIngredient?.id ?? null);
  const selectedLocationId = values.locationId ? Number(values.locationId) : null;

  useEffect(() => {
    const firstError = Object.keys(fieldErrors)[0] as InventoryFormField | undefined;
    if (!firstError) return;
    const control = formRef.current?.elements.namedItem(firstError);
    if (control instanceof HTMLElement) control.focus();
  }, [fieldErrors]);

  function updateField<Field extends InventoryFormField>(
    field: Field,
    value: FormValues[Field],
  ) {
    setValues((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => {
      const next = { ...current };
      delete next[field];
      return next;
    });
    setQuantityApiError(null);
    setError(null);
    setSuccess(null);
    if (field === "ingredientId") stock.refresh();
  }

  function validate(): InventoryFormErrors {
    const errors: InventoryFormErrors = {};
    if (!ingredients.some((ingredient) => String(ingredient.id) === values.ingredientId)) {
      errors.ingredientId = "Selecciona un ingrediente de la lista.";
    }

    const quantity = Number(values.quantity);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      errors.quantity = "Introduce una cantidad mayor que cero.";
    }

    if (!REASONS.some((reason) => reason.value === values.reason)) {
      errors.reason = "Selecciona un motivo válido.";
    }

    const locationId = Number(values.locationId);
    if (!LOCATION_IDS.some((id) => id === locationId)) {
      errors.locationId = "Selecciona un local.";
    }

    return errors;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isLocked()) return;
    setQuantityApiError(null);
    setError(null);
    setSuccess(null);

    const validationErrors = validate();
    if (Object.keys(validationErrors).length) {
      setFieldErrors(validationErrors);
      setError("Revisa los campos señalados antes de registrar la salida.");
      return;
    }

    const ingredient = ingredients.find(
      (item) => String(item.id) === values.ingredientId,
    );
    if (!ingredient) return;

    setFieldErrors({});
    void run(async () => {
      const input: OutboundOrderInput = {
        ingredient_id: ingredient.id,
        quantity: Number(values.quantity),
        reason: values.reason,
        location_id: Number(values.locationId),
      };

      try {
        await createOutboundOrder(input);
        setValues((current) => ({
          ...current,
          quantity: "",
          reason: "consumption",
          locationId: "",
        }));
        setFieldErrors({});
        setSuccess({
          ingredientName: ingredient.name,
          quantity: input.quantity,
          unit: ingredient.unit,
          reason: input.reason,
          locationId: input.location_id,
        });
        stock.refresh();
      } catch (caught) {
        if (caught instanceof InventoryServiceError && caught.status === 400) {
          setQuantityApiError(caught.message);
          stock.refresh();
        } else {
          setError(caught instanceof Error
            ? caught.message
            : "No se pudo registrar la salida. Inténtalo de nuevo.");
        }
      }
    });
  }

  function fieldDescription(field: InventoryFormField, extraId?: string) {
    const ids = [
      fieldErrors[field] ? `${field}-error` : null,
      field === "quantity" && quantityApiError ? "quantity-api-error" : null,
      extraId,
    ].filter(Boolean).join(" ");
    return ids || undefined;
  }

  const quantity = Number(values.quantity);
  const showStockWarning = isQuantityAboveLocationStock(
    stock.ingredient,
    selectedLocationId,
    quantity,
  ) && !stock.loading && !stock.error;
  const localStock = stock.ingredient && selectedLocationId !== null
    ? getLocationStock(stock.ingredient, selectedLocationId)
    : null;
  const stockPresentation = stock.ingredient && localStock !== null
    ? STOCK_LEVEL_PRESENTATION[
      getStockLevel(stock.ingredient.unit, localStock)
    ]
    : null;
  const successLocalStock = success && stock.ingredient
    ? getLocationStock(stock.ingredient, success.locationId)
    : null;

  return (
    <section
      className="rounded-2xl border border-orange-200 bg-white p-5 shadow-sm sm:p-8"
      aria-labelledby="inventory-outbound-title"
    >
      <h2 id="inventory-outbound-title" className="mb-5 text-xl font-bold">
        Datos de la salida
      </h2>

      <form ref={formRef} noValidate onSubmit={submit}>
        <fieldset
          disabled={isSubmitting}
          className="grid gap-5 disabled:opacity-70 sm:grid-cols-2"
          aria-busy={isSubmitting}
        >
          <legend className="sr-only">Formulario de orden de salida</legend>

          <div className="grid gap-2 font-semibold">
            <label htmlFor="ingredientId">Ingrediente *</label>
            <select
              id="ingredientId"
              name="ingredientId"
              value={selectedIngredient ? values.ingredientId : ""}
              onChange={(event) => updateField("ingredientId", event.target.value)}
              className={fieldClass}
              required
              disabled={loading || Boolean(ingredientsError) || ingredients.length === 0}
              aria-invalid={Boolean(fieldErrors.ingredientId)}
              aria-describedby={fieldDescription("ingredientId")}
            >
              <option value="">Selecciona un ingrediente</option>
              {ingredients.map((ingredient) => (
                <option key={ingredient.id} value={ingredient.id}>
                  {ingredient.name} ({ingredient.sku})
                </option>
              ))}
            </select>
            {fieldErrors.ingredientId && (
              <span id="ingredientId-error" className="font-normal text-red-800">
                {fieldErrors.ingredientId}
              </span>
            )}
            {loading && (
              <span role="status" className="font-normal text-gray-700">
                Cargando ingredientes...
              </span>
            )}
            {ingredientsError && (
              <div role="alert" className="grid gap-2 font-normal text-red-800">
                <p>{ingredientsError}</p>
                <button
                  type="button"
                  onClick={retry}
                  className="min-h-11 w-fit rounded border border-red-800 px-3 font-semibold underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2"
                >
                  Reintentar
                </button>
              </div>
            )}
            {!loading && !ingredientsError && ingredients.length === 0 && (
              <span role="status" className="font-normal text-gray-700">
                No hay ingredientes registrados.
              </span>
            )}
          </div>

          <label className="grid gap-2 font-semibold" htmlFor="quantity">
            Cantidad *
            <input
              id="quantity"
              name="quantity"
              type="number"
              step="any"
              inputMode="decimal"
              value={values.quantity}
              onChange={(event) => updateField("quantity", event.target.value)}
              className={fieldClass}
              required
              aria-invalid={Boolean(fieldErrors.quantity || quantityApiError)}
              aria-describedby={fieldDescription(
                "quantity",
                selectedIngredient ? "quantity-unit" : undefined,
              )}
            />
            {selectedIngredient && (
              <span id="quantity-unit" className="font-normal text-gray-700">
                Unidad: {selectedIngredient.unit}
              </span>
            )}
            {fieldErrors.quantity && (
              <span id="quantity-error" className="font-normal text-red-800">
                {fieldErrors.quantity}
              </span>
            )}
            {quantityApiError && (
              <span id="quantity-api-error" role="alert" className="font-normal text-red-800">
                {quantityApiError}
              </span>
            )}
          </label>

          <label className="grid gap-2 font-semibold" htmlFor="reason">
            Motivo *
            <select
              id="reason"
              name="reason"
              value={values.reason}
              onChange={(event) => updateField(
                "reason",
                REASONS.find((reason) => reason.value === event.target.value)?.value ?? "consumption",
              )}
              className={fieldClass}
              required
              aria-invalid={Boolean(fieldErrors.reason)}
              aria-describedby={fieldDescription("reason")}
            >
              {REASONS.map(({ value, label }) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
            {fieldErrors.reason && (
              <span id="reason-error" className="font-normal text-red-800">
                {fieldErrors.reason}
              </span>
            )}
          </label>

          <label className="grid gap-2 font-semibold" htmlFor="locationId">
            Local *
            <select
              id="locationId"
              name="locationId"
              value={values.locationId}
              onChange={(event) => updateField("locationId", event.target.value)}
              className={fieldClass}
              required
              aria-invalid={Boolean(fieldErrors.locationId)}
              aria-describedby={fieldDescription("locationId")}
            >
              <option value="">Selecciona un local</option>
              {LOCATION_IDS.map((id) => (
                <option key={id} value={id}>Local {id}</option>
              ))}
            </select>
            {fieldErrors.locationId && (
              <span id="locationId-error" className="font-normal text-red-800">
                {fieldErrors.locationId}
              </span>
            )}
          </label>

          <div className="grid gap-2 rounded-lg border border-gray-200 bg-gray-50 p-4 sm:col-span-2">
            <h3 className="font-semibold">Stock disponible</h3>
            {!selectedIngredient && (
              <p role="status" className="text-gray-700">
                Selecciona un ingrediente para ver su stock
              </p>
            )}
            {selectedIngredient && selectedLocationId === null && (
              <p role="status" className="text-gray-700">
                Selecciona un local para ver su stock en ese local
              </p>
            )}
            {selectedIngredient && selectedLocationId !== null && stock.loading && (
              <p role="status" className="text-gray-700">Consultando stock…</p>
            )}
            {selectedIngredient && selectedLocationId !== null && stock.error && (
              <div role="alert" className="grid gap-2 text-red-900">
                <p>{stock.error}</p>
                <button
                  type="button"
                  onClick={stock.refresh}
                  className="min-h-11 w-fit rounded border border-red-800 px-3 font-semibold underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2"
                >
                  Reintentar
                </button>
              </div>
            )}
            {selectedIngredient && stock.ingredient && localStock !== null && stockPresentation && (
              <p className="flex flex-wrap items-center gap-3 text-gray-800">
                <span>
                  Stock disponible en el Local {selectedLocationId}: {quantityFormatter.format(localStock)} {stock.ingredient.unit}
                </span>
                <span className={`inline-flex items-center gap-2 rounded px-2.5 py-1 text-sm font-semibold ${stockPresentation.className}`}>
                  <span aria-hidden="true">{stockPresentation.symbol}</span>
                  {stockPresentation.label}
                </span>
              </p>
            )}
            {showStockWarning && stock.ingredient && (
              <p aria-live="polite" className="text-sm font-semibold text-amber-950">
                La cantidad supera el stock disponible en el Local {selectedLocationId} ({quantityFormatter.format(localStock ?? 0)} {stock.ingredient.unit}). La salida será rechazada.
              </p>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
            <button
              type="submit"
              disabled={isSubmitting || loading || Boolean(ingredientsError) || ingredients.length === 0}
              className="inline-flex min-h-11 items-center justify-center rounded-lg bg-orange-700 px-5 font-semibold text-white hover:bg-orange-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSubmitting ? "Registrando salida…" : "Registrar salida"}
            </button>
            {isSubmitting && (
              <span role="status" className="text-sm text-gray-700">
                Enviando los datos...
              </span>
            )}
          </div>
        </fieldset>

        {error && (
          <p role="alert" className="mt-5 rounded-lg border border-red-300 bg-red-50 p-4 text-red-900">
            {error}
          </p>
        )}
        {success && (
          <p role="status" className="mt-5 grid gap-2 rounded-lg border border-green-300 bg-green-50 p-4 text-green-950">
            <span>
              Salida registrada: {quantityFormatter.format(success.quantity)} {formatQuantityUnit(success.quantity, success.unit)} de {success.ingredientName} ({EXIT_REASON_LABELS[success.reason]}, Local {success.locationId}). Stock disponible ahora en el Local {success.locationId}: {stock.loading
                ? "Consultando..."
                : successLocalStock !== null && stock.ingredient
                  ? `${quantityFormatter.format(successLocalStock)} ${stock.ingredient.unit}`
                  : "no disponible"}.
            </span>
            <Link
              href="/inventory/orders"
              className="w-fit font-semibold underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2"
            >
              Ver historial
            </Link>
          </p>
        )}
      </form>
    </section>
  );
}