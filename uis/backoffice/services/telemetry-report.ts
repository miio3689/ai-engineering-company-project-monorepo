import { apiRequest } from "@/services/api-client";
import {
  API_UNAVAILABLE_MESSAGE,
  INVALID_API_RESPONSE_MESSAGE,
  readJsonResponse,
} from "@/services/api-errors";
import type { TelemetryReport } from "@/types/telemetry-report";

const METRIC_KEYS = [
  "events_per_day",
  "error_rate_by_day",
  "error_rate_by_type",
  "page_load_ms_by_route",
  "auth_failure_rate",
] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isTelemetryReport(value: unknown): value is TelemetryReport {
  if (!isRecord(value)) return false;
  const { period, metrics } = value;
  if (!isRecord(period) || !isRecord(metrics)) return false;
  return typeof period.from === "string"
    && typeof period.to === "string"
    && METRIC_KEYS.every((key) => Array.isArray(metrics[key]));
}

export async function fetchTelemetryReport(
  signal?: AbortSignal,
): Promise<TelemetryReport> {
  const response = await apiRequest("/telemetry/report", { signal });
  if (!response.ok) throw new Error(API_UNAVAILABLE_MESSAGE);
  const payload = await readJsonResponse<unknown>(response);
  if (!isTelemetryReport(payload)) throw new Error(INVALID_API_RESPONSE_MESSAGE);
  return payload;
}
