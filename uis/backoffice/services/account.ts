import { apiRequest } from "@/services/api-client";
import {
  API_UNAVAILABLE_MESSAGE,
  INVALID_API_RESPONSE_MESSAGE,
  readJsonResponse,
} from "@/services/api-errors";
import type { Account, Profile, ProfileInput } from "@/types/account";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isProfile(value: unknown): value is Profile {
  return isRecord(value)
    && typeof value.id === "number"
    && typeof value.user_id === "number"
    && typeof value.name === "string"
    && (typeof value.phone === "string" || value.phone === null)
    && (typeof value.address === "string" || value.address === null);
}

function isAccount(value: unknown): value is Account {
  return isRecord(value)
    && typeof value.email === "string"
    && (value.role === "admin" || value.role === "manager" || value.role === "user")
    && (value.profile === null || isProfile(value.profile));
}

async function checkResponse(response: Response, action: string): Promise<void> {
  if (response.ok) return;
  if (response.status === 404) {
    throw new Error("No hay un perfil asociado a esta cuenta. Contacta con la administración para que lo cree.");
  }
  if (response.status === 422) {
    throw new Error("No se pudieron validar los datos del perfil. Revisa el nombre, el teléfono y la dirección.");
  }
  throw new Error(`No se pudo ${action}. ${API_UNAVAILABLE_MESSAGE}`);
}

export async function fetchAccount(signal?: AbortSignal): Promise<Account> {
  const response = await apiRequest("/auth/me", { signal });
  await checkResponse(response, "cargar la cuenta");
  const account = await readJsonResponse<unknown>(response);
  if (!isAccount(account)) throw new Error(INVALID_API_RESPONSE_MESSAGE);
  return account;
}

export async function updateProfile(input: ProfileInput): Promise<Profile> {
  const response = await apiRequest("/profiles/me", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: input.name, phone: input.phone, address: input.address }),
  });
  await checkResponse(response, "guardar el perfil");
  const profile = await readJsonResponse<unknown>(response);
  if (!isProfile(profile)) throw new Error(INVALID_API_RESPONSE_MESSAGE);
  return profile;
}
