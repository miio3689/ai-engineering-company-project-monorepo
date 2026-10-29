import type { Metadata } from "next";
import type { ReactNode } from "react";

import AuthGuard from "@/components/auth-guard";

import "./globals.css";

export const metadata: Metadata = {
  title: "Talent Pipeline Tracker",
  description: "Gestion interna de candidaturas para Brasaland.",
};

interface RootLayoutProps {
  children: ReactNode;
}

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="es">
      <body><AuthGuard>{children}</AuthGuard></body>
    </html>
  );
}
