"use client";

import type { ReactNode } from "react";

import type { TelemetryReport } from "@/types/telemetry-report";

interface TelemetryReportViewProps {
  report: TelemetryReport | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

const numberFormatter = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1 });
const percentFormatter = new Intl.NumberFormat("es-ES", {
  style: "percent",
  maximumFractionDigits: 1,
});
const instantFormatter = new Intl.DateTimeFormat("es-ES", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
});

function formatInstant(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : `${instantFormatter.format(date)} UTC`;
}

const sectionClass = "grid gap-3 rounded-lg border border-gray-200 bg-white p-4 sm:p-6";
const tableWrapperClass = "min-w-0 overflow-x-auto";
const tableClass = "w-full min-w-[480px] border-collapse text-left text-sm text-gray-800";
const headClass = "bg-gray-100 text-xs uppercase text-gray-700";
const cellClass = "px-4 py-3";

function MetricSection({
  id,
  title,
  question,
  empty,
  children,
}: {
  id: string;
  title: string;
  question: string;
  empty: boolean;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className={sectionClass}>
      <div>
        <h2 id={id} className="text-xl font-bold">{title}</h2>
        <p className="text-sm text-gray-700">{question}</p>
      </div>
      {empty ? (
        <p role="status" className="text-gray-700">Sin datos en este período.</p>
      ) : (
        <div className={tableWrapperClass}>{children}</div>
      )}
    </section>
  );
}

