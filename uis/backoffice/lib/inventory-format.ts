const quantityFormatter = new Intl.NumberFormat("es-ES", {
  maximumFractionDigits: 3,
});

const orderDateFormatter = new Intl.DateTimeFormat("es-ES", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatQuantity(value: number): string {
  return quantityFormatter.format(value);
}

export function formatOrderDate(isoString: string): string {
  const hasTimezone = /(?:z|[+-]\d{2}:\d{2})$/i.test(isoString);
  const date = new Date(hasTimezone ? isoString : `${isoString}Z`);

  return Number.isNaN(date.getTime())
    ? "Fecha no disponible"
    : orderDateFormatter.format(date);
}