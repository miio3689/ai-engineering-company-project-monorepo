"use client";

import { useEffect, useState } from "react";

import {
  fetchLatestPipelineRun,
  fetchWeeklyLocationPerformance,
} from "@/services/business-performance";
import type {
  PipelineRunSummary,
  WeeklyLocationPerformance,
} from "@/types/business-performance";

interface ReportResult {
  key: string;
  report: WeeklyLocationPerformance | null;
  latestRun: PipelineRunSummary | null;
  error: string | null;
}

/** Reporte semanal de una semana concreta (weekStart) o de la última semana cerrada (null). */
export function useWeeklyLocationPerformance(weekStart: string | null) {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<ReportResult | null>(null);
  const key = `${weekStart ?? "latest"}#${attempt}`;

  useEffect(() => {
    const controller = new AbortController();

    async function loadReport() {
      try {
        const [report, latestRun] = await Promise.all([
          fetchWeeklyLocationPerformance(weekStart, controller.signal),
          // La fecha de actualización es informativa: si falla, el reporte se muestra igual.
          fetchLatestPipelineRun(controller.signal).catch(() => null),
        ]);
        if (!controller.signal.aborted) setResult({ key, report, latestRun, error: null });
      } catch (error: unknown) {
        if (!controller.signal.aborted) {
          setResult({
            key,
            report: null,
            latestRun: null,
            error: error instanceof Error
              ? error.message
              : "No se pudo cargar el reporte semanal. Inténtalo de nuevo.",
          });
        }
      }
    }

    void loadReport();
    return () => controller.abort();
  }, [key, weekStart]);

  const current = result?.key === key ? result : null;
  return {
    report: current?.report ?? null,
    latestRun: current?.latestRun ?? null,
    loading: current === null,
    error: current?.error ?? null,
    retry: () => setAttempt((value) => value + 1),
  };
}
