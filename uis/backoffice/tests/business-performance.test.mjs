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

const { fetchWeeklyLocationPerformance, fetchLatestPipelineRun } =
  await import("../services/business-performance.ts");
const { currentWeekStart, groupByCurrency, shiftWeek, wasteRatio } =
  await import("../lib/business-performance.ts");
const { API_UNAVAILABLE_MESSAGE, INVALID_API_RESPONSE_MESSAGE } =
  await import("../services/api-errors.ts");
const originalFetch = globalThis.fetch;
const originalBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

const location = (overrides = {}) => ({
  location_id: "1",
  country: "CO",
  total_purchase_cost: 50000,
  total_waste_cost: 10000,
  waste_ratio: 0.2,
  stockout_events_count: 2,
  price_alert_events_count: 1,
  currency: "COP",
  ...overrides,
});

let fetchCalls;
let payload;
let status;

beforeEach(() => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://api.test";
  fetchCalls = [];
  payload = { week_start: "2026-11-16", locations: [location()] };
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

test("sin semana elegida consulta el endpoint de KPIs sin parámetros", async () => {
  assert.deepEqual(await fetchWeeklyLocationPerformance(null), payload);
  assert.equal(fetchCalls[0].url, "http://api.test/reporting/weekly-location-performance");
});

test("con semana elegida envía week_start", async () => {
  await fetchWeeklyLocationPerformance("2026-11-09");
  assert.equal(
    fetchCalls[0].url,
    "http://api.test/reporting/weekly-location-performance?week_start=2026-11-09",
  );
});

test("acepta la respuesta vacía del pipeline sin semanas calculadas", async () => {
  payload = { week_start: null, locations: [] };
  assert.deepEqual(await fetchWeeklyLocationPerformance(null), payload);
});

test("rechaza un KPI con tipo incorrecto", async () => {
  payload.locations = [location({ total_waste_cost: "10000" })];
  await assert.rejects(fetchWeeklyLocationPerformance(null), { message: INVALID_API_RESPONSE_MESSAGE });
});

test("un HTTP 500 usa el mensaje de servicio no disponible", async () => {
  status = 500;
  await assert.rejects(fetchWeeklyLocationPerformance(null), { message: API_UNAVAILABLE_MESSAGE });
});

test("la última corrida es null si el pipeline nunca se ejecutó (404)", async () => {
  status = 404;
  payload = { detail: "Not found" };
  assert.equal(await fetchLatestPipelineRun(), null);
});

test("la última corrida devuelve estado y fechas", async () => {
  payload = {
    status: "completed",
    started_at: "2026-11-23T05:00:00Z",
    finished_at: "2026-11-23T05:01:10Z",
    details: {},
  };
  assert.deepEqual(await fetchLatestPipelineRun(), {
    status: "completed",
    started_at: "2026-11-23T05:00:00Z",
    finished_at: "2026-11-23T05:01:10Z",
  });
});

test("agrupa por moneda sin mezclar COP y USD y recalcula el ratio del conjunto", () => {
  const groups = groupByCurrency([
    location({ location_id: "1", total_purchase_cost: 50000, total_waste_cost: 10000 }),
    location({ location_id: "3", total_purchase_cost: 30000, total_waste_cost: 2000 }),
    location({ location_id: "2", country: "US", currency: "USD", total_purchase_cost: 37.5, total_waste_cost: 0 }),
  ]);
  assert.deepEqual(groups.map((group) => group.label), ["Colombia · COP", "Estados Unidos · USD"]);
  assert.equal(groups[0].totals.total_purchase_cost, 80000);
  assert.equal(groups[0].totals.total_waste_cost, 12000);
  assert.equal(groups[0].totals.waste_ratio, 0.15); // 12.000 / 80.000, no la media de ratios
  assert.equal(groups[1].totals.total_purchase_cost, 37.5);
});

test("ratio de merma 0 sin compras y navegación entre semanas ISO", () => {
  assert.equal(wasteRatio(0, 5000), 0);
  assert.equal(shiftWeek("2026-11-16", -1), "2026-11-09");
  assert.equal(shiftWeek("2026-12-28", 1), "2027-01-04");
  assert.equal(currentWeekStart(new Date("2026-11-22T23:59:00Z")), "2026-11-16"); // domingo
  assert.equal(currentWeekStart(new Date("2026-11-23T00:00:00Z")), "2026-11-23"); // lunes
});
