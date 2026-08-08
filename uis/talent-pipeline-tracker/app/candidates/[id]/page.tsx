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
    <main className="mx-auto w-full max-w-3xl p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold">{candidate.name}</h1>
      </header>

      <section className="space-y-1 rounded border p-4">
        <p>Puesto: {candidate.position}</p>
        <p>Estado: {getStatusLabel(candidate.status)}</p>
        <p>Etapa: {getStageLabel(candidate.stage)}</p>
      </section>

      <nav className="mt-6">
        <Link href="/" className="underline">
          Volver al listado
        </Link>
      </nav>
    </main>
  );
}
