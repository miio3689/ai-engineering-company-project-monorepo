export interface IncidentBreakdown {
  count: number;
  percentage: number;
}

export interface IncidentAnalysisResponse {
  total_records: number;
  valid_records: number;
  invalid_records: number;
  invalid_by_rule: Record<string, number>;
  category_counts: Record<string, IncidentBreakdown>;
  status_counts: Record<string, IncidentBreakdown>;
  satisfaction: {
    average: number | null;
    scored_cases: number;
    counts: Record<string, number>;
  };
}
