"use client";

import { useRef, useState } from "react";

import { useIncidentList } from "@/hooks/use-incidents";
import {
  IncidentServiceError,
  updateIncidentStatus,
} from "@/services/incidents";
import {
  getIncidentOptionLabel,
  INCIDENT_BRANCHES,
  INCIDENT_CATEGORIES,
  INCIDENT_ORIGINS,
  INCIDENT_STATUSES,
  INCIDENT_STATUS_TRANSITIONS,
  type Incident,
  type IncidentBranch,
  type IncidentOrigin,
  type IncidentStatus,
} from "@/types/incident";

function displayDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Fecha no disponible";
  return new Intl.DateTimeFormat("es-CO", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function StatusAction({
  incident,
  disabled,
  onChange,
}: {
  incident: Incident;
  disabled: boolean;
  onChange: (status: IncidentStatus) => void;
}) {
  const [selected, setSelected] = useState("");
  const options = INCIDENT_STATUS_TRANSITIONS[incident.status];

  if (options.length === 0) {
    return <p className="text-sm text-gray-600">Estado final</p>;
  }

  return (
    <label className="grid min-w-0 gap-2 font-semibold" htmlFor={`incident-status-${incident.id}`}>
      Cambiar estado
      <select
        id={`incident-status-${incident.id}`}
        value={selected}
        disabled={disabled}
        onChange={(event) => {
          const next = options.find((value) => value === event.target.value);
          setSelected("");
          if (next) onChange(next);
        }}
        className="min-h-11 w-full rounded-lg border border-gray-400 bg-white px-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-700 disabled:opacity-60"
      >
        <option value="">Selecciona una acción</option>
        {options.map((status) => (
          <option key={status} value={status}>
            {getIncidentOptionLabel(INCIDENT_STATUSES, status)}
          </option>
        ))}
      </select>
    </label>
  );
}

export default function IncidentList() {
  const [status, setStatus] = useState<IncidentStatus | "">("");
  const [origin, setOrigin] = useState<IncidentOrigin | "">("");
  const [branch, setBranch] = useState<IncidentBranch | "">("");
  const [pendingIds, setPendingIds] = useState<Set<number>>(() => new Set());
  const [rowErrors, setRowErrors] = useState<Record<number, string>>({});
  const pendingRef = useRef(new Set<number>());
  const filters = {
    ...(status ? { status } : {}),
    ...(origin ? { origin } : {}),
    ...(branch ? { branch } : {}),
  };
  const { incidents, loading, error, retry, replaceIncident } = useIncidentList(filters);
  const hasFilters = Boolean(status || origin || branch);

  async function changeStatus(incident: Incident, nextStatus: IncidentStatus) {
    if (pendingRef.current.has(incident.id)) return;
    pendingRef.current.add(incident.id);
    setPendingIds((current) => new Set(current).add(incident.id));
    setRowErrors((current) => {
      const next = { ...current };
      delete next[incident.id];
      return next;
    });

    replaceIncident({ ...incident, status: nextStatus });
    try {
      replaceIncident(await updateIncidentStatus(incident.id, nextStatus));
    } catch (caught) {
      replaceIncident(incident);
      const message = caught instanceof IncidentServiceError
        ? caught.fieldErrors.status ?? caught.message
        : "No se pudo cambiar el estado. Inténtalo de nuevo.";
      setRowErrors((current) => ({ ...current, [incident.id]: message }));
    } finally {
      pendingRef.current.delete(incident.id);
      setPendingIds((current) => {
        const next = new Set(current);
        next.delete(incident.id);
        return next;
      });
    }
  }

  return (
    <section className="grid min-w-0 gap-4" aria-labelledby="incident-list-title">
      <div className="grid gap-4 rounded-2xl border border-gray-200 bg-white p-5 sm:grid-cols-3 sm:p-6">
        <label className="grid gap-2 font-semibold" htmlFor="filter-incident-status">
          Estado
          <select
            id="filter-incident-status"
            value={status}
            onChange={(event) => setStatus(
              INCIDENT_STATUSES.find((option) => option.value === event.target.value)?.value ?? "",
            )}
            className="min-h-11 w-full rounded-lg border border-gray-400 bg-white px-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-700"
          >
            <option value="">Todos los estados</option>
            {INCIDENT_STATUSES.map(({ value, label }) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <label className="grid gap-2 font-semibold" htmlFor="filter-incident-origin">
          Origen
          <select
            id="filter-incident-origin"
            value={origin}
            onChange={(event) => setOrigin(
              INCIDENT_ORIGINS.find((option) => option.value === event.target.value)?.value ?? "",
            )}
            className="min-h-11 w-full rounded-lg border border-gray-400 bg-white px-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-700"
          >
            <option value="">Todos los orígenes</option>
            {INCIDENT_ORIGINS.map(({ value, label }) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <label className="grid gap-2 font-semibold" htmlFor="filter-incident-branch">
          Sede
          <select
            id="filter-incident-branch"
            value={branch}
            onChange={(event) => setBranch(
              INCIDENT_BRANCHES.find((option) => option.value === event.target.value)?.value ?? "",
            )}
            className="min-h-11 w-full rounded-lg border border-gray-400 bg-white px-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-700"
          >
            <option value="">Todas las sedes</option>
            {INCIDENT_BRANCHES.map(({ value, label }) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
      </div>

      <section
        className="min-w-0 rounded-2xl border border-gray-200 bg-white p-5 sm:p-6"
        aria-labelledby="incident-list-title"
        aria-busy={loading}
      >
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="incident-list-title" className="text-xl font-bold">
            Incidencias
          </h2>
          <p role="status" className="text-sm text-gray-600">
            {loading
              ? "Cargando incidencias…"
              : error
                ? "No se pudo cargar el listado."
                : `${incidents.length} incidencias`}
          </p>
        </div>

        {loading && (
          <p role="status" className="rounded-lg bg-gray-50 p-4 text-gray-700">
            Cargando listado…
          </p>
        )}
        {!loading && error && (
          <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-4 text-red-900">
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
        {!loading && !error && incidents.length === 0 && (
          <p className="rounded-lg bg-gray-50 p-4 text-gray-700">
            {hasFilters
              ? "Ninguna incidencia coincide con los filtros seleccionados."
              : "Todavía no hay incidencias registradas."}
          </p>
        )}

        {!loading && !error && incidents.length > 0 && (
          <ul className="grid min-w-0 gap-4">
            {incidents.map((incident) => (
              <li key={incident.id} className="min-w-0">
                <article className="grid min-w-0 gap-4 rounded-xl border border-gray-200 p-4 sm:p-5">
                  <header className="flex min-w-0 flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="break-words text-lg font-bold">{incident.title}</h3>
                      <p className="mt-2 break-words text-gray-700">{incident.description}</p>
                    </div>
                    <span className="inline-flex min-h-8 shrink-0 items-center rounded-full bg-orange-100 px-3 py-1 text-sm font-semibold text-orange-950">
                      {getIncidentOptionLabel(INCIDENT_STATUSES, incident.status)}
                    </span>
                  </header>

                  <dl className="grid min-w-0 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    <div className="min-w-0">
                      <dt className="text-sm font-semibold text-gray-600">Categoría</dt>
                      <dd className="break-words">{getIncidentOptionLabel(INCIDENT_CATEGORIES, incident.category)}</dd>
                    </div>
                    <div className="min-w-0">
                      <dt className="text-sm font-semibold text-gray-600">Origen</dt>
                      <dd>{getIncidentOptionLabel(INCIDENT_ORIGINS, incident.origin)}</dd>
                    </div>
                    <div className="min-w-0">
                      <dt className="text-sm font-semibold text-gray-600">Sede</dt>
                      <dd className="break-words">{getIncidentOptionLabel(INCIDENT_BRANCHES, incident.branch)}</dd>
                    </div>
                    <div className="min-w-0">
                      <dt className="text-sm font-semibold text-gray-600">Fecha de registro</dt>
                      <dd>{displayDate(incident.created_at)}</dd>
                    </div>
                  </dl>

                  <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(14rem,0.7fr)] sm:items-end">
                    <StatusAction
                      incident={incident}
                      disabled={pendingIds.has(incident.id)}
                      onChange={(nextStatus) => void changeStatus(incident, nextStatus)}
                    />
                    {pendingIds.has(incident.id) && (
                      <p role="status" className="text-sm text-gray-700">
                        Actualizando estado…
                      </p>
                    )}
                  </div>
                  {rowErrors[incident.id] && (
                    <p role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-red-900">
                      {rowErrors[incident.id]}
                    </p>
                  )}
                </article>
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}
