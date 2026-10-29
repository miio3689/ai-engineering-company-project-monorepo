"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useSyncExternalStore, type ReactNode } from "react";

import { ACCESS_TOKEN_KEY } from "@/services/api-client";

type SessionState = "checking" | "authenticated" | "anonymous" | "unavailable";

function getSessionSnapshot(): SessionState {
  try {
    return window.localStorage.getItem(ACCESS_TOKEN_KEY)?.trim() ? "authenticated" : "anonymous";
  } catch {
    return "unavailable";
  }
}

function getServerSnapshot(): SessionState {
  return "checking";
}

function subscribe(onChange: () => void) {
  window.addEventListener("storage", onChange);
  window.addEventListener("focus", onChange);
  window.addEventListener("pageshow", onChange);
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener("focus", onChange);
    window.removeEventListener("pageshow", onChange);
  };
}

function ProtectedContent({ children }: { children: ReactNode }) {
  const router = useRouter();
  const session = useSyncExternalStore(subscribe, getSessionSnapshot, getServerSnapshot);

  useEffect(() => {
    if (session === "anonymous") router.replace("/login");
  }, [router, session]);

  if (session === "unavailable") {
    return (
      <main className="mx-auto my-10 grid w-[92%] max-w-lg gap-4 rounded-xl bg-white p-6 text-gray-800">
        <p role="alert">No se puede comprobar la sesión. Permite el almacenamiento local en tu navegador y vuelve a intentarlo.</p>
        <Link href="/login" className="rounded underline focus-visible:outline-2 focus-visible:outline-offset-4">Ir a iniciar sesión</Link>
      </main>
    );
  }

  if (session !== "authenticated") {
    return <p role="status" className="mx-auto my-10 w-[92%] max-w-lg text-gray-800">Comprobando sesión…</p>;
  }

  return children;
}

export default function AuthGuard({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  if (pathname === "/login" || pathname === "/register") return children;

  return <ProtectedContent key={pathname}>{children}</ProtectedContent>;
}
