import Link from "next/link";

import CandidateListFilters from "@/components/candidate-list-filters";
import { getStageLabel, getStatusLabel } from "@/lib/candidate-labels";
import { fetchCandidates } from "@/services/api";
import type { Candidate, CandidateStage, CandidateStatus } from "@/types/models";

export const dynamic = "force-dynamic";

const VALID_STATUSES: CandidateStatus[] = ["received", "in_progress", "selected", "discarded"];
const VALID_STAGES: CandidateStage[] = [
  "pending",
  "review",
  "personal_interview",
  "technical_interview",
  "offer_presented",
];

interface CandidatesPageProps {
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

function parseStatus(value?: string): CandidateStatus | undefined {
  if (!value) {
    return undefined;
  }

  return VALID_STATUSES.includes(value as CandidateStatus)
    ? (value as CandidateStatus)
    : undefined;
}

function parseStage(value?: string): CandidateStage | undefined {
  if (!value) {
    return undefined;
  }

  return VALID_STAGES.includes(value as CandidateStage)
    ? (value as CandidateStage)
    : undefined;
}

function matchesSearch(candidate: Candidate, query: string): boolean {
  if (!query) {
    return true;
  }

  const normalizedQuery = query.toLocaleLowerCase();
  return (
    candidate.name.toLocaleLowerCase().includes(normalizedQuery)
    || candidate.email.toLocaleLowerCase().includes(normalizedQuery)
  );
}

function buildCurrentQuery(
  searchQuery: string,
  status: CandidateStatus | undefined,
  stage: CandidateStage | undefined,
): string {
  const params = new URLSearchParams();

  if (searchQuery) {
    params.set("q", searchQuery);
  }

  if (status) {
    params.set("status", status);
  }

  if (stage) {
    params.set("stage", stage);
  }

  const query = params.toString();
  return query ? `?${query}` : "";
}

export default async function CandidatesPage({ searchParams }: CandidatesPageProps) {
  const resolvedSearchParams = await searchParams;
  const rawQuery = getSingleValue(resolvedSearchParams.q) ?? "";
  const searchQuery = rawQuery.trim();
  const statusFilter = parseStatus(getSingleValue(resolvedSearchParams.status));
  const stageFilter = parseStage(getSingleValue(resolvedSearchParams.stage));

  const candidates = await fetchCandidates();
  const filteredCandidates = candidates.filter((candidate) => {
    const matchesStatus = !statusFilter || candidate.status === statusFilter;
    const matchesStage = !stageFilter || candidate.stage === stageFilter;
    const matchesQuery = matchesSearch(candidate, searchQuery);

    return matchesStatus && matchesStage && matchesQuery;
  });
  const currentQuery = buildCurrentQuery(searchQuery, statusFilter, stageFilter);

  return (
    <main>
      <header>
        <h1>Listado de candidaturas</h1>
      </header>

      <CandidateListFilters
        searchQuery={searchQuery}
        statusFilter={statusFilter}
        stageFilter={stageFilter}
      />

      {filteredCandidates.length === 0 ? (
        <p>No hay candidaturas disponibles.</p>
      ) : (
        <ul>
          {filteredCandidates.map((candidate) => (
            <li key={candidate.id}>
              <h2>
                <Link href={`/candidates/${candidate.id}${currentQuery}`}>{candidate.name}</Link>
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