export default function TelemetryReportView({
  report,
  loading,
  error,
  onRetry,
}: TelemetryReportViewProps) {
  if (loading) {
    return (
      <p role="status" className="rounded-lg border border-gray-200 bg-white p-5 text-gray-700">
        Cargando el reporte técnico...
      </p>
    );
  }

  if (error) {
    return (
      <div role="alert" className="grid gap-3 rounded-lg border border-red-300 bg-red-50 p-5 text-red-950">
        <p>{error}</p>
        <button
          type="button"
          onClick={onRetry}
          className="min-h-11 w-fit rounded border border-red-800 px-4 font-semibold underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2"
        >
          Reintentar
        </button>
      </div>
    );
  }

  if (!report) return null;

  const { metrics } = report;
  const maxEvents = metrics.events_per_day.reduce((max, row) => Math.max(max, row.events), 1);

  return (
    <div className="grid min-w-0 gap-6">
      <p className="rounded-lg border border-gray-200 bg-white p-4 text-gray-800">
        <span className="font-semibold">Período:</span>{" "}
        <time dateTime={report.period.from}>{formatInstant(report.period.from)}</time>
        {" → "}
        <time dateTime={report.period.to}>{formatInstant(report.period.to)}</time>
        {" (inicio incluido, fin excluido)"}
      </p>

      <MetricSection
        id="events-per-day"
        title="Eventos por día y tipo"
        question="¿Qué eventos ocurren y con qué frecuencia?"
        empty={metrics.events_per_day.length === 0}
      >
        <table className={tableClass}>
          <caption className="sr-only">Volumen de eventos por día y tipo de evento</caption>
          <thead className={headClass}>
            <tr>
              <th scope="col" className={cellClass}>Día (UTC)</th>
              <th scope="col" className={cellClass}>Tipo de evento</th>
              <th scope="col" className={cellClass}>Eventos</th>
              <th scope="col" className={cellClass}>Volumen</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {metrics.events_per_day.map((row) => (
              <tr key={`${row.date}-${row.event_type}`}>
                <td className={cellClass}>{row.date}</td>
                <td className={cellClass}>{row.event_type}</td>
                <td className={cellClass}>{numberFormatter.format(row.events)}</td>
                <td className={cellClass}>
                  <progress
                    className="h-2 w-full"
                    value={row.events}
                    max={maxEvents}
                    aria-label={`${row.events} eventos ${row.event_type} el ${row.date}`}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </MetricSection>

      <MetricSection
        id="error-rate-by-day"
        title="Tasa de errores por día"
        question="¿Qué tan sano está el sistema cada día? Errores y avisos sobre el total de eventos."
        empty={metrics.error_rate_by_day.length === 0}
      >
        <table className={tableClass}>
          <caption className="sr-only">Tasa de errores y avisos por día</caption>
          <thead className={headClass}>
            <tr>
              <th scope="col" className={cellClass}>Día (UTC)</th>
              <th scope="col" className={cellClass}>Eventos</th>
              <th scope="col" className={cellClass}>Errores</th>
              <th scope="col" className={cellClass}>Avisos</th>
              <th scope="col" className={cellClass}>Tasa de error</th>
              <th scope="col" className={cellClass}>Tasa de incidencias</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {metrics.error_rate_by_day.map((row) => (
              <tr key={row.date}>
                <td className={cellClass}>{row.date}</td>
                <td className={cellClass}>{numberFormatter.format(row.events)}</td>
                <td className={cellClass}>{numberFormatter.format(row.errors)}</td>
                <td className={cellClass}>{numberFormatter.format(row.warnings)}</td>
                <td className={cellClass}>{percentFormatter.format(row.error_rate)}</td>
                <td className={cellClass}>{percentFormatter.format(row.problem_rate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </MetricSection>

      <MetricSection
        id="error-rate-by-type"
        title="Tasa de incidencias por tipo de evento"
        question="¿Qué tipos de evento señalan problemas? Errores y avisos sobre el total de cada tipo."
        empty={metrics.error_rate_by_type.length === 0}
      >
        <table className={tableClass}>
          <caption className="sr-only">Tasa de errores y avisos por tipo de evento</caption>
          <thead className={headClass}>
            <tr>
              <th scope="col" className={cellClass}>Tipo de evento</th>
              <th scope="col" className={cellClass}>Eventos</th>
              <th scope="col" className={cellClass}>Errores</th>
              <th scope="col" className={cellClass}>Avisos</th>
              <th scope="col" className={cellClass}>Tasa de incidencias</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {metrics.error_rate_by_type.map((row) => (
              <tr key={row.event_type}>
                <td className={cellClass}>{row.event_type}</td>
                <td className={cellClass}>{numberFormatter.format(row.events)}</td>
                <td className={cellClass}>{numberFormatter.format(row.errors)}</td>
                <td className={cellClass}>{numberFormatter.format(row.warnings)}</td>
                <td className={cellClass}>{percentFormatter.format(row.problem_rate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </MetricSection>

      <MetricSection
        id="page-load"
        title="Tiempo de carga por pantalla"
        question="¿Qué tan rápido cargan las pantallas? Media y percentil 95 por día y ruta."
        empty={metrics.page_load_ms_by_route.length === 0}
      >
        <table className={tableClass}>
          <caption className="sr-only">Tiempo de carga por día y ruta</caption>
          <thead className={headClass}>
            <tr>
              <th scope="col" className={cellClass}>Día (UTC)</th>
              <th scope="col" className={cellClass}>Ruta</th>
              <th scope="col" className={cellClass}>Muestras</th>
              <th scope="col" className={cellClass}>Media (ms)</th>
              <th scope="col" className={cellClass}>p95 (ms)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {metrics.page_load_ms_by_route.map((row) => (
              <tr key={`${row.date}-${row.route}`}>
                <td className={cellClass}>{row.date}</td>
                <td className={cellClass}>{row.route}</td>
                <td className={cellClass}>{numberFormatter.format(row.samples)}</td>
                <td className={cellClass}>{numberFormatter.format(row.avg_ms)}</td>
                <td className={cellClass}>{numberFormatter.format(row.p95_ms)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </MetricSection>

      <MetricSection
        id="auth-failure-rate"
        title="Fallos de inicio de sesión por día"
        question="¿Con qué frecuencia falla el login? Intentos fallidos sobre el total de intentos."
        empty={metrics.auth_failure_rate.length === 0}
      >
        <table className={tableClass}>
          <caption className="sr-only">Tasa diaria de fallos de inicio de sesión</caption>
          <thead className={headClass}>
            <tr>
              <th scope="col" className={cellClass}>Día (UTC)</th>
              <th scope="col" className={cellClass}>Intentos</th>
              <th scope="col" className={cellClass}>Fallidos</th>
              <th scope="col" className={cellClass}>Tasa de fallos</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {metrics.auth_failure_rate.map((row) => (
              <tr key={row.date}>
                <td className={cellClass}>{row.date}</td>
                <td className={cellClass}>{numberFormatter.format(row.attempts)}</td>
                <td className={cellClass}>{numberFormatter.format(row.failures)}</td>
                <td className={cellClass}>{percentFormatter.format(row.failure_rate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </MetricSection>
    </div>
  );
}
