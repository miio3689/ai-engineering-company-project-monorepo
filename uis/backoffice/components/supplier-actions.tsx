"use client";

import { useState, type FormEvent } from "react";

import { updateSupplierRate, updateSupplierStatus } from "@/services/suppliers";
import { SupplierStatus, type Supplier } from "@/types/supplier";

export default function SupplierActions({ supplier, onSaved }: {
  supplier: Supplier;
  onSaved: (supplier: Supplier) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [rate, setRate] = useState(String(supplier.rate_per_unit));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const buttonClass = "min-h-11 rounded-lg border border-gray-400 px-3 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-60";

  async function save(operation: () => Promise<Supplier>, message: string) {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const updated = await operation();
      onSaved(updated);
      setEditing(false);
      setSuccess(message);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo actualizar el proveedor.");
    } finally {
      setBusy(false);
    }
  }

  function submitRate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = Number(rate);
    if (!rate.trim() || !Number.isFinite(value) || value <= 0) {
      setSuccess(null);
      setError("La tarifa debe ser un número mayor que cero.");
      return;
    }
    void save(() => updateSupplierRate(supplier.id, value), "Tarifa actualizada.");
  }

  return (
    <div className="grid min-w-48 gap-2">
      {editing ? (
        <form noValidate onSubmit={submitRate} className="grid gap-2">
          <label htmlFor={`supplier-rate-${supplier.id}`}>Nueva tarifa ({supplier.currency})</label>
          <input id={`supplier-rate-${supplier.id}`} type="number" step="any" required
            value={rate} onChange={(event) => setRate(event.target.value)} disabled={busy}
            aria-invalid={Boolean(error)} aria-describedby={error ? `supplier-action-error-${supplier.id}` : undefined}
            className="min-h-11 w-full rounded-lg border border-gray-400 px-3 focus-visible:outline-2 focus-visible:outline-offset-2" />
          <button type="submit" disabled={busy} className={buttonClass}>Guardar tarifa</button>
          <button type="button" disabled={busy} className={buttonClass} onClick={() => { setEditing(false); setError(null); }}>Cancelar</button>
        </form>
      ) : (
        <button type="button" disabled={busy} className={buttonClass}
          aria-label={`Editar tarifa de ${supplier.name}`}
          onClick={() => { setRate(String(supplier.rate_per_unit)); setEditing(true); setError(null); setSuccess(null); }}>
          Editar tarifa
        </button>
      )}
      <button type="button" disabled={busy} className={buttonClass}
        aria-label={`${supplier.status === SupplierStatus.Active ? "Suspender" : "Activar"} a ${supplier.name}`}
        onClick={() => void save(
          () => updateSupplierStatus(supplier.id, supplier.status === SupplierStatus.Active ? SupplierStatus.Suspended : SupplierStatus.Active),
          supplier.status === SupplierStatus.Active ? "Proveedor suspendido." : "Proveedor activado.",
        )}>
        {supplier.status === SupplierStatus.Active ? "Suspender" : "Activar"}
      </button>
      {busy && <p role="status">Guardando…</p>}
      {error && <p id={`supplier-action-error-${supplier.id}`} role="alert" className="text-sm text-red-800">{error}</p>}
      {success && <p role="status" className="text-sm text-green-900">{success}</p>}
    </div>
  );
}
