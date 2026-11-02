import IncidentList from "@/components/incident-list";
import IncidentManagerNavigation from "@/components/incident-manager-navigation";
import IncidentSummary from "@/components/incident-summary";

export default function IncidentListPage() {
  return (
    <main className="mx-auto my-6 grid w-[92%] max-w-6xl min-w-0 gap-6 text-gray-800 sm:my-10">
      <header className="rounded-2xl border border-orange-200 bg-orange-50 p-5 sm:p-8">
        <p className="text-sm font-semibold text-orange-800">Brasaland · Operaciones</p>
        <h1 className="mt-2 text-2xl font-bold sm:text-3xl">Gestor de incidencias</h1>
        <p className="mt-2 text-gray-700">
          Consulta los reportes y actualiza su seguimiento.
        </p>
      </header>
      <IncidentManagerNavigation />
      <IncidentSummary />
      <IncidentList />
    </main>
  );
}
