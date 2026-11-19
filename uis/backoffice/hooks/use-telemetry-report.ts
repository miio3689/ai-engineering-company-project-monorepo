"use client";

import { useEffect, useState } from "react";

import { fetchTelemetryReport } from "@/services/telemetry-report";
import type { TelemetryReport } from "@/types/telemetry-report";

interface ReportResult {
  attempt: number;
  report: TelemetryReport | null;
  error: string | null;
}

export function useTelemetryReport() {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<ReportResult | null>(null);
  const [requestLoading, setRequestLoading] = useState(true);
  const loading = requestLoading || result?.attempt !== attempt;

  useEffect(() => {
    const controller = new AbortController();

    async function loadReport() {
      try {
        const report = await fetchTelemetryReport(controller.signal);
        if (!controller.signal.aborted) setResult({ attempt, report, error: null });
      } catch (error: unknown) {
        if (!controller.signal.aborted) {
          setResult({
            attempt,
            report: null,
            error: error instanceof Error
              ? error.message
              : "No se pudo cargar el reporte técnico. Inténtalo de nuevo.",
          });
        }
      } finally {
        if (!controller.signal.aborted) setRequestLoading(false);
      }
    }

    void loadReport();
    return () => controller.abort();
  }, [attempt]);

  return {
    report: result?.attempt === attempt ? result.report : null,
    loading,
    error: result?.attempt === attempt ? result.error : null,
    retry: () => setAttempt((value) => value + 1),
  };
}
