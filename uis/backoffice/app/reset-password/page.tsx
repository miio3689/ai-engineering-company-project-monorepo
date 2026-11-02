import { Suspense } from "react";
import type { Metadata } from "next";

import ResetPasswordForm from "@/components/reset-password-form";

export const metadata: Metadata = {
  title: "Restablecer contraseña | Brasaland",
  description: "Elige una nueva contraseña para tu cuenta de Brasaland.",
};

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<p role="status" className="mx-auto my-10 w-[92%] max-w-lg text-gray-800">Cargando formulario de restablecimiento…</p>}>
      <ResetPasswordForm />
    </Suspense>
  );
}