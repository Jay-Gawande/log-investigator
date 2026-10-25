import { buildQuery } from "./query-string";
import type {
  InvestigateRequest,
  InvestigationResult,
  LogsPage,
  Meta,
  Overview,
  Trace,
} from "./types";

export type FieldErrors = Record<string, string>;

export class ApiError extends Error {
  status: number;
  fieldErrors: FieldErrors;

  constructor(status: number, message: string, fieldErrors: FieldErrors = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

const SKIP_LOC = new Set(["body", "query", "path"]);

/** Turn FastAPI's `detail` (a string, or a list of {loc, msg}) into a message plus per-field errors. */
export function parseDetail(detail: unknown): { message: string; fields: FieldErrors } {
  if (typeof detail === "string") return { message: detail, fields: {} };
  if (Array.isArray(detail)) {
    const fields: FieldErrors = {};
    const messages: string[] = [];
    for (const item of detail) {
      const loc: unknown[] = Array.isArray(item?.loc) ? item.loc : [];
      const raw: string = typeof item?.msg === "string" ? item.msg : "Invalid value";
      const msg = raw.replace(/^Value error, /, "");
      const name = loc.filter((p) => typeof p === "string" && !SKIP_LOC.has(p)).join(".");
      if (name) {
        if (!fields[name]) fields[name] = msg;
        messages.push(`${name}: ${msg}`);
      } else {
        messages.push(msg);
      }
    }
    return { message: messages.join("; ") || "Invalid request", fields };
  }
  return { message: "Request failed", fields: {} };
}

async function send(path: string, init?: RequestInit): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, init);
  } catch {
    throw new ApiError(0, "Cannot reach the backend. Is the API running?");
  }
  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = (await res.json()).detail;
    } catch {
      // body was not JSON
    }
    if (detail == null) {
      const message = res.status >= 500 ? `Server error (${res.status})` : `Request failed (${res.status})`;
      throw new ApiError(res.status, message);
    }
    const { message, fields } = parseDetail(detail);
    throw new ApiError(res.status, message, fields);
  }
  return res;
}

async function getJson<T>(path: string): Promise<T> {
  return (await send(path)).json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await send(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json() as Promise<T>;
}

/** The API accepts ISO timestamps; allow a space separator from stored values. */
const iso = (ts: string) => ts.replace(" ", "T");

export type OverviewParams = { start: string; end: string; bucket_minutes?: number; service?: string };
export type LogsParams = {
  start: string;
  end: string;
  service?: string;
  level?: string;
  error_type?: string;
  request_id?: string;
  q?: string;
  order?: "asc" | "desc";
  limit?: number;
  offset?: number;
};

export const getHealth = () => getJson<{ status: string }>("/health");
export const getMeta = () => getJson<Meta>("/meta");

export const getOverview = (p: OverviewParams) =>
  getJson<Overview>(
    `/logs/overview${buildQuery({ ...p, start: iso(p.start), end: iso(p.end) })}`,
  );

export const getLogs = (p: LogsParams) =>
  getJson<LogsPage>(`/logs${buildQuery({ ...p, start: iso(p.start), end: iso(p.end) })}`);

export const getTrace = (id: string) => getJson<Trace>(`/requests/${encodeURIComponent(id)}`);

export const investigate = (body: InvestigateRequest) =>
  postJson<InvestigationResult>("/investigate", body);

export async function renderReport(result: InvestigationResult): Promise<string> {
  const res = await send("/report/render", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(result),
  });
  return res.text();
}
