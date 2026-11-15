export type TelemetrySection =
  | "home"
  | "inventory"
  | "suppliers"
  | "incidents"
  | "account"
  | "auth"
  | "candidates";

const AUTH_ROUTES = new Set(["/login", "/register", "/forgot-password", "/reset-password"]);
const SECTION_BY_FIRST_SEGMENT = new Map<string, TelemetrySection>([
  ["inventory", "inventory"],
  ["suppliers", "suppliers"],
  ["incidents", "incidents"],
  ["account", "account"],
  ["candidates", "candidates"],
]);

/** Plantilla de ruta: sin identificadores ni query string (nunca la URL completa). */
export function toRouteTemplate(path: string): string {
  const pathname = path.split(/[?#]/)[0] || "/";
  const template = pathname
    .split("/")
    .map((segment, index, all) => {
      if (segment === "") return segment;
      if (/^\d+$/.test(segment) || all[index - 1] === "candidates") return "{id}";
      return segment;
    })
    .join("/");
  return (template.startsWith("/") ? template : `/${template}`).slice(0, 120);
}

/** Sección principal del backoffice a la que pertenece una ruta, o null si no es una de ellas. */
export function sectionForRoute(path: string): TelemetrySection | null {
  const pathname = path.split(/[?#]/)[0] || "/";
  if (pathname === "/") return "home";
  if (AUTH_ROUTES.has(pathname)) return "auth";
  return SECTION_BY_FIRST_SEGMENT.get(pathname.split("/")[1] ?? "") ?? null;
}
