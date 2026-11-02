"use client";

import { useEffect, useState } from "react";

import { fetchIncidents, fetchIncidentSummary } from "@/services/incidents";
import type {
  Incident,
  IncidentFilters,
  IncidentSummary,
} from "@/types/incident";

interface IncidentListResult {
  key: string;
  incidents: Incident[];
  error: string | null;
}

interface SummaryResult {
  attempt: number;
  summary: IncidentSummary | null;
  error: string | null;
}

export function useIncidentList(filters: IncidentFilters) {
  const { status, origin, branch } = filters;
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<IncidentListResult | null>(null);
  const key = JSON.stringify([
    status ?? "",
    origin ?? "",
    branch ?? "",
    attempt,
  ]);
  const loading = result?.key !== key;

  useEffect(() => {
    const controller = new AbortController();
    fetchIncidents({ status, origin, branch }, controller.signal)
      .then((incidents) => {
        if (!controller.signal.aborted) {
          setResult({ key, incidents, error: null });
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setResult({
            key,
            incidents: [],
            error: error instanceof Error
              ? error.message
              : "No se pudo cargar el listado de incidencias. Inténtalo de nuevo.",
          });
        }
      });
    return () => controller.abort();
  }, [status, origin, branch, key]);

  function replaceIncident(updated: Incident) {
    setResult((current) => {
      if (!current || current.key !== key) return current;
      return {
        ...current,
        incidents: current.incidents.map((incident) =>
          incident.id === updated.id ? updated : incident
        ),
      };
    });
  }

  return {
    incidents: result?.key === key ? result.incidents : [],
    loading,
    error: result?.key === key ? result.error : null,
    retry: () => setAttempt((value) => value + 1),
    replaceIncident,
  };
}

export function useIncidentSummary() {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<SummaryResult | null>(null);
  const loading = result?.attempt !== attempt;

  useEffect(() => {
    const controller = new AbortController();
    fetchIncidentSummary(controller.signal)
      .then((summary) => {
        if (!controller.signal.aborted) {
          setResult({ attempt, summary, error: null });
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setResult({
            attempt,
            summary: null,
            error: error instanceof Error
              ? error.message
              : "No se pudo cargar el resumen. Inténtalo de nuevo.",
          });
        }
      });
    return () => controller.abort();
  }, [attempt]);

  return {
    summary: result?.attempt === attempt ? result.summary : null,
    loading,
    error: result?.attempt === attempt ? result.error : null,
    retry: () => setAttempt((value) => value + 1),
  };
}
