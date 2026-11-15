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

const telemetry = await import("../services/telemetry.ts");
const { TELEMETRY_ALLOWLIST } = await import("../lib/telemetry-allowlist.ts");

const ENDPOINT = "http://telemetry.test/telemetry/events";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const originalFetch = globalThis.fetch;
const originalEndpoint = process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT;
const originalNavigator = Object.getOwnPropertyDescriptor(globalThis, "navigator");
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

let fetchCalls;
let beacons;
let documentHandlers;
let storage;

function fakeToken(claims) {
  const encode = (value) => Buffer.from(JSON.stringify(value)).toString("base64url");
  return `${encode({ alg: "HS256", typ: "JWT" })}.${encode(claims)}.firma`;
}

function page(extra = {}) {
  return { route_template: "/inventory/products", section: "inventory", ...extra };
}

beforeEach(() => {
  process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT = ENDPOINT;
  fetchCalls = [];
  beacons = [];
  documentHandlers = {};
  storage = new Map();
  globalThis.window = {
    localStorage: { getItem: (key) => storage.get(key) ?? null },
    addEventListener: () => undefined,
  };
  globalThis.document = {
    visibilityState: "visible",
    addEventListener: (name, handler) => { documentHandlers[name] = handler; },
  };
  Object.defineProperty(globalThis, "navigator", {
    value: { sendBeacon: (url, blob) => { beacons.push({ url, blob }); return true; } },
    configurable: true,
    writable: true,
  });
  globalThis.fetch = async (url, options) => {
    fetchCalls.push({ url, options, body: JSON.parse(options.body) });
    return { ok: true, status: 200 };
  };
  telemetry.resetTelemetryForTests({ baseBackoffMs: 1, flushIntervalMs: 25 });
});

afterEach(() => {
  telemetry.resetTelemetryForTests();
  globalThis.fetch = originalFetch;
  if (originalEndpoint === undefined) delete process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT;
  else process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT = originalEndpoint;
  if (originalNavigator) Object.defineProperty(globalThis, "navigator", originalNavigator);
  delete globalThis.window;
  delete globalThis.document;
});

test("track añade solo los campos del envelope automáticamente", async () => {
  storage.set("access_token", fakeToken({ user_uuid: 7 }));
  telemetry.track("page_viewed", page());
  await telemetry.flush();

  assert.equal(fetchCalls.length, 1);
  assert.equal(fetchCalls[0].url, ENDPOINT);
  assert.equal(fetchCalls[0].options.method, "POST");
  const [event] = fetchCalls[0].body.events;
  assert.match(event.eventId, UUID);
  assert.match(event.sessionId, UUID);
  assert.match(event.requestId, UUID);
  assert.equal(event.userId, "7");
  assert.equal(event.event_type, "page_viewed");
  assert.equal(event.schemaVersion, "1.0.0");
  assert.ok(!Number.isNaN(Date.parse(event.timestamp)));
  assert.deepEqual(event.properties, page());
});

test("sin token el userId es anonymous", async () => {
  telemetry.track("page_viewed", page());
  await telemetry.flush();
  assert.equal(fetchCalls[0].body.events[0].userId, "anonymous");
});

test("el sessionId se mantiene y cambia al iniciar una sesión nueva", async () => {
  telemetry.track("page_viewed", page());
  telemetry.track("page_viewed", page());
  telemetry.startTelemetrySession();
  telemetry.track("page_viewed", page());
  await telemetry.flush();
  const [first, second, third] = fetchCalls[0].body.events;
  assert.equal(first.sessionId, second.sessionId);
  assert.notEqual(second.sessionId, third.sessionId);
});

test("descarta eventos desconocidos y propiedades fuera de la allowlist", async () => {
  telemetry.track("evento_inventado", {});
  telemetry.track("page_viewed", page({ email: "a@b.c", nombre: "Ana" }));
  await telemetry.flush();
  assert.equal(fetchCalls.length, 1);
  assert.equal(fetchCalls[0].body.events.length, 1);
  assert.deepEqual(fetchCalls[0].body.events[0].properties, page());
});

test("envía en lote al llegar a 20 eventos, no uno a uno", () => {
  for (let index = 0; index < 20; index += 1) telemetry.track("page_viewed", page());
  assert.equal(fetchCalls.length, 1);
  assert.equal(fetchCalls[0].body.events.length, 20);
  telemetry.track("page_viewed", page());
  assert.equal(fetchCalls.length, 1);
});

