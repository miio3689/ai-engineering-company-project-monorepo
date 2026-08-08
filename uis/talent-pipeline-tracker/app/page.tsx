import Link from "next/link";

import { getStageLabel, getStatusLabel } from "@/lib/candidate-labels";
import { fetchCandidates } from "@/services/api";

export const dynamic = "force-dynamic";

export default async function CandidatesPage() {
  const candidates = await fetchCandidates();

  return (
    <main className="mx-auto w-full max-w-3xl p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold">Listado de candidaturas</h1>
      </header>

      {candidates.length === 0 ? (
        <p>No hay candidaturas disponibles.</p>
      ) : (
        <ul className="space-y-4">
          {candidates.map((candidate) => (
            <li key={candidate.id} className="rounded border p-4">
              <h2 className="text-lg font-medium">
                <Link href={`/candidates/${candidate.id}`} className="underline">
                  {candidate.name}
                </Link>
              </h2>
              <p>Puesto: {candidate.position}</p>
              <p>Estado: {getStatusLabel(candidate.status)}</p>
              <p>Etapa: {getStageLabel(candidate.stage)}</p>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
