"use client";

import {
  currentWeekStart,
  formatCount,
  formatMoney,
  formatPercent,
  formatWeekRange,
  groupByCurrency,
  locationLabel,
  shiftWeek,
  type CurrencyGroup,
} from "@/lib/business-performance";
import type {
  LocationPerformance,
  PipelineRunSummary,
  WeeklyLocationPerformance,
} from "@/types/business-performance";

type KpiKey =
  | "total_purchase_cost"
  | "total_waste_cost"
  | "waste_ratio"
  | "stockout_events_count"
  | "price_alert_events_count";

interface KpiDefinition {
  key: KpiKey;
  /** Nombre exacto del KPI en la sección "KPIs a medir" del BRIEFING. */
  name: string;
  measures: string;
  format: (value: number, currency: string) => string;
}

// Mismo orden y mismos nombres que la sección 2 del BRIEFING de Brasaland.
const KPIS: KpiDefinition[] = [
  {
    key: "total_purchase_cost",
    name: "Costo de compra por local",
    measures: "Cuánto gastó cada local comprando ingredientes a proveedores durante la semana.",
    format: formatMoney,
  },
  {
    key: "total_waste_cost",
    name: "Costo de merma por local",
    measures: "Cuánto perdió cada local por producto vencido, error de cocina o robo durante la semana.",
    format: formatMoney,
  },
  {
    key: "waste_ratio",
    name: "Ratio de merma",
    measures: "El costo de merma como proporción del costo de compra de ese local en la semana (0 % si no hubo compras).",
    format: (value) => formatPercent(value),
  },
  {
    key: "stockout_events_count",
    name: "Frecuencia de quiebre de stock",
    measures: "Cuántas veces en la semana el stock de algún ingrediente cayó por debajo del mínimo configurado.",
    format: (value) => `${formatCount(value)} ${value === 1 ? "vez" : "veces"}`,
  },
  {
    key: "price_alert_events_count",
    name: "Frecuencia de alertas de precio",
    measures: "Cuántas veces en la semana el costo de un ingrediente subió de forma anómala respecto a su histórico.",
    format: (value) => `${formatCount(value)} ${value === 1 ? "alerta" : "alertas"}`,
  },
];

const cardClass = "grid gap-4 rounded-lg border border-gray-200 bg-white p-4 sm:p-6";
const buttonClass =
  "min-h-11 rounded-lg border border-gray-400 bg-white px-4 font-semibold disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2";

const updatedFormatter = new Intl.DateTimeFormat("es-ES", {
  dateStyle: "long",
  timeStyle: "short",
  timeZone: "UTC",
});

function Freshness({ run }: { run: PipelineRunSummary | null }) {
  if (!run) return null;
  if (run.status === "running") {
    return <p className="text-sm text-gray-700">Se están actualizando los datos en este momento.</p>;
  }
  const updatedAt = run.finished_at ? new Date(run.finished_at) : null;
  return (
    <div className="grid gap-2">
      {updatedAt && !Number.isNaN(updatedAt.getTime()) && (
        <p className="text-sm text-gray-700">
          Datos actualizados el{" "}
          <time dateTime={run.finished_at ?? undefined}>{updatedFormatter.format(updatedAt)} UTC</time>.
        </p>
      )}
      {run.status === "failed" && (
        <p role="status" className="rounded bg-amber-50 p-3 text-sm text-amber-950">
          La última actualización automática no terminó. Las cifras pueden no incluir los
          movimientos más recientes; el equipo técnico ya tiene el detalle.
        </p>
      )}
    </div>
  );
}

function rankByKpi(rows: LocationPerformance[], key: KpiKey): LocationPerformance[] {
  return [...rows].sort(
    (a, b) => b[key] - a[key] || Number(a.location_id) - Number(b.location_id),
  );
}

