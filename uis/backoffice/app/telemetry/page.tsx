"use client";

import TelemetryReportView from "@/components/telemetry-report-view";
import { useTelemetryReport } from "@/hooks/use-telemetry-report";

export default function TelemetryPage() {
  const { report, loading, error, retry } = useTelemetryReport();

  return (
    <main className="mx-auto my-6 grid w-[92%] max-w-6xl min-w-0 gap-6 text-gray-800 sm:my-10">
      <header className="rounded-2xl border border-orange-200 bg-orange-50 p-5 sm:p-8">
        <p className="text-sm font-semibold text-orange-800">Brasaland · Ingeniería</p>
        <h1 className="mt-2 text-2xl font-bold sm:text-3xl">Telemetría técnica</h1>
        <p className="mt-2 text-gray-700">
          Salud operativa del sistema: volumen de eventos, errores, tiempos de carga y fallos
          de inicio de sesión de los últimos 7 días. Vista técnica para el equipo de ingeniería.
        </p>
      </header>
      <TelemetryReportView report={report} loading={loading} error={error} onRetry={retry} />
    </main>
  );
}
