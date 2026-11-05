"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const sections = [
  { href: "/inventory/products", label: "Productos" },
  { href: "/inventory/orders/inbound", label: "Registrar entrada" },
  { href: "/inventory/orders/outbound", label: "Registrar salida" },
  { href: "/inventory/orders", label: "Historial de órdenes" },
];

export default function InventoryNavigation() {
  const pathname = usePathname();

  return (
    <nav
      className="flex flex-wrap gap-2"
      aria-label="Navegación del inventario"
    >
      {sections.map(({ href, label }) => (
        <Link
          key={href}
          href={href}
          aria-current={pathname === href ? "page" : undefined}
          className={`inline-flex min-h-11 items-center rounded-lg border px-4 font-semibold underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-700 ${
            pathname === href
              ? "border-orange-700 bg-orange-700 text-white"
              : "border-gray-300 bg-white text-gray-800 hover:bg-orange-50"
          }`}
        >
          {label}
        </Link>
      ))}
    </nav>
  );
}