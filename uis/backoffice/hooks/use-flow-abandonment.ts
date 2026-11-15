"use client";

import { useEffect, useMemo, useRef } from "react";

import { flushOnExit, track } from "@/services/telemetry";

export type AbandonableFlow =
  | "inbound_order"
  | "outbound_order"
  | "incident_register"
  | "supplier_create";
type FlowStep = "form_opened" | "field_edited" | "validation_failed" | "submit_started";

interface FlowState {
  openedAt: number;
  step: FlowStep;
  filled: number;
  finished: boolean;
  reported: boolean;
}

/**
 * Detecta formularios iniciados y no enviados. Emite flow_abandoned una sola
 * vez al salir de la pantalla o cerrar la pestaña; solo cuenta campos rellenos.
 */
export function useFlowAbandonment(flow: AbandonableFlow) {
  const state = useRef<FlowState>({
    openedAt: 0,
    step: "form_opened",
    filled: 0,
    finished: false,
    reported: false,
  });

  useEffect(() => {
    state.current.openedAt = Date.now();

    function report() {
      const current = state.current;
      if (current.finished || current.reported || current.step === "form_opened") return;
      current.reported = true;
      track("flow_abandoned", {
        flow,
        last_step_reached: current.step,
        elapsed_ms: Date.now() - current.openedAt,
        fields_filled_count: current.filled,
      });
    }
    function reportOnExit() {
      report();
      flushOnExit();
    }

    window.addEventListener("pagehide", reportOnExit);
    return () => {
      window.removeEventListener("pagehide", reportOnExit);
      report();
    };
  }, [flow]);

  return useMemo(
    () => ({
      fieldEdited(filledCount: number) {
        state.current.step = "field_edited";
        state.current.filled = filledCount;
        state.current.finished = false;
        state.current.reported = false;
      },
      validationFailed() {
        state.current.step = "validation_failed";
      },
      submitStarted() {
        state.current.step = "submit_started";
      },
      completed() {
        state.current.finished = true;
      },
    }),
    [],
  );
}
