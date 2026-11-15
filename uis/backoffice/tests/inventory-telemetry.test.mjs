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
const { InventoryServiceError } = await import("../services/inventory.ts");
const inventoryTelemetry = await import("../lib/inventory-telemetry.ts");
const schemas = JSON.parse(
  readFileSync(new URL("../../../docs/telemetry/event-schemas.json", import.meta.url), "utf8"),
);

const ENDPOINT = "http://telemetry.test/telemetry/events";
const originalFetch = globalThis.fetch;
const originalEndpoint = process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT;
const originalNavigator = Object.getOwnPropertyDescriptor(globalThis, "navigator");

let fetchCalls;
let documentHandlers;
let storage;

const ingredient = (overrides = {}) => ({
  id: 42,
  name: "Arroz",
  sku: "AR-42",
  unit: "kg",
  category: "produce",
  country: "CO",
  current_stock: 25,
  stock_by_location: [],
  ...overrides,
});

const inboundInput = (overrides = {}) => ({
  ingredient_id: 42,
  quantity: 6,
  supplier_name: "Proveedor de prueba",
  location_id: 3,
  ...overrides,
});

const outboundInput = (overrides = {}) => ({
  ingredient_id: 42,
  quantity: 4,
  reason: "consumption",
  location_id: 3,
  ...overrides,
});

const inventoryOrder = (type, overrides = {}) => ({
  id: 99,
  type,
  ingredient_id: 42,
  name: "Arroz",
  sku: "AR-42",
  quantity: 4,
  location_id: 3,
  created_at: "2026-01-01T00:00:00Z",
  user_uuid: "7",
  ...(type === "inbound" ? { supplier_name: "Proveedor de prueba" } : { reason: "consumption" }),
  ...overrides,
});

function assertSchema(events) {
  for (const event of events) {
    assert.ok(Object.hasOwn(schemas.events, event.event_type), event.event_type);
    const schema = schemas.events[event.event_type].schema.properties;
    const properties = schema.properties;
    const allowed = Object.keys(properties.properties);
    for (const required of properties.required) {
      assert.ok(Object.hasOwn(event.properties, required), `${event.event_type}: ${required}`);
    }
    for (const key of Object.keys(event.properties)) {
      assert.ok(allowed.includes(key), `${event.event_type}: unexpected property ${key}`);
    }
  }
}

async function takeEvents() {
  await telemetry.flush();
  const events = fetchCalls.flatMap((call) => call.body.events);
  assertSchema(events);
  fetchCalls = [];
  return events;
}

