import { apiRequest } from "@/services/api-client";
import type { Account, Profile, ProfileInput } from "@/types/account";

async function checkResponse(response: Response, action: string): Promise<void> {
  if (response.ok) return;
  if (response.status === 404) {
    throw new Error("No hay un perfil asociado a esta cuenta. Contacta con la administración para que lo cree.");
  }
  if (response.status === 422) {
    throw new Error("No se pudieron validar los datos del perfil. Revisa el nombre, el teléfono y la dirección.");
  }
  throw new Error(`No se pudo ${action} (HTTP ${response.status}). Inténtalo de nuevo.`);
}

export async function fetchAccount(signal?: AbortSignal): Promise<Account> {
  const response = await apiRequest("/auth/me", { signal });
  await checkResponse(response, "cargar la cuenta");
  return (await response.json()) as Account;
}

export async function updateProfile(input: ProfileInput): Promise<Profile> {
  const response = await apiRequest("/profiles/me", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: input.name, phone: input.phone, address: input.address }),
  });
  await checkResponse(response, "guardar el perfil");
  return (await response.json()) as Profile;
}
