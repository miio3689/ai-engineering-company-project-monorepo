"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { ACCESS_TOKEN_KEY } from "@/services/api-client";

const linkClass = "flex min-h-11 items-center rounded px-2 underline focus-visible:outline-2 focus-visible:outline-offset-2";
const links = [
  { href: "/", label: "Candidaturas" },
  { href: "/incidents", label: "Incidencias" },
  { href: "/suppliers", label: "Proveedores" },
  { href: "/account/profile", label: "Mi perfil" },
];

export default function BackofficeNavigation() {
  const pathname = usePathname();
  const [error, setError] = useState<string | null>(null);
  if (pathname === "/login" || pathname === "/register") return null;

  function logout() {
    try {
      window.localStorage.removeItem(ACCESS_TOKEN_KEY);
    } catch {
      setError("No se pudo cerrar la sesión. Permite el almacenamiento local y vuelve a intentarlo.");
      return;
    }
    window.dispatchEvent(new Event("storage"));
    // Drop the authenticated document and its in-memory Next.js router cache.
    window.location.replace("/login");
  }

  return (
    <header className="border-b border-gray-200 bg-white px-4 py-2 text-gray-800">
      <nav className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-3 gap-y-1" aria-label="Navegación del backoffice">
        {links.map(({ href, label }) => (
          <Link key={href} href={href} aria-current={pathname === href ? "page" : undefined} className={linkClass}>{label}</Link>
        ))}
        <button type="button" onClick={logout} className="min-h-11 rounded-lg border border-gray-400 px-3 focus-visible:outline-2 focus-visible:outline-offset-2 sm:ml-auto">Cerrar sesión</button>
      </nav>
      {error && <p role="alert" className="mx-auto mt-2 max-w-6xl rounded bg-red-50 p-3 text-red-900">{error}</p>}
    </header>
  );
}