beforeEach(() => {
  process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT = ENDPOINT;
  fetchCalls = [];
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
    value: { sendBeacon: () => true },
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

test("una salida de consumo emite solo outbound_order_created", async () => {
  inventoryTelemetry.trackOutboundCreated(
    ingredient(),
    outboundInput(),
    inventoryOrder("outbound"),
    null,
    null,
  );
  const events = await takeEvents();
  assert.deepEqual(events.map((event) => event.event_type), ["outbound_order_created"]);
});

test("la merma emite solo stock_waste_registered con motivo; sin motivo no emite orden", async () => {
  inventoryTelemetry.trackOutboundCreated(
    ingredient(),
    outboundInput({ reason: "waste" }),
    inventoryOrder("outbound", { reason: "waste" }),
    "expired",
    null,
  );
  const wasteEvents = await takeEvents();
  assert.deepEqual(wasteEvents.map((event) => event.event_type), ["stock_waste_registered"]);
  assert.equal(wasteEvents[0].properties.reason, "expired");

  inventoryTelemetry.trackOutboundCreated(
    ingredient(),
    outboundInput({ reason: "waste" }),
    inventoryOrder("outbound", { reason: "waste" }),
    null,
    null,
  );
  assert.deepEqual(await takeEvents(), []);
});

test("el umbral se emite solo al cruzarlo hacia abajo y depende de la unidad", async () => {
  inventoryTelemetry.trackOutboundCreated(
    ingredient({ unit: "kg" }),
    outboundInput({ quantity: 10 }),
    inventoryOrder("outbound"),
    null,
    25,
  );
  const crossing = await takeEvents();
  const thresholdEvent = crossing.find((event) => event.event_type === "stock_threshold_triggered");
  assert.ok(thresholdEvent);
  assert.equal(thresholdEvent.properties.quantity, 15);
  assert.equal(thresholdEvent.properties.threshold_quantity, 20);

  inventoryTelemetry.trackOutboundCreated(
    ingredient({ unit: "kg" }),
    outboundInput({ quantity: 2 }),
    inventoryOrder("outbound"),
    null,
    10,
  );
  assert.ok(!(await takeEvents()).some((event) => event.event_type === "stock_threshold_triggered"));

  inventoryTelemetry.trackOutboundCreated(
    ingredient({ unit: "kg" }),
    outboundInput({ quantity: 5 }),
    inventoryOrder("outbound"),
    null,
    100,
  );
  assert.ok(!(await takeEvents()).some((event) => event.event_type === "stock_threshold_triggered"));

  inventoryTelemetry.trackOutboundCreated(
    ingredient({ unit: "unidad" }),
    outboundInput({ quantity: 2 }),
    inventoryOrder("outbound"),
    null,
    51,
  );
  const unitEvents = await takeEvents();
  assert.equal(
    unitEvents.find((event) => event.event_type === "stock_threshold_triggered")?.properties.threshold_quantity,
    50,
  );
});

test("trackOutboundRejected asigna los motivos del esquema y omite 401", async () => {
  const expected = [
    [400, "insufficient_stock"],
    [404, "ingredient_not_found"],
    [422, "validation_error"],
    [503, "database_error"],
  ];
  for (const [status, reason] of expected) {
    inventoryTelemetry.trackOutboundRejected(
      ingredient(),
      outboundInput(),
      new InventoryServiceError("error", status),
      8,
    );
    const [event] = await takeEvents();
    assert.equal(event.event_type, "outbound_order_rejected");
    assert.equal(event.properties.rejection_reason, reason);
    assert.equal(event.properties.available_quantity, 8);
  }
  inventoryTelemetry.trackOutboundRejected(
    ingredient(),
    outboundInput(),
    new InventoryServiceError("error", 401),
    8,
  );
  assert.deepEqual(await takeEvents(), []);
});

test("la entrada incluye su id, proveedor y país/moneda coherentes", async () => {
  inventoryTelemetry.trackInboundCreated(
    ingredient({ country: "CO" }),
    inboundInput(),
    inventoryOrder("inbound"),
  );
  const [colombianEvent] = await takeEvents();
  assert.equal(colombianEvent.properties.inbound_order_id, 99);
  assert.equal(colombianEvent.properties.supplier_name, "Proveedor de prueba");
  assert.equal(colombianEvent.properties.country, "CO");
  assert.equal(colombianEvent.properties.currency, "COP");

  inventoryTelemetry.trackInboundCreated(
    ingredient({ country: "US" }),
    inboundInput(),
    inventoryOrder("inbound"),
  );
  const [usEvent] = await takeEvents();
  assert.equal(usEvent.properties.country, "US");
  assert.equal(usEvent.properties.currency, "USD");
});

test("la validación se limita por formulario/campo y no transmite el valor", async () => {
  inventoryTelemetry.trackInventoryValidationFailed("inbound_order", {
    quantity: "Introduce una cantidad mayor que cero: valor_privado",
  });
  inventoryTelemetry.trackInventoryValidationFailed("inbound_order", {
    quantity: "Introduce una cantidad mayor que cero: valor_privado",
  });
  inventoryTelemetry.trackInventoryValidationFailed("inbound_order", {
    supplierName: "Introduce el nombre del proveedor: valor_privado",
  });
  const events = await takeEvents();
  assert.equal(events.length, 2);
  assert.deepEqual(
    events.map((event) => event.properties.field_name).sort(),
    ["quantity", "supplier_name"],
  );
  assert.ok(events.every((event) => !JSON.stringify(event).includes("valor_privado")));
});
