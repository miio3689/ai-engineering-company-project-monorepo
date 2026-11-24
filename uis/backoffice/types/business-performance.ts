/** Fila de reporting.weekly_location_performance tal como la expone services/reporting. */
export interface LocationPerformance {
  location_id: string;
  country: string;
  total_purchase_cost: number;
  total_waste_cost: number;
  waste_ratio: number;
  stockout_events_count: number;
  price_alert_events_count: number;
  currency: string;
}

/** GET /reporting/weekly-location-performance */
export interface WeeklyLocationPerformance {
  /** Lunes de la semana ISO (YYYY-MM-DD, UTC); null si el pipeline aún no calculó ninguna. */
  week_start: string | null;
  locations: LocationPerformance[];
}

/** Lo que el dashboard necesita de GET /reporting/pipeline-runs/latest. */
export interface PipelineRunSummary {
  status: string;
  started_at: string;
  finished_at: string | null;
}
