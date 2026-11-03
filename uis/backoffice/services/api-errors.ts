export const API_UNAVAILABLE_MESSAGE =
  "El servicio no está disponible, inténtalo más tarde.";
export const API_CONNECTION_MESSAGE =
  "No se pudo conectar con el servicio. Comprueba tu conexión e inténtalo de nuevo.";
export const INVALID_API_RESPONSE_MESSAGE =
  "El servicio devolvió una respuesta no válida. Inténtalo de nuevo.";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function validationMessages(payload: unknown): string[] {
  if (!isRecord(payload)) return [];

  if (Array.isArray(payload.errors)) {
    const messages = payload.errors.flatMap((item) => {
      if (!isRecord(item) || typeof item.message !== "string" || !item.message.trim()) {
        return [];
      }
      return [
        typeof item.field === "string" && item.field.trim()
          ? `${item.field}: ${item.message.trim()}`
          : item.message.trim(),
      ];
    });
    if (messages.length) return messages;
  }

  if (typeof payload.detail === "string" && payload.detail.trim()) {
    return [payload.detail.trim()];
  }

  if (Array.isArray(payload.detail)) {
    return payload.detail.flatMap((item) => {
      if (!isRecord(item)) return [];
      const message = typeof item.msg === "string" ? item.msg : item.message;
      return typeof message === "string" && message.trim() ? [message.trim()] : [];
    });
  }

  return [];
}

export async function buildApiErrorMessage(response: Response): Promise<string> {
  if (response.status === 404) {
    return "No se encontró el recurso solicitado.";
  }

  if (response.status !== 400 && response.status !== 422) {
    return API_UNAVAILABLE_MESSAGE;
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return "Los datos no son válidos. Revísalos e inténtalo de nuevo.";
  }

  const messages = validationMessages(payload);
  return messages.length
    ? messages.join(" ")
    : "Los datos no son válidos. Revísalos e inténtalo de nuevo.";
}

export async function readJsonResponse<T>(response: Response): Promise<T> {
  try {
    return (await response.json()) as T;
  } catch {
    throw new Error(INVALID_API_RESPONSE_MESSAGE);
  }
}
