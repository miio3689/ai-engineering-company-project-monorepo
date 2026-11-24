import type { LocationPerformance } from "@/types/business-performance";

const DAY_MS = 24 * 60 * 60 * 1000;
const COUNTRY_NAMES: Record<string, string> = { CO: "Colombia", US: "Estados Unidos" };

/** Una moneda: los locales de COP y de USD se reportan lado a lado, nunca sumados. */
export interface CurrencyGroup {
  currency: string;
  label: string;
  locations: LocationPerformance[];
  totals: {
    total_purchase_cost: number;
    total_waste_cost: number;
    waste_ratio: number;
    stockout_events_count: number;
    price_alert_events_count: number;
  };
}

function parseIsoDay(value: string): Date {
  return new Date(`${value}T00:00:00Z`);
}

function toIsoDay(value: Date): string {
  return value.toISOString().slice(0, 10);
}

/** Lunes de la semana ISO, desplazado `weeks` semanas (YYYY-MM-DD). */
export function shiftWeek(weekStart: string, weeks: number): string {
  return toIsoDay(new Date(parseIsoDay(weekStart).getTime() + weeks * 7 * DAY_MS));
}

/** Lunes de la semana en curso (UTC), para no ofrecer semanas futuras. */
export function currentWeekStart(today: Date = new Date()): string {
  const midnight = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  const daysSinceMonday = (today.getUTCDay() + 6) % 7;
  return toIsoDay(new Date(midnight - daysSinceMonday * DAY_MS));
}

const dayFormatter = new Intl.DateTimeFormat("es-ES", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

/** "16 de noviembre de 2026 – 22 de noviembre de 2026": de lunes a domingo. */
export function formatWeekRange(weekStart: string): string {
  const monday = parseIsoDay(weekStart);
  const sunday = new Date(monday.getTime() + 6 * DAY_MS);
  return `${dayFormatter.format(monday)} – ${dayFormatter.format(sunday)}`;
}

export function locationLabel(locationId: string): string {
  return `Local ${locationId}`;
}

export function countryName(country: string): string {
  return COUNTRY_NAMES[country] ?? country;
}

/** Ratio de merma de un conjunto de locales: merma total / compra total (0 sin compras). */
export function wasteRatio(purchaseCost: number, wasteCost: number): number {
  return purchaseCost > 0 ? wasteCost / purchaseCost : 0;
}

export function groupByCurrency(locations: LocationPerformance[]): CurrencyGroup[] {
  const byCurrency = new Map<string, LocationPerformance[]>();
  for (const location of locations) {
    byCurrency.set(location.currency, [...(byCurrency.get(location.currency) ?? []), location]);
  }
  return [...byCurrency.entries()]
    .map(([currency, rows]) => {
      const sum = (pick: (row: LocationPerformance) => number) =>
        rows.reduce((total, row) => total + pick(row), 0);
      const purchase = sum((row) => row.total_purchase_cost);
      const waste = sum((row) => row.total_waste_cost);
      const countries = [...new Set(rows.map((row) => countryName(row.country)))].join(", ");
      return {
        currency,
        label: `${countries} · ${currency}`,
        locations: rows,
        totals: {
          total_purchase_cost: purchase,
          total_waste_cost: waste,
          waste_ratio: wasteRatio(purchase, waste),
          stockout_events_count: sum((row) => row.stockout_events_count),
          price_alert_events_count: sum((row) => row.price_alert_events_count),
        },
      };
    })
    // COP (los 13 locales de Colombia) primero; después el resto por orden alfabético.
    .sort((a, b) => (a.currency === "COP" ? -1 : b.currency === "COP" ? 1 : a.currency.localeCompare(b.currency)));
}

const moneyFormatters = new Map<string, Intl.NumberFormat>();

export function formatMoney(value: number, currency: string): string {
  if (!moneyFormatters.has(currency)) {
    moneyFormatters.set(
      currency,
      new Intl.NumberFormat("es-CO", {
        style: "currency",
        currency,
        currencyDisplay: "code",
        maximumFractionDigits: currency === "COP" ? 0 : 2,
      }),
    );
  }
  return moneyFormatters.get(currency)!.format(value);
}

const percentFormatter = new Intl.NumberFormat("es-ES", {
  style: "percent",
  maximumFractionDigits: 1,
});

export function formatPercent(value: number): string {
  return percentFormatter.format(value);
}

const countFormatter = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 0 });

export function formatCount(value: number): string {
  return countFormatter.format(value);
}
