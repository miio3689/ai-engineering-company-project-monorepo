export interface ReportPeriod {
  from: string;
  to: string;
}

export interface EventsPerDayRow {
  date: string;
  event_type: string;
  events: number;
}

export interface ErrorRateByDayRow {
  date: string;
  events: number;
  errors: number;
  warnings: number;
  error_rate: number;
  problem_rate: number;
}

export interface ErrorRateByTypeRow {
  event_type: string;
  events: number;
  errors: number;
  warnings: number;
  error_rate: number;
  problem_rate: number;
}

export interface PageLoadRow {
  date: string;
  route: string;
  samples: number;
  avg_ms: number;
  p95_ms: number;
}

export interface AuthFailureRow {
  date: string;
  attempts: number;
  failures: number;
  failure_rate: number;
}

export interface TelemetryReport {
  period: ReportPeriod;
  metrics: {
    events_per_day: EventsPerDayRow[];
    error_rate_by_day: ErrorRateByDayRow[];
    error_rate_by_type: ErrorRateByTypeRow[];
    page_load_ms_by_route: PageLoadRow[];
    auth_failure_rate: AuthFailureRow[];
  };
}
