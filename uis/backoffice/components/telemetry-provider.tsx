"use client";

import { usePathname } from "next/navigation";
import { useReportWebVitals } from "next/web-vitals";
import { useEffect, useRef } from "react";

import { reportFrontendError } from "@/lib/telemetry-errors";
import { sectionForRoute, toRouteTemplate } from "@/lib/telemetry-routes";
import { track } from "@/services/telemetry";

// Ignora redirecciones inmediatas (por ejemplo "/" → "/login").
const PAGE_VIEW_DEBOUNCE_MS = 1_000;

const handleWebVital: Parameters<typeof useReportWebVitals>[0] = (metric) => {
  if (metric.name !== "LCP") return;
  const navigation = performance.getEntriesByType("navigation")[0] as
    | PerformanceNavigationTiming
    | undefined;
  const type = navigation?.type;
  track("page_load_measured", {
    route_template: toRouteTemplate(window.location.pathname),
    navigation_type: type === "reload" || type === "back_forward" ? type : "navigate",
    load_ms: Math.round(
      navigation && navigation.loadEventEnd > 0 ? navigation.loadEventEnd : metric.value,
    ),
    lcp_ms: Math.round(metric.value),
  });
};

/** Captura transversal: vistas de página, tiempo de carga y errores no capturados. */
export default function TelemetryProvider() {
  const pathname = usePathname();
  const previousRoute = useRef<string | null>(null);

  useReportWebVitals(handleWebVital);

  useEffect(() => {
    const section = sectionForRoute(pathname);
    const route = toRouteTemplate(pathname);
    const timer = window.setTimeout(() => {
      if (section) {
        track("page_viewed", {
          route_template: route,
          section,
          referrer_route: previousRoute.current ?? undefined,
        });
      }
      previousRoute.current = route;
    }, PAGE_VIEW_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [pathname]);

  useEffect(() => {
    const onError = (event: ErrorEvent) => reportFrontendError(event.error ?? event.message, false);
    const onRejection = (event: PromiseRejectionEvent) => reportFrontendError(event.reason, false);
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onRejection);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onRejection);
    };
  }, []);

  return null;
}
