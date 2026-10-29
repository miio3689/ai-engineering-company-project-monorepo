"use client";

import { useAccountProfile } from "@/hooks/use-account-profile";

const fieldClass = "min-h-11 w-full rounded-lg border border-gray-400 bg-white px-3 py-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-700";

export default function AccountProfile() {
  const { account, draft, loading, saving, error, success, nameError, nameRef, edit, reset, retry, save } = useAccountProfile();

  return (
    <main className="mx-auto my-6 grid w-[92%] max-w-2xl gap-5 rounded-2xl border border-gray-200 bg-white p-5 text-gray-800 sm:my-10 sm:p-8" itemScope itemType="https://schema.org/ProfilePage">
      <header className="grid gap-2">
        <h1 className="text-2xl font-bold" itemProp="name">Mi perfil</h1>
        <p>Consulta tu cuenta y actualiza tus datos de perfil.</p>
      </header>
      {loading ? <p role="status">Cargando cuenta…</p> : account && (
        <>
          <dl className="grid gap-1">
            <dt className="font-semibold">Correo electrónico</dt>
            <dd className="break-all">{account.email}</dd>
          </dl>
          <p className="text-sm text-gray-600">El correo no se puede modificar desde esta vista.</p>
          {account.profile ? (
            <form noValidate onSubmit={save} onReset={reset} aria-busy={saving}>
              <fieldset disabled={saving} className="grid gap-4 disabled:opacity-70">
                <legend className="sr-only">Datos de perfil</legend>
                <div className="grid gap-2">
                  <label htmlFor="profile-name" className="font-semibold">Nombre *</label>
                  <input ref={nameRef} id="profile-name" name="name" autoComplete="name" required value={draft.name} onChange={(event) => edit("name", event.target.value)} aria-invalid={Boolean(nameError)} aria-describedby={nameError ? "profile-name-error" : undefined} className={fieldClass} />
                  {nameError && <p id="profile-name-error" role="alert" className="text-sm text-red-800">{nameError}</p>}
                </div>
                <div className="grid gap-2">
                  <label htmlFor="profile-phone" className="font-semibold">Teléfono (opcional)</label>
                  <input id="profile-phone" name="phone" type="tel" autoComplete="tel" value={draft.phone ?? ""} onChange={(event) => edit("phone", event.target.value)} className={fieldClass} />
                </div>
                <div className="grid gap-2">
                  <label htmlFor="profile-address" className="font-semibold">Dirección (opcional)</label>
                  <input id="profile-address" name="address" autoComplete="street-address" value={draft.address ?? ""} onChange={(event) => edit("address", event.target.value)} className={fieldClass} />
                </div>
                <div className="flex flex-wrap gap-3">
                  <button type="submit" className="min-h-11 rounded-lg bg-orange-700 px-4 font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-2">{saving ? "Guardando…" : "Guardar cambios"}</button>
                  <button type="reset" className="min-h-11 rounded-lg border border-gray-400 px-4 focus-visible:outline-2 focus-visible:outline-offset-2">Restablecer cambios</button>
                </div>
              </fieldset>
              <p role="status" className="mt-3">{saving ? "Guardando perfil…" : success ? "Perfil actualizado correctamente." : ""}</p>
            </form>
          ) : <p role="status">No hay un perfil asociado a tu cuenta. Contacta con la administración para que lo cree; esta API solo permite actualizar perfiles existentes.</p>}
        </>
      )}
      {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-red-900">{error}</p>}
      {!loading && !account && <button type="button" onClick={retry} className="min-h-11 rounded-lg border border-gray-400 px-4 focus-visible:outline-2 focus-visible:outline-offset-2">Reintentar carga</button>}
    </main>
  );
}
