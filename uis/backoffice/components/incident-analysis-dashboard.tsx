"use client";

import { useRef, useState } from "react";

import { useIncidentAnalysis } from "@/hooks/use-incident-analysis";
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
        {Object.entries(rows).map(([label, values]) => (
          <li key={label}>
            <span>{label.replaceAll("_", " ")}</span>
            <strong>{values.count}</strong>
            <span className="incident-percentage">{values.percentage.toFixed(1)}%</span>
            <span className="incident-bar-track" aria-hidden="true">
              <span className="incident-bar" style={{ width: `${values.percentage}%` }} />
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function AnalysisResults({ analysis }: { analysis: IncidentAnalysisResponse }) {
  return (
    <div className="incident-results" aria-live="polite">
      <section className="incident-metrics" aria-label="Resumen del análisis">
        <article className="incident-card incident-metric">
          <span>Total de incidencias</span>
          <strong>{analysis.total_records}</strong>
        </article>
        <article className="incident-card incident-metric incident-metric-good">
          <span>Registros válidos</span>
          <strong>{analysis.valid_records}</strong>
        </article>
        <article className="incident-card incident-metric incident-metric-warning">
          <span>Registros inválidos</span>
          <strong>{analysis.invalid_records}</strong>
        </article>
      </section>

      {analysis.invalid_records > 0 && (
        <section className="incident-card incident-invalid" aria-label="Registros inválidos">
          <h2>Incidencias que requieren revisión</h2>
          <p>
            Se encontraron <strong>{analysis.invalid_records}</strong> registros inválidos. El
            desglose de reglas activadas es:
          </p>
          <ul>
            {Object.entries(analysis.invalid_by_rule).map(([rule, count]) => (
              <li key={rule}>
                <span>{ERROR_LABELS[rule] ?? rule.replaceAll("_", " ")}</span>
                <strong>{count}</strong>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="incident-breakdown-grid">
        <BreakdownTable title="Incidencias por categoría" rows={analysis.category_counts} />
        <BreakdownTable title="Incidencias por estado" rows={analysis.status_counts} />
      </div>

      <section className="incident-card incident-satisfaction">
        <div className="incident-section-heading">
          <div>
            <h2>Índice de satisfacción</h2>
            <p>{analysis.satisfaction.scored_cases} respuestas de casos cerrados</p>
          </div>
          <strong className="incident-average">
            {analysis.satisfaction.average === null
              ? "—"
              : `${analysis.satisfaction.average.toFixed(2)} / 5`}
          </strong>
        </div>
        <ul>
          {Object.entries(analysis.satisfaction.counts).map(([score, count]) => (
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

export default function IncidentAnalysisDashboard() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const { analysis, isAnalyzing, isDownloading, error, analyze, download } = useIncidentAnalysis();

  async function submitFile(file?: File): Promise<void> {
    if (!file) return;
    setFileName(file.name);
    await analyze(file);
  }

  function handleFile(file?: File): void {
    if (!file) return;
    if (!file.name.toLocaleLowerCase().endsWith(".csv")) {
      setFileName(file.name);
      void analyze(file);
      return;
    }
    void submitFile(file);
  }

  return (
    <div className="incident-analysis-page">
      <header className="incident-page-header">
        <div>
          <p className="incident-eyebrow">Brasaland · Operaciones</p>
          <h1>Analizador de incidencias</h1>
          <p>Valida y resume los reportes operativos de las 14 sedes.</p>
        </div>
        <span className="incident-header-mark" aria-hidden="true">B</span>
      </header>

      <section className="incident-upload-card" aria-labelledby="incident-upload-title">
        <div>
          <h2 id="incident-upload-title">Sube el archivo de incidencias</h2>
          <p>Selecciona el CSV exportado para ver las métricas operativas.</p>
        </div>
        <button
          type="button"
          className={`incident-dropzone${isDragging ? " is-dragging" : ""}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(event) => {
            event.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setIsDragging(false);
            handleFile(event.dataTransfer.files[0]);
          }}
          disabled={isAnalyzing}
          aria-label="Seleccionar o arrastrar un fichero CSV"
        >
          <span className="incident-upload-icon" aria-hidden="true">↑</span>
          <strong>{isDragging ? "Suelta el archivo aquí" : "Arrastra el CSV aquí o selecciónalo"}</strong>
          <span>Formato esperado: .csv · UTF-8</span>
          {fileName && <span className="incident-file-name">Archivo: {fileName}</span>}
        </button>
        <input
          ref={inputRef}
          className="incident-file-input"
          type="file"
          accept=".csv,text/csv"
          onChange={(event) => {
            handleFile(event.target.files?.[0]);
            event.currentTarget.value = "";
          }}
          aria-label="Seleccionar fichero CSV"
        />
        {isAnalyzing && (
          <p className="incident-loading" role="status">
            <span className="incident-spinner" aria-hidden="true" />
            Analizando incidencias…
          </p>
        )}
        {error && <p className="incident-error" role="alert">{error}</p>}
      </section>

      {analysis && (
        <>
          <div className="incident-results-heading">
            <div>
              <p className="incident-eyebrow">Informe generado</p>
              <h2>Resumen del análisis</h2>
            </div>
            <button
              type="button"
              className="incident-export-button"
              onClick={() => void download()}
              disabled={isDownloading}
            >
              {isDownloading ? "Preparando CSV…" : "↓  Descargar resultados CSV"}
            </button>
          </div>
          <AnalysisResults analysis={analysis} />
        </>
      )}
    </div>
  );
}
