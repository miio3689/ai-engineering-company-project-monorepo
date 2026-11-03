"use client";

import Link from "next/link";

interface ErrorPageProps {
  error: Error;
  reset: () => void;
}

export default function ErrorPage({ reset }: ErrorPageProps) {
  return (
    <main className="mx-auto my-10 grid w-[92%] max-w-2xl gap-4 rounded-2xl border border-red-300 bg-red-50 p-6 text-gray-900">
      <h1 className="text-2xl font-bold">No se pudo cargar esta página</h1>
      <p>Ocurrió un problema inesperado. Inténtalo de nuevo o vuelve al inicio.</p>
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={reset}
          className="min-h-11 rounded-lg bg-orange-700 px-4 font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-2"
        >
          Reintentar
        </button>
        <Link
          href="/"
          className="inline-flex min-h-11 items-center rounded-lg border border-gray-500 px-4 font-semibold underline focus-visible:outline-2 focus-visible:outline-offset-2"
        >
          Ir a la página principal
        </Link>
      </div>
      <p>Si el problema continúa, contacta con soporte.</p>
    </main>
  );
}
