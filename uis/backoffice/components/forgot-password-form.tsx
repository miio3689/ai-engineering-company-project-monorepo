"use client";

import Link from "next/link";

import { useForgotPassword } from "@/hooks/use-forgot-password";

const fieldClass = "min-h-11 w-full rounded-lg border border-gray-400 bg-white px-3 py-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-700";

export default function ForgotPasswordForm() {
  const { busy, submitted, error, edit, submit } = useForgotPassword();

  return (
    <main className="mx-auto my-6 grid w-[92%] max-w-lg gap-5 rounded-2xl border border-gray-200 bg-white p-5 text-gray-800 sm:my-12 sm:p-8" itemScope itemType="https://schema.org/WebPage">
      <header className="grid gap-2">
        <p className="font-semibold text-orange-700">Brasaland · Backoffice</p>
        <h1 className="text-2xl font-bold" itemProp="name">Recuperar contraseña</h1>
        <p>Indica el correo asociado a tu cuenta.</p>
      </header>
      <form noValidate onSubmit={submit} aria-busy={busy}>
        <fieldset disabled={busy || submitted} className="grid gap-4 disabled:opacity-70">
          <legend className="sr-only">Correo de la cuenta</legend>
          <div className="grid gap-2">
            <label htmlFor="forgot-email" className="font-semibold">Correo electrónico</label>
            <input id="forgot-email" name="email" type="email" autoComplete="email" autoCapitalize="none" required onChange={edit} className={fieldClass} />
          </div>
          <button type="submit" disabled={busy || submitted} className="min-h-11 rounded-lg bg-orange-700 px-4 font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60">
            {busy ? "Enviando…" : submitted ? "Solicitud enviada" : "Enviar instrucciones"}
          </button>
        </fieldset>
        {submitted && <p role="status" className="mt-4 rounded-lg bg-green-50 p-3 text-gray-800">Si esa dirección está registrada, recibirás un enlace en breve.</p>}
        {error && <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-red-900">{error}</p>}
      </form>
      <Link href="/login" className="w-fit rounded underline focus-visible:outline-2 focus-visible:outline-offset-4">Volver a iniciar sesión</Link>
    </main>
  );
}