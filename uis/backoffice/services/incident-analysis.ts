import type { IncidentAnalysisResponse } from "@/types/incident-analysis";
import { apiRequest } from "@/services/api-client";
import {
  buildApiErrorMessage,
  INVALID_API_RESPONSE_MESSAGE,
  readJsonResponse,
} from "@/services/api-errors";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNumberMap(value: unknown): value is Record<string, number> {
  return isRecord(value) && Object.values(value).every((item) => typeof item === "number");
}

function isBreakdownMap(
  value: unknown,
): value is IncidentAnalysisResponse["category_counts"] {
  return isRecord(value) && Object.values(value).every((item) =>
    isRecord(item)
    && typeof item.count === "number"
    && typeof item.percentage === "number"
  );
}

function isIncidentAnalysisResponse(value: unknown): value is IncidentAnalysisResponse {
  if (!isRecord(value) || !isRecord(value.satisfaction)) return false;
  const satisfaction = value.satisfaction;
  return typeof value.total_records === "number"
    && typeof value.valid_records === "number"
    && typeof value.invalid_records === "number"
    && isNumberMap(value.invalid_by_rule)
    && isBreakdownMap(value.category_counts)
    && isBreakdownMap(value.status_counts)
    && (typeof satisfaction.average === "number" || satisfaction.average === null)
    && typeof satisfaction.scored_cases === "number"
    && isNumberMap(satisfaction.counts);
}

export async function analyzeIncidentCsv(file: File): Promise<IncidentAnalysisResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiRequest("/api/incidents/analyze", {
    method: "POST",
    body: formData,
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await buildApiErrorMessage(response));
  }

  const analysis = await readJsonResponse<unknown>(response);
  if (!isIncidentAnalysisResponse(analysis)) {
    throw new Error(INVALID_API_RESPONSE_MESSAGE);
  }
  return analysis;
}

export async function downloadIncidentAnalysisCsv(): Promise<void> {
  const response = await apiRequest("/api/incidents/results/export", {
    method: "GET",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await buildApiErrorMessage(response));
  }

  let objectUrl: string | null = null;
  try {
    const blob = await response.blob();
    objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = "results.csv";
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
  } catch {
    throw new Error("No se pudo preparar la descarga. Inténtalo de nuevo.");
  } finally {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
  }
}
