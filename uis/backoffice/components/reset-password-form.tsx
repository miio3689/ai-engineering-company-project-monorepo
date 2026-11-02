"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { useResetPassword } from "@/hooks/use-reset-password";

const fieldClass = "min-h-11 w-full rounded-lg border bg-white px-3 py-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-700";

export default function ResetPasswordForm() {
  const token = useSearchParams().get("token")?.trim() ?? "";
  const { busy, errors, error, formRef, edit, submit } = useResetPassword(token);

  if (!token) {
    return (
      <main className="mx-auto my-6 grid w-[92%] max-w-lg gap-5 rounded-2xl border border-gray-200 bg-white p-5 text-gray-800 sm:my-12 sm:p-8" itemScope itemType="https://schema.org/WebPage">
        <header className="grid gap-2">
          <p className="font-semibold text-orange-700">Brasaland · Backoffice</p>
          <h1 className="text-2xl font-bold" itemProp="name">Restablecer contraseña</h1>
        </header>
        <p role="alert" className="rounded-lg bg-red-50 p-3 text-red-900">El enlace no es válido, ha caducado o ya se ha utilizado.</p>
        <Link href="/forgot-password" className="w-fit rounded underline focus-visible:outline-2 focus-visible:outline-offset-4">Solicitar un enlace nuevo</Link>
      </main>
    );
  }

  return (
    <main className="mx-auto my-6 grid w-[92%] max-w-lg gap-5 rounded-2xl border border-gray-200 bg-white p-5 text-gray-800 sm:my-12 sm:p-8" itemScope itemType="https://schema.org/WebPage">
      <header className="grid gap-2">
        <p className="font-semibold text-orange-700">Brasaland · Backoffice</p>
        <h1 className="text-2xl font-bold" itemProp="name">Restablecer contraseña</h1>
        <p>Elige una contraseña nueva para tu cuenta.</p>
      </header>
      <form ref={formRef} noValidate onSubmit={submit} aria-busy={busy}>
        <fieldset disabled={busy} className="grid gap-4 disabled:opacity-70">
          <legend className="sr-only">Nueva contraseña</legend>
          <div className="grid gap-2">
            <label htmlFor="reset-new-password" className="font-semibold">Nueva contraseña</label>
            <input id="reset-new-password" name="new_password" type="password" autoComplete="new-password" required aria-invalid={Boolean(errors.new_password)} aria-describedby={errors.new_password ? "reset-new-password-error" : undefined} onChange={() => edit("new_password")} className={`${fieldClass} ${errors.new_password ? "border-red-700" : "border-gray-400"}`} />
            {errors.new_password && <p id="reset-new-password-error" role="alert" className="text-sm text-red-800">{errors.new_password}</p>}
          </div>
          <div className="grid gap-2">
            <label htmlFor="reset-confirm-password" className="font-semibold">Confirmar nueva contraseña</label>
            <input id="reset-confirm-password" name="confirm_password" type="password" autoComplete="new-password" required aria-invalid={Boolean(errors.confirm_password)} aria-describedby={errors.confirm_password ? "reset-confirm-password-error" : undefined} onChange={() => edit("confirm_password")} className={`${fieldClass} ${errors.confirm_password ? "border-red-700" : "border-gray-400"}`} />
            {errors.confirm_password && <p id="reset-confirm-password-error" role="alert" className="text-sm text-red-800">{errors.confirm_password}</p>}
          </div>
          <button type="submit" className="min-h-11 rounded-lg bg-orange-700 px-4 font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60">{busy ? "Guardando…" : "Guardar contraseña"}</button>
        </fieldset>
        <p role="status" className="mt-3">{busy ? "Actualizando la contraseña…" : ""}</p>
        {error && <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-red-900">{error}</p>}
      </form>
      {error && <Link href="/forgot-password" className="w-fit rounded underline focus-visible:outline-2 focus-visible:outline-offset-4">Solicitar un enlace nuevo</Link>}
    </main>
  );
}