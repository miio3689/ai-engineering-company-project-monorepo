export const ACCESS_TOKEN_KEY = "access_token";

export async function apiRequest(
  path: string,
  options: RequestInit = {},
  { authenticated = true }: { authenticated?: boolean } = {},
): Promise<Response> {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!baseUrl) throw new Error("Falta NEXT_PUBLIC_API_BASE_URL en el entorno.");

  const headers = new Headers(options.headers);
  if (authenticated && typeof window !== "undefined") {
    const token = window.localStorage.getItem(ACCESS_TOKEN_KEY);
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, {
    cache: "no-store",
    ...options,
    headers,
  });

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
