import type { Metadata } from "next";

import AccountProfile from "@/components/account-profile";

export const metadata: Metadata = {
  title: "Mi perfil | Brasaland",
  description: "Consulta tu cuenta y actualiza tus datos de perfil.",
};

export default function ProfilePage() {
  return <AccountProfile />;
}
