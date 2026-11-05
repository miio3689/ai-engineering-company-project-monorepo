"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { useInventoryProducts } from "@/hooks/use-inventory-products";
import { createInboundOrder, InventoryServiceError } from "@/services/inventory";
import { LOCATION_IDS, type InboundOrderInput } from "@/types/inventory";

interface FormValues {
  ingredientId: string;
  quantity: string;
  supplierName: string;
  locationId: string;
}

type InventoryFormField = keyof FormValues;
type InventoryFormErrors = Partial<Record<InventoryFormField, string>>;

const INITIAL_VALUES: FormValues = {
  ingredientId: "",
  quantity: "",
  supplierName: "",
  locationId: "",
};

const SUPPLIER_SUGGESTIONS = [
  "Carnes del Valle S.A.",
  "MiamiMeat Co.",
  "Salsas Artesanales Ltda.",
];

const fieldClass = "min-h-11 w-full rounded-lg border border-gray-400 bg-white px-3 py-2 text-base focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-700";

const quantityFormatter = new Intl.NumberFormat("es-ES", {
  maximumFractionDigits: 3,
});

export default function InventoryInboundForm() {
  const searchParams = useSearchParams();
  const { ingredients, loading, error: ingredientsError, retry } = useInventoryProducts();
  const [values, setValues] = useState<FormValues>(() => ({
    ...INITIAL_VALUES,
    ingredientId: searchParams.get("ingredient_id") ?? "",
  }));
  const [fieldErrors, setFieldErrors] = useState<InventoryFormErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);
  const submittingRef = useRef(false);

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
    setError(null);
    setSuccess(null);
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

    if (!values.supplierName.trim()) {
      errors.supplierName = "Introduce el nombre del proveedor.";
    }

    const locationId = Number(values.locationId);
    if (!LOCATION_IDS.some((id) => id === locationId)) {
      errors.locationId = "Selecciona un local.";
    }

    return errors;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submittingRef.current) return;
    setError(null);
    setSuccess(null);

    const validationErrors = validate();
    if (Object.keys(validationErrors).length) {
      setFieldErrors(validationErrors);
      setError("Revisa los campos señalados antes de registrar la entrada.");
      return;
    }

    const ingredient = ingredients.find(
      (item) => String(item.id) === values.ingredientId,
    );
    if (!ingredient) return;

    setFieldErrors({});
    submittingRef.current = true;
    setIsSubmitting(true);

    const input: InboundOrderInput = {
      ingredient_id: ingredient.id,
      quantity: Number(values.quantity),
      supplier_name: values.supplierName.trim(),
      location_id: Number(values.locationId),
    };

    try {
      await createInboundOrder(input);
      const unit = ingredient.unit === "kg"
        ? "kg"
        : ingredient.unit === "litro"
          ? input.quantity === 1 ? "litro" : "litros"
          : input.quantity === 1 ? "unidad" : "unidades";
      setValues(INITIAL_VALUES);
      setFieldErrors({});
      setSuccess(
        `Entrada registrada: ${quantityFormatter.format(input.quantity)} ${unit} de ${ingredient.name} (Local ${input.location_id}, proveedor ${input.supplier_name}).`,
      );
    } catch (caught) {
      setError(caught instanceof InventoryServiceError || caught instanceof Error
        ? caught.message
        : "No se pudo registrar la entrada. Inténtalo de nuevo.");
    } finally {
      submittingRef.current = false;
      setIsSubmitting(false);
    }
  }

  function fieldDescription(field: InventoryFormField, extraId?: string) {
    const ids = [fieldErrors[field] ? `${field}-error` : null, extraId]
      .filter(Boolean)
      .join(" ");
    return ids || undefined;
  }

  const selectedIngredient = ingredients.find(
    (ingredient) => String(ingredient.id) === values.ingredientId,
  );

  return (
    <section
      className="rounded-2xl border border-orange-200 bg-white p-5 shadow-sm sm:p-8"
      aria-labelledby="inventory-inbound-title"
    >
      <h2 id="inventory-inbound-title" className="mb-5 text-xl font-bold">
        Datos de la entrada
      </h2>

      <form ref={formRef} noValidate onSubmit={submit}>
        <fieldset
          disabled={isSubmitting}
          className="grid gap-5 disabled:opacity-70 sm:grid-cols-2"
          aria-busy={isSubmitting}
        >
          <legend className="sr-only">Formulario de orden de entrada</legend>

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
              <span role="alert" className="grid gap-2 font-normal text-red-800">
                <span>{ingredientsError}</span>
                <button
                  type="button"
                  onClick={retry}
                  className="min-h-11 w-fit rounded border border-red-800 px-3 font-semibold underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2"
                >
                  Reintentar
                </button>
              </span>
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
              aria-invalid={Boolean(fieldErrors.quantity)}
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
          </label>

          <label className="grid gap-2 font-semibold" htmlFor="supplierName">
            Proveedor *
            <input
              id="supplierName"
              name="supplierName"
              type="text"
              list="inventory-supplier-suggestions"
              value={values.supplierName}
              onChange={(event) => updateField("supplierName", event.target.value)}
              className={fieldClass}
              required
              aria-invalid={Boolean(fieldErrors.supplierName)}
              aria-describedby={fieldDescription("supplierName")}
            />
            <datalist id="inventory-supplier-suggestions">
              {SUPPLIER_SUGGESTIONS.map((supplier) => (
                <option key={supplier} value={supplier} />
              ))}
            </datalist>
            {fieldErrors.supplierName && (
              <span id="supplierName-error" className="font-normal text-red-800">
                {fieldErrors.supplierName}
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

          <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
            <button
              type="submit"
              disabled={isSubmitting || loading || Boolean(ingredientsError) || ingredients.length === 0}
              className="inline-flex min-h-11 items-center justify-center rounded-lg bg-orange-700 px-5 font-semibold text-white hover:bg-orange-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSubmitting ? "Registrando entrada…" : "Registrar entrada"}
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
            <span>{success}</span>
            <Link
              href="/inventory/products"
              className="w-fit font-semibold underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2"
            >
              Ver inventario
            </Link>
          </p>
        )}
      </form>
    </section>
  );
}