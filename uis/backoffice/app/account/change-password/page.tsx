import type { Metadata } from "next";

import ChangePasswordForm from "@/components/change-password-form";

export const metadata: Metadata = {
  title: "Cambiar contraseña | Brasaland",
  description: "Actualiza la contraseña de tu cuenta de Brasaland.",
};

export default function ChangePasswordPage() {
  return <ChangePasswordForm />;
}