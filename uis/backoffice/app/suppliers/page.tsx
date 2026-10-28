import type { Metadata } from "next";
import Link from "next/link";

import SupplierDirectory from "@/components/supplier-directory";

export const metadata: Metadata = {
  title: "Directorio de proveedores | Brasaland",
  description: "Consulta proveedores, tarifas y estados por país y categoría.",
};

export default function SuppliersPage() {
  return (
    <main className="mx-auto my-6 grid w-[92%] max-w-6xl gap-6 text-gray-800 sm:my-10" itemScope itemType="https://schema.org/CollectionPage">
      <nav className="flex flex-wrap gap-4 text-sm" aria-label="Navegación principal">
        <Link className="rounded underline focus-visible:outline-2 focus-visible:outline-offset-4" href="/">
          ← Listado de candidaturas
        </Link>
        <Link className="rounded underline focus-visible:outline-2 focus-visible:outline-offset-4" href="/incidents">
          Análisis de incidencias
        </Link>
        <span aria-current="page">Proveedores</span>
      </nav>
      <SupplierDirectory />
    </main>
  );
}
