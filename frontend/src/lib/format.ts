// Timestamps from the API are naive (no timezone). Everything here treats them as plain wall-clock
// values: they are parsed with Date.UTC and printed back with toISOString, so the browser's own
// timezone never shifts them.

const TS_RE = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?/;

/** Milliseconds for a naive timestamp (wall-clock arithmetic only). NaN if it cannot be parsed. */
export function tsToMs(ts: string): number {
  const m = TS_RE.exec(ts);
  if (!m) return NaN;
  const ms = m[7] ? Number(m[7].padEnd(3, "0").slice(0, 3)) : 0;
  return Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]), Number(m[4]), Number(m[5]), Number(m[6] ?? 0), ms);
}

/** Inverse of tsToMs: "2026-10-01T14:05:00.000". */
export function msToTs(ms: number): string {
  return new Date(ms).toISOString().slice(0, 23);
}

export function addMinutes(ts: string, minutes: number): string {
  return msToTs(tsToMs(ts) + minutes * 60000);
}

/** "2026-10-01T14:05:00.060" -> "2026-10-01 14:05:00.060". */
export function fmtTs(ts: string | null | undefined): string {
  if (!ts) return "-";
  return ts.replace("T", " ");
}

/** "2026-10-01 14:05:00.060" -> "14:05:00.060". */
export function fmtClock(ts: string | null | undefined): string {
  if (!ts) return "-";
  const t = ts.replace("T", " ");
  const i = t.indexOf(" ");
  return i >= 0 ? t.slice(i + 1) : t;
}

/** Axis label: time only on a single day, "MM-DD HH:mm" when the data spans several days. */
export function fmtAxis(ts: string, multiDay: boolean): string {
  const t = ts.replace("T", " ");
  return multiDay ? t.slice(5, 16) : t.slice(11, 16);
}

/** Value for <input type="datetime-local">, minute precision. */
export function toInputValue(ts: string): string {
  return ts.replace(" ", "T").slice(0, 16);
}

/** Add seconds back so the API gets a full ISO timestamp. */
export function fromInputValue(value: string): string {
  const v = value.replace(" ", "T");
  return v.length === 16 ? `${v}:00` : v;
}

/** Datetime-local value for an API timestamp. With ceil=true, rounds up to the next whole minute. */
export function inputFromTs(ts: string, ceil = false): string {
  const base = toInputValue(ts);
  if (!ceil) return base;
  const ms = tsToMs(ts);
  const floored = tsToMs(`${base}:00`);
  return Number.isNaN(ms) || ms === floored ? base : toInputValue(msToTs(floored + 60000));
}

export function fmtDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)} ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(2)} s`;
  const minutes = Math.floor(ms / 60000);
  const seconds = Math.round((ms % 60000) / 1000);
  return `${minutes} min ${seconds} s`;
}

/** "+3.04 s" style offset used on timelines. */
export function fmtOffset(ms: number): string {
  return ms === 0 ? "first" : `+${fmtDuration(ms)}`;
}

export function pct(value: number | null | undefined): string {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "-";
}

export function fmtNumber(n: number | null | undefined): string {
  return typeof n === "number" ? n.toLocaleString("en-US") : "-";
}

// ---- colors and tones ----

const SERVICE_COLORS: Record<string, string> = {
  "api-gateway": "#2563eb",
  "auth-service": "#9333ea",
  "order-service": "#0d9488",
  "db-service": "#ea580c",
};
const FALLBACK_COLORS = ["#db2777", "#65a30d", "#0891b2", "#ca8a04", "#7c3aed", "#475569"];

export function serviceColor(service: string): string {
  const known = SERVICE_COLORS[service];
  if (known) return known;
  let hash = 0;
  for (const ch of service) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return FALLBACK_COLORS[hash % FALLBACK_COLORS.length];
}

export function levelTone(level: string): "red" | "amber" | "gray" {
  if (level === "ERROR") return "red";
  if (level === "WARN") return "amber";
  return "gray";
}

export function levelBarClass(level: string): string {
  if (level === "ERROR") return "bg-red-500";
  if (level === "WARN") return "bg-amber-500";
  return "bg-slate-400";
}