function KpiTable({ kpi, group }: { kpi: KpiDefinition; group: CurrencyGroup }) {
  const rows = rankByKpi(group.locations, kpi.key);
  const max = Math.max(...rows.map((row) => row[kpi.key]), 0);
  const total = group.totals[kpi.key];

  return (
    <div className="grid min-w-0 gap-2">
      <h3 className="font-semibold text-gray-800">{group.label}</h3>
      {max === 0 ? (
        <p className="text-sm text-gray-700">
          Sin actividad esta semana en {group.label} para este indicador (todos los locales en 0).
        </p>
      ) : (
        <div className="min-w-0 overflow-x-auto">
          <table className="w-full min-w-[420px] border-collapse text-left text-sm text-gray-800">
            <caption className="sr-only">{`${kpi.name}, ${group.label}, de mayor a menor`}</caption>
            <thead className="bg-gray-100 text-xs uppercase text-gray-700">
              <tr>
                <th scope="col" className="px-3 py-2">Local</th>
                <th scope="col" className="px-3 py-2 text-right">{kpi.name}</th>
                <th scope="col" className="w-2/5 px-3 py-2">
                  <span className="sr-only">Comparación entre locales</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {rows.map((row) => (
                <tr key={row.location_id}>
                  <th scope="row" className="px-3 py-2 font-normal">{locationLabel(row.location_id)}</th>
                  <td className="px-3 py-2 text-right font-semibold tabular-nums">
                    {kpi.format(row[kpi.key], row.currency)}
                  </td>
                  <td className="px-3 py-2" aria-hidden="true">
                    <div className="h-3 w-full rounded bg-gray-100">
                      <div
                        className="h-3 rounded bg-orange-600"
                        style={{ width: `${max > 0 ? (row[kpi.key] / max) * 100 : 0}%` }}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="border-t-2 border-gray-300">
              <tr>
                <th scope="row" className="px-3 py-2 text-left">
                  {kpi.key === "waste_ratio" ? "Conjunto de locales" : "Total"}
                </th>
                <td className="px-3 py-2 text-right font-bold tabular-nums">
                  {kpi.format(total, group.currency)}
                </td>
                <td />
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}

function SummaryTiles({ group }: { group: CurrencyGroup }) {
  return (
    <section aria-label={`Resumen de ${group.label}`} className="grid gap-2">
      <h3 className="font-semibold text-gray-800">
        {group.label} · {group.locations.length} {group.locations.length === 1 ? "local" : "locales"}
      </h3>
      <dl className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {KPIS.map((kpi) => (
          <div key={kpi.key} className="rounded-lg border border-gray-200 bg-gray-50 p-3">
            <dt className="text-xs font-semibold text-gray-700">{kpi.name}</dt>
            <dd className="mt-1 text-lg font-bold tabular-nums">
              {kpi.format(group.totals[kpi.key], group.currency)}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

interface WeeklyPerformanceDashboardProps {
  report: WeeklyLocationPerformance | null;
  latestRun: PipelineRunSummary | null;
  loading: boolean;
  error: string | null;
  selectedWeek: string | null;
  onSelectWeek: (weekStart: string | null) => void;
  onRetry: () => void;
}

export default function WeeklyPerformanceDashboard({
  report,
  latestRun,
  loading,
  error,
  selectedWeek,
  onSelectWeek,
  onRetry,
}: WeeklyPerformanceDashboardProps) {
  if (loading) {
    return (
      <p role="status" className="rounded-lg border border-gray-200 bg-white p-5 text-gray-700">
        Cargando el reporte semanal...
      </p>
    );
  }

  if (error) {
    return (
      <div role="alert" className="grid gap-3 rounded-lg border border-red-300 bg-red-50 p-5 text-red-950">
        <p>{error}</p>
        <button type="button" onClick={onRetry} className="min-h-11 w-fit rounded border border-red-800 px-4 font-semibold underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2">
          Reintentar
        </button>
      </div>
    );
  }

  if (!report) return null;

  if (!report.week_start) {
    return (
      <p role="status" className="rounded-lg border border-gray-200 bg-white p-5 text-gray-700">
        Todavía no hay ninguna semana calculada. El reporte se genera automáticamente cada lunes
        por la mañana.
      </p>
    );
  }

  const week = report.week_start;
  const groups = groupByCurrency(report.locations);
  const nextWeek = shiftWeek(week, 1);
  const isCurrentWeek = week === currentWeekStart();

  return (
    <div className="grid min-w-0 gap-6">
      <section aria-labelledby="report-period" className={cardClass}>
        <div className="grid gap-1">
          <p className="text-sm font-semibold text-gray-700">Período del reporte</p>
          <h2 id="report-period" className="text-xl font-bold sm:text-2xl">
            Semana del {formatWeekRange(week)}
          </h2>
          {isCurrentWeek && (
            <p className="text-sm text-amber-900">
              Semana en curso: las cifras todavía pueden cambiar hasta el domingo.
            </p>
          )}
          <Freshness run={latestRun} />
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className={buttonClass} onClick={() => onSelectWeek(shiftWeek(week, -1))}>
            ← Semana anterior
          </button>
          <button
            type="button"
            className={buttonClass}
            disabled={nextWeek > currentWeekStart()}
            onClick={() => onSelectWeek(nextWeek)}
          >
            Semana siguiente →
          </button>
          {selectedWeek !== null && (
            <button type="button" className={buttonClass} onClick={() => onSelectWeek(null)}>
              Última semana cerrada
            </button>
          )}
        </div>
      </section>

      {groups.length === 0 ? (
        <p role="status" className="rounded-lg border border-gray-200 bg-white p-5 text-gray-700">
          No hay cifras para esta semana. Prueba con otra semana.
        </p>
      ) : (
        <>
          <section aria-labelledby="summary" className={cardClass}>
            <div>
              <h2 id="summary" className="text-xl font-bold">Resumen de la semana</h2>
              <p className="text-sm text-gray-700">
                Cada moneda se muestra por separado: las cifras en pesos colombianos (COP) y en
                dólares (USD) no se suman ni se convierten entre sí.
              </p>
            </div>
            {groups.map((group) => <SummaryTiles key={group.currency} group={group} />)}
          </section>

          {KPIS.map((kpi) => (
            <section key={kpi.key} aria-labelledby={`kpi-${kpi.key}`} className={cardClass}>
              <div>
                <h2 id={`kpi-${kpi.key}`} className="text-xl font-bold">{kpi.name}</h2>
                <p className="text-sm text-gray-700">{kpi.measures} Locales de mayor a menor.</p>
              </div>
              {groups.map((group) => <KpiTable key={group.currency} kpi={kpi} group={group} />)}
            </section>
          ))}
        </>
      )}
    </div>
  );
}
