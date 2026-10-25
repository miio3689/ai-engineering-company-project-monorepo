"use client";

import { useState } from "react";

import { analyzeIncidentCsv, downloadIncidentAnalysisCsv } from "@/services/incident-analysis";
import type { IncidentAnalysisResponse } from "@/types/incident-analysis";

interface UseIncidentAnalysisResult {
  analysis: IncidentAnalysisResponse | null;
  isAnalyzing: boolean;
  isDownloading: boolean;
  error: string | null;
  analyze: (file: File) => Promise<void>;
  download: () => Promise<void>;
  clearError: () => void;
}

function getFriendlyError(error: unknown): string {
  if (error instanceof Error) {
    if (error.message.includes("Failed to fetch")) {
      return "No se pudo conectar con el servicio de análisis. Comprueba que la API está disponible e inténtalo de nuevo.";
    }
    return error.message;
  }
  return "Ha ocurrido un error inesperado al procesar la solicitud.";
}

export function useIncidentAnalysis(): UseIncidentAnalysisResult {
  const [analysis, setAnalysis] = useState<IncidentAnalysisResponse | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function analyze(file: File): Promise<void> {
    setError(null);
    setAnalysis(null);
    setIsAnalyzing(true);
    try {
      setAnalysis(await analyzeIncidentCsv(file));
    } catch (caughtError) {
      setError(getFriendlyError(caughtError));
    } finally {
      setIsAnalyzing(false);
    }
  }

  async function download(): Promise<void> {
    setError(null);
    setIsDownloading(true);
    try {
      await downloadIncidentAnalysisCsv();
    } catch (caughtError) {
      setError(getFriendlyError(caughtError));
    } finally {
      setIsDownloading(false);
    }
  }

  return {
    analysis,
    isAnalyzing,
    isDownloading,
    error,
    analyze,
    download,
    clearError: () => setError(null),
  };
}
