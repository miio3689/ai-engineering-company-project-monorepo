import { notFound } from "next/navigation";

import CandidateDetailManager from "@/components/candidate-detail-manager";
import PageLoadError from "@/components/page-load-error";
import { fetchCandidateById, fetchCandidateNotes } from "@/services/api";
import type { Candidate, CandidateNote } from "@/types/models";

export const dynamic = "force-dynamic";

interface CandidateDetailPageProps {
  params: Promise<{ id?: string | string[] }>;
  searchParams: Promise<{
    q?: string | string[];
    status?: string | string[];
    stage?: string | string[];
  }>;
}

function getSingleValue(value?: string | string[]): string | undefined {
  if (!value) {
    return undefined;
  }

  return Array.isArray(value) ? value[0] : value;
}

function buildBackHref(
  q?: string | string[],
  status?: string | string[],
  stage?: string | string[],
): string {
  const params = new URLSearchParams();
  const query = getSingleValue(q)?.trim();
  const statusValue = getSingleValue(status);
  const stageValue = getSingleValue(stage);

  if (query) {
    params.set("q", query);
  }

  if (statusValue) {
    params.set("status", statusValue);
  }

  if (stageValue) {
    params.set("stage", stageValue);
  }

  const queryString = params.toString();
  return queryString ? `/?${queryString}` : "/";
}

export default async function CandidateDetailPage({
  params,
  searchParams,
}: CandidateDetailPageProps) {
  const { id } = await params;
  const resolvedSearchParams = await searchParams;
  const candidateId = Array.isArray(id) ? id[0] : id;

  if (!candidateId) {
    notFound();
  }

  let candidate: Candidate | null;
  try {
    candidate = await fetchCandidateById(candidateId);
  } catch {
    return (
      <PageLoadError
        title="No se pudo cargar la candidatura"
        message="El servicio no está disponible. Inténtalo de nuevo o vuelve al listado."
        exitHref="/"
        exitLabel="Volver al listado"
      />
    );
  }

  if (!candidate) {
    notFound();
  }

  let notes: CandidateNote[];
  try {
    notes = await fetchCandidateNotes(candidateId);
  } catch {
    return (
      <PageLoadError
        title="No se pudieron cargar las notas"
        message="La candidatura está disponible, pero no se pudieron cargar sus notas. Inténtalo de nuevo."
        exitHref="/"
        exitLabel="Volver al listado"
      />
    );
  }

  const backHref = buildBackHref(
    resolvedSearchParams.q,
    resolvedSearchParams.status,
    resolvedSearchParams.stage,
  );

  return <CandidateDetailManager candidate={candidate} notes={notes} backHref={backHref} />;
}
