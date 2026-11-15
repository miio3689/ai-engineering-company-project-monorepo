"use client";

import dynamic from "next/dynamic";
import { useState } from "react";

import { updateSupplierRate, updateSupplierStatus } from "@/services/suppliers";
import { SupplierStatus, type Supplier } from "@/types/supplier";

const SupplierRateEditor = dynamic(() => import("@/components/supplier-rate-editor"), {
  loading: () => (
    <div className="grid min-h-[11.25rem] min-w-48 content-start gap-2" role="status" aria-busy="true">
      <span className="sr-only">Cargando editor de tarifa…</span>
    </div>
  ),
});

export default function SupplierActions({ supplier, onSaved }: {
  supplier: Supplier;
  onSaved: (supplier: Supplier) => void;
}) {
  const [editing, setEditing] = useState(false);
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

  return (
    <div className="grid min-w-48 gap-2">
      {editing ? (
        <SupplierRateEditor
          supplier={supplier}
          busy={busy}
          error={error}
          buttonClass={buttonClass}
          onCancel={() => { setEditing(false); setError(null); }}
          onInvalid={() => {
            setSuccess(null);
            setError("La tarifa debe ser un número mayor que cero.");
          }}
          onSubmit={(rate) => void save(
            () => updateSupplierRate(supplier.id, rate),
            "Tarifa actualizada.",
          )}
        />
      ) : (
        <button type="button" disabled={busy} className={buttonClass}
          aria-label={`Editar tarifa de ${supplier.name}`}
          onClick={() => { setEditing(true); setError(null); setSuccess(null); }}>
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
