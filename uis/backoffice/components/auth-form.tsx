"use client";

import Link from "next/link";

import { useAuthForm } from "@/hooks/use-auth-form";
import type { AuthField, AuthMode } from "@/types/auth";

const fieldClass = "min-h-11 w-full rounded-lg border bg-white px-3 py-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-700";

export default function AuthForm({ mode }: { mode: AuthMode }) {
  const { busy, errors, error, submit, reset, formRef } = useAuthForm(mode);
  const registration = mode === "register";
  const fields: { name: AuthField; label: string; type: string; autoComplete: string; required?: boolean }[] = [
    { name: "email", label: "Correo electrónico", type: "email", autoComplete: "username", required: true },
    { name: "password", label: "Contraseña", type: "password", autoComplete: registration ? "new-password" : "current-password", required: true },
    ...(registration ? [
      { name: "name" as const, label: "Nombre (opcional)", type: "text", autoComplete: "name" },
      { name: "phone" as const, label: "Teléfono (opcional)", type: "tel", autoComplete: "tel" },
      { name: "address" as const, label: "Dirección (opcional)", type: "text", autoComplete: "street-address" },
    ] : []),
  ];

  return (
    <main className="mx-auto my-6 w-[92%] max-w-lg rounded-2xl border border-gray-200 bg-white p-5 text-gray-800 sm:my-12 sm:p-8" itemScope itemType="https://schema.org/WebPage">
      <header className="mb-6 grid gap-2">
        <p className="font-semibold text-orange-700">Brasaland · Backoffice</p>
        <h1 className="text-2xl font-bold" itemProp="name">{registration ? "Crear cuenta" : "Iniciar sesión"}</h1>
        <p>{registration ? "Regístrate para acceder al equipo de Brasaland." : "Accede con tu correo y contraseña."}</p>
      </header>
      <form ref={formRef} noValidate onSubmit={submit} onReset={reset} aria-busy={busy}>
        <fieldset disabled={busy} className="grid gap-4 disabled:opacity-70">
          <legend className="sr-only">{registration ? "Datos de registro" : "Credenciales de acceso"}</legend>
          {fields.map((field) => (
            <div key={field.name} className="grid gap-2">
              <label htmlFor={`auth-${field.name}`} className="font-semibold">
                {field.label}{field.required ? " *" : ""}
              </label>
              <input
                id={`auth-${field.name}`}
                name={field.name}
                type={field.type}
                autoComplete={field.autoComplete}
                autoCapitalize={field.name === "email" ? "none" : undefined}
                required={field.required}
                aria-invalid={Boolean(errors[field.name])}
                aria-describedby={errors[field.name] ? `auth-${field.name}-error` : field.name === "name" ? "auth-profile-hint" : undefined}
                className={`${fieldClass} ${errors[field.name] ? "border-red-700" : "border-gray-400"}`}
              />
              {field.name === "name" && <p id="auth-profile-hint" className="text-sm text-gray-600">El nombre es necesario si indicas teléfono o dirección.</p>}
              {errors[field.name] && <p id={`auth-${field.name}-error`} role="alert" className="text-sm text-red-800">{errors[field.name]}</p>}
            </div>
          ))}
          <div className="flex flex-wrap gap-3">
            <button type="submit" className="min-h-11 rounded-lg bg-orange-700 px-4 font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-2">
              {busy ? "Conectando…" : registration ? "Crear cuenta" : "Iniciar sesión"}
            </button>
            <button type="reset" className="min-h-11 rounded-lg border border-gray-400 px-4 focus-visible:outline-2 focus-visible:outline-offset-2">Limpiar formulario</button>
          </div>
        </fieldset>
        <p role="status" className="mt-3 text-sm">{busy ? registration ? "Creando cuenta e iniciando sesión…" : "Iniciando sesión…" : ""}</p>
        {error && <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-red-900">{error}</p>}
      </form>
      <nav className="mt-6" aria-label="Acceso al backoffice">
        <Link href={registration ? "/login" : "/register"} className="rounded underline focus-visible:outline-2 focus-visible:outline-offset-4">
          {registration ? "¿Ya tienes cuenta? Iniciar sesión" : "¿No tienes cuenta? Crear cuenta"}
        </Link>
      </nav>
    </main>
  );
}
