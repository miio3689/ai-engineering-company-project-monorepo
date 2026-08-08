import type { Candidate } from "@/types/models";

interface RecordOut {
  id: string;
  full_name: string;
  email: string;
  phone: string;
  position: string;
  linkedin_url: string | null;
  cv_url: string | null;
  status: string;
  stage: string;
  experience_years: number;
  applied_at: string;
}

interface RecordsResponse {
  data: RecordOut[];
}

function parseStatus(status: string): Candidate["status"] {
  if (
    status === "received"
    || status === "in_progress"
    || status === "selected"
    || status === "discarded"
  ) {
    return status;
  }

  throw new Error(`Estado invalido recibido desde la API: ${status}`);
}

function parseStage(stage: string): Candidate["stage"] {
  if (
    stage === "pending"
    || stage === "review"
    || stage === "personal_interview"
    || stage === "technical_interview"
    || stage === "offer_presented"
  ) {
    return stage;
  }

  throw new Error(`Etapa invalida recibida desde la API: ${stage}`);
}

function mapRecordToCandidate(record: RecordOut): Candidate {
  return {
    id: record.id,
    name: record.full_name,
    email: record.email,
    phone: record.phone,
    position: record.position,
    linkedinUrl: record.linkedin_url ?? undefined,
    resumeUrl: record.cv_url ?? undefined,
    yearsOfExperience: record.experience_years,
    status: parseStatus(record.status),
    stage: parseStage(record.stage),
    appliedAt: record.applied_at,
  };
}

function getApiBaseUrl(): string {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

  if (!baseUrl) {
    throw new Error("Falta NEXT_PUBLIC_API_BASE_URL en el entorno.");
  }

  return baseUrl.replace(/\/$/, "");
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    method: "GET",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Error API ${response.status}: ${response.statusText}`);
  }

  return (await response.json()) as T;
}

export async function fetchCandidates(): Promise<Candidate[]> {
  const response = await getJson<RecordsResponse>("/records");
  return response.data.map(mapRecordToCandidate);
}

export async function fetchCandidateById(id: string): Promise<Candidate | null> {
  const response = await fetch(`${getApiBaseUrl()}/records/${id}`, {
    method: "GET",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`Error API ${response.status}: ${response.statusText}`);
  }

  const record = (await response.json()) as RecordOut;
  return mapRecordToCandidate(record);
}
