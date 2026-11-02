"use client";

import { useIncidentSummary } from "@/hooks/use-incidents";
import {
  getIncidentOptionLabel,
  INCIDENT_BRANCHES,
  INCIDENT_CATEGORIES,
  INCIDENT_ORIGINS,
  INCIDENT_STATUSES,
} from "@/types/incident";

function Breakdown<T extends string>({
  title,
  options,
  counts,
}: {
  title: string;
  options: readonly { value: T; label: string }[];
  counts: Readonly<Record<T, number>>;
}) {
  return (
    <section className="min-w-0 rounded-xl border border-gray-200 bg-white p-4 sm:p-5">
      <h3 className="mb-3 text-lg font-bold">{title}</h3>
      <ul className="grid gap-2">
        {options.map(({ value }) => (
          <li
            key={value}
            className="flex min-h-10 items-center justify-between gap-3 border-b border-gray-100 py-2 last:border-0"
          >
            <span className="break-words">{getIncidentOptionLabel(options, value)}</span>
            <strong className="shrink-0 tabular-nums">{counts[value]}</strong>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function IncidentSummary() {
  const { summary, loading, error, retry } = useIncidentSummary();

  return (
    <section
      className="grid min-w-0 gap-4"
      aria-labelledby="incident-summary-title"
      aria-busy={loading}
    >
      <header className="rounded-2xl border border-orange-200 bg-orange-50 p-5 sm:p-7">
        <h2 id="incident-summary-title" className="text-xl font-bold">
          Resumen de incidencias
        </h2>
        <p className="mt-2 text-gray-700">
          Totales por estado, categoría, origen y sede.
        </p>
      </header>

      {loading && (
        <p role="status" className="rounded-xl border border-gray-200 bg-white p-4 text-gray-700">
          Cargando resumen…
        </p>
      )}

      {!loading && error && (
        <div role="alert" className="rounded-xl border border-red-300 bg-red-50 p-4 text-red-900">
          <p>{error}</p>
          <button
            type="button"
            onClick={retry}
            className="mt-3 min-h-11 rounded-lg border border-red-700 px-4 font-semibold underline focus-visible:outline-2 focus-visible:outline-offset-2"
          >
            Reintentar
          </button>
        </div>
      )}

      {!loading && summary && (
        <>
          <article className="rounded-2xl border border-orange-300 bg-white p-5 shadow-sm">
            <p className="text-sm font-semibold text-orange-800">Total general</p>
            <strong className="mt-1 block text-4xl tabular-nums">{summary.total}</strong>
          </article>
          <div className="grid min-w-0 gap-4 md:grid-cols-2">
            <Breakdown
              title="Por estado"
              options={INCIDENT_STATUSES}
              counts={summary.by_status}
            />
            <Breakdown
              title="Por categoría"
              options={INCIDENT_CATEGORIES}
              counts={summary.by_category}
            />
            <Breakdown
              title="Por origen"
              options={INCIDENT_ORIGINS}
              counts={summary.by_origin}
            />
            <Breakdown
              title="Por sede"
              options={INCIDENT_BRANCHES}
              counts={summary.by_branch}
            />
          </div>
        </>
      )}
    </section>
  );
}
