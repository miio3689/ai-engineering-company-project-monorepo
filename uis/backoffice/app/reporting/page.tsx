"use client";

import { useState } from "react";

import WeeklyPerformanceDashboard from "@/components/weekly-performance-dashboard";
import { useWeeklyLocationPerformance } from "@/hooks/use-weekly-location-performance";

export default function ReportingPage() {
  // null = la última semana cerrada (la que elige GET /reporting/weekly-location-performance).
  const [selectedWeek, setSelectedWeek] = useState<string | null>(null);
  const { report, latestRun, loading, error, retry } = useWeeklyLocationPerformance(selectedWeek);

  return (
    <main className="mx-auto my-6 grid w-[92%] max-w-6xl min-w-0 gap-6 text-gray-800 sm:my-10">
      <header className="rounded-2xl border border-orange-200 bg-orange-50 p-5 sm:p-8">
        <p className="text-sm font-semibold text-orange-800">Brasaland · Dirección</p>
        <h1 className="mt-2 text-2xl font-bold sm:text-3xl">
          Reporte Semanal de Costo y Merma por Local
        </h1>
        <p className="mt-2 text-gray-700">
          Cuánto compró y cuánto perdió por merma cada local en la semana, y con qué frecuencia
          se quedó sin stock o recibió alertas de precio. Se actualiza automáticamente cada lunes
          por la mañana.
        </p>
      </header>
      <WeeklyPerformanceDashboard
        report={report}
        latestRun={latestRun}
        loading={loading}
        error={error}
        selectedWeek={selectedWeek}
        onSelectWeek={setSelectedWeek}
        onRetry={retry}
      />
    </main>
  );
}
