import type { Metadata } from "next";

import ForgotPasswordForm from "@/components/forgot-password-form";

export const metadata: Metadata = {
  title: "Recuperar contraseña | Brasaland",
  description: "Solicita un enlace para restablecer tu contraseña de Brasaland.",
};

export default function ForgotPasswordPage() {
  return <ForgotPasswordForm />;
}