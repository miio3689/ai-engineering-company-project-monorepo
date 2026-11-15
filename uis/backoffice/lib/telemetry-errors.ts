import { toRouteTemplate } from "@/lib/telemetry-routes";
import { track } from "@/services/telemetry";

const WINDOW_MS = 60_000;
const MAX_PER_FINGERPRINT = 5;
const seen = new Map<string, { count: number; since: number }>();

/** Huella estable (FNV-1a de 32 bits). No permite recuperar el mensaje original. */
export function errorFingerprint(name: string, message: string, route: string): string {
  let hash = 0x811c9dc5;
  for (const char of `${name}|${route}|${message}`) {
    hash ^= char.codePointAt(0) ?? 0;
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash.toString(16).padStart(8, "0");
}

/** Envía frontend_error_captured: sin mensaje ni traza; máximo 5 por huella y minuto. */
export function reportFrontendError(error: unknown, handled: boolean): void {
  try {
    const name = error instanceof Error && error.name ? error.name : "NonErrorThrown";
    const message = error instanceof Error ? error.message : String(error);
    const route = toRouteTemplate(window.location.pathname);
    const fingerprint = errorFingerprint(name, message, route);
    const now = Date.now();
    const entry = seen.get(fingerprint);
    if (!entry || now - entry.since > WINDOW_MS) {
      seen.set(fingerprint, { count: 1, since: now });
    } else if (entry.count >= MAX_PER_FINGERPRINT) {
      return;
    } else {
      entry.count += 1;
    }
    track("frontend_error_captured", {
      error_name: name.slice(0, 80),
      error_fingerprint: fingerprint,
      route_template: route,
      handled,
    });
  } catch {
    // La telemetría nunca debe romper la aplicación.
  }
}
