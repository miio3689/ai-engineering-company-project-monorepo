"use client";

import { useState, type FormEvent } from "react";

import type { Supplier } from "@/types/supplier";

interface SupplierRateEditorProps {
  supplier: Supplier;
  busy: boolean;
  error: string | null;
  buttonClass: string;
  onCancel: () => void;
  onInvalid: () => void;
  onSubmit: (rate: number) => void;
}

export default function SupplierRateEditor({
  supplier,
  busy,
  error,
  buttonClass,
  onCancel,
  onInvalid,
  onSubmit,
}: SupplierRateEditorProps) {
  const [rate, setRate] = useState(String(supplier.rate_per_unit));

  function submitRate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = Number(rate);
    if (!rate.trim() || !Number.isFinite(value) || value <= 0) {
      onInvalid();
      return;
    }
    onSubmit(value);
  }

  return (
    <form noValidate onSubmit={submitRate} className="grid gap-2">
      <label htmlFor={`supplier-rate-${supplier.id}`}>Nueva tarifa ({supplier.currency})</label>
      <input id={`supplier-rate-${supplier.id}`} type="number" step="any" required
        value={rate} onChange={(event) => setRate(event.target.value)} disabled={busy}
        aria-invalid={Boolean(error)} aria-describedby={error ? `supplier-action-error-${supplier.id}` : undefined}
        className="min-h-11 w-full rounded-lg border border-gray-400 px-3 focus-visible:outline-2 focus-visible:outline-offset-2" />
      <button type="submit" disabled={busy} className={buttonClass}>Guardar tarifa</button>
      <button type="button" disabled={busy} className={buttonClass} onClick={onCancel}>Cancelar</button>
    </form>
  );
}
