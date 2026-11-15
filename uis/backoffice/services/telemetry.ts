import { ACCESS_TOKEN_KEY } from "@/services/api-client";
import { TELEMETRY_ALLOWLIST } from "@/lib/telemetry-allowlist";

export type TelemetryProperties = Record<string, unknown>;

// Envelope estándar: docs/telemetry/telemetry-plan.md, sección 6.
export interface TelemetryEvent {
  eventId: string;
  timestamp: string;
  sessionId: string;
  userId: string;
  event_type: string;
  schemaVersion: string;
  requestId: string;
  properties: TelemetryProperties;
}

export const TELEMETRY_SCHEMA_VERSION = "1.0.0";
export const FLUSH_INTERVAL_MS = 10_000;
export const MAX_BATCH_SIZE = 20;
export const MAX_RETRIES = 3;
export const BASE_BACKOFF_MS = 1_000;
const MAX_QUEUE_SIZE = 100;

// text/plain evita el preflight de CORS y es lo que admite sendBeacon sin
// cabeceras; el backend lee el cuerpo como JSON igualmente.
const CONTENT_TYPE = "text/plain;charset=UTF-8";

let queue: TelemetryEvent[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;
let sessionId: string | null = null;
let listenersInstalled = false;
let flushIntervalMs = FLUSH_INTERVAL_MS;
let baseBackoffMs = BASE_BACKOFF_MS;

function endpoint(): string | null {
  return process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT?.trim() || null;
}

function warn(message: string): void {
  if (process.env.NODE_ENV !== "production") console.warn(`[telemetry] ${message}`);
}

// crypto.randomUUID solo existe en contextos seguros (HTTPS o localhost);
// getRandomValues funciona también en HTTP.
function randomUuid(): string {
  const cryptoApi = globalThis.crypto;
  if (typeof cryptoApi.randomUUID === "function") return cryptoApi.randomUUID();
  const bytes = new Uint8Array(16);
  cryptoApi.getRandomValues(bytes);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0"));
  return [
    hex.slice(0, 4).join(""),
    hex.slice(4, 6).join(""),
    hex.slice(6, 8).join(""),
    hex.slice(8, 10).join(""),
    hex.slice(10).join(""),
  ].join("-");
}

/** Genera un sessionId nuevo. Se llama al iniciar sesión; vive solo en memoria. */
export function startTelemetrySession(): void {
  sessionId = randomUuid();
}

function currentSessionId(): string {
  if (!sessionId) sessionId = randomUuid();
  return sessionId;
}

// Lee solo el identificador público de la cuenta del token (claim user_uuid,
// un entero). No valida la firma ni guarda el token.
function currentUserId(): string {
  try {
    const payload = window.localStorage.getItem(ACCESS_TOKEN_KEY)?.split(".")[1];
    if (!payload) return "anonymous";
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, "=");
    const claims = JSON.parse(atob(padded)) as { user_uuid?: unknown };
    const id = Number(claims.user_uuid);
    return Number.isInteger(id) && id > 0 ? String(id) : "anonymous";
  } catch {
    return "anonymous";
  }
}

// Aplica la allowlist del plan: solo pasan las claves permitidas del evento.
function sanitizeProperties(
  eventType: string,
  properties: TelemetryProperties,
): TelemetryProperties | null {
  const allowed = TELEMETRY_ALLOWLIST[eventType];
  if (!allowed) return null;
  const clean: TelemetryProperties = {};
  for (const key of allowed) {
    const value = properties[key];
    if (value !== undefined && value !== null) clean[key] = value;
  }
  return clean;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function sendWithRetry(batch: TelemetryEvent[]): Promise<void> {
  const url = endpoint();
  if (!url) return;
  const body = JSON.stringify({ events: batch });

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt += 1) {
    if (attempt > 0) await delay(baseBackoffMs * 2 ** (attempt - 1));
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": CONTENT_TYPE },
        body,
        cache: "no-store",
      });
      if (response.ok) return;
      if (response.status < 500 && response.status !== 429) {
        warn(`lote rechazado (${response.status}); se descarta sin reintentar`);
        return;
      }
    } catch {
      // Error de red: se reintenta con espera exponencial.
    }
  }
  warn("lote descartado tras agotar los reintentos");
}

function scheduleFlush(): void {
  if (flushTimer !== null) return;
  flushTimer = setTimeout(() => {
    flushTimer = null;
    void flush();
  }, flushIntervalMs);
}

/** Envía un lote de hasta 20 eventos con reintentos. */
export async function flush(): Promise<void> {
  if (flushTimer !== null) {
    clearTimeout(flushTimer);
    flushTimer = null;
  }
  const batch = queue.splice(0, MAX_BATCH_SIZE);
  if (queue.length >= MAX_BATCH_SIZE) void flush();
  else if (queue.length > 0) scheduleFlush();
  if (batch.length === 0) return;
  await sendWithRetry(batch);
}

// Al cerrar o esconder la pestaña el navegador cancela fetch; sendBeacon sí llega.
function flushWithBeacon(): void {
  if (flushTimer !== null) {
    clearTimeout(flushTimer);
    flushTimer = null;
  }
  const url = endpoint();
  if (!url) {
    queue = [];
    return;
  }
  while (queue.length > 0) {
    const body = JSON.stringify({ events: queue.splice(0, MAX_BATCH_SIZE) });
    let sent = false;
    try {
      sent = navigator.sendBeacon(url, new Blob([body], { type: CONTENT_TYPE }));
    } catch {
      sent = false;
    }
    if (!sent) {
      void fetch(url, {
        method: "POST",
        headers: { "Content-Type": CONTENT_TYPE },
        body,
        keepalive: true,
      }).catch(() => undefined);
    }
  }
}

function installLifecycleListeners(): void {
  if (listenersInstalled) return;
  listenersInstalled = true;
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flushWithBeacon();
  });
  window.addEventListener("pagehide", flushWithBeacon);
}

/**
 * Única función pública de captura. Añade sola eventId, timestamp, sessionId,
 * userId, schemaVersion y requestId. Nunca lanza errores ni bloquea la app.
 */
export function track(eventType: string, properties: TelemetryProperties = {}): void {
  try {
    if (typeof window === "undefined" || !endpoint()) return;
    const clean = sanitizeProperties(eventType, properties);
    if (!clean) {
      warn(`evento desconocido descartado: ${eventType}`);
      return;
    }
    installLifecycleListeners();
    queue.push({
      eventId: randomUuid(),
      timestamp: new Date().toISOString(),
      sessionId: currentSessionId(),
      userId: currentUserId(),
      event_type: eventType,
      schemaVersion: TELEMETRY_SCHEMA_VERSION,
      requestId: randomUuid(),
      properties: clean,
    });
    if (queue.length > MAX_QUEUE_SIZE) queue.splice(0, queue.length - MAX_QUEUE_SIZE);
    if (queue.length >= MAX_BATCH_SIZE) void flush();
    else scheduleFlush();
  } catch {
    // La telemetría nunca debe romper la aplicación.
  }
}

/** Solo para tests: vacía el estado y permite acortar los tiempos. */
export function resetTelemetryForTests(
  options: { flushIntervalMs?: number; baseBackoffMs?: number } = {},
): void {
  if (flushTimer !== null) clearTimeout(flushTimer);
  flushTimer = null;
  queue = [];
  sessionId = null;
  listenersInstalled = false;
  flushIntervalMs = options.flushIntervalMs ?? FLUSH_INTERVAL_MS;
  baseBackoffMs = options.baseBackoffMs ?? BASE_BACKOFF_MS;
}