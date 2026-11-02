import type { Metadata } from "next";

import AuthForm from "@/components/auth-form";

export const metadata: Metadata = {
  title: "Iniciar sesión | Brasaland",
  description: "Acceso al backoffice de Brasaland.",
};

interface LoginPageProps {
  searchParams: Promise<{ reset?: string | string[] }>;
}

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const { reset } = await searchParams;
  return <AuthForm mode="login" resetSuccess={reset === "success"} />;
}
