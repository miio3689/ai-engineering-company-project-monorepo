import type { Metadata } from "next";

import AuthForm from "@/components/auth-form";

export const metadata: Metadata = {
  title: "Iniciar sesión | Brasaland",
  description: "Acceso al backoffice de Brasaland.",
};

export default function LoginPage() {
  return <AuthForm mode="login" />;
}
