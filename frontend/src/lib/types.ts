// Timestamps are strings without a timezone. Never convert them through `new Date(...)`.

export type Meta = {
  min_ts: string | null;
  max_ts: string | null;
  total_rows: number;
  services: string[];
  levels: string[];
  error_types: string[];
};

export type OverviewPoint = { ts: string; errors: number; warns: number; total: number };
export type Overview = { bucket_minutes: number; points: OverviewPoint[] };

export type LogRow = {
  id: number;
  ts: string;
  service: string;
  level: string;
  request_id: string;
  message: string;
  error_type: string | null;
  latency_ms: number | null;
};
export type LogsPage = { items: LogRow[]; limit: number; offset: number; has_more: boolean };

export type TraceEvent = {
  id: number;
  ts: string;
  offset_ms: number;
  service: string;
  level: string;
  message: string;
  error_type: string | null;
  latency_ms: number | null;
};
export type Trace = {
  request_id: string;
  start: string;
  end: string;
  duration_ms: number;
  services: string[];
  has_errors: boolean;
  events: TraceEvent[];
};

// ---- investigation result ----

export type Period = {
  start: string;
  end: string;
  bad_lines_in_window: number;
  peak_bad_per_minute: number;
  baseline_bad_per_minute: number;
  other_windows_found: number;
};

export type ServiceRow = {
  service: string;
  errors: number;
  warns: number;
  total_lines: number;
  first_error: string | null;
  avg_latency_ms: number | null;
};

export type ErrorGroup = {
  service: string;
  level: string;
  error_type: string | null;
  pattern: string;
  count: number;
  first_seen: string;
  last_seen: string;
};

export type TraceLine = {
  ts: string;
  service: string;
  level: string;
  error_type: string | null;
  message: string;
};

export type Traces = {
  requests_sampled: number;
  common_paths: { path: string; count: number }[];
  sample_traces: { request_id: string; events: TraceLine[] }[];
};

export type TimelineRow = {
  service: string;
  level: string;
  error_type: string | null;
  first_seen: string;
  last_seen: string;
  occurrences: number;
};

export type Hypothesis = {
  root_cause_service: string;
  root_cause_error_type: string;
  explanation?: string;
  propagation_path?: string[];
  confidence?: number;
  source?: "llm" | "rule_based_fallback" | string;
};

export type Verification = {
  verified: boolean;
  error_exists_in_window?: boolean;
  appeared_first?: boolean;
  coverage_of_failing_requests?: number;
  coverage_ok?: boolean;
  reason?: string;
};

export type Attempt = {
  attempt: number | "fallback";
  hypothesis?: Partial<Hypothesis>;
  verification?: Partial<Verification>;
  error?: string;
};

type ResultBase = {
  incident: string;
  requested_range: { start: string; end: string };
};

export type NoAnomalyResult = ResultBase & { status: "no_anomaly_found" };

export type OkResult = ResultBase & {
  status: "ok";
  period: Period;
  services: ServiceRow[];
  error_groups: ErrorGroup[];
  traces: Traces;
  timeline: TimelineRow[];
  hypothesis: Hypothesis;
  verification: Verification;
  attempts: Attempt[];
};

export type InvestigationResult = OkResult | NoAnomalyResult;

export type InvestigateRequest = { description: string; start: string; end: string };
