import { apiRequest } from "@/services/api-client";
import type {
  Incident,
  IncidentCreateInput,
  IncidentFieldErrors,
  IncidentFilters,
  IncidentStatus,
  IncidentSummary,
} from "@/types/incident";

const INCIDENTS_PATH = "/api/incidents";
const INCIDENT_FIELDS = new Set([
  "title",
  "description",
  "category",
  "status",
  "origin",
  "branch",
]);

export class IncidentServiceError extends Error {
  constructor(
    message: string,
    public readonly fieldErrors: IncidentFieldErrors = {},
  ) {
    super(message);
    this.name = "IncidentServiceError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

async function responseError(response: Response): Promise<IncidentServiceError> {
  if (response.status === 400) {
    let payload: unknown;
    try {
      payload = await response.json();
    } catch (error) {
      if (!(error instanceof SyntaxError)) throw error;
      return new IncidentServiceError(
        "Los datos no son válidos. Revísalos e inténtalo de nuevo.",
      );
    }

    const fieldErrors: IncidentFieldErrors = {};
    if (isRecord(payload) && Array.isArray(payload.errors)) {
      for (const item of payload.errors) {
        if (
          !isRecord(item)
          || typeof item.field !== "string"
          || typeof item.message !== "string"
          || !INCIDENT_FIELDS.has(item.field)
        ) {
          continue;
        }
        fieldErrors[item.field as keyof IncidentFieldErrors] = item.message;
      }
    }
    return new IncidentServiceError(
      Object.keys(fieldErrors).length
        ? "Revisa los campos indicados e inténtalo de nuevo."
        : "Los datos no son válidos. Revísalos e inténtalo de nuevo.",
      fieldErrors,
    );
  }

  if (response.status === 404) {
    return new IncidentServiceError(
      "La incidencia ya no está disponible. Actualiza el listado e inténtalo de nuevo.",
    );
  }

  return new IncidentServiceError(
    "No se pudo completar la solicitud. Inténtalo de nuevo.",
  );
}

async function request(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  try {
    return await apiRequest(path, options);
  } catch (error) {
    if (options.signal?.aborted) throw error;
    if (error instanceof Error && error.message.includes("Tu sesión")) {
      throw new IncidentServiceError(error.message);
    }
    throw new IncidentServiceError(
      "No se pudo conectar con el servicio de incidencias. Comprueba la conexión e inténtalo de nuevo.",
    );
  }
}

async function readResponse<T>(response: Response): Promise<T> {
  if (!response.ok) throw await responseError(response);
  try {
    return (await response.json()) as T;
  } catch (error) {
    if (!(error instanceof SyntaxError)) throw error;
    throw new IncidentServiceError(
      "El servicio devolvió una respuesta no válida. Inténtalo de nuevo.",
    );
  }
}

export async function fetchIncidents(
  filters: IncidentFilters = {},
  signal?: AbortSignal,
): Promise<Incident[]> {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.origin) params.set("origin", filters.origin);
  if (filters.branch) params.set("branch", filters.branch);
  const query = params.toString();
  const response = await request(
    `${INCIDENTS_PATH}${query ? `?${query}` : ""}`,
    { signal },
  );
  return readResponse<Incident[]>(response);
}

export async function createIncident(
  input: IncidentCreateInput,
): Promise<Incident> {
  const response = await request(INCIDENTS_PATH, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return readResponse<Incident>(response);
}

export async function updateIncidentStatus(
  id: number,
  status: IncidentStatus,
): Promise<Incident> {
  const response = await request(`${INCIDENTS_PATH}/${id}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  return readResponse<Incident>(response);
}

export async function fetchIncidentSummary(
  signal?: AbortSignal,
): Promise<IncidentSummary> {
  const response = await request(`${INCIDENTS_PATH}/summary`, { signal });
  return readResponse<IncidentSummary>(response);
}
