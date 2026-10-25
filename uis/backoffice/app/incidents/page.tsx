import Link from "next/link";

import IncidentAnalysisDashboard from "@/components/incident-analysis-dashboard";

export default function IncidentAnalysisPage() {
  return (
    <main className="incident-shell">
      <nav className="incident-breadcrumb" aria-label="Navegación principal">
        <Link href="/">← Listado de candidaturas</Link>
        <span aria-current="page">Análisis de incidencias</span>
      </nav>
      <IncidentAnalysisDashboard />
    </main>
  );
}
