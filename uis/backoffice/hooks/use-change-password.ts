"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { validatePasswordPair } from "@/lib/password-validation";
import { AuthError, changePassword } from "@/services/auth";
import type { AuthFieldErrors, PasswordField } from "@/types/auth";

export function useChangePassword() {
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<AuthFieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    const first = Object.keys(errors)[0] as PasswordField | undefined;
    if (!busy && first) {
      const element = formRef.current?.elements.namedItem(first);
      if (element instanceof HTMLInputElement) element.focus();
    }
  }, [busy, errors]);

  function edit(field: PasswordField) {
    setErrors((current) => {
      const next = { ...current };
      delete next[field];
      if (field === "new_password" || field === "confirm_password") {
        delete next.new_password;
        delete next.confirm_password;
      }
      return next;
    });
    setError(null);
    setSuccess(false);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const currentPassword = String(data.get("current_password") ?? "");
    const newPassword = String(data.get("new_password") ?? "");
    const confirmation = String(data.get("confirm_password") ?? "");
    const nextErrors: AuthFieldErrors = validatePasswordPair(newPassword, confirmation);
    if (!currentPassword) nextErrors.current_password = "Introduce tu contraseña actual.";
    setErrors(nextErrors);
    setError(null);
    setSuccess(false);
    if (Object.keys(nextErrors).length) return;

    setBusy(true);
    try {
      await changePassword({ current_password: currentPassword, new_password: newPassword });
      form.reset();
      setSuccess(true);
    } catch (caught) {
      if (caught instanceof AuthError) {
        setErrors(caught.fields);
        setError(caught.message || null);
      } else {
        setError("No se pudo cambiar la contraseña. Comprueba tu conexión e inténtalo de nuevo.");
      }
    } finally {
      setBusy(false);
    }
  }

  return { busy, errors, error, success, formRef, edit, submit };
}