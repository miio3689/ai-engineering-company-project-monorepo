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

const { ACCESS_TOKEN_KEY, apiRequest } = await import("../services/api-client.ts");
const { AuthError, login, register } = await import("../services/auth.ts");
const { validateAuthForm } = await import("../lib/auth-form-validation.ts");
const { fetchSuppliers, createSupplier, updateSupplierRate, updateSupplierStatus } = await import("../services/suppliers.ts");
const { analyzeIncidentCsv, downloadIncidentAnalysisCsv } = await import("../services/incident-analysis.ts");
const { fetchCandidates, fetchCandidateById } = await import("../services/api.ts");
const { fetchAccount, updateProfile } = await import("../services/account.ts");

const originalFetch = globalThis.fetch;
const originalWindow = globalThis.window;
const originalBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
process.env.NEXT_PUBLIC_API_BASE_URL = "http://api.test/";

afterEach(() => {
  globalThis.fetch = originalFetch;
  if (originalWindow === undefined) delete globalThis.window;
  else globalThis.window = originalWindow;
});

function browser(token = "first-token") {
  const storage = new Map(token ? [[ACCESS_TOKEN_KEY, token]] : []);
  const redirects = [];
  globalThis.window = {
    localStorage: {
      getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: (key) => storage.delete(key),
    },
    location: { assign: (path) => redirects.push(path) },
  };
  return { storage, redirects };
}

function respond(body, status = 200) {
  globalThis.fetch = async () => Response.json(body, { status });
}

test("reads the current token on every request and preserves options", async () => {
  const { storage } = browser();
  const calls = [];
  const signal = new AbortController().signal;
  const body = new FormData();
  body.append("file", new Blob(["csv"]), "test.csv");
  globalThis.fetch = async (url, options) => {
    calls.push({ url, ...options });
    return Response.json([]);
  };
  await apiRequest("/protected", { method: "POST", body, signal, headers: { Accept: "application/json" } });
  storage.set(ACCESS_TOKEN_KEY, "new-token");
  await apiRequest("/protected");
  storage.delete(ACCESS_TOKEN_KEY);
  await apiRequest("/protected");
  assert.equal(calls[0].url, "http://api.test/protected");
  assert.equal(calls[0].headers.get("Authorization"), "Bearer first-token");
  assert.equal(calls[0].headers.get("Accept"), "application/json");
  assert.equal(calls[0].headers.has("Content-Type"), false);
  assert.equal(calls[0].body, body);
  assert.equal(calls[0].signal, signal);
  assert.equal(calls[1].headers.get("Authorization"), "Bearer new-token");
  assert.equal(calls[2].headers.has("Authorization"), false);
});

test("protected 401 clears the token and navigates to login", async () => {
  const { storage, redirects } = browser();
  respond({ detail: "expired" }, 401);
  await assert.rejects(apiRequest("/protected"), /sesión ha caducado/);
  assert.equal(storage.has(ACCESS_TOKEN_KEY), false);
  assert.deepEqual(redirects, ["/login"]);
});

test("public login 401 stays on the form, keeps existing storage, and is readable", async () => {
  const { storage, redirects } = browser();
  respond({ detail: "Credenciales inválidas." }, 401);
  await assert.rejects(login({ email: "test@example.com", password: "wrong" }), /correo o la contraseña no son correctos/);
  assert.equal(storage.get(ACCESS_TOKEN_KEY), "first-token");
  assert.deepEqual(redirects, []);
});

test("403 is not treated as an expired session; server requests do not access window", async () => {
  const { storage, redirects } = browser();
  respond({}, 403);
  assert.equal((await apiRequest("/protected")).status, 403);
  assert.equal(storage.get(ACCESS_TOKEN_KEY), "first-token");
  assert.deepEqual(redirects, []);
  delete globalThis.window;
  respond([]);
  assert.equal((await apiRequest("/protected")).status, 200);
});

test("login sends username=email as URL-encoded form data without Authorization", async () => {
  browser();
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "http://api.test/auth/login");
    assert.equal(options.headers.get("Content-Type"), "application/x-www-form-urlencoded");
    assert.equal(options.headers.has("Authorization"), false);
    assert.equal(options.body.get("username"), "test+auth@example.com");
    assert.equal(options.body.get("password"), " p&ss+=word ");
    assert.equal(options.body.has("email"), false);
    return Response.json({ access_token: "valid-token", token_type: "bearer" });
  };
  assert.deepEqual(await login({ email: "test+auth@example.com", password: " p&ss+=word " }), {
    access_token: "valid-token", token_type: "bearer",
  });
});

test("registration is public JSON and preserves optional profile fields", async () => {
  browser();
  const input = { email: "test@example.com", password: "secret", name: "Test", phone: "123", address: "Test street" };
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "http://api.test/users");
    assert.equal(options.headers.has("Authorization"), false);
    assert.equal(options.headers.get("Content-Type"), "application/json");
    assert.deepEqual(JSON.parse(options.body), input);
    return Response.json({ id: 1 }, { status: 201 });
  };
  await register(input);
});

test("duplicate email and FastAPI 422 errors map to individual fields", async () => {
  const input = { email: "test@example.com", password: "secret" };
  respond({ detail: "Ya existe un usuario." }, 409);
  await assert.rejects(register(input), (error) => error instanceof AuthError && /Ya existe/.test(error.fields.email) && !error.message);
  respond({ detail: [
    { loc: ["body", "email"], msg: "invalid" },
    { loc: ["body", "password"], msg: "invalid" },
    { loc: ["body"], msg: "Value error, name es obligatorio cuando se indican datos de perfil." },
  ] }, 422);
  await assert.rejects(register(input), (error) => error instanceof AuthError && Object.keys(error.fields).length === 3 && !error.message);
});

