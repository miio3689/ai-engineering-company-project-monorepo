import type { Metadata } from "next";

import AuthForm from "@/components/auth-form";

export const metadata: Metadata = {
  title: "Crear cuenta | Brasaland",
  description: "Registro de usuarios del backoffice de Brasaland.",
};

export default function RegisterPage() {
  return <AuthForm mode="register" />;
}
