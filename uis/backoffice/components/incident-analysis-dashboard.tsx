"use client";

import dynamic from "next/dynamic";
import { useRef, useState } from "react";

import { useIncidentAnalysis } from "@/hooks/use-incident-analysis";

const AnalysisResults = dynamic(() => import("@/components/incident-analysis-results"), {
  loading: () => (
    <div className="incident-results min-h-[32rem]" role="status" aria-busy="true">
      <span className="sr-only">Preparando resultados del análisis…</span>
    </div>
  ),
});

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
        {error && (
          <div className="incident-error" role="alert">
            <p>{error}</p>
            <button
              type="button"
              onClick={() => analysis ? void download() : inputRef.current?.click()}
              disabled={isAnalyzing || isDownloading}
            >
              {analysis ? "Reintentar descarga" : "Seleccionar otro archivo"}
            </button>
          </div>
        )}
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
