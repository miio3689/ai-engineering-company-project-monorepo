"use client";

import { useState, type FormEvent } from "react";

import { forgotPassword } from "@/services/auth";

export function useForgotPassword() {
  const [busy, setBusy] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function edit() {
    setError(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || submitted) return;
    const form = event.currentTarget;
    const email = String(new FormData(form).get("email") ?? "").trim();
    const emailInput = form.elements.namedItem("email");
    if (emailInput instanceof HTMLInputElement && !emailInput.checkValidity()) {
      emailInput.focus();
      emailInput.reportValidity();
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await forgotPassword({ email });
      setSubmitted(true);
    } catch {
      setError("No se pudo completar la solicitud. Comprueba tu conexión e inténtalo de nuevo.");
    } finally {
      setBusy(false);
    }
  }

  return { busy, submitted, error, edit, submit };
}