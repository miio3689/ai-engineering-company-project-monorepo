"use client";

import { useChangePassword } from "@/hooks/use-change-password";

const fieldClass = "min-h-11 w-full rounded-lg border bg-white px-3 py-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-700";

export default function ChangePasswordForm() {
  const { busy, errors, error, success, formRef, edit, submit } = useChangePassword();

  return (
    <main className="mx-auto my-6 grid w-[92%] max-w-lg gap-5 rounded-2xl border border-gray-200 bg-white p-5 text-gray-800 sm:my-12 sm:p-8" itemScope itemType="https://schema.org/WebPage">
      <header className="grid gap-2">
        <p className="font-semibold text-orange-700">Brasaland · Backoffice</p>
        <h1 className="text-2xl font-bold" itemProp="name">Cambiar contraseña</h1>
        <p>Confirma tu contraseña actual y elige una nueva.</p>
      </header>
      <form ref={formRef} noValidate onSubmit={submit} aria-busy={busy}>
        <fieldset disabled={busy} className="grid gap-4 disabled:opacity-70">
          <legend className="sr-only">Datos de contraseña</legend>
          <div className="grid gap-2">
            <label htmlFor="change-current-password" className="font-semibold">Contraseña actual</label>
            <input id="change-current-password" name="current_password" type="password" autoComplete="current-password" required aria-invalid={Boolean(errors.current_password)} aria-describedby={errors.current_password ? "change-current-password-error" : undefined} onChange={() => edit("current_password")} className={`${fieldClass} ${errors.current_password ? "border-red-700" : "border-gray-400"}`} />
            {errors.current_password && <p id="change-current-password-error" role="alert" className="text-sm text-red-800">{errors.current_password}</p>}
          </div>
          <div className="grid gap-2">
            <label htmlFor="change-new-password" className="font-semibold">Nueva contraseña</label>
            <input id="change-new-password" name="new_password" type="password" autoComplete="new-password" required aria-invalid={Boolean(errors.new_password)} aria-describedby={errors.new_password ? "change-new-password-error" : undefined} onChange={() => edit("new_password")} className={`${fieldClass} ${errors.new_password ? "border-red-700" : "border-gray-400"}`} />
            {errors.new_password && <p id="change-new-password-error" role="alert" className="text-sm text-red-800">{errors.new_password}</p>}
          </div>
          <div className="grid gap-2">
            <label htmlFor="change-confirm-password" className="font-semibold">Confirmar nueva contraseña</label>
            <input id="change-confirm-password" name="confirm_password" type="password" autoComplete="new-password" required aria-invalid={Boolean(errors.confirm_password)} aria-describedby={errors.confirm_password ? "change-confirm-password-error" : undefined} onChange={() => edit("confirm_password")} className={`${fieldClass} ${errors.confirm_password ? "border-red-700" : "border-gray-400"}`} />
            {errors.confirm_password && <p id="change-confirm-password-error" role="alert" className="text-sm text-red-800">{errors.confirm_password}</p>}
          </div>
          <button type="submit" className="min-h-11 rounded-lg bg-orange-700 px-4 font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60">{busy ? "Guardando…" : "Cambiar contraseña"}</button>
        </fieldset>
        <p role="status" className="mt-3">{busy ? "Actualizando la contraseña…" : success ? "Contraseña actualizada correctamente." : ""}</p>
        {error && <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-red-900">{error}</p>}
      </form>
    </main>
  );
}