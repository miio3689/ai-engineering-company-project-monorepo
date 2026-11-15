"use client";

import type { IncidentAnalysisResponse } from "@/types/incident-analysis";

const SATISFACTION_LABELS: Record<string, string> = {
  "1": "Muy insatisfecho",
  "2": "Insatisfecho",
  "3": "Neutral",
  "4": "Satisfecho",
  "5": "Muy satisfecho",
};

const ERROR_LABELS: Record<string, string> = {
  missing_or_invalid_location_id: "Ubicación ausente o no válida",
  missing_or_invalid_category: "Categoría ausente o no válida",
  empty_or_short_description: "Descripción vacía o demasiado corta",
  missing_reporter_id: "Falta el identificador del informante",
  closed_without_satisfaction_score: "Incidencia cerrada sin puntuación de satisfacción",
  satisfaction_score_out_of_range: "Puntuación de satisfacción fuera del rango 1–5",
};

interface BreakdownTableProps {
  title: string;
  rows: Record<string, { count: number; percentage: number }>;
}

function BreakdownTable({ title, rows }: BreakdownTableProps) {
  return (
    <section className="incident-card incident-breakdown">
      <h2>{title}</h2>
      <ul>
        {Object.entries(rows ?? {}).map(([label, values]) => (
          <li key={label}>
            <span>{label.replaceAll("_", " ")}</span>
            <strong>{values?.count ?? 0}</strong>
            <span className="incident-percentage">{(values?.percentage ?? 0).toFixed(1)}%</span>
            <span className="incident-bar-track" aria-hidden="true">
              <span className="incident-bar" style={{ width: `${values?.percentage ?? 0}%` }} />
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function AnalysisResults({ analysis }: { analysis: IncidentAnalysisResponse }) {
  const invalidRecords = analysis.invalid_records ?? 0;
  const satisfactionAverage = analysis.satisfaction?.average ?? null;

  return (
    <div className="incident-results" aria-live="polite">
      <section className="incident-metrics" aria-label="Resumen del análisis">
        <article className="incident-card incident-metric">
          <span>Total de incidencias</span>
          <strong>{analysis.total_records ?? 0}</strong>
        </article>
        <article className="incident-card incident-metric incident-metric-good">
          <span>Registros válidos</span>
          <strong>{analysis.valid_records ?? 0}</strong>
        </article>
        <article className="incident-card incident-metric incident-metric-warning">
          <span>Registros inválidos</span>
          <strong>{invalidRecords}</strong>
        </article>
      </section>

      {invalidRecords > 0 && (
        <section className="incident-card incident-invalid" aria-label="Registros inválidos">
          <h2>Incidencias que requieren revisión</h2>
          <p>
            Se encontraron <strong>{invalidRecords}</strong> registros inválidos. El
            desglose de reglas activadas es:
          </p>
          <ul>
            {Object.entries(analysis.invalid_by_rule ?? {}).map(([rule, count]) => (
              <li key={rule}>
                <span>{ERROR_LABELS[rule] ?? rule.replaceAll("_", " ")}</span>
                <strong>{count}</strong>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="incident-breakdown-grid">
        <BreakdownTable title="Incidencias por categoría" rows={analysis.category_counts ?? {}} />
        <BreakdownTable title="Incidencias por estado" rows={analysis.status_counts ?? {}} />
      </div>

      <section className="incident-card incident-satisfaction">
        <div className="incident-section-heading">
          <div>
            <h2>Índice de satisfacción</h2>
            <p>{analysis.satisfaction?.scored_cases ?? 0} respuestas de casos cerrados</p>
          </div>
          <strong className="incident-average">
            {satisfactionAverage === null
              ? "—"
              : `${satisfactionAverage.toFixed(2)} / 5`}
          </strong>
        </div>
        <ul>
          {Object.entries(analysis.satisfaction?.counts ?? {}).map(([score, count]) => (
            <li key={score}>
              <span className="incident-score">{score}</span>
              <span>{SATISFACTION_LABELS[score] ?? `Puntuación ${score}`}</span>
              <strong>{count}</strong>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
