"use client";

import { useState, type FormEvent } from "react";

import { createSupplier } from "@/services/suppliers";
import {
  SUPPLIER_CATEGORIES, SUPPLIER_CATEGORY_LABELS, SUPPLIER_COUNTRIES,
  SupplierStatus, type Supplier,
} from "@/types/supplier";

const fieldClass = "min-h-11 w-full rounded-lg border border-gray-400 bg-white px-3 py-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-700";

export default function CreateSupplierForm({ onSaved }: { onSaved: (supplier: Supplier) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const name = String(data.get("name") ?? "").trim();
    const country = SUPPLIER_COUNTRIES.find((value) => value === data.get("country"));
    const categories = SUPPLIER_CATEGORIES.filter((value) => data.getAll("categories").includes(value));
    const rate = Number(data.get("rate_per_unit"));
    const currency = data.get("currency");
    const status = data.get("status");
    const email = String(data.get("contact_email") ?? "").trim();
    setError(null);
    setSuccess(null);
    if (!name) return setError("Introduce el nombre del proveedor.");
    if (!country) return setError("Selecciona el país del proveedor.");
    if (!categories.length) return setError("Selecciona al menos una categoría.");
    if (!Number.isFinite(rate) || rate <= 0) return setError("La tarifa debe ser un número mayor que cero.");
    if (currency !== "COP" && currency !== "USD") return setError("Selecciona una moneda válida.");
    if (currency !== (country === "Colombia" ? "COP" : "USD")) {
      return setError(`Para ${country}, la moneda debe ser ${country === "Colombia" ? "COP" : "USD"}.`);
    }
    if (status !== SupplierStatus.Active && status !== SupplierStatus.Suspended) return setError("Selecciona un estado válido.");
    const emailInput = form.elements.namedItem("contact_email");
    if (email && emailInput instanceof HTMLInputElement && !emailInput.validity.valid) {
      return setError("Introduce un correo de contacto válido, por ejemplo compras@empresa.com.");
    }
    setBusy(true);
    try {
      const supplier = await createSupplier({
        name, country, categories, rate_per_unit: rate, currency, status,
        ...(email ? { contact_email: email } : {}),
        ...(String(data.get("notes") ?? "").trim() ? { notes: String(data.get("notes")).trim() } : {}),
      });
      onSaved(supplier);
      form.reset();
      setSuccess(`Proveedor ${supplier.name} creado correctamente. Si hay filtros activos, solo aparecerá si coincide con ellos.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo crear el proveedor.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-5" aria-labelledby="create-supplier-title">
      <h2 id="create-supplier-title" className="mb-4 text-xl font-bold">Nuevo proveedor</h2>
      <form noValidate onSubmit={submit} onReset={() => { setError(null); setSuccess(null); }}>
        <fieldset disabled={busy} className="grid gap-4 disabled:opacity-70 sm:grid-cols-2" aria-describedby={error ? "supplier-create-error" : undefined}>
          <legend className="sr-only">Datos del nuevo proveedor</legend>
          <label className="grid gap-2 font-semibold">Nombre *
            <input name="name" required className={fieldClass} />
          </label>
          <label className="grid gap-2 font-semibold">País del nuevo proveedor *
            <select name="country" required className={fieldClass} defaultValue="Colombia">
              {SUPPLIER_COUNTRIES.map((country) => <option key={country}>{country}</option>)}
            </select>
          </label>
          <fieldset className="grid gap-2 rounded-lg border border-gray-300 p-3 sm:col-span-2">
            <legend className="px-1 font-semibold">Categorías * (selecciona una o varias)</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              {SUPPLIER_CATEGORIES.map((category) => (
                <label key={category} className="flex min-h-9 items-center gap-2">
                  <input type="checkbox" name="categories" value={category} className="size-4 accent-orange-700 focus-visible:outline-2 focus-visible:outline-offset-2" />
                  {SUPPLIER_CATEGORY_LABELS[category]}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="grid gap-2 font-semibold">Tarifa por unidad *
            <input name="rate_per_unit" type="number" step="any" required className={fieldClass} />
          </label>
          <label className="grid gap-2 font-semibold">Moneda *
            <select name="currency" defaultValue="COP" className={fieldClass} required>
              <option value="COP">COP · Colombia</option><option value="USD">USD · USA</option>
            </select>
          </label>
          <label className="grid gap-2 font-semibold">Estado inicial *
            <select name="status" defaultValue={SupplierStatus.Active} className={fieldClass} required>
              <option value={SupplierStatus.Active}>Activo</option><option value={SupplierStatus.Suspended}>Suspendido</option>
            </select>
          </label>
          <label className="grid gap-2 font-semibold">Correo de contacto (opcional)
            <input name="contact_email" type="email" className={fieldClass} />
          </label>
          <label className="grid gap-2 font-semibold sm:col-span-2">Notas (opcional)
            <textarea name="notes" rows={3} className={fieldClass} />
          </label>
          <div className="flex flex-wrap gap-3 sm:col-span-2">
            <button type="submit" className="min-h-11 rounded-lg bg-orange-700 px-4 font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-2">
              {busy ? "Creando…" : "Crear proveedor"}
            </button>
            <button type="reset" className="min-h-11 rounded-lg border border-gray-400 px-4 focus-visible:outline-2 focus-visible:outline-offset-2">Limpiar formulario</button>
          </div>
        </fieldset>
        {error && <p id="supplier-create-error" role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-red-900">{error}</p>}
        {success && <p role="status" className="mt-4 rounded-lg bg-green-50 p-3 text-green-900">{success}</p>}
      </form>
    </section>
  );
}
