import Link from "next/link";

import { getStageLabel, getStatusLabel } from "@/lib/candidate-labels";
import { fetchCandidates } from "@/services/api";

export const dynamic = "force-dynamic";

export default async function CandidatesPage() {
  const candidates = await fetchCandidates();

  return (
    <main>
      <header>
        <h1>Listado de candidaturas</h1>
      </header>

      {candidates.length === 0 ? (
        <p>No hay candidaturas disponibles.</p>
      ) : (
        <ul>
          {candidates.map((candidate) => (
            <li key={candidate.id}>
              <h2>
                <Link href={`/candidates/${candidate.id}`}>{candidate.name}</Link>
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
