import { apiRequest } from "@/services/api-client";
import type { AuthField, AuthFieldErrors, AuthToken, LoginInput, RegistrationInput } from "@/types/auth";

const fieldMessages: Record<AuthField, string> = {
  email: "Introduce un correo válido, por ejemplo nombre@empresa.com.",
  password: "Introduce una contraseña válida.",
  name: "Introduce tu nombre si incluyes teléfono o dirección.",
  phone: "Revisa el teléfono.",
  address: "Revisa la dirección.",
};

export class AuthError extends Error {
  constructor(message: string, public readonly fields: AuthFieldErrors = {}) {
    super(message);
    this.name = "AuthError";
  }
}

async function readAuthJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch (error) {
    if (!(error instanceof SyntaxError)) throw error;
    throw new AuthError("La API devolvió una respuesta no válida. Inténtalo de nuevo.");
  }
}

async function responseError(response: Response, registration: boolean): Promise<AuthError> {
  if (registration && response.status === 409) {
    return new AuthError("", { email: "Ya existe una cuenta con este correo. Inicia sesión o usa otro." });
  }
  if (!registration && response.status === 401) {
    return new AuthError("El correo o la contraseña no son correctos.");
  }
  if (response.status === 422) {
    const payload = await readAuthJson(response);
    const fields: AuthFieldErrors = {};
    let unrecognized = false;
    if (payload && typeof payload === "object" && "detail" in payload && Array.isArray(payload.detail)) {
      for (const issue of payload.detail) {
        if (!issue || typeof issue !== "object") {
          unrecognized = true;
          continue;
        }
        const field: unknown = "loc" in issue && Array.isArray(issue.loc) ? issue.loc[1] : undefined;
        if (typeof field === "string" && Object.hasOwn(fieldMessages, field)) {
          const key = field as AuthField;
          fields[key] = fieldMessages[key];
        } else if ("msg" in issue && typeof issue.msg === "string" && issue.msg.includes("name es obligatorio")) {
          fields.name = fieldMessages.name;
        } else {
          unrecognized = true;
        }
      }
    } else {
      unrecognized = true;
    }
    return new AuthError(
      unrecognized || !Object.keys(fields).length ? "No se pudieron validar los datos enviados. Revisa el formulario." : "",
      fields,
    );
  }
  return new AuthError(`No se pudo ${registration ? "crear la cuenta" : "iniciar sesión"} (HTTP ${response.status}). Inténtalo de nuevo.`);
}

export async function login(input: LoginInput): Promise<AuthToken> {
  const response = await apiRequest("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: input.email, password: input.password }),
  }, { authenticated: false });
  if (!response.ok) throw await responseError(response, false);

  const token = await readAuthJson(response);
  if (
    !token || typeof token !== "object"
    || !("access_token" in token) || typeof token.access_token !== "string" || !token.access_token.trim()
    || !("token_type" in token) || token.token_type !== "bearer"
  ) {
    throw new AuthError("La API no devolvió un token válido. Inténtalo de nuevo.");
  }
  return { access_token: token.access_token, token_type: token.token_type };
}

export async function register(input: RegistrationInput): Promise<void> {
  const response = await apiRequest("/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  }, { authenticated: false });
  if (!response.ok) throw await responseError(response, true);
}
