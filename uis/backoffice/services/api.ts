import type { Candidate, CandidateNote, CandidateStage, CandidateStatus } from "@/types/models";
import { apiRequest } from "@/services/api-client";
import { buildApiErrorMessage, readJsonResponse } from "@/services/api-errors";

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

interface CandidateNoteOut {
  id: string;
  candidate_id: string;
  content: string;
  created_at: string;
}

interface CandidatePayload {
  name: string;
  email: string;
  phone: string;
  position: string;
  linkedinUrl?: string;
  resumeUrl?: string;
  yearsOfExperience: number;
  status: CandidateStatus;
  stage: CandidateStage;
  appliedAt: string;
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

  throw new Error("La API devolvió un estado de candidatura no válido.");
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

  throw new Error("La API devolvió una etapa de candidatura no válida.");
}

function mapRecordToCandidate(record: RecordOut): Candidate {
  return {
    id: record.id,
    name: record.full_name ?? "Nombre no disponible",
    email: record.email ?? "",
    phone: record.phone ?? "",
    position: record.position ?? "Puesto no disponible",
    linkedinUrl: record.linkedin_url ?? undefined,
    resumeUrl: record.cv_url ?? undefined,
    yearsOfExperience: record.experience_years ?? 0,
    status: parseStatus(record.status),
    stage: parseStage(record.stage),
    appliedAt: record.applied_at ?? "",
  };
}

function mapNoteToCandidateNote(note: CandidateNoteOut): CandidateNote {
  return {
    id: note.id,
    candidateId: note.candidate_id,
    content: note.content ?? "",
    createdAt: note.created_at ?? "",
  };
}

