"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import { validateAuthForm } from "@/lib/auth-form-validation";
import { ACCESS_TOKEN_KEY } from "@/services/api-client";
import { AuthError, login, register } from "@/services/auth";
import { startTelemetrySession, track } from "@/services/telemetry";
import type { AuthFieldErrors, AuthMode, RegistrationInput } from "@/types/auth";

let failedLoginAttempts = 0;

type LoginFailureReason = "invalid_credentials" | "validation_error" | "service_error";

function loginFailureReason(caught: unknown): LoginFailureReason {
  if (caught instanceof AuthError && caught.code === "invalid_credentials") return "invalid_credentials";
  if (caught instanceof AuthError && Object.keys(caught.fields).length) return "validation_error";
  return "service_error";
}

// Nunca incluye el correo ni la contraseña escritos.
function trackLoginFailure(reason: LoginFailureReason) {
  failedLoginAttempts += 1;
  track("login_failed", { failure_reason: reason, attempt_number_in_session: failedLoginAttempts });
}

export function useAuthForm(mode: AuthMode) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<AuthFieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    const first = Object.keys(errors)[0];
    if (!busy && first) {
      const element = formRef.current?.elements.namedItem(first);
      if (element instanceof HTMLInputElement) element.focus();
    }
  }, [busy, errors]);

  function reset() {
    setErrors({});
    setError(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const input: RegistrationInput = {
      email: String(data.get("email") ?? "").trim(),
      password: String(data.get("password") ?? ""),
    };
    if (mode === "register") {
      for (const field of ["name", "phone", "address"] as const) {
        const value = String(data.get(field) ?? "").trim();
        if (value) input[field] = value;
      }
    }
    reset();
    const validation = validateAuthForm(input, mode);
    if (Object.keys(validation).length) {
      setErrors(validation);
      if (mode === "login") trackLoginFailure("validation_error");
      return;
    }

    setBusy(true);
    let accountCreated = false;
    try {
      if (mode === "register") {
        await register(input);
        accountCreated = true;
      }
      const token = await login(input);
      window.localStorage.setItem(ACCESS_TOKEN_KEY, token.access_token);
      failedLoginAttempts = 0;
      startTelemetrySession();
      track("login_succeeded", { auth_method: "password" });
      router.replace("/");
    } catch (caught) {
      if (mode === "login") trackLoginFailure(loginFailureReason(caught));
      if (accountCreated) {
        setError("Tu cuenta se ha creado, pero no se pudo completar el inicio de sesión. Ve a Iniciar sesión con tus credenciales; no necesitas registrarte otra vez.");
      } else if (caught instanceof AuthError) {
        setErrors(caught.fields);
        setError(caught.message || null);
      } else if (caught instanceof DOMException) {
        setError("No se pudo guardar la sesión. Permite el almacenamiento local en tu navegador e inténtalo de nuevo.");
      } else if (caught instanceof TypeError) {
        setError("No se pudo conectar con la API. Comprueba tu conexión e inténtalo de nuevo.");
      } else {
        setError(caught instanceof Error ? caught.message : "No se pudo completar la solicitud. Inténtalo de nuevo.");
      }
    } finally {
      setBusy(false);
    }
  }

  return { busy, errors, error, submit, reset, formRef };
}
