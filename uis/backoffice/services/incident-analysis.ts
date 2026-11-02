import type { IncidentAnalysisResponse } from "@/types/incident-analysis";
import { apiRequest } from "@/services/api-client";

async function getApiError(response: Response): Promise<string> {
  const fallback = `No se pudo completar la solicitud (HTTP ${response.status}).`;

  try {
    const payload: unknown = await response.json();
    if (payload && typeof payload === "object" && "detail" in payload) {
      const { detail } = payload as { detail?: unknown };
      if (typeof detail === "string" && detail.trim()) {
        return detail;
      }
    }
  } catch {
    // Use the friendly fallback when the server response is not JSON.
  }

  return fallback;
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
    throw new Error(await getApiError(response));
  }

  return (await response.json()) as IncidentAnalysisResponse;
}

export async function downloadIncidentAnalysisCsv(): Promise<void> {
  const response = await apiRequest("/api/incidents/results/export", {
    method: "GET",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await getApiError(response));
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = "results.csv";
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}