test("con menos de 20 eventos espera al temporizador y envía un solo lote", async () => {
  for (let index = 0; index < 3; index += 1) telemetry.track("page_viewed", page());
  assert.equal(fetchCalls.length, 0);
  await sleep(80);
  assert.equal(fetchCalls.length, 1);
  assert.equal(fetchCalls[0].body.events.length, 3);
});

test("reintenta tras un fallo de red y termina enviando", async () => {
  let attempts = 0;
  globalThis.fetch = async () => {
    attempts += 1;
    if (attempts < 3) throw new TypeError("network");
    return { ok: true, status: 200 };
  };
  telemetry.track("page_viewed", page());
  await telemetry.flush();
  assert.equal(attempts, 3);
});

test("descarta el lote tras 1 intento + 3 reintentos", async () => {
  let attempts = 0;
  globalThis.fetch = async () => { attempts += 1; return { ok: false, status: 503 }; };
  telemetry.track("page_viewed", page());
  await telemetry.flush();
  assert.equal(attempts, 4);
  await telemetry.flush();
  assert.equal(attempts, 4);
});

test("un 422 se descarta sin reintentar", async () => {
  let attempts = 0;
  globalThis.fetch = async () => { attempts += 1; return { ok: false, status: 422 }; };
  telemetry.track("page_viewed", page());
  await telemetry.flush();
  assert.equal(attempts, 1);
});

test("al esconder la pestaña envía lo pendiente con sendBeacon", async () => {
  for (let index = 0; index < 3; index += 1) telemetry.track("page_viewed", page());
  globalThis.document.visibilityState = "hidden";
  documentHandlers.visibilitychange();

  assert.equal(beacons.length, 1);
  assert.equal(beacons[0].url, ENDPOINT);
  assert.equal(beacons[0].blob.type.toLowerCase(), "text/plain;charset=utf-8");
  assert.equal(JSON.parse(await beacons[0].blob.text()).events.length, 3);
  assert.equal(fetchCalls.length, 0);
});

test("la allowlist del código coincide con docs/telemetry/event-schemas.json", () => {
  const schemas = JSON.parse(
    readFileSync(new URL("../../../docs/telemetry/event-schemas.json", import.meta.url), "utf8"),
  );
  assert.deepEqual(
    Object.keys(TELEMETRY_ALLOWLIST).sort(),
    Object.keys(schemas.events).sort(),
  );
  for (const [name, event] of Object.entries(schemas.events)) {
    assert.deepEqual(
      [...TELEMETRY_ALLOWLIST[name]].sort(),
      Object.keys(event.schema.properties.properties.properties).sort(),
      name,
    );
  }
});

const { toRouteTemplate, sectionForRoute } = await import("../lib/telemetry-routes.ts");
const { errorFingerprint } = await import("../lib/telemetry-errors.ts");

test("toRouteTemplate sustituye identificadores y descarta la query string", () => {
  assert.equal(toRouteTemplate("/inventory/products/12"), "/inventory/products/{id}");
  assert.equal(toRouteTemplate("/candidates/abc"), "/candidates/{id}");
  assert.equal(toRouteTemplate("/inventory/orders/inbound?ingredient_id=5"), "/inventory/orders/inbound");
  assert.equal(toRouteTemplate("/login?password=secreto"), "/login");
  assert.equal(toRouteTemplate("/"), "/");
});

test("sectionForRoute devuelve la sección o null", () => {
  assert.equal(sectionForRoute("/"), "home");
  assert.equal(sectionForRoute("/login"), "auth");
  assert.equal(sectionForRoute("/inventory/products"), "inventory");
  assert.equal(sectionForRoute("/account/profile"), "account");
  assert.equal(sectionForRoute("/ruta-que-no-existe"), null);
});

test("errorFingerprint es estable y tiene el formato del esquema", () => {
  const first = errorFingerprint("TypeError", "x is undefined", "/inventory/products");
  assert.equal(first, errorFingerprint("TypeError", "x is undefined", "/inventory/products"));
  assert.notEqual(first, errorFingerprint("TypeError", "otro mensaje", "/inventory/products"));
  assert.match(first, /^[0-9a-f]{8}$/);
});