import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { registerHooks } from "node:module";
import { afterEach, test } from "node:test";
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

const { getLocationStock, isQuantityAboveLocationStock } = await import("../lib/inventory-stock.ts");
const { fetchIngredient } = await import("../services/inventory.ts");
const originalFetch = globalThis.fetch;
const originalBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
process.env.NEXT_PUBLIC_API_BASE_URL = "http://inventory.test";

afterEach(() => {
  globalThis.fetch = originalFetch;
});

const ingredient = {
  id: 1,
  name: "Falda de ternera",
  sku: "BRS-BEEF-001",
  unit: "kg",
  category: "meat",
  country: "CO",
  current_stock: 15,
  stock_by_location: [
    { location_id: 1, quantity: 8 },
    { location_id: 2, quantity: 7 },
  ],
};

test("getLocationStock returns local stock, zero for absent location, or global total", () => {
  assert.equal(getLocationStock(ingredient, 1), 8);
  assert.equal(getLocationStock(ingredient, 5), 0);
  assert.equal(getLocationStock(ingredient, null), 15);
});

test("isIngredient accepts finite stock_by_location records", async () => {
  globalThis.fetch = async () => Response.json(ingredient);
  assert.deepEqual(await fetchIngredient(1), ingredient);
});

test("isIngredient rejects missing or invalid stock_by_location", async () => {
  globalThis.fetch = async () => {
    const legacyPayload = { ...ingredient };
    delete legacyPayload.stock_by_location;
    return Response.json(legacyPayload);
  };
  await assert.rejects(fetchIngredient(1));

  for (const stockByLocation of [
    [{ location_id: 1.5, quantity: 2 }],
    [{ location_id: 1, quantity: Number.NaN }],
    [null],
  ]) {
    globalThis.fetch = async () => Response.json({
      ...ingredient,
      stock_by_location: stockByLocation,
    });
    await assert.rejects(fetchIngredient(1));
  }

  const infiniteQuantityPayload = JSON.stringify({
    ...ingredient,
    stock_by_location: [{ location_id: 1, quantity: 1 }],
  }).replace('"quantity":1', '"quantity":1e1000');
  globalThis.fetch = async () => new Response(infiniteQuantityPayload, {
    headers: { "Content-Type": "application/json" },
  });
  await assert.rejects(fetchIngredient(1));
});

test("outbound warning compares the requested quantity with selected local stock", () => {
  assert.equal(isQuantityAboveLocationStock(ingredient, 1, 8), false);
  assert.equal(isQuantityAboveLocationStock(ingredient, 1, 8.001), true);
  assert.equal(isQuantityAboveLocationStock(ingredient, 5, 0.001), true);
  assert.equal(isQuantityAboveLocationStock(ingredient, null, 100), false);
  assert.equal(isQuantityAboveLocationStock(null, 1, 100), false);
});

test.after(() => {
  if (originalBaseUrl === undefined) delete process.env.NEXT_PUBLIC_API_BASE_URL;
  else process.env.NEXT_PUBLIC_API_BASE_URL = originalBaseUrl;
});