test("server failures and malformed tokens do not become successful logins", async () => {
  respond({}, 503);
  await assert.rejects(login({ email: "test@example.com", password: "secret" }), /HTTP 503/);
  for (const token of [{}, { access_token: "", token_type: "bearer" }, { access_token: "token", token_type: "other" }]) {
    respond(token);
    await assert.rejects(login({ email: "test@example.com", password: "secret" }), /token válido/);
  }
  globalThis.fetch = async () => new Response("<html>Unavailable</html>");
  await assert.rejects(login({ email: "test@example.com", password: "secret" }), /respuesta no válida/);
});

test("email, password and conditional profile validation match the backend", () => {
  for (const email of ["", "invalid", "a@b", ".a@example.com", "a..b@example.com", "a@-example.com", "a@example.com@"]) {
    assert.ok(validateAuthForm({ email, password: "secret" }, "register").email);
  }
  assert.ok(validateAuthForm({ email: "test@example.com", password: "" }, "login").password);
  assert.ok(validateAuthForm({ email: "test@example.com", password: "secret", phone: "123" }, "register").name);
  assert.deepEqual(validateAuthForm({ email: "test+auth@example.com", password: " p&ss ", name: "Test", address: "Street" }, "register"), {});
  assert.deepEqual(validateAuthForm({ email: "test@example.com", password: "secret" }, "register"), {});
});

test("all existing service surfaces use the shared token client", async () => {
  browser("shared-token");
  const paths = [];
  globalThis.fetch = async (url, options) => {
    assert.equal(options.headers.get("Authorization"), "Bearer shared-token");
    paths.push(url);
    if (url.endsWith("/records")) return Response.json({ data: [] });
    if (url.endsWith("/records/missing")) return Response.json({}, { status: 404 });
    return Response.json([]);
  };
  await fetchCandidates();
  assert.equal(await fetchCandidateById("missing"), null);
  await fetchSuppliers({ country: "USA", category: "carne" });
  await createSupplier({});
  await updateSupplierRate(1, 10);
  await updateSupplierStatus(1, "active");
  await analyzeIncidentCsv(new File(["csv"], "test.csv"));
  assert.equal(paths.length, 7);
  assert.ok(paths.some((path) => path.endsWith("/suppliers?country=USA&category=carne")));
});

test("incident downloads also clear the session on 401", async () => {
  const { storage, redirects } = browser();
  respond({}, 401);
  await assert.rejects(downloadIncidentAnalysisCsv(), /sesión ha caducado/);
  assert.equal(storage.has(ACCESS_TOKEN_KEY), false);
  assert.deepEqual(redirects, ["/login"]);
});

test("account loading uses GET /auth/me with Bearer token and abort support", async () => {
  browser();
  const account = { email: "test@example.com", role: "user", profile: { id: 2, user_id: 1, name: "Test", phone: null, address: "Street" } };
  const signal = new AbortController().signal;
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "http://api.test/auth/me");
    assert.equal(options.headers.get("Authorization"), "Bearer first-token");
    assert.equal(options.signal, signal);
    assert.equal(options.cache, "no-store");
    return Response.json(account);
  };
  assert.deepEqual(await fetchAccount(signal), account);
});

test("profile update uses PUT with only editable fields and returned server profile", async () => {
  browser();
  const profile = { id: 2, user_id: 1, name: "Updated", phone: null, address: "Street" };
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "http://api.test/profiles/me");
    assert.equal(options.method, "PUT");
    assert.equal(options.headers.get("Authorization"), "Bearer first-token");
    assert.equal(options.headers.get("Content-Type"), "application/json");
    assert.deepEqual(JSON.parse(options.body), { name: "Updated", phone: null, address: "Street" });
    return Response.json(profile);
  };
  assert.deepEqual(await updateProfile({ ...profile, email: "not-sent@example.com" }), profile);
});

test("missing profile remains null and profile API failures are readable", async () => {
  const input = { name: "Test", phone: null, address: null };
  respond({ email: "test@example.com", role: "user", profile: null });
  assert.equal((await fetchAccount()).profile, null);
  respond({ detail: "No tiene un perfil." }, 404);
  await assert.rejects(updateProfile(input), /No hay un perfil asociado/);
  respond({ detail: [{ loc: ["body", "name"], msg: "invalid" }] }, 422);
  await assert.rejects(updateProfile(input), /Revisa el nombre/);
  respond({}, 503);
  await assert.rejects(fetchAccount(), /cargar la cuenta \(HTTP 503\)/);
  await assert.rejects(updateProfile(input), /guardar el perfil \(HTTP 503\)/);
});

test("both account endpoints retain central 401 logout handling", async () => {
  for (const request of [() => fetchAccount(), () => updateProfile({ name: "Test", phone: null, address: null })]) {
    const { storage, redirects } = browser();
    respond({}, 401);
    await assert.rejects(request(), /sesión ha caducado/);
    assert.equal(storage.has(ACCESS_TOKEN_KEY), false);
    assert.deepEqual(redirects, ["/login"]);
  }
});

test.after(() => {
  if (originalBaseUrl === undefined) delete process.env.NEXT_PUBLIC_API_BASE_URL;
  else process.env.NEXT_PUBLIC_API_BASE_URL = originalBaseUrl;
});
