import { Suspense } from "react";

import InventoryInboundForm from "@/components/inventory-inbound-form";
import InventoryNavigation from "@/components/inventory-navigation";

export default function InventoryInboundPage() {
  return (
    <main className="mx-auto my-6 grid w-[92%] max-w-6xl min-w-0 gap-6 text-gray-800 sm:my-10">
      <header className="rounded-2xl border border-orange-200 bg-orange-50 p-5 sm:p-8">
        <p className="text-sm font-semibold text-orange-800">Brasaland · Operaciones</p>
        <h1 className="mt-2 text-2xl font-bold sm:text-3xl">Registrar orden de entrada</h1>
        <p className="mt-2 text-gray-700">
          Registra las entregas recibidas de tus proveedores.
        </p>
      </header>
      <InventoryNavigation />
      <Suspense
        fallback={(
          <p role="status" className="rounded-lg border border-gray-200 bg-white p-5 text-gray-700">
            Cargando formulario…
          </p>
        )}
      >
        <InventoryInboundForm />
      </Suspense>
    </main>
  );
}