import { apiRequest } from "@/services/api-client";
import {
  API_UNAVAILABLE_MESSAGE,
  INVALID_API_RESPONSE_MESSAGE,
  readJsonResponse,
} from "@/services/api-errors";
import type {
  LocationPerformance,
  PipelineRunSummary,
  WeeklyLocationPerformance,
} from "@/types/business-performance";

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isLocationPerformance(value: unknown): value is LocationPerformance {
  return isRecord(value)
    && typeof value.location_id === "string"
    && typeof value.country === "string"
    && typeof value.currency === "string"
    && isFiniteNumber(value.total_purchase_cost)
    && isFiniteNumber(value.total_waste_cost)
    && isFiniteNumber(value.waste_ratio)
    && isFiniteNumber(value.stockout_events_count)
    && isFiniteNumber(value.price_alert_events_count);
}

function isWeeklyLocationPerformance(value: unknown): value is WeeklyLocationPerformance {
  if (!isRecord(value)) return false;
  const weekIsValid = value.week_start === null
    || (typeof value.week_start === "string" && ISO_DAY.test(value.week_start));
  return weekIsValid
    && Array.isArray(value.locations)
    && value.locations.every(isLocationPerformance);
}

/** KPIs de todos los locales para una semana (por defecto, la última semana cerrada). */
export async function fetchWeeklyLocationPerformance(
  weekStart: string | null,
  signal?: AbortSignal,
): Promise<WeeklyLocationPerformance> {
  const query = weekStart ? `?week_start=${encodeURIComponent(weekStart)}` : "";
  const response = await apiRequest(`/reporting/weekly-location-performance${query}`, { signal });
  if (!response.ok) throw new Error(API_UNAVAILABLE_MESSAGE);
  const payload = await readJsonResponse<unknown>(response);
  if (!isWeeklyLocationPerformance(payload)) throw new Error(INVALID_API_RESPONSE_MESSAGE);
  return payload;
}

/** Última corrida del pipeline (para mostrar cuándo se actualizaron los datos), o null. */
export async function fetchLatestPipelineRun(
  signal?: AbortSignal,
): Promise<PipelineRunSummary | null> {
  const response = await apiRequest("/reporting/pipeline-runs/latest", { signal });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(API_UNAVAILABLE_MESSAGE);
  const payload = await readJsonResponse<unknown>(response);
  if (
    !isRecord(payload)
    || typeof payload.status !== "string"
    || typeof payload.started_at !== "string"
    || !(payload.finished_at === null || typeof payload.finished_at === "string")
  ) {
    throw new Error(INVALID_API_RESPONSE_MESSAGE);
  }
  return {
    status: payload.status,
    started_at: payload.started_at,
    finished_at: payload.finished_at,
  };
}