function mapCandidatePayloadToApi(payload: CandidatePayload): Omit<RecordOut, "id"> {
  return {
    full_name: payload.name,
    email: payload.email,
    phone: payload.phone,
    position: payload.position,
    linkedin_url: payload.linkedinUrl?.trim() ? payload.linkedinUrl : null,
    cv_url: payload.resumeUrl?.trim() ? payload.resumeUrl : null,
    status: payload.status,
    stage: payload.stage,
    experience_years: payload.yearsOfExperience,
    applied_at: payload.appliedAt,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function toRecordOut(value: unknown): RecordOut {
  if (!isRecord(value) || typeof value.id !== "string" || !value.id) {
    throw new Error("El servicio devolvió una candidatura no válida.");
  }

  return {
    id: value.id,
    full_name: typeof value.full_name === "string" ? value.full_name : "Nombre no disponible",
    email: typeof value.email === "string" ? value.email : "",
    phone: typeof value.phone === "string" ? value.phone : "",
    position: typeof value.position === "string" ? value.position : "Puesto no disponible",
    linkedin_url: typeof value.linkedin_url === "string" ? value.linkedin_url : null,
    cv_url: typeof value.cv_url === "string" ? value.cv_url : null,
    status: typeof value.status === "string" ? value.status : "",
    stage: typeof value.stage === "string" ? value.stage : "",
    experience_years: typeof value.experience_years === "number" ? value.experience_years : 0,
    applied_at: typeof value.applied_at === "string" ? value.applied_at : "",
  };
}

function toCandidateNoteOut(value: unknown): CandidateNoteOut {
  if (!isRecord(value) || typeof value.id !== "string" || !value.id) {
    throw new Error("El servicio devolvió una nota no válida.");
  }

  return {
    id: value.id,
    candidate_id: typeof value.candidate_id === "string" ? value.candidate_id : "",
    content: typeof value.content === "string" ? value.content : "",
    created_at: typeof value.created_at === "string" ? value.created_at : "",
  };
}

async function getJson<T>(path: string): Promise<T> {
  const response = await apiRequest(path, {
    method: "GET",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(await buildApiErrorMessage(response));
  }

  return readJsonResponse<T>(response);
}

async function sendJson<TResponse>(
  path: string,
  method: "POST" | "PUT" | "PATCH",
  body: unknown,
): Promise<TResponse> {
  const response = await apiRequest(path, {
    method,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(await buildApiErrorMessage(response));
  }

  return readJsonResponse<TResponse>(response);
}

function extractRecord(payload: unknown): RecordOut {
  if (!isRecord(payload)) {
    throw new Error("El servicio devolvió una candidatura no válida.");
  }
  if ("data" in payload) {
    return toRecordOut(payload.data);
  }

  return toRecordOut(payload);
}

function extractNote(payload: unknown): CandidateNoteOut {
  if (!isRecord(payload)) {
    throw new Error("El servicio devolvió una nota no válida.");
  }
  if ("data" in payload) {
    return toCandidateNoteOut(payload.data);
  }

  return toCandidateNoteOut(payload);
}

function extractNotes(payload: unknown): CandidateNoteOut[] {
  if (Array.isArray(payload)) {
    return payload.map(toCandidateNoteOut);
  }

  if (!isRecord(payload)) {
    throw new Error("El servicio devolvió una respuesta de notas no válida.");
  }
  if (!Array.isArray(payload.data)) {
    throw new Error("El servicio devolvió una respuesta de notas no válida.");
  }
  return payload.data.map(toCandidateNoteOut);
}

async function sendNoContent(path: string, method: "DELETE"): Promise<void> {
  const response = await apiRequest(path, {
    method,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(await buildApiErrorMessage(response));
  }
}

export async function fetchCandidates(): Promise<Candidate[]> {
  const response = await getJson<unknown>("/records");
  if (!isRecord(response) || !Array.isArray(response.data)) {
    throw new Error("El servicio devolvió un listado de candidaturas no válido.");
  }
  return response.data.map((record) => mapRecordToCandidate(toRecordOut(record)));
}

export async function fetchCandidateById(id: string): Promise<Candidate | null> {
  const response = await apiRequest(`/records/${id}`, {
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
    throw new Error(await buildApiErrorMessage(response));
  }

  const payload = await readJsonResponse<unknown>(response);
  const record = extractRecord(payload);
  return mapRecordToCandidate(record);
}

export async function fetchCandidateNotes(candidateId: string): Promise<CandidateNote[]> {
  const response = await getJson<unknown>(`/records/${candidateId}/notes`);
  return extractNotes(response).map(mapNoteToCandidateNote);
}

export async function updateCandidateStatus(
  candidateId: string,
  status: CandidateStatus,
): Promise<Candidate> {
  const response = await sendJson<unknown>(`/records/${candidateId}`, "PATCH", { status });
  const record = extractRecord(response);
  return mapRecordToCandidate(record);
}

export async function updateCandidateStage(
  candidateId: string,
  stage: CandidateStage,
): Promise<Candidate> {
  const response = await sendJson<unknown>(`/records/${candidateId}`, "PATCH", { stage });
  const record = extractRecord(response);
  return mapRecordToCandidate(record);
}

export async function addCandidateNote(candidateId: string, content: string): Promise<CandidateNote> {
  const response = await sendJson<unknown>(
    `/records/${candidateId}/notes`,
    "POST",
    { content },
  );
  const note = extractNote(response);
  return mapNoteToCandidateNote(note);
}

export async function deleteCandidateNote(candidateId: string, noteId: string): Promise<void> {
  await sendNoContent(`/records/${candidateId}/notes/${noteId}`, "DELETE");
}

export async function createCandidate(payload: CandidatePayload): Promise<Candidate> {
  const response = await sendJson<unknown>("/records", "POST", mapCandidatePayloadToApi(payload));
  const record = extractRecord(response);
  return mapRecordToCandidate(record);
}

export async function updateCandidate(
  candidateId: string,
  payload: CandidatePayload,
): Promise<Candidate> {
  const response = await sendJson<unknown>(
    `/records/${candidateId}`,
    "PATCH",
    mapCandidatePayloadToApi(payload),
  );
  const record = extractRecord(response);
  return mapRecordToCandidate(record);
}
