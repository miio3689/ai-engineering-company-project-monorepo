import type { AuthFieldErrors, AuthMode, RegistrationInput } from "@/types/auth";

export function validateAuthForm(input: RegistrationInput, mode: AuthMode): AuthFieldErrors {
  const errors: AuthFieldErrors = {};
  const parts = input.email.split("@");
  const [local = "", domain = ""] = parts;
  const validEmail = parts.length === 2 && input.email.length <= 254 && local.length > 0 && local.length <= 64
    && /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+$/.test(local)
    && !local.startsWith(".") && !local.endsWith(".") && !local.includes("..")
    && domain.split(".").length >= 2
    && domain.split(".").every((label) => /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/.test(label));
  if (!validEmail) errors.email = "Introduce un correo válido, por ejemplo nombre@empresa.com.";
  if (!input.password) errors.password = "Introduce tu contraseña.";
  if (mode === "register" && !input.name && (input.phone || input.address)) {
    errors.name = "Introduce tu nombre si incluyes teléfono o dirección.";
  }
  return errors;
}
