import Link from "next/link";
import { notFound } from "next/navigation";

import { getStageLabel, getStatusLabel } from "@/lib/candidate-labels";
import { fetchCandidateById } from "@/services/api";

export const dynamic = "force-dynamic";

interface CandidateDetailPageProps {
  params: Promise<{ id?: string | string[] }>;
}

export default async function CandidateDetailPage({ params }: CandidateDetailPageProps) {
  const { id } = await params;
  const candidateId = Array.isArray(id) ? id[0] : id;

  if (!candidateId) {
    notFound();
  }

  const candidate = await fetchCandidateById(candidateId);

  if (!candidate) {
    notFound();
  }

  return (
    <main>
      <header>
        <h1>{candidate.name}</h1>
      </header>

      <section>
        <p>Puesto: {candidate.position}</p>
        <p>Estado: {getStatusLabel(candidate.status)}</p>
        <p>Etapa: {getStageLabel(candidate.stage)}</p>
      </section>

      <nav>
        <Link href="/">Volver al listado</Link>
      </nav>
    </main>
  );
}
