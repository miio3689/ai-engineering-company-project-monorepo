import { API_CONNECTION_MESSAGE, API_UNAVAILABLE_MESSAGE } from "@/services/api-errors";

export const ACCESS_TOKEN_KEY = "access_token";

export async function apiRequest(
  path: string,
  options: RequestInit = {},
  { authenticated = true }: { authenticated?: boolean } = {},
): Promise<Response> {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!baseUrl) throw new Error(API_UNAVAILABLE_MESSAGE);

  const headers = new Headers(options.headers);
  if (authenticated && typeof window !== "undefined") {
    let token: string | null;
    try {
      token = window.localStorage.getItem(ACCESS_TOKEN_KEY);
    } catch {
      throw new Error("No se pudo comprobar la sesión. Permite el almacenamiento local e inténtalo de nuevo.");
    }
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, {
      cache: "no-store",
      ...options,
      headers,
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new Error(API_CONNECTION_MESSAGE);
  }

  if (authenticated && response.status === 401) {
    if (typeof window !== "undefined") {
      try {
        window.localStorage.removeItem(ACCESS_TOKEN_KEY);
      } finally {
        // This shared service runs outside React; reload to discard authenticated UI state.
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign("/login");
      }
    }
    throw new Error("Tu sesión ha caducado o no es válida. Inicia sesión de nuevo.");
  }

  return response;
}
