"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

interface PageLoadErrorProps {
  title: string;
  message: string;
  exitHref: string;
  exitLabel: string;
}

export default function PageLoadError({
  title,
  message,
  exitHref,
  exitLabel,
}: PageLoadErrorProps) {
  const router = useRouter();

  return (
    <main className="page-shell">
      <section className="empty-state" role="alert">
        <h1>{title}</h1>
        <p>{message}</p>
        <div className="flex flex-wrap justify-center gap-3">
          <button type="button" className="primary-button" onClick={() => router.refresh()}>
            Reintentar
          </button>
          <Link className="candidate-link" href={exitHref}>
            {exitLabel}
          </Link>
        </div>
      </section>
    </main>
  );
}
