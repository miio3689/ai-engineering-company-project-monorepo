import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { registerHooks } from "node:module";
import { afterEach, beforeEach, test } from "node:test";
import ts from "typescript";

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.startsWith("@/")) {
      return nextResolve(new URL(`../${specifier.slice(2)}.ts`, import.meta.url).href, context);
    }
    return nextResolve(specifier, context);
  },
  load(url, context, nextLoad) {
    if (url.startsWith("file:") && url.endsWith(".ts")) {
      const { outputText } = ts.transpileModule(readFileSync(new URL(url), "utf8"), {
        compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
      });
      return { format: "module", source: outputText, shortCircuit: true };
    }
    return nextLoad(url, context);
  },
});

const { fetchTelemetryReport } = await import("../services/telemetry-report.ts");
const { API_UNAVAILABLE_MESSAGE, INVALID_API_RESPONSE_MESSAGE } =
  await import("../services/api-errors.ts");
const originalFetch = globalThis.fetch;
const originalBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

const validPayload = () => ({
  period: { from: "2026-11-16T00:00:00+00:00", to: "2026-11-19T00:00:00+00:00" },
  metrics: {
    events_per_day: [],
    error_rate_by_day: [],
    error_rate_by_type: [],
    page_load_ms_by_route: [],
    auth_failure_rate: [],
  },
});

let fetchCalls;
let payload;
let status;

beforeEach(() => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://api.test";
  fetchCalls = [];
  payload = validPayload();
  status = 200;
  globalThis.fetch = async (url, options) => {
    fetchCalls.push({ url, options });
    return new Response(JSON.stringify(payload), {
      status,
      headers: { "content-type": "application/json" },
    });
  };
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  if (originalBaseUrl === undefined) delete process.env.NEXT_PUBLIC_API_BASE_URL;
  else process.env.NEXT_PUBLIC_API_BASE_URL = originalBaseUrl;
});

test("devuelve el payload válido y consulta /telemetry/report", async () => {
  assert.deepEqual(await fetchTelemetryReport(), payload);
  assert.equal(fetchCalls.length, 1);
  assert.equal(fetchCalls[0].url, "http://api.test/telemetry/report");
});

test("rechaza una métrica ausente", async () => {
  delete payload.metrics.auth_failure_rate;
  await assert.rejects(fetchTelemetryReport(), { message: INVALID_API_RESPONSE_MESSAGE });
});

test("rechaza un período sin from/to", async () => {
  payload.period = { from: "2026-11-16T00:00:00Z" };
  await assert.rejects(fetchTelemetryReport(), { message: INVALID_API_RESPONSE_MESSAGE });
});

test("un HTTP 500 usa el mensaje de servicio no disponible", async () => {
  status = 500;
  await assert.rejects(fetchTelemetryReport(), { message: API_UNAVAILABLE_MESSAGE });
});
