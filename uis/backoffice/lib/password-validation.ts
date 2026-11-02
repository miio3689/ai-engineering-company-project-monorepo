import type { PasswordField } from "@/types/auth";

export type PasswordPairErrors = Partial<Record<"new_password" | "confirm_password", string>>;

export function validatePasswordPair(
  newPassword: string,
  confirmation: string,
): PasswordPairErrors {
  const errors: PasswordPairErrors = {};
  if (!newPassword) errors.new_password = "Introduce una contraseña nueva.";
  if (!confirmation) {
    errors.confirm_password = "Confirma la nueva contraseña.";
  } else if (newPassword && confirmation !== newPassword) {
    errors.confirm_password = "Las contraseñas no coinciden.";
  }
  return errors;
}

export function firstPasswordError(errors: Partial<Record<PasswordField, string>>): PasswordField | undefined {
  return (Object.keys(errors) as PasswordField[])[0];
}