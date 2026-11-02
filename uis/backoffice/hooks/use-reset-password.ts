"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import { validatePasswordPair } from "@/lib/password-validation";
import { AuthError, resetPassword } from "@/services/auth";
import type { AuthFieldErrors, PasswordField } from "@/types/auth";

export function useResetPassword(token: string) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<AuthFieldErrors>({});
  const [error, setError] = useState<string | null>(null);
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
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const newPassword = String(data.get("new_password") ?? "");
    const confirmation = String(data.get("confirm_password") ?? "");
    const validation = validatePasswordPair(newPassword, confirmation);
    setErrors(validation);
    setError(null);
    if (Object.keys(validation).length) return;

    setBusy(true);
    try {
      await resetPassword({ token, new_password: newPassword });
      router.replace("/login?reset=success");
    } catch (caught) {
      setError(
        caught instanceof AuthError && caught.message
          ? caught.message
          : "No se pudo restablecer la contraseña. Inténtalo de nuevo.",
      );
      if (caught instanceof AuthError) setErrors(caught.fields);
    } finally {
      setBusy(false);
    }
  }

  return { busy, errors, error, formRef, edit, submit };
}