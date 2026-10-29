"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { fetchAccount, updateProfile } from "@/services/account";
import type { Account, ProfileInput } from "@/types/account";

function friendlyError(error: unknown): string {
  if (error instanceof TypeError) return "No se pudo conectar con la API. Comprueba tu conexión e inténtalo de nuevo.";
  if (error instanceof SyntaxError) return "La API devolvió una respuesta no válida. Inténtalo de nuevo.";
  return error instanceof Error ? error.message : "No se pudo completar la solicitud. Inténtalo de nuevo.";
}

export function useAccountProfile() {
  const [account, setAccount] = useState<Account | null>(null);
  const [draft, setDraft] = useState<ProfileInput>({ name: "", phone: null, address: null });
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchAccount(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        setAccount(data);
        setDraft(data.profile ? { name: data.profile.name, phone: data.profile.phone, address: data.profile.address } : { name: "", phone: null, address: null });
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) setError(friendlyError(caught));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [attempt]);

  function retry() {
    setError(null);
    setLoading(true);
    setAttempt((value) => value + 1);
  }

  function edit(field: keyof ProfileInput, value: string) {
    setDraft((current) => ({ ...current, [field]: value }));
    setSuccess(false);
    setNameError(null);
  }

  function reset() {
    if (!account?.profile) return;
    const { name, phone, address } = account.profile;
    setDraft({ name, phone, address });
    setError(null);
    setNameError(null);
    setSuccess(false);
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving || !account?.profile) return;
    setError(null);
    setSuccess(false);
    if (!draft.name.trim()) {
      setNameError("Introduce tu nombre.");
      nameRef.current?.focus();
      return;
    }
    setNameError(null);
    setSaving(true);
    try {
      const profile = await updateProfile({
        name: draft.name.trim(),
        phone: draft.phone?.trim() || null,
        address: draft.address?.trim() || null,
      });
      setAccount((current) => current ? { ...current, profile } : current);
      setDraft({ name: profile.name, phone: profile.phone, address: profile.address });
      setSuccess(true);
    } catch (caught) {
      setError(friendlyError(caught));
    } finally {
      setSaving(false);
    }
  }

  return { account, draft, loading, saving, error, success, nameError, nameRef, edit, reset, retry, save };
}
