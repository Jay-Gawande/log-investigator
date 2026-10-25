import { describe, expect, it } from "vitest";
import { buildQuery } from "@/lib/query-string";
import { highlightBand, prepareTimeline, snapToBucket } from "@/lib/timeline";
import type { OverviewPoint, TimelineRow } from "@/lib/types";

const row = (service: string, first: string, last: string, occ = 100, level = "ERROR"): TimelineRow => ({
  service,
  level,
  error_type: `${service.toUpperCase()}_ERR`,
  first_seen: first,
  last_seen: last,
  occurrences: occ,
});

// a database outage: db-service fails first, the rest follow within a few seconds
const OUTAGE: TimelineRow[] = [
  row("api-gateway", "2026-10-01T14:05:03.150", "2026-10-01T14:17:00.000"),
  row("db-service", "2026-10-01T14:05:00.000", "2026-10-01T14:17:00.000"),
  row("order-service", "2026-10-01T14:05:03.100", "2026-10-01T14:17:00.000"),
];

describe("prepareTimeline", () => {
  it("handles an empty list", () => {
    expect(prepareTimeline([]).rows).toEqual([]);
  });

  it("orders rows by first appearance and marks the first", () => {
    const t = prepareTimeline(OUTAGE);
    expect(t.rows.map((r) => r.service)).toEqual(["db-service", "order-service", "api-gateway"]);
    expect(t.rows[0].isFirst).toBe(true);
    expect(t.rows.slice(1).every((r) => !r.isFirst)).toBe(true);
  });

  it("computes onset offsets in milliseconds", () => {
    const t = prepareTimeline(OUTAGE);
    expect(t.rows.map((r) => r.offsetMs)).toEqual([0, 3100, 3150]);
    expect(t.maxOffsetMs).toBe(3150);
  });

  it("scales the onset bar to the largest offset, with a visible minimum", () => {
    const t = prepareTimeline(OUTAGE);
    expect(t.rows[0].onsetPct).toBe(2);
    expect(t.rows[2].onsetPct).toBe(100);
    expect(t.rows[1].onsetPct).toBeGreaterThan(95);
  });

  it("keeps active-span bars inside 0 to 100 percent", () => {
    const t = prepareTimeline(OUTAGE);
    for (const r of t.rows) {
      expect(r.left).toBeGreaterThanOrEqual(0);
      expect(r.left + r.width).toBeLessThanOrEqual(100.0001);
    }
    expect(t.rows[0].left).toBe(0);
    expect(t.rows[0].width).toBe(100);
  });

  it("gives a single-instant error a minimum visible width", () => {
    const t = prepareTimeline([
      row("db-service", "2026-10-01T14:05:00.000", "2026-10-01T14:10:00.000"),
      row("auth-service", "2026-10-01T14:07:00.000", "2026-10-01T14:07:00.000", 1, "WARN"),
    ]);
    const warn = t.rows.find((r) => r.service === "auth-service");
    expect(warn?.width).toBeGreaterThanOrEqual(0.8);
  });

  it("does not divide by zero when everything happens at one instant", () => {
    const t = prepareTimeline([row("a", "2026-10-01T14:05:00.000", "2026-10-01T14:05:00.000")]);
    expect(Number.isFinite(t.rows[0].left)).toBe(true);
    expect(Number.isFinite(t.rows[0].width)).toBe(true);
    expect(Number.isFinite(t.rows[0].onsetPct)).toBe(true);
  });

  it("does not mutate its input", () => {
    const copy = OUTAGE.map((r) => r.service);
    prepareTimeline(OUTAGE);
    expect(OUTAGE.map((r) => r.service)).toEqual(copy);
  });
});

const points = (minutes: number[]): OverviewPoint[] =>
  minutes.map((m) => ({
    ts: `2026-10-01T14:${String(m).padStart(2, "0")}:00.000`,
    errors: 0,
    warns: 0,
    total: 0,
  }));

describe("snapToBucket and highlightBand", () => {
  const p = points([0, 5, 10, 15, 20]);

  it("finds the bucket that contains a timestamp", () => {
    expect(snapToBucket(p, "2026-10-01 14:07:30")).toBe("2026-10-01T14:05:00.000");
    expect(snapToBucket(p, "2026-10-01T14:10:00")).toBe("2026-10-01T14:10:00.000");
  });

  it("clamps to the first bucket for earlier times, and handles no points", () => {
    expect(snapToBucket(p, "2026-10-01T13:00:00")).toBe("2026-10-01T14:00:00.000");
    expect(snapToBucket([], "2026-10-01T14:00:00")).toBeNull();
  });

  it("builds a band from the detected period (end is exclusive)", () => {
    const band = highlightBand(p, "2026-10-01 14:05:00", "2026-10-01 14:15:00");
    expect(band).toEqual({ x1: "2026-10-01T14:05:00.000", x2: "2026-10-01T14:10:00.000" });
  });

  it("never returns an inverted band", () => {
    const band = highlightBand(p, "2026-10-01 14:12:00", "2026-10-01 14:13:00");
    expect(band?.x1).toBe(band?.x2);
  });
});

describe("buildQuery", () => {
  it("skips empty values", () => {
    expect(buildQuery({ a: "1", b: "", c: undefined, d: null, e: false })).toBe("?a=1");
  });

  it("returns an empty string when there is nothing to add", () => {
    expect(buildQuery({})).toBe("");
    expect(buildQuery({ a: "" })).toBe("");
  });

  it("keeps zero and encodes special characters", () => {
    const q = buildQuery({ offset: 0, q: "a b&c", start: "2026-10-01T14:05" });
    expect(q).toContain("offset=0");
    expect(q).toContain("q=a+b%26c");
    expect(q).toContain("start=2026-10-01T14%3A05");
  });
});